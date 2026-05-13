"""Data types for the paper trading judgment and execution pipeline."""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Decision:
    """Output of the judgment rule evaluation.

    action: "hold" | "open" | "close" | "add" | "reduce"
    direction: "long" | "short" | ""
    target_position_pct: fraction of equity for the target position (0.0 ~ 1.0)
    reason: human-readable explanation for logging
    """

    action: str
    direction: str = ""
    target_position_pct: float = 0.0
    entry_size_pct: float = 0.0
    reason: str = ""


@dataclass
class AccountState:
    """Snapshot of the virtual account for judgment rule evaluation."""

    balance: float
    has_position: bool
    position_side: str  # "long" | "short" | "flat"
    position_entry: float
    position_quantity: float
    position_margin: float
    unrealized_pnl: float
    position_bars_held: int  # number of bars since position opened
    target_position_pct: float  # current target set by judgment engine
    actual_position_pct: float  # current position as fraction of equity
    equity: float
    allowed_direction: str = "mixed"  # DNA direction constraint: "long" | "short" | "mixed"


@dataclass
class JudgmentConfig:
    """Configuration for judgment rules."""

    min_hold_bars: int = 3  # minimum bars before allowing close
    min_profit_ratio: float = 2.0  # minimum pnl / fee ratio to allow close
    initial_entry_pct: float = 0.33  # first entry as fraction of target
    profit_add_only: bool = True  # only add when unrealized pnl > 0
    max_hold_bars: int | None = None  # force close if losing and held too long
    max_fill_bars: int = 3  # max consecutive no-signal auto-fill bars
    fee_rate: float = 0.001  # trading fee rate for min_profit calculation
    confidence_sizing_enabled: bool = False  # scale entry by MTF confidence


@dataclass
class BarSignals:
    """Signals for a single bar (last bar extracted from SignalSet)."""

    entry: bool = False
    exit: bool = False
    add: bool = False
    reduce: bool = False
    direction: float = 1.0  # +1 long, -1 short
    confidence: float = 1.0  # MTF confidence [0.1, 1.0], default 1.0 (no effect)

@dataclass
class Tranche:
    """Single limit-order tranche in a PositionPlan."""

    price_level: float
    size_pct: float
    status: str = "pending"  # "pending" | "filled" | "cancelled"
    bars_waiting: int = 0


@dataclass
class PositionPlan:
    """Position building plan with multiple tranches."""

    tranches: list  # List[Tranche]
    target_pct: float
    max_wait_bars: int = 5
    max_chase_pct: float = 0.5

    @classmethod
    def from_prediction(
        cls,
        prediction,
        target_pct: float,
        side: str,
        entry_price: float,
        stop_loss: float,
    ) -> PositionPlan:
        """Create a plan from a PredictionResult.

        Creates 2 limit-order tranches:
        - Long: at predicted_low + width*0.2 and predicted_low
        - Short: at predicted_high - width*0.2 and predicted_high
        """
        remaining_pct = target_pct * 0.67
        size_per_tranche = remaining_pct / 2

        if side == "long":
            tranches = [
                Tranche(
                    price_level=prediction.low + prediction.width * 0.2,
                    size_pct=size_per_tranche,
                ),
                Tranche(
                    price_level=prediction.low,
                    size_pct=size_per_tranche,
                ),
            ]
        else:
            tranches = [
                Tranche(
                    price_level=prediction.high - prediction.width * 0.2,
                    size_pct=size_per_tranche,
                ),
                Tranche(
                    price_level=prediction.high,
                    size_pct=size_per_tranche,
                ),
            ]

        return cls(tranches=tranches, target_pct=target_pct)


    @staticmethod
    def from_signal_set(sig_set, idx: int) -> BarSignals:
        """Extract signals for a specific bar index from a SignalSet."""
        raw_direction = (
            float(sig_set.entry_direction.iloc[idx])
            if sig_set.entry_direction is not None
            else 1.0
        )
        # NaN protection: suppress entry when direction is invalid
        entry = bool(sig_set.entries.iloc[idx])
        if entry and math.isnan(raw_direction):
            entry = False
            raw_direction = 0.0

        # Extract confidence if available
        raw_confidence = 1.0
        sig_confidence = getattr(sig_set, "confidence", None)
        if sig_confidence is not None:
            val = float(sig_confidence.iloc[idx])
            raw_confidence = val if not math.isnan(val) else 1.0

        return BarSignals(
            entry=entry,
            exit=bool(sig_set.exits.iloc[idx]),
            add=bool(sig_set.adds.iloc[idx]),
            reduce=bool(sig_set.reduces.iloc[idx]),
            direction=raw_direction,
            confidence=raw_confidence,
        )
