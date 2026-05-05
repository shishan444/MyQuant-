"""VirtualAccount: bar-open execution for paper trading.

Replaces PositionManager with Decision-based execution at bar_open price.
Mirrors PositionManager's risk logic (SL/TP, liquidation, funding, slippage)
but separates signal interpretation from execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from core.trading.position import Position, ClosedTrade, EquitySnapshot
from core.trading.types import AccountState, Decision

_RATE_PER_8H = 0.001

_HOURS_PER_BAR = {
    "1m": 1 / 60, "5m": 5 / 60, "15m": 0.25, "30m": 0.5,
    "1h": 1, "4h": 4, "1d": 24, "3d": 72,
}


class VirtualAccount:
    """Virtual trading account with bar-open execution.

    Processing order per bar (via process_bar_v2):
    1. SL/TP check using HIGH/LOW, execute at OPEN
    2. Liquidation check (leverage > 1)
    3. Execute pending Decision at OPEN
    4. Funding cost deduction
    5. Equity snapshot
    """

    def __init__(
        self,
        dna,
        init_cash: float = 100_000.0,
        fee: float = 0.001,
        slippage: float = 0.0,
    ):
        self._init_cash = init_cash
        self._fee = fee
        self._slippage = slippage

        # Risk parameters from DNA
        self._leverage: int = dna.risk_genes.leverage
        self._direction: str = dna.risk_genes.direction
        self._position_size: float = dna.risk_genes.position_size
        self._stop_loss: float = dna.risk_genes.stop_loss or 0.0
        self._take_profit: Optional[float] = dna.risk_genes.take_profit
        self._timeframe: str = dna.execution_genes.timeframe

        # Cumulative stats from prior sessions (for resume)
        self._prior_trades: int = 0
        self._prior_pnl: float = 0.0
        self._prior_wins: int = 0
        self._prior_losses: int = 0

        # State
        self.balance: float = init_cash
        self.position: Optional[Position] = None
        self.closed_trades: List[ClosedTrade] = []
        self.equity_snapshots: List[EquitySnapshot] = []
        self._position_open_bar_time: Optional[str] = None

    # ------------------------------------------------------------------
    # Cumulative stats
    # ------------------------------------------------------------------

    @property
    def total_trades(self) -> int:
        return self._prior_trades + len(self.closed_trades)

    @property
    def total_pnl(self) -> float:
        return self._prior_pnl + sum(t.pnl for t in self.closed_trades)

    @property
    def win_count(self) -> int:
        return self._prior_wins + sum(1 for t in self.closed_trades if t.pnl > 0)

    @property
    def loss_count(self) -> int:
        return self._prior_losses + sum(1 for t in self.closed_trades if t.pnl <= 0)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _unrealized_pnl(self, price: float) -> float:
        if self.position is None:
            return 0.0
        pos = self.position
        if pos.side == "long":
            return pos.quantity * (price - pos.entry_price)
        return pos.quantity * (pos.entry_price - price)

    def _equity(self, price: float) -> float:
        if self.position is None:
            return self.balance
        return self.balance + self.position.margin + self._unrealized_pnl(price)

    def _actual_position_pct(self, price: float) -> float:
        if self.position is None:
            return 0.0
        eq = self._equity(price)
        if eq <= 0:
            return 0.0
        return self.position.margin / eq

    def _bars_held(self) -> int:
        if self._position_open_bar_time is None:
            return 0
        return len([s for s in self.equity_snapshots
                    if s.position_side != "flat"])

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def _close_position(self, price: float, reason: str) -> dict:
        pos = self.position
        pnl = self._unrealized_pnl(price)
        close_fee = self._fee * pos.quantity * price
        slippage_cost = self._slippage * pos.quantity * price

        self.balance += pos.margin + pnl - close_fee - slippage_cost

        trade = ClosedTrade(
            side=pos.side,
            entry_price=pos.entry_price,
            exit_price=price,
            quantity=pos.quantity,
            pnl=pnl - close_fee - slippage_cost,
            exit_reason=reason,
        )
        self.closed_trades.append(trade)
        self.position = None
        self._position_open_bar_time = None

        return {
            "type": "position_closed",
            "side": trade.side,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "quantity": trade.quantity,
            "pnl": trade.pnl,
            "exit_reason": reason,
        }

    def _open_position(self, side: str, price: float) -> dict:
        margin = self.balance * self._position_size
        if margin <= 0:
            return {"type": "open_skipped", "reason": "insufficient_balance"}
        quantity = margin * self._leverage / price
        open_fee = self._fee * quantity * price
        open_slippage = self._slippage * quantity * price
        self.balance -= margin + open_fee + open_slippage
        self.position = Position(
            side=side,
            entry_price=price,
            quantity=quantity,
            margin=margin,
        )
        return {
            "type": "position_opened",
            "side": side,
            "entry_price": price,
            "quantity": quantity,
        }

    def _add_position(self, price: float) -> dict:
        pos = self.position
        add_value = self.balance * self._position_size
        if add_value <= 0:
            return {"type": "add_skipped", "reason": "insufficient_balance"}
        add_qty = add_value * self._leverage / price
        add_fee = self._fee * add_qty * price
        add_slippage = self._slippage * add_qty * price
        new_qty = pos.quantity + add_qty
        new_ep = (pos.entry_price * pos.quantity + price * add_qty) / new_qty
        self.balance -= add_value + add_fee + add_slippage
        pos.entry_price = new_ep
        pos.quantity = new_qty
        pos.margin += add_value
        return {
            "type": "position_added",
            "side": pos.side,
            "price": price,
            "quantity_added": add_qty,
            "new_entry_price": new_ep,
        }

    def _reduce_position(self, price: float) -> dict:
        pos = self.position
        reduce_qty = pos.quantity * self._position_size
        if reduce_qty <= 0:
            return {"type": "reduce_skipped", "reason": "zero_quantity"}
        if pos.side == "long":
            reduce_pnl = reduce_qty * (price - pos.entry_price)
        else:
            reduce_pnl = reduce_qty * (pos.entry_price - price)
        reduce_fee = self._fee * reduce_qty * price
        reduce_slippage = self._slippage * reduce_qty * price
        reduce_margin = pos.margin * (reduce_qty / pos.quantity)
        pos.quantity -= reduce_qty
        pos.margin -= reduce_margin
        self.balance += reduce_margin + reduce_pnl - reduce_fee - reduce_slippage
        event = {
            "type": "position_reduced",
            "side": pos.side,
            "price": price,
            "quantity_reduced": reduce_qty,
            "pnl": reduce_pnl - reduce_fee - reduce_slippage,
        }
        if pos.quantity < 1e-8:
            self.position = None
            self._position_open_bar_time = None
        return event

    # ------------------------------------------------------------------
    # Risk checks
    # ------------------------------------------------------------------

    def check_sl_tp(self, bar_high: float, bar_low: float, bar_open: float) -> list:
        """Check SL/TP using bar HIGH/LOW, execute at bar_open."""
        if self.position is None:
            return []
        events = []
        pos = self.position
        ep = pos.entry_price

        if pos.side == "long":
            if self._stop_loss > 0 and bar_low <= ep * (1.0 - self._stop_loss):
                events.append(self._close_position(bar_open, "sl"))
            elif (self._take_profit is not None
                  and self._take_profit > 0
                  and bar_high >= ep * (1.0 + self._take_profit)):
                events.append(self._close_position(bar_open, "tp"))
        else:  # short
            if self._stop_loss > 0 and bar_high >= ep * (1.0 + self._stop_loss):
                events.append(self._close_position(bar_open, "sl"))
            elif (self._take_profit is not None
                  and self._take_profit > 0
                  and bar_low <= ep * (1.0 - self._take_profit)):
                events.append(self._close_position(bar_open, "tp"))

        return events

    def check_liquidation(self, current_price: float) -> bool:
        """Check liquidation for leveraged positions."""
        if self._leverage <= 1 or self.position is None:
            return False
        maintenance = self._init_cash * (1.0 - 0.9 / (self._leverage ** 2))
        return self._equity(current_price) < maintenance

    def apply_funding(self, current_price: float) -> None:
        """Apply funding cost for leveraged positions."""
        if self._leverage <= 1 or self.position is None:
            return
        hours = _HOURS_PER_BAR.get(self._timeframe, 4)
        periods = hours / 8.0
        borrowed_ratio = (self._leverage - 1) / self._leverage
        cost_rate = _RATE_PER_8H * periods * borrowed_ratio
        cost = self.position.quantity * current_price * cost_rate
        self.balance -= cost
        self.position.cumulative_funding += cost

    # ------------------------------------------------------------------
    # Decision execution
    # ------------------------------------------------------------------

    def execute_decision(self, decision: Decision, open_price: float) -> list:
        """Execute a Decision at the given open price."""
        events = []

        if decision.action == "open" and self.position is None:
            side = decision.direction
            event = self._open_position(side, open_price)
            events.append(event)
            if event["type"] == "position_opened":
                self._position_open_bar_time = None  # set on first snapshot

        elif decision.action == "close" and self.position is not None:
            events.append(self._close_position(open_price, decision.reason or "signal"))

        elif decision.action == "add" and self.position is not None:
            event = self._add_position(open_price)
            events.append(event)

        elif decision.action == "reduce" and self.position is not None:
            event = self._reduce_position(open_price)
            events.append(event)

        return events

    # ------------------------------------------------------------------
    # Snapshot & state
    # ------------------------------------------------------------------

    def take_snapshot(self, bar_time: str, current_price: float) -> None:
        """Record equity snapshot."""
        if self.position is not None:
            if self._position_open_bar_time is None:
                self._position_open_bar_time = bar_time
            side = self.position.side
            upnl = self._unrealized_pnl(current_price)
            eq = self.balance + self.position.margin + upnl
        else:
            side = "flat"
            upnl = 0.0
            eq = self.balance
        self.equity_snapshots.append(EquitySnapshot(
            timestamp=bar_time,
            position_side=side,
            equity=eq,
            unrealized_pnl=upnl,
            balance=self.balance,
        ))

    def get_state(self, current_price: float) -> AccountState:
        """Return AccountState snapshot for judgment rule evaluation."""
        has_pos = self.position is not None
        return AccountState(
            balance=self.balance,
            has_position=has_pos,
            position_side=self.position.side if has_pos else "flat",
            position_entry=self.position.entry_price if has_pos else 0.0,
            position_quantity=self.position.quantity if has_pos else 0.0,
            position_margin=self.position.margin if has_pos else 0.0,
            unrealized_pnl=self._unrealized_pnl(current_price),
            position_bars_held=self._bars_held(),
            target_position_pct=0.0,  # set by runner
            actual_position_pct=self._actual_position_pct(current_price),
            equity=self._equity(current_price),
        )

    # ------------------------------------------------------------------
    # Facade
    # ------------------------------------------------------------------

    def process_bar_v2(
        self,
        bar_high: float,
        bar_low: float,
        bar_open: float,
        bar_close: float,
        bar_time: str,
        pending_decision: Optional[Decision] = None,
    ) -> list:
        """Process one bar atomically.

        Order: check_sl_tp -> check_liquidation -> execute_decision
               -> apply_funding -> take_snapshot.
        """
        events = []
        position_closed = False

        # Step 1: SL/TP check
        sl_tp_events = self.check_sl_tp(bar_high, bar_low, bar_open)
        events.extend(sl_tp_events)
        if sl_tp_events:
            position_closed = True

        # Step 2: Liquidation check
        if not position_closed and self.check_liquidation(bar_open):
            events.append(self._close_position(bar_open, "liquidation"))
            position_closed = True

        # Step 3: Execute pending decision (skip if SL/TP/liquidation closed)
        if not position_closed and pending_decision is not None:
            events.extend(self.execute_decision(pending_decision, bar_open))

        # Step 4: Funding cost
        self.apply_funding(bar_close)

        # Step 5: Snapshot
        self.take_snapshot(bar_time, bar_close)

        return events
