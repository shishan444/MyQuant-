"""Indicator computation engine.

Provides _compute_indicator() and compute_all_indicators() for batch
pre-computation via pandas-ta.  Registry structures and indicator
definitions live in registry.py and are re-exported here for backward
compatibility.
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pandas_ta as ta

# Re-export registry structures for backward compatibility
from core.features.registry import (
    ParamDef,
    IndicatorDef,
    INDICATOR_REGISTRY,
    get_interchangeable,
)


# ---------------------------------------------------------------------------
# Default parameter sets for pre-computation
# ---------------------------------------------------------------------------

_DEFAULT_PARAMS: Dict[str, List[Dict[str, Any]]] = {
    "EMA": [{"period": p} for p in [10, 20, 50, 100, 200]],
    "SMA": [{"period": p} for p in [10, 20, 50, 100, 200]],
    "WMA": [{"period": p} for p in [10, 20, 50]],
    "DEMA": [{"period": p} for p in [10, 20, 50]],
    "TEMA": [{"period": p} for p in [10, 20, 50]],
    "RSI": [{"period": p} for p in [7, 14, 21]],
    "MACD": [{"fast": 12, "slow": 26, "signal": 9}],
    "Stochastic": [{"k_period": 14, "d_period": 3}],
    "CCI": [{"period": 20}],
    "ROC": [{"period": 12}],
    "Williams %R": [{"period": 14}],
    "BB": [{"period": 20, "std": 2.0}],
    "ATR": [{"period": 14}],
    "Keltner": [{"ema_period": 20, "atr_period": 10, "multiplier": 2.0}],
    "Donchian": [{"period": 20}],
    "OBV": [{}],
    "CMF": [{"period": 20}],
    "MFI": [{"period": 14}],
    "ADX": [{"period": 14}],
    "PSAR": [{"step": 0.02, "max_step": 0.2}],
    # New indicators
    "RVOL": [{"period": 20}, {"period": 50}],
    "VROC": [{"period": 14}],
    "AD": [{}],
    "CVD": [{}],
    "VWMA": [{"period": 20}, {"period": 50}],
    "Aroon": [{"period": 25}],
    "CMO": [{"period": 14}],
    "TRIX": [{"period": 12}],
    # VolumeProfile is guard_only and expensive; compute on demand only
    # Pattern indicators (no params)
    "BearishEngulfing": [{}],
    "EveningStar": [{}],
    "ThreeBlackCrows": [{}],
    "ShootingStar": [{}],
    "ThreeWhiteSoldiers": [{}],
    "MorningStar": [{}],
    "BullishReversal": [{}],
    "BearishReversal": [{}],
    "BullishDivergence": [{}],
    "BearishDivergence": [{}],
}


# ---------------------------------------------------------------------------
# Computation engine
# ---------------------------------------------------------------------------

def _compute_indicator(df: pd.DataFrame, name: str, params: Dict[str, Any]) -> pd.DataFrame:
    """Compute a single indicator and return DataFrame with named columns."""
    result = df.copy()

    if name == "EMA":
        period = int(params["period"])
        result[f"ema_{period}"] = ta.ema(df["close"], length=period)
    elif name == "SMA":
        period = int(params["period"])
        result[f"sma_{period}"] = ta.sma(df["close"], length=period)
    elif name == "RSI":
        period = int(params["period"])
        result[f"rsi_{period}"] = ta.rsi(df["close"], length=period)
    elif name == "MACD":
        fast, slow, signal = int(params["fast"]), int(params["slow"]), int(params["signal"])
        macd_df = ta.macd(df["close"], fast=fast, slow=slow, signal=signal)
        if macd_df is not None:
            result[f"macd_{fast}_{slow}_{signal}"] = macd_df.iloc[:, 0]
            result[f"macd_signal_{fast}_{slow}_{signal}"] = macd_df.iloc[:, 1]
            result[f"macd_histogram_{fast}_{slow}_{signal}"] = macd_df.iloc[:, 2]
    elif name == "BB":
        period, std = int(params["period"]), float(params["std"])
        bb_df = ta.bbands(df["close"], length=period, std=std)
        if bb_df is not None:
            result[f"bb_upper_{period}_{std}"] = bb_df.iloc[:, 0]
            result[f"bb_middle_{period}_{std}"] = bb_df.iloc[:, 1]
            result[f"bb_lower_{period}_{std}"] = bb_df.iloc[:, 2]
    elif name == "ATR":
        period = int(params["period"])
        result[f"atr_{period}"] = ta.atr(df["high"], df["low"], df["close"], length=period)
    elif name == "ADX":
        period = int(params["period"])
        result[f"adx_{period}"] = ta.adx(df["high"], df["low"], df["close"], length=period).iloc[:, 0]
    elif name == "WMA":
        period = int(params["period"])
        result[f"wma_{period}"] = ta.wma(df["close"], length=period)
    elif name == "DEMA":
        period = int(params["period"])
        result[f"dema_{period}"] = ta.dema(df["close"], length=period)
    elif name == "TEMA":
        period = int(params["period"])
        result[f"tema_{period}"] = ta.tema(df["close"], length=period)
    elif name == "Stochastic":
        k_period = int(params["k_period"])
        d_period = int(params["d_period"])
        stoch_df = ta.stoch(df["high"], df["low"], df["close"],
                            k=k_period, d=d_period)
        if stoch_df is not None:
            result[f"stoch_k_{k_period}_{d_period}"] = stoch_df.iloc[:, 0]
            result[f"stoch_d_{k_period}_{d_period}"] = stoch_df.iloc[:, 1]
    elif name == "CCI":
        period = int(params["period"])
        result[f"cci_{period}"] = ta.cci(df["high"], df["low"], df["close"], length=period)
    elif name == "ROC":
        period = int(params["period"])
        result[f"roc_{period}"] = ta.roc(df["close"], length=period)
    elif name == "Williams %R":
        period = int(params["period"])
        result[f"willr_{period}"] = ta.willr(df["high"], df["low"], df["close"], length=period)
    elif name == "Keltner":
        ema_p = int(params["ema_period"])
        atr_p = int(params["atr_period"])
        mult = float(params["multiplier"])
        kc_name = f"kc_{ema_p}_{atr_p}_{mult}"
        kc_df = ta.kc(df["high"], df["low"], df["close"],
                       length=ema_p, atr_length=atr_p, mamode="ema")
        if kc_df is not None:
            result[f"{kc_name}_upper"] = kc_df.iloc[:, 0]
            result[f"{kc_name}_middle"] = kc_df.iloc[:, 1]
            result[f"{kc_name}_lower"] = kc_df.iloc[:, 2]
    elif name == "Donchian":
        period = int(params["period"])
        dc_df = ta.donchian(df["high"], df["low"], lower_length=period, upper_length=period)
        if dc_df is not None:
            result[f"dc_upper_{period}"] = dc_df.iloc[:, 0]
            result[f"dc_middle_{period}"] = (dc_df.iloc[:, 0] + dc_df.iloc[:, 1]) / 2
            result[f"dc_lower_{period}"] = dc_df.iloc[:, 1]
    elif name == "OBV":
        result["obv"] = ta.obv(df["close"], df["volume"])
    elif name == "CMF":
        period = int(params["period"])
        result[f"cmf_{period}"] = ta.cmf(df["high"], df["low"], df["close"], df["volume"], length=period)
    elif name == "MFI":
        period = int(params["period"])
        result[f"mfi_{period}"] = ta.mfi(df["high"], df["low"], df["close"], df["volume"], length=period)
    elif name == "PSAR":
        step = float(params["step"])
        max_step = float(params["max_step"])
        psar_val = ta.psar(df["high"], df["low"], df["close"],
                           af=step, max_af=max_step)
        if psar_val is not None:
            result["psar"] = psar_val.iloc[:, 0]
    # ── New indicators ──
    elif name == "RVOL":
        period = int(params["period"])
        vol_sma = ta.sma(df["volume"], length=period)
        result[f"rvol_{period}"] = df["volume"] / vol_sma
    elif name == "VROC":
        period = int(params["period"])
        result[f"vroc_{period}"] = ta.roc(df["volume"], length=period)
    elif name == "AD":
        result["ad"] = ta.ad(df["high"], df["low"], df["close"], df["volume"])
    elif name == "CVD":
        hl_range = df["high"] - df["low"]
        # Guard against division by zero
        safe_range = hl_range.replace(0, np.nan)
        cvd_raw = df["volume"] * (df["close"] - df["open"]) / safe_range
        result["cvd"] = cvd_raw.fillna(0).cumsum()
    elif name == "VWMA":
        period = int(params["period"])
        result[f"vwma_{period}"] = ta.vwma(df["close"], df["volume"], length=period)
    elif name == "Aroon":
        period = int(params["period"])
        aroon_df = ta.aroon(df["high"], df["low"], length=period)
        if aroon_df is not None:
            result[f"aroon_up_{period}"] = aroon_df.iloc[:, 0]
            result[f"aroon_down_{period}"] = aroon_df.iloc[:, 1]
            result[f"aroon_osc_{period}"] = aroon_df.iloc[:, 2]
    elif name == "CMO":
        period = int(params["period"])
        result[f"cmo_{period}"] = ta.cmo(df["close"], length=period)
    elif name == "TRIX":
        period = int(params["period"])
        trix_df = ta.trix(df["close"], length=period)
        if trix_df is not None:
            result[f"trix_{period}"] = trix_df.iloc[:, 0]
    elif name == "VolumeProfile":
        bins = int(params.get("bins", 50))
        lookback = int(params.get("lookback", 60))
        poc_col = f"vp_poc_{bins}_{lookback}"
        vah_col = f"vp_vah_{bins}_{lookback}"
        val_col = f"vp_val_{bins}_{lookback}"
        result[poc_col] = _rolling_volume_profile(
            df["close"], df["volume"], bins=bins, lookback=lookback, which="poc",
        )
        result[vah_col] = _rolling_volume_profile(
            df["close"], df["volume"], bins=bins, lookback=lookback, which="vah",
        )
        result[val_col] = _rolling_volume_profile(
            df["close"], df["volume"], bins=bins, lookback=lookback, which="val",
        )

    # ── Pattern indicators ──
    elif name == "BearishEngulfing":
        from core.features.patterns.candlestick import detect_bearish_engulfing
        pat = detect_bearish_engulfing(result)
        result["pattern_bearish_engulfing"] = pat["pattern_bearish_engulfing"]
    elif name == "EveningStar":
        from core.features.patterns.candlestick import detect_evening_star
        pat = detect_evening_star(result)
        result["pattern_evening_star"] = pat["pattern_evening_star"]
    elif name == "ThreeBlackCrows":
        from core.features.patterns.candlestick import detect_three_black_crows
        pat = detect_three_black_crows(result)
        result["pattern_3blackcrows"] = pat["pattern_3blackcrows"]
    elif name == "ShootingStar":
        from core.features.patterns.candlestick import detect_shooting_star
        pat = detect_shooting_star(result)
        result["pattern_shooting_star"] = pat["pattern_shooting_star"]
    elif name == "ThreeWhiteSoldiers":
        from core.features.patterns.candlestick import detect_three_white_soldiers
        pat = detect_three_white_soldiers(result)
        result["pattern_3whitesoldiers"] = pat["pattern_3whitesoldiers"]
    elif name == "MorningStar":
        from core.features.patterns.candlestick import detect_morning_star
        pat = detect_morning_star(result)
        result["pattern_morning_star"] = pat["pattern_morning_star"]
    elif name == "BullishReversal":
        from core.features.patterns.candlestick import detect_bullish_reversal
        pat = detect_bullish_reversal(result)
        result["pattern_bullish_reversal"] = pat["pattern_bullish_reversal"]
    elif name == "BearishReversal":
        from core.features.patterns.candlestick import detect_bearish_reversal
        pat = detect_bearish_reversal(result)
        result["pattern_bearish_reversal"] = pat["pattern_bearish_reversal"]
    elif name == "BullishDivergence":
        from core.features.patterns.divergence import detect_bullish_divergence
        pat = detect_bullish_divergence(result)
        result["pattern_bullish_divergence"] = pat["pattern_bullish_divergence"]
    elif name == "BearishDivergence":
        from core.features.patterns.divergence import detect_bearish_divergence
        pat = detect_bearish_divergence(result)
        result["pattern_bearish_divergence"] = pat["pattern_bearish_divergence"]

    return result


def _rolling_volume_profile(
    close: pd.Series,
    volume: pd.Series,
    bins: int = 50,
    lookback: int = 60,
    which: str = "poc",
) -> pd.Series:
    """Compute rolling volume profile and return POC/VAH/VAL series.

    Args:
        close: Close price series.
        volume: Volume series.
        bins: Number of price bins for histogram.
        lookback: Rolling window size.
        which: "poc" (point of control), "vah" (value area high), "val" (value area low).

    Returns:
        Series of the requested level values, same index as input.
    """
    close_vals = close.values
    volume_vals = volume.values
    n = len(close_vals)

    result = np.full(n, np.nan)

    for i in range(lookback - 1, n):
        window_close = close_vals[i - lookback + 1 : i + 1]
        window_vol = volume_vals[i - lookback + 1 : i + 1]

        if len(window_close) < 5:
            continue

        c_min = np.nanmin(window_close)
        c_max = np.nanmax(window_close)
        if c_max == c_min:
            result[i] = c_min
            continue

        # Build histogram
        edges = np.linspace(c_min, c_max, bins + 1)
        indices = np.digitize(window_close, edges) - 1
        indices = np.clip(indices, 0, bins - 1)
        vol_by_bin = np.zeros(bins)
        for j in range(len(indices)):
            vol_by_bin[indices[j]] += window_vol[j]

        total_vol = vol_by_bin.sum()
        if total_vol == 0:
            continue

        poc_idx = int(np.argmax(vol_by_bin))
        poc_price = (edges[poc_idx] + edges[poc_idx + 1]) / 2

        if which == "poc":
            result[i] = poc_price
        else:
            # Value area: bins containing 70% of volume around POC
            sorted_indices = np.argsort(vol_by_bin)[::-1]
            cumulative = 0.0
            va_bins = set()
            for idx in sorted_indices:
                va_bins.add(idx)
                cumulative += vol_by_bin[idx]
                if cumulative >= total_vol * 0.7:
                    break
            va_prices = [(edges[b], edges[b + 1]) for b in va_bins]
            if which == "vah":
                result[i] = max(h[1] for h in va_prices)
            elif which == "val":
                result[i] = min(h[0] for h in va_prices)

    return pd.Series(result, index=close.index)


def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Pre-compute all default indicators and append as columns.

    Args:
        df: OHLCV DataFrame with columns: open, high, low, close, volume
            and DatetimeIndex.

    Returns:
        Enhanced DataFrame with indicator columns appended.
    """
    result = df.copy()

    for name, param_sets in _DEFAULT_PARAMS.items():
        for params in param_sets:
            try:
                indicator_cols = _compute_indicator(result, name, params)
                # Only add new columns (not duplicate OHLCV)
                for col in indicator_cols.columns:
                    if col not in result.columns:
                        result[col] = indicator_cols[col]
            except Exception:
                # Skip indicators that fail on given data
                continue

    return result
