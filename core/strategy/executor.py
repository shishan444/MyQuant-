"""DNA to vectorbt signal conversion - the critical bridge module."""

from __future__ import annotations

import pandas as pd

from MyQuant.core.strategy.dna import StrategyDNA, SignalRole


def evaluate_condition(
    indicator_series: pd.Series,
    close_series: pd.Series,
    condition: dict,
) -> pd.Series:
    """Convert a structured condition dict to a boolean Series.

    Args:
        indicator_series: The indicator values.
        close_series: The close price series.
        condition: Dict with "type" and optional "threshold".

    Returns:
        Boolean Series with same index as input.
    """
    cond_type = condition["type"]

    if cond_type == "lt":
        return indicator_series < condition["threshold"]
    elif cond_type == "gt":
        return indicator_series > condition["threshold"]
    elif cond_type == "le":
        return indicator_series <= condition["threshold"]
    elif cond_type == "ge":
        return indicator_series >= condition["threshold"]
    elif cond_type == "cross_above":
        threshold = condition.get("threshold")
        if threshold is not None:
            return (indicator_series.shift(1) < threshold) & (indicator_series >= threshold)
        else:
            # Cross above another series (not used in v0.1)
            return pd.Series(False, index=indicator_series.index)
    elif cond_type == "cross_below":
        threshold = condition.get("threshold")
        if threshold is not None:
            return (indicator_series.shift(1) > threshold) & (indicator_series <= threshold)
        else:
            return pd.Series(False, index=indicator_series.index)
    elif cond_type == "price_above":
        return close_series > indicator_series
    elif cond_type == "price_below":
        return close_series < indicator_series
    else:
        return pd.Series(False, index=indicator_series.index)


def combine_signals(signal_list: list[pd.Series], logic: str) -> pd.Series:
    """Combine multiple boolean Series with AND or OR logic."""
    if not signal_list:
        return pd.Series(False, index=signal_list[0].index if signal_list else [])

    if logic == "AND":
        result = signal_list[0].copy()
        for s in signal_list[1:]:
            result = result & s
        return result
    elif logic == "OR":
        result = signal_list[0].copy()
        for s in signal_list[1:]:
            result = result | s
        return result
    else:
        return signal_list[0].copy()


def _get_indicator_column(df: pd.DataFrame, gene) -> pd.Series:
    """Resolve an indicator column from the enhanced DataFrame.

    Tries exact name match first, then prefix-based search.
    """
    indicator = gene.indicator
    params = gene.params

    # Build expected column name patterns
    if indicator == "RSI":
        col = f"rsi_{params['period']}"
    elif indicator == "EMA":
        col = f"ema_{params['period']}"
    elif indicator == "SMA":
        col = f"sma_{params['period']}"
    elif indicator == "MACD":
        field = gene.field_name or "histogram"
        fast, slow, sig = params["fast"], params["slow"], params["signal"]
        col = f"macd_{field}_{fast}_{slow}_{sig}" if field != "histogram" else f"macd_histogram_{fast}_{slow}_{sig}"
        if field == "macd":
            col = f"macd_{fast}_{slow}_{sig}"
        elif field == "signal":
            col = f"macd_signal_{fast}_{slow}_{sig}"
    elif indicator == "BB":
        field = gene.field_name or "upper"
        period, std = params["period"], params["std"]
        std_str = str(std).replace(".0", "")
        col = f"bb_{field}_{period}_{std_str}"
    elif indicator == "ATR":
        col = f"atr_{params['period']}"
    elif indicator == "ADX":
        col = f"adx_{params['period']}"
    else:
        # Fallback: try to find by prefix
        matches = [c for c in df.columns if c.lower().startswith(indicator.lower())]
        if matches:
            col = matches[0]
        else:
            raise ValueError(f"Cannot find column for indicator {indicator}")

    if col in df.columns:
        return df[col]

    # Fallback: prefix match
    matches = [c for c in df.columns if col in c]
    if matches:
        return df[matches[0]]

    raise ValueError(f"Column '{col}' not found in DataFrame. Available: {list(df.columns)}")


def dna_to_signals(
    dna: StrategyDNA,
    enhanced_df: pd.DataFrame,
) -> tuple[pd.Series, pd.Series]:
    """Convert a StrategyDNA to entry/exit boolean Series.

    Args:
        dna: Strategy genome.
        enhanced_df: DataFrame with indicator columns appended.

    Returns:
        Tuple of (entries, exits) boolean Series.
    """
    close = enhanced_df["close"]

    # Separate signals by role
    entry_triggers = []
    entry_guards = []
    exit_triggers = []
    exit_guards = []

    for gene in dna.signal_genes:
        try:
            indicator_col = _get_indicator_column(enhanced_df, gene)
            signal = evaluate_condition(indicator_col, close, gene.condition)
            signal = signal.fillna(False)

            if gene.role == SignalRole.ENTRY_TRIGGER:
                entry_triggers.append(signal)
            elif gene.role == SignalRole.ENTRY_GUARD:
                entry_guards.append(signal)
            elif gene.role == SignalRole.EXIT_TRIGGER:
                exit_triggers.append(signal)
            elif gene.role == SignalRole.EXIT_GUARD:
                exit_guards.append(signal)
        except ValueError:
            continue

    # Combine entry signals
    all_entry = entry_triggers + entry_guards
    if not all_entry:
        entries = pd.Series(False, index=enhanced_df.index)
    else:
        entries = combine_signals(all_entry, dna.logic_genes.entry_logic)

    # Combine exit signals
    all_exit = exit_triggers + exit_guards
    if not all_exit:
        exits = pd.Series(False, index=enhanced_df.index)
    else:
        exits = combine_signals(all_exit, dna.logic_genes.exit_logic)

    # Prevent simultaneous entry+exit on same bar (favor exit)
    both = entries & exits
    entries = entries & ~both

    return entries, exits
