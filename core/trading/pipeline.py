"""Mode-agnostic decision pipeline for paper trading.

Extracted from runner.py's inner bar loop. Handles:
  observe -> predict -> manage orders -> SL/TP -> execute -> evaluate signals
without depending on data source (live/replay).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from core.trading.judgment import evaluate
from core.trading.order_generator import generate_order
from core.trading.order_manager import OrderManager
from core.trading.types import (
    BarSignals,
    Decision,
    JudgmentConfig,
    OrderEvent,
    PipelineResult,
    PositionPlan,
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineState:
    """Mutable state carried across bars within the pipeline."""

    pending_decision: Optional[Decision] = None
    current_plan: Optional[PositionPlan] = None
    prev_prediction: object = None


class DecisionPipeline:
    """Process one bar at a time, producing trading decisions.

    This class is the core decision logic shared by both replay and live modes.
    It does NOT handle data fetching, persistence, or stop/continue control.
    """

    def __init__(
        self,
        config: JudgmentConfig,
        dna_risk_genes=None,
    ) -> None:
        self.config = config
        self.dna_risk_genes = dna_risk_genes
        self.order_manager = OrderManager(config)
        self.state = PipelineState()

    def _extract_atr(self, df, bar_idx: int) -> Optional[float]:
        """Extract ATR value from DataFrame at given bar index.

        Returns None when:
        - sl_mode != "atr"
        - df is None
        - ATR column not found
        - ATR value is NaN or <= 0
        """
        if self.dna_risk_genes is None or self.dna_risk_genes.sl_mode != "atr":
            return None
        if df is None:
            return None
        atr_col = f"atr_{self.dna_risk_genes.atr_period}"
        if atr_col not in df.columns:
            return None
        val = float(df[atr_col].iloc[bar_idx])
        if val != val or val <= 0:  # NaN guard
            return None
        return val

    def _compute_sl_tp(self, entry_price: float, side: str,
                        atr_value: float) -> tuple:
        """Compute absolute SL/TP prices from ATR.

        Returns (sl_price, tp_price). tp_price is None when take_profit is None.
        """
        rg = self.dna_risk_genes
        sl_mult = rg.stop_loss
        tp_mult = rg.take_profit

        if side == "long":
            sl = entry_price - sl_mult * atr_value
            tp = (entry_price + tp_mult * atr_value) if tp_mult else None
        else:
            sl = entry_price + sl_mult * atr_value
            tp = (entry_price - tp_mult * atr_value) if tp_mult else None

        return sl, tp

    def process_bar(
        self,
        bar_high: float,
        bar_low: float,
        bar_open: float,
        bar_close: float,
        bar_time: str,
        bar_idx: int,
        account,
        predictor=None,
        df=None,
        sig_set=None,
        position_size: float = 0.30,
        stop_loss_pct: float = 0.05,
    ) -> PipelineResult:
        """Process one bar through the full decision pipeline.

        Steps:
          1. observe (update GARCH with previous prediction)
          2. predict (forecast next bar range)
          3. manage existing orders (fill / validity / timeout)
          4. SL/TP check (with corrected execution price)
          5. Execute pending decision (exit/reduce)
          6. PositionPlan lifecycle
          7. Evaluate signals -> generate new order or decision

        Args:
            bar_high/low/open/close: OHLC for this bar.
            bar_time: ISO timestamp string.
            bar_idx: Index into the DataFrame for signal extraction.
            account: VirtualAccount instance.
            predictor: PriceRangePredictor (optional).
            df: DataFrame for predictor.predict().
            sig_set: SignalSet for signal extraction.
            position_size: DNA risk gene for position sizing.
            stop_loss_pct: DNA risk gene for stop loss.

        Returns:
            PipelineResult with events, order_events, prediction, pending_decision.
        """
        events: list[dict] = []
        order_events: list[OrderEvent] = []

        # Extract ATR for dynamic SL/TP (returns None in pct mode)
        atr_value = self._extract_atr(df, bar_idx)

        # Step 1: Observe previous bar's actual result
        if predictor is not None and self.state.prev_prediction is not None:
            predictor.observe(bar_high, bar_low, self.state.prev_prediction)

        # Step 2: Predict next bar's range
        prediction = None
        if predictor is not None and df is not None:
            prediction = predictor.predict(df, bar_idx)
        self.state.prev_prediction = prediction

        # Step 3: Manage existing limit orders
        current_signals = None
        if sig_set is not None:
            current_signals = BarSignals.from_signal_set(sig_set, bar_idx)

        mgr_result = self.order_manager.manage(
            bar_high, bar_low, prediction, current_signals,
        )
        for oe in mgr_result.filled:
            order_events.append(oe)
            order_obj = self.order_manager.get_processed_order(oe.order_id)
            sl_price, tp_price = None, None
            if order_obj.source == "entry" and atr_value is not None:
                sl_price, tp_price = self._compute_sl_tp(
                    order_obj.price, order_obj.side, atr_value)
            fill_events = account.fill_order(order_obj,
                                             sl_price=sl_price, tp_price=tp_price)
            events.extend(fill_events)
        for oe in mgr_result.cancelled:
            order_events.append(oe)
        for oe in mgr_result.expired:
            order_events.append(oe)

        # Step 4: SL/TP check (uses corrected trigger price)
        sl_tp_events = account.check_sl_tp(bar_high, bar_low)
        events.extend(sl_tp_events)

        # Step 5: Liquidation check
        if not sl_tp_events and account.check_liquidation(bar_open):
            events.append(account._close_position(bar_open, "liquidation"))

        # Step 5b: Execute pending exit/reduce decision from previous bar
        position_closed = bool(sl_tp_events) or any(
            e.get("type") == "position_closed" for e in events
        )
        deferred: Optional[Decision] = None
        if position_closed and self.state.pending_decision is not None:
            if self.state.pending_decision.action == "open":
                deferred = self.state.pending_decision
        elif self.state.pending_decision is not None:
            dec = self.state.pending_decision
            sl_price, tp_price = None, None
            if dec.action == "open" and atr_value is not None:
                sl_price, tp_price = self._compute_sl_tp(
                    bar_open, dec.direction, atr_value)
            events.extend(account.execute_decision(
                dec, bar_open, sl_price=sl_price, tp_price=tp_price))
        self.state.pending_decision = None

        # Step 6: PositionPlan lifecycle
        for ev in events:
            if ev.get("type") == "position_opened" and prediction is not None:
                self.state.current_plan = PositionPlan.from_prediction(
                    prediction=prediction,
                    target_pct=position_size,
                    side=ev["side"],
                    entry_price=ev["entry_price"],
                    stop_loss=stop_loss_pct,
                )
            elif ev.get("type") == "position_closed":
                self.state.current_plan = None

        # Step 6b: Process PositionPlan tranches (legacy, for adds)
        if account.position is not None and self.state.current_plan is not None:
            tranche_events = account._process_tranches(
                self.state.current_plan, bar_high, bar_low, bar_open, prediction,
            )
            events.extend(tranche_events)

        # If SL/TP deferred an open decision, preserve it for next bar
        if deferred is not None:
            self.state.pending_decision = deferred
            return PipelineResult(
                events=events,
                order_events=order_events,
                prediction=prediction,
                pending_decision=deferred,
            )

        # Step 7: Evaluate signals -> generate order or decision
        if current_signals is not None:
            account_state = account.get_state(bar_close)

            if self.config.use_limit_orders:
                # Predictive order management path
                self._evaluate_with_orders(
                    current_signals, prediction, account_state,
                    account, bar_idx, bar_open,
                )
            else:
                # Legacy path: signal -> immediate decision
                decision = evaluate(current_signals, account_state, self.config)
                if decision.action != "hold":
                    self.state.pending_decision = decision

        # Step 8: Funding + Snapshot
        account.apply_funding(bar_close)
        account.take_snapshot(bar_time, bar_close)

        return PipelineResult(
            events=events,
            order_events=order_events,
            prediction=prediction,
            pending_decision=self.state.pending_decision,
        )

    def _evaluate_with_orders(
        self,
        signals: BarSignals,
        prediction,
        account_state,
        account,
        bar_idx: int,
        bar_open: float,
    ) -> None:
        """Evaluate signals using predictive order management.

        Entry signals -> generate limit Order (via OrderGenerator).
        Exit/reduce signals -> immediate execution (market).
        """
        # Exit/reduce: immediate execution, no limit order
        if (signals.exit or signals.reduce) and account_state.has_position:
            decision = evaluate(signals, account_state, self.config)
            if decision.action != "hold":
                self.state.pending_decision = decision
            return

        # Entry with no position: generate limit order
        if signals.entry and not account_state.has_position:
            if not self.order_manager.has_pending_entry:
                order = generate_order(
                    signals, prediction, account_state, self.config,
                    bar_idx=bar_idx, source="entry",
                )
                if order is not None:
                    self.order_manager.add_order(order)
            return

        # Entry with same-direction position: generate add order
        if signals.entry and account_state.has_position:
            direction = "long" if signals.direction > 0 else "short"
            if direction == account_state.position_side:
                if self.config.profit_add_only and account_state.unrealized_pnl < 0:
                    return
                order = generate_order(
                    signals, prediction, account_state, self.config,
                    bar_idx=bar_idx, source="add",
                )
                if order is not None:
                    self.order_manager.add_order(order)
            else:
                # Reversal: close first
                decision = evaluate(signals, account_state, self.config)
                if decision.action != "hold":
                    self.state.pending_decision = decision
