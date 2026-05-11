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
