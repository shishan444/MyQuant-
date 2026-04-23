"""DNA to vectorbt signal conversion - the critical bridge module."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy.dna import StrategyDNA, SignalRole


@dataclass
class SignalSet:
    """Complete set of trading signals for a strategy."""

    entries: pd.Series     # open position signals
    exits: pd.Series       # close position signals
    adds: pd.Series        # add to position signals
    reduces: pd.Series     # reduce position signals
    trend_direction: pd.Series  # trend direction (+1 long, -1 short, 0 neutral)


def evaluate_condition(
    indicator_series: pd.Series,
    close_series: pd.Series,
    condition: dict,
    df: pd.DataFrame | None = None,
) -> pd.Series:
    """Convert a structured condition dict to a boolean Series.

    Args:
        indicator_series: The indicator values.
        close_series: The close price series.
        condition: Dict with "type" and optional "threshold".
        df: Full enhanced DataFrame (needed for cross_above_series,
            lookback_any/all, touch_bounce, role_reversal, wick_touch).

    Returns:
        Boolean Series with same index as input.
    """
    cond_type = condition["type"]

    if cond_type == "eq":
        threshold = condition.get("threshold", 1)
        return indicator_series == threshold
    elif cond_type == "lt":
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
    # ── Phase 2: dynamic conditions ──
    elif cond_type == "cross_above_series":
        target_series = _resolve_target_indicator_series(condition, df)
        if target_series is None:
            return pd.Series(False, index=indicator_series.index)
        return (indicator_series.shift(1) < target_series.shift(1)) & (indicator_series >= target_series)
    elif cond_type == "cross_below_series":
        target_series = _resolve_target_indicator_series(condition, df)
        if target_series is None:
            return pd.Series(False, index=indicator_series.index)
        return (indicator_series.shift(1) > target_series.shift(1)) & (indicator_series <= target_series)
    elif cond_type == "lookback_any":
        window = condition.get("window", 5)
        inner = condition.get("inner", {})
        inner_signal = _evaluate_inner_condition(indicator_series, close_series, inner, df)
        return inner_signal.rolling(window=window, min_periods=1).apply(any, raw=False).fillna(False).astype(bool)
    elif cond_type == "lookback_all":
        window = condition.get("window", 5)
        inner = condition.get("inner", {})
        inner_signal = _evaluate_inner_condition(indicator_series, close_series, inner, df)
        return inner_signal.rolling(window=window, min_periods=1).apply(all, raw=False).fillna(False).astype(bool)
    # ── Phase 4: support/resistance conditions ──
    elif cond_type == "touch_bounce":
        return _eval_touch_bounce(indicator_series, close_series, df, condition)
    elif cond_type == "role_reversal":
        return _eval_role_reversal(indicator_series, close_series, df, condition)
    elif cond_type == "wick_touch":
        return _eval_wick_touch(indicator_series, close_series, df, condition)
    else:
        return pd.Series(False, index=indicator_series.index)


def _resolve_target_indicator_series(condition: dict, df: pd.DataFrame | None) -> pd.Series | None:
    """Resolve target_indicator + target_params to a Series from df."""
    if df is None:
        return None
    target_name = condition.get("target_indicator", "")
    target_params = condition.get("target_params", {})
    # Build a minimal gene-like object to reuse _get_indicator_column
    gene = _SimpleGene(target_name, target_params)
    try:
        return _get_indicator_column(df, gene)
    except ValueError:
        return None


def _evaluate_inner_condition(
    indicator_series: pd.Series,
    close_series: pd.Series,
    inner: dict,
    df: pd.DataFrame | None,
) -> pd.Series:
    """Evaluate an inner condition for lookback window types."""
    inner_type = inner.get("type", "")
    if inner_type in ("lt", "gt", "le", "ge"):
        threshold = inner.get("threshold", 0)
        if inner_type == "lt":
            return indicator_series < threshold
        elif inner_type == "gt":
            return indicator_series > threshold
        elif inner_type == "le":
            return indicator_series <= threshold
        elif inner_type == "ge":
            return indicator_series >= threshold
    elif inner_type == "price_above":
        return close_series > indicator_series
    elif inner_type == "price_below":
        return close_series < indicator_series
    # For complex inner conditions, delegate to evaluate_condition
    return evaluate_condition(indicator_series, close_series, inner, df)


def _eval_touch_bounce(
    indicator_series: pd.Series,
    close_series: pd.Series,
    df: pd.DataFrame | None,
    condition: dict,
) -> pd.Series:
    """Touch-bounce: price touches indicator line then bounces.

    direction="support": low near line + close above line + next close higher
    direction="resistance": high near line + close below line + next close lower
    """
    if df is None:
        return pd.Series(False, index=indicator_series.index)

    direction = condition.get("direction", "support")
    proximity_pct = condition.get("proximity_pct", 0.01)

    low = df["low"]
    high = df["high"]
    line = indicator_series

    # Proximity check using only past/current data (no shift(-1))
    if direction == "support":
        proximity = (low - line).abs() <= line.abs() * proximity_pct
        above_line = close_series > line
        bounce_up = close_series > close_series.shift(1)  # current close > previous close
        result = proximity & above_line & bounce_up
    else:
        proximity = (high - line).abs() <= line.abs() * proximity_pct
        below_line = close_series < line
        bounce_down = close_series < close_series.shift(1)  # current close < previous close
        result = proximity & below_line & bounce_down

    return result.fillna(False)


def _eval_role_reversal(
    indicator_series: pd.Series,
    close_series: pd.Series,
    df: pd.DataFrame | None,
    condition: dict,
) -> pd.Series:
    """Role reversal: indicator line switches from support to resistance or vice versa.

    role="support": recently crossed above + currently above
    role="resistance": recently crossed below + currently below
    """
    if df is None:
        return pd.Series(False, index=indicator_series.index)

    role = condition.get("role", "resistance")
    lookback = condition.get("lookback", 10)

    line = indicator_series

    if role == "support":
        # Line was resistance (price was below), now price is above
        was_below = close_series.shift(lookback) < line.shift(lookback)
        now_above = close_series > line
        result = was_below & now_above
    else:
        # Line was support (price was above), now price is below
        was_above = close_series.shift(lookback) > line.shift(lookback)
        now_below = close_series < line
        result = was_above & now_below

    return result.fillna(False)


def _eval_wick_touch(
    indicator_series: pd.Series,
    close_series: pd.Series,
    df: pd.DataFrame | None,
    condition: dict,
) -> pd.Series:
    """Wick touch: wick touches indicator line but close is on the other side.

    direction="above": high near line + close below line
    direction="below": low near line + close above line
    """
    if df is None:
        return pd.Series(False, index=indicator_series.index)

    direction = condition.get("direction", "above")
    proximity_pct = condition.get("proximity_pct", 0.01)

    low = df["low"]
    high = df["high"]
    line = indicator_series

    if direction == "above":
        wick_near = (high - line).abs() <= line.abs() * proximity_pct
        close_below = close_series < line
        result = wick_near & close_below
    else:
        wick_near = (low - line).abs() <= line.abs() * proximity_pct
        close_above = close_series > line
        result = wick_near & close_above

    return result.fillna(False)


class _SimpleGene:
    """Minimal gene-like object for _get_indicator_column reuse."""
    __slots__ = ("indicator", "params", "field_name")

    def __init__(self, indicator: str, params: dict, field_name: str | None = None):
        self.indicator = indicator
        self.params = params
        self.field_name = field_name


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
    elif indicator == "WMA":
        col = f"wma_{params['period']}"
    elif indicator == "DEMA":
        col = f"dema_{params['period']}"
    elif indicator == "TEMA":
        col = f"tema_{params['period']}"
    elif indicator == "RVOL":
        col = f"rvol_{params['period']}"
    elif indicator == "VROC":
        col = f"vroc_{params['period']}"
    elif indicator == "AD":
        col = "ad"
    elif indicator == "CVD":
        col = "cvd"
    elif indicator == "VWMA":
        col = f"vwma_{params['period']}"
    elif indicator == "Aroon":
        field = gene.field_name or "aroon_up"
        period = params["period"]
        col = f"{field}_{period}"
    elif indicator == "CMO":
        col = f"cmo_{params['period']}"
    elif indicator == "TRIX":
        col = f"trix_{params['period']}"
    elif indicator == "VolumeProfile":
        field = gene.field_name or "vp_poc"
        bins = params.get("bins", 50)
        lookback = params.get("lookback", 60)
        col = f"{field}_{bins}_{lookback}"
    elif indicator == "Keltner":
        field = gene.field_name or "upper"
        ema_p, atr_p, mult = params["ema_period"], params["atr_period"], params["multiplier"]
        kc_name = f"kc_{ema_p}_{atr_p}_{mult}"
        col = f"{kc_name}_{field}"
    elif indicator == "Donchian":
        field = gene.field_name or "upper"
        period = params["period"]
        col = f"dc_{field}_{period}"
    elif indicator == "CCI":
        col = f"cci_{params['period']}"
    elif indicator == "ROC":
        col = f"roc_{params['period']}"
    elif indicator == "Stochastic":
        field = gene.field_name or "k"
        k_period = params["k_period"]
        d_period = params["d_period"]
        prefix = "stoch_k" if field == "k" else "stoch_d"
        col = f"{prefix}_{k_period}_{d_period}"
    elif indicator == "OBV":
        col = "obv"
    elif indicator == "CMF":
        col = f"cmf_{params['period']}"
    elif indicator == "MFI":
        col = f"mfi_{params['period']}"
    elif indicator == "PSAR":
        col = "psar"
    elif indicator == "Williams %R":
        col = f"willr_{params['period']}"
    elif indicator == "BearishEngulfing":
        col = "pattern_bearish_engulfing"
    elif indicator == "EveningStar":
        col = "pattern_evening_star"
    elif indicator == "ThreeBlackCrows":
        col = "pattern_3blackcrows"
    elif indicator == "ShootingStar":
        col = "pattern_shooting_star"
    elif indicator == "ThreeWhiteSoldiers":
        col = "pattern_3whitesoldiers"
    elif indicator == "MorningStar":
        col = "pattern_morning_star"
    elif indicator == "BullishReversal":
        col = "pattern_bullish_reversal"
    elif indicator == "BearishReversal":
        col = "pattern_bearish_reversal"
    elif indicator == "BullishDivergence":
        col = "pattern_bullish_divergence"
    elif indicator == "BearishDivergence":
        col = "pattern_bearish_divergence"
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


def evaluate_layer(
    layer,
    df: pd.DataFrame,
) -> SignalSet:
    """Evaluate a single TimeframeLayer on a pre-computed DataFrame.

    Returns SignalSet with entries, exits, adds, reduces, trend_direction.
    """
    close = df["close"]
    entry_triggers, entry_guards = [], []
    exit_triggers, exit_guards = [], []
    add_triggers, add_guards = [], []
    reduce_triggers, reduce_guards = [], []

    for gene in layer.signal_genes:
        try:
            indicator_col = _get_indicator_column(df, gene)
            signal = evaluate_condition(indicator_col, close, gene.condition, df=df)
            signal = signal.fillna(False)

            if gene.role == SignalRole.ENTRY_TRIGGER:
                entry_triggers.append(signal)
            elif gene.role == SignalRole.ENTRY_GUARD:
                entry_guards.append(signal)
            elif gene.role == SignalRole.EXIT_TRIGGER:
                exit_triggers.append(signal)
            elif gene.role == SignalRole.EXIT_GUARD:
                exit_guards.append(signal)
            elif gene.role == SignalRole.ADD_TRIGGER:
                add_triggers.append(signal)
            elif gene.role == SignalRole.ADD_GUARD:
                add_guards.append(signal)
            elif gene.role == SignalRole.REDUCE_TRIGGER:
                reduce_triggers.append(signal)
            elif gene.role == SignalRole.REDUCE_GUARD:
                reduce_guards.append(signal)
        except ValueError:
            continue

    all_entry = entry_triggers + entry_guards
    entries = combine_signals(all_entry, layer.logic_genes.entry_logic) if all_entry else pd.Series(False, index=df.index)

    all_exit = exit_triggers + exit_guards
    exits = combine_signals(all_exit, layer.logic_genes.exit_logic) if all_exit else pd.Series(False, index=df.index)

    logic = layer.logic_genes
    add_logic = getattr(logic, 'add_logic', 'AND') or 'AND'
    reduce_logic = getattr(logic, 'reduce_logic', 'AND') or 'AND'

    all_add = add_triggers + add_guards
    adds = combine_signals(all_add, add_logic) if all_add else pd.Series(False, index=df.index)

    all_reduce = reduce_triggers + reduce_guards
    reduces = combine_signals(all_reduce, reduce_logic) if all_reduce else pd.Series(False, index=df.index)

    # Prevent simultaneous entry+exit (favor exit)
    both = entries & exits
    entries = entries & ~both

    # Simple trend direction: +1 if close > EMA(50), -1 if below
    trend_cols = [c for c in df.columns if c.startswith("ema_")]
    if trend_cols:
        ema_col = df[trend_cols[0]]
        trend_direction = pd.Series(0, index=df.index)
        trend_direction[close > ema_col] = 1
        trend_direction[close < ema_col] = -1
    else:
        trend_direction = pd.Series(0, index=df.index)

    return SignalSet(
        entries=entries,
        exits=exits,
        adds=adds,
        reduces=reduces,
        trend_direction=trend_direction,
    )


def resample_signals(
    high_tf_signals: pd.Series,
    target_index: pd.DatetimeIndex,
) -> pd.Series:
    """Forward-fill higher timeframe signals to match execution timeframe index."""
    if high_tf_signals.empty or len(target_index) == 0:
        return pd.Series(False, index=target_index)

    reindexed = high_tf_signals.reindex(target_index, method="ffill")
    return reindexed.fillna(False).astype(bool)


def dna_to_signals(
    dna: StrategyDNA,
    enhanced_df: pd.DataFrame,
    dfs_by_timeframe: dict | None = None,
) -> tuple[pd.Series, pd.Series]:
    """Convert a StrategyDNA to entry/exit boolean Series.

    Returns (entries, exits) for backward compatibility.
    Use dna_to_signal_set() for full SignalSet with adds/reduces.
    """
    sig_set = dna_to_signal_set(dna, enhanced_df, dfs_by_timeframe)
    return sig_set.entries, sig_set.exits


def dna_to_signal_set(
    dna: StrategyDNA,
    enhanced_df: pd.DataFrame,
    dfs_by_timeframe: dict | None = None,
) -> SignalSet:
    """Convert a StrategyDNA to a full SignalSet with adds/reduces."""
    # MTF mode
    if dna.is_mtf and dfs_by_timeframe is not None:
        layer_entries = []
        layer_exits = []
        layer_adds = []
        layer_reduces = []

        for layer in dna.layers:
            layer_df = dfs_by_timeframe.get(layer.timeframe)
            if layer_df is None:
                continue

            sig = evaluate_layer(layer, layer_df)

            exec_tf = dna.execution_genes.timeframe
            if layer.timeframe != exec_tf:
                layer_entries.append(resample_signals(sig.entries, enhanced_df.index))
                layer_exits.append(resample_signals(sig.exits, enhanced_df.index))
                layer_adds.append(resample_signals(sig.adds, enhanced_df.index))
                layer_reduces.append(resample_signals(sig.reduces, enhanced_df.index))
            else:
                layer_entries.append(sig.entries.reindex(enhanced_df.index, fill_value=False))
                layer_exits.append(sig.exits.reindex(enhanced_df.index, fill_value=False))
                layer_adds.append(sig.adds.reindex(enhanced_df.index, fill_value=False))
                layer_reduces.append(sig.reduces.reindex(enhanced_df.index, fill_value=False))

        if not layer_entries:
            return SignalSet(
                entries=pd.Series(False, index=enhanced_df.index),
                exits=pd.Series(False, index=enhanced_df.index),
                adds=pd.Series(False, index=enhanced_df.index),
                reduces=pd.Series(False, index=enhanced_df.index),
                trend_direction=pd.Series(0, index=enhanced_df.index),
            )

        combined_entries = combine_signals(layer_entries, dna.cross_layer_logic)
        combined_exits = combine_signals(layer_exits, dna.cross_layer_logic)
        combined_adds = combine_signals(layer_adds, dna.cross_layer_logic)
        combined_reduces = combine_signals(layer_reduces, dna.cross_layer_logic)

        both = combined_entries & combined_exits
        combined_entries = combined_entries & ~both

        # Trend direction from shortest timeframe
        trend_cols = [c for c in enhanced_df.columns if c.startswith("ema_")]
        if trend_cols:
            trend_direction = pd.Series(0, index=enhanced_df.index)
            trend_direction[enhanced_df["close"] > enhanced_df[trend_cols[0]]] = 1
            trend_direction[enhanced_df["close"] < enhanced_df[trend_cols[0]]] = -1
        else:
            trend_direction = pd.Series(0, index=enhanced_df.index)

        return SignalSet(
            entries=combined_entries,
            exits=combined_exits,
            adds=combined_adds,
            reduces=combined_reduces,
            trend_direction=trend_direction,
        )

    # Single-timeframe mode
    close = enhanced_df["close"]

    entry_triggers, entry_guards = [], []
    exit_triggers, exit_guards = [], []
    add_triggers, add_guards = [], []
    reduce_triggers, reduce_guards = [], []

    for gene in dna.signal_genes:
        try:
            indicator_col = _get_indicator_column(enhanced_df, gene)
            signal = evaluate_condition(indicator_col, close, gene.condition, df=enhanced_df)
            signal = signal.fillna(False)

            if gene.role == SignalRole.ENTRY_TRIGGER:
                entry_triggers.append(signal)
            elif gene.role == SignalRole.ENTRY_GUARD:
                entry_guards.append(signal)
            elif gene.role == SignalRole.EXIT_TRIGGER:
                exit_triggers.append(signal)
            elif gene.role == SignalRole.EXIT_GUARD:
                exit_guards.append(signal)
            elif gene.role == SignalRole.ADD_TRIGGER:
                add_triggers.append(signal)
            elif gene.role == SignalRole.ADD_GUARD:
                add_guards.append(signal)
            elif gene.role == SignalRole.REDUCE_TRIGGER:
                reduce_triggers.append(signal)
            elif gene.role == SignalRole.REDUCE_GUARD:
                reduce_guards.append(signal)
        except ValueError:
            continue

    all_entry = entry_triggers + entry_guards
    entries = combine_signals(all_entry, dna.logic_genes.entry_logic) if all_entry else pd.Series(False, index=enhanced_df.index)

    all_exit = exit_triggers + exit_guards
    exits = combine_signals(all_exit, dna.logic_genes.exit_logic) if all_exit else pd.Series(False, index=enhanced_df.index)

    add_logic = getattr(dna.logic_genes, 'add_logic', 'AND') or 'AND'
    reduce_logic = getattr(dna.logic_genes, 'reduce_logic', 'AND') or 'AND'

    all_add = add_triggers + add_guards
    adds = combine_signals(all_add, add_logic) if all_add else pd.Series(False, index=enhanced_df.index)

    all_reduce = reduce_triggers + reduce_guards
    reduces = combine_signals(all_reduce, reduce_logic) if all_reduce else pd.Series(False, index=enhanced_df.index)

    both = entries & exits
    entries = entries & ~both

    # Trend direction
    trend_cols = [c for c in enhanced_df.columns if c.startswith("ema_")]
    if trend_cols:
        trend_direction = pd.Series(0, index=enhanced_df.index)
        trend_direction[close > enhanced_df[trend_cols[0]]] = 1
        trend_direction[close < enhanced_df[trend_cols[0]]] = -1
    else:
        trend_direction = pd.Series(0, index=enhanced_df.index)

    return SignalSet(
        entries=entries,
        exits=exits,
        adds=adds,
        reduces=reduces,
        trend_direction=trend_direction,
    )
