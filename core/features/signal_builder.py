"""Signal builder: extract indicator requirements from DNA and build entry/exit signals.

Higher-level interface than executor.py - takes raw DNA and enhanced DataFrame,
resolves indicator columns, and returns boolean signal Series.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd

from core.strategy.dna import StrategyDNA, SignalRole
from core.strategy.executor import evaluate_condition, combine_signals


def extract_indicator_requirements(dna: StrategyDNA) -> List[Tuple[str, Dict[str, Any]]]:
    """Extract unique indicator name + param combinations from DNA.

    Returns:
        List of (indicator_name, params) tuples, deduplicated.
    """
    seen = set()
    result = []
    for gene in dna.signal_genes:
        key = (gene.indicator, tuple(sorted(gene.params.items())))
        if key not in seen:
            seen.add(key)
            result.append((gene.indicator, gene.params))
    return result


def _resolve_column(df: pd.DataFrame, indicator: str, params: Dict[str, Any],
                    field_name: str | None = None) -> pd.Series | None:
    """Find the right DataFrame column for an indicator gene.

    Returns None if column not found.
    """
    if indicator == "RSI":
        col = f"rsi_{params['period']}"
    elif indicator == "EMA":
        col = f"ema_{params['period']}"
    elif indicator == "SMA":
        col = f"sma_{params['period']}"
    elif indicator == "MACD":
        fast, slow, sig = params["fast"], params["slow"], params["signal"]
        field = field_name or "histogram"
        if field == "macd":
            col = f"macd_{fast}_{slow}_{sig}"
        elif field == "signal":
            col = f"macd_signal_{fast}_{slow}_{sig}"
        else:
            col = f"macd_histogram_{fast}_{slow}_{sig}"
    elif indicator == "BB":
        period, std = params["period"], params["std"]
        std_str = str(std).replace(".0", "")
        field = field_name or "upper"
        col = f"bb_{field}_{period}_{std_str}"
    elif indicator == "ATR":
        col = f"atr_{params['period']}"
    elif indicator == "ADX":
        col = f"adx_{params['period']}"
    else:
        # Generic fallback
        matches = [c for c in df.columns if c.lower().startswith(indicator.lower())]
        if matches:
            col = matches[0]
        else:
            return None

    if col in df.columns:
        return df[col]

    # Prefix fallback
    matches = [c for c in df.columns if col in c]
    if matches:
        return df[matches[0]]

    return None


def build_signals(
    dna: StrategyDNA,
    enhanced_df: pd.DataFrame,
) -> Tuple[pd.Series, pd.Series]:
    """Build entry/exit boolean Series from StrategyDNA using enhanced DataFrame.

    Similar to executor.dna_to_signals but with more robust column resolution.
    Missing indicator columns are silently skipped.
    """
    close = enhanced_df["close"]

    entry_triggers = []
    entry_guards = []
    exit_triggers = []
    exit_guards = []

    for gene in dna.signal_genes:
        col_series = _resolve_column(enhanced_df, gene.indicator, gene.params, gene.field_name)
        if col_series is None:
            continue

        signal = evaluate_condition(col_series, close, gene.condition)
        signal = signal.fillna(False)

        if gene.role == SignalRole.ENTRY_TRIGGER:
            entry_triggers.append(signal)
        elif gene.role == SignalRole.ENTRY_GUARD:
            entry_guards.append(signal)
        elif gene.role == SignalRole.EXIT_TRIGGER:
            exit_triggers.append(signal)
        elif gene.role == SignalRole.EXIT_GUARD:
            exit_guards.append(signal)

    # Combine
    all_entry = entry_triggers + entry_guards
    if not all_entry:
        entries = pd.Series(False, index=enhanced_df.index)
    else:
        entries = combine_signals(all_entry, dna.logic_genes.entry_logic)

    all_exit = exit_triggers + exit_guards
    if not all_exit:
        exits = pd.Series(False, index=enhanced_df.index)
    else:
        exits = combine_signals(all_exit, dna.logic_genes.exit_logic)

    # Prevent simultaneous entry+exit (favor exit)
    both = entries & exits
    entries = entries & ~both

    return entries, exits
