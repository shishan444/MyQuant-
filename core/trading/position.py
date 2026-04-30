"""Position Manager: pure-Python state machine mirroring backtest engine logic.

Processing order per bar (mirrors engine.py order_func_nb):
1. Liquidation check (leverage > 1)
2. SL/TP check using HIGH/LOW prices
3. Exit signal
4. Entry signal (only when flat)
5. Reduce signal (before add, matching engine order)
6. Add signal (weighted average entry price)
7. Funding cost deduction
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


_RATE_PER_8H = 0.001

_HOURS_PER_BAR = {
    "1m": 1 / 60, "5m": 5 / 60, "15m": 0.25, "30m": 0.5,
    "1h": 1, "4h": 4, "1d": 24, "3d": 72,
}


@dataclass
class Position:
    """Open position state."""
    side: str           # "long" | "short"
    entry_price: float
    quantity: float
    margin: float
    cumulative_funding: float = 0.0


@dataclass
class ClosedTrade:
    """Record of a closed trade."""
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    exit_reason: str    # "signal" | "sl" | "tp" | "liquidation"


@dataclass
class EquitySnapshot:
    """Per-bar equity snapshot."""
    timestamp: str
    position_side: str  # "long" | "short" | "flat"
    equity: float
    unrealized_pnl: float
    balance: float


class PositionManager:
    """Position state machine for paper trading.

    Mirrors backtest engine (engine.py order_func_nb) logic in pure Python,
    enabling real-time bar-by-bar position management.

    Key differences from backtest:
    - Executes immediately on current bar (no 1-bar shift)
    - Applies funding cost per-bar (backtest applies post-hoc)
    - Uses explicit balance/margin tracking
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

        # State
        self.balance: float = init_cash
        self.position: Optional[Position] = None
        self.closed_trades: List[ClosedTrade] = []
        self.equity_snapshots: List[EquitySnapshot] = []

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
        pos = self.position
        return self.balance + pos.margin + self._unrealized_pnl(price)

    def _close_position(self, price: float, reason: str) -> dict:
        pos = self.position
        pnl = self._unrealized_pnl(price)
        close_fee = self._fee * pos.quantity * price

        self.balance += pos.margin + pnl - close_fee

        trade = ClosedTrade(
            side=pos.side,
            entry_price=pos.entry_price,
            exit_price=price,
            quantity=pos.quantity,
            pnl=pnl - close_fee,
            exit_reason=reason,
        )
        self.closed_trades.append(trade)
        self.position = None

        return {
            "type": "position_closed",
            "side": trade.side,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "pnl": trade.pnl,
            "exit_reason": reason,
        }

    def _apply_funding(self, price: float) -> None:
        if self._leverage <= 1 or self.position is None:
            return
        hours = _HOURS_PER_BAR.get(self._timeframe, 4)
        periods = hours / 8.0
        borrowed_ratio = (self._leverage - 1) / self._leverage
        cost_rate = _RATE_PER_8H * periods * borrowed_ratio
        cost = self.position.quantity * price * cost_rate
        self.balance -= cost
        self.position.cumulative_funding += cost

    def _snapshot(self, bar_time: str, price: float) -> None:
        if self.position is not None:
            side = self.position.side
            upnl = self._unrealized_pnl(price)
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

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def process_bar(
        self,
        bar_time: str,
        bar_high: float,
        bar_low: float,
        bar_close: float,
        entry_signal: bool = False,
        exit_signal: bool = False,
        add_signal: bool = False,
        reduce_signal: bool = False,
        direction: float = 1.0,
    ) -> List[dict]:
        """Process one bar. Returns list of event dicts."""
        events: list[dict] = []
        price = bar_close

        # 1. Liquidation (leverage > 1, position open)
        if self._leverage > 1 and self.position is not None:
            maintenance = self._init_cash * (1.0 - 0.9 / (self._leverage ** 2))
            if self._equity(price) < maintenance:
                events.append(self._close_position(price, "liquidation"))
                self._apply_funding(price)
                self._snapshot(bar_time, price)
                return events

        # 2. SL / TP using HIGH/LOW
        if self.position is not None:
            pos = self.position
            ep = pos.entry_price
            triggered = False

            if pos.side == "long":
                if self._stop_loss > 0 and bar_low <= ep * (1.0 - self._stop_loss):
                    events.append(self._close_position(price, "sl"))
                    triggered = True
                elif (self._take_profit is not None
                      and self._take_profit > 0
                      and bar_high >= ep * (1.0 + self._take_profit)):
                    events.append(self._close_position(price, "tp"))
                    triggered = True
            else:  # short
                if self._stop_loss > 0 and bar_high >= ep * (1.0 + self._stop_loss):
                    events.append(self._close_position(price, "sl"))
                    triggered = True
                elif (self._take_profit is not None
                      and self._take_profit > 0
                      and bar_low <= ep * (1.0 - self._take_profit)):
                    events.append(self._close_position(price, "tp"))
                    triggered = True

            if triggered:
                self._apply_funding(price)
                self._snapshot(bar_time, price)
                return events

        # 3. Exit signal
        if exit_signal and self.position is not None:
            events.append(self._close_position(price, "signal"))
            self._apply_funding(price)
            self._snapshot(bar_time, price)
            return events

        # 4. Entry signal (only when flat)
        if entry_signal and self.position is None:
            if self._direction == "long":
                side = "long"
            elif self._direction == "short":
                side = "short"
            else:  # mixed
                side = "long" if direction > 0 else "short"

            margin = self.balance * self._position_size
            if margin > 0:
                quantity = margin * self._leverage / price
                open_fee = self._fee * quantity * price
                self.balance -= margin + open_fee
                self.position = Position(
                    side=side,
                    entry_price=price,
                    quantity=quantity,
                    margin=margin,
                )
                events.append({
                    "type": "position_opened",
                    "side": side,
                    "entry_price": price,
                    "quantity": quantity,
                })

        # 5. Reduce signal (before add, matching engine order)
        if reduce_signal and self.position is not None:
            pos = self.position
            reduce_qty = pos.quantity * self._position_size
            if reduce_qty > 0:
                if pos.side == "long":
                    reduce_pnl = reduce_qty * (price - pos.entry_price)
                else:
                    reduce_pnl = reduce_qty * (pos.entry_price - price)
                reduce_fee = self._fee * reduce_qty * price
                reduce_margin = pos.margin * (reduce_qty / pos.quantity)

                pos.quantity -= reduce_qty
                pos.margin -= reduce_margin
                self.balance += reduce_margin + reduce_pnl - reduce_fee

                events.append({
                    "type": "position_reduced",
                    "quantity_reduced": reduce_qty,
                    "pnl": reduce_pnl - reduce_fee,
                })

                if pos.quantity < 1e-8:
                    self.position = None

        # 6. Add signal
        if add_signal and self.position is not None:
            pos = self.position
            add_value = self.balance * self._position_size
            if add_value > 0:
                add_qty = add_value * self._leverage / price
                add_fee = self._fee * add_qty * price

                new_qty = pos.quantity + add_qty
                if new_qty > 0:
                    new_ep = (pos.entry_price * pos.quantity
                              + price * add_qty) / new_qty
                else:
                    new_ep = pos.entry_price

                self.balance -= add_value + add_fee
                pos.entry_price = new_ep
                pos.quantity = new_qty
                pos.margin += add_value

                events.append({
                    "type": "position_added",
                    "quantity_added": add_qty,
                    "new_entry_price": new_ep,
                })

        # 7. Funding cost
        self._apply_funding(price)

        # 8. Snapshot
        self._snapshot(bar_time, price)

        return events
