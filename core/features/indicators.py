"""Indicator registry and computation engine.

Defines the 18 supported indicators across 5 categories, with typed parameter
ranges for use in strategy validation and mutation operators. Provides batch
computation via pandas-ta.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd
import pandas_ta as ta


# ---------------------------------------------------------------------------
# Registry data structures
# ---------------------------------------------------------------------------

@dataclass
class ParamDef:
    """Parameter definition with range constraints for mutation."""
    type: str          # "int" | "float"
    min: float
    max: float
    default: float
    step: float

    def clamp(self, value: float) -> float:
        """Clamp value to valid range, rounded to step boundary."""
        import math
        value = max(self.min, min(self.max, value))
        return round(value / self.step) * self.step


@dataclass
class IndicatorDef:
    """Definition of a single indicator in the registry."""
    category: str
    params: Dict[str, ParamDef]
    output_fields: List[str]
    supported_conditions: List[str]
    guard_only: bool = False


# ---------------------------------------------------------------------------
# Indicator Registry (18 indicators, 5 categories)
# ---------------------------------------------------------------------------

INDICATOR_REGISTRY: Dict[str, IndicatorDef] = {
    # ══════ trend (6) ══════
    "EMA": IndicatorDef(
        category="trend",
        params={"period": ParamDef("int", 5, 200, 50, 5)},
        output_fields=["ema"],
        supported_conditions=["price_above", "price_below", "cross_above", "cross_below"],
    ),
    "SMA": IndicatorDef(
        category="trend",
        params={"period": ParamDef("int", 5, 200, 50, 5)},
        output_fields=["sma"],
        supported_conditions=["price_above", "price_below", "cross_above", "cross_below"],
    ),
    "WMA": IndicatorDef(
        category="trend",
        params={"period": ParamDef("int", 5, 200, 50, 5)},
        output_fields=["wma"],
        supported_conditions=["price_above", "price_below", "cross_above", "cross_below"],
    ),
    "DEMA": IndicatorDef(
        category="trend",
        params={"period": ParamDef("int", 5, 200, 50, 5)},
        output_fields=["dema"],
        supported_conditions=["price_above", "price_below", "cross_above", "cross_below"],
    ),
    "TEMA": IndicatorDef(
        category="trend",
        params={"period": ParamDef("int", 5, 200, 50, 5)},
        output_fields=["tema"],
        supported_conditions=["price_above", "price_below", "cross_above", "cross_below"],
    ),
    "VWAP": IndicatorDef(
        category="trend",
        params={},
        output_fields=["vwap"],
        supported_conditions=["price_above", "price_below"],
    ),

    # ══════ momentum (6) ══════
    "RSI": IndicatorDef(
        category="momentum",
        params={"period": ParamDef("int", 2, 50, 14, 2)},
        output_fields=["rsi"],
        supported_conditions=["lt", "gt", "le", "ge"],
    ),
    "MACD": IndicatorDef(
        category="momentum",
        params={
            "fast": ParamDef("int", 5, 30, 12, 2),
            "slow": ParamDef("int", 20, 60, 26, 2),
            "signal": ParamDef("int", 5, 20, 9, 1),
        },
        output_fields=["macd", "signal", "histogram"],
        supported_conditions=["cross_above", "cross_below", "gt", "lt"],
    ),
    "Stochastic": IndicatorDef(
        category="momentum",
        params={
            "k_period": ParamDef("int", 5, 50, 14, 2),
            "d_period": ParamDef("int", 3, 20, 3, 1),
        },
        output_fields=["k", "d"],
        supported_conditions=["lt", "gt", "cross_above", "cross_below"],
    ),
    "CCI": IndicatorDef(
        category="momentum",
        params={"period": ParamDef("int", 5, 50, 20, 2)},
        output_fields=["cci"],
        supported_conditions=["lt", "gt"],
    ),
    "ROC": IndicatorDef(
        category="momentum",
        params={"period": ParamDef("int", 2, 50, 12, 2)},
        output_fields=["roc"],
        supported_conditions=["gt", "lt", "cross_above", "cross_below"],
    ),
    "Williams %R": IndicatorDef(
        category="momentum",
        params={"period": ParamDef("int", 2, 50, 14, 2)},
        output_fields=["willr"],
        supported_conditions=["lt", "gt"],
    ),

    # ══════ volatility (4) ══════
    "BB": IndicatorDef(
        category="volatility",
        params={
            "period": ParamDef("int", 5, 50, 20, 2),
            "std": ParamDef("float", 1.0, 3.0, 2.0, 0.5),
        },
        output_fields=["upper", "middle", "lower", "bandwidth", "percent"],
        supported_conditions=["price_above", "price_below"],
    ),
    "ATR": IndicatorDef(
        category="volatility",
        params={"period": ParamDef("int", 5, 50, 14, 2)},
        output_fields=["atr"],
        supported_conditions=["gt", "lt"],
        guard_only=True,
    ),
    "Keltner": IndicatorDef(
        category="volatility",
        params={
            "ema_period": ParamDef("int", 5, 50, 20, 2),
            "atr_period": ParamDef("int", 5, 50, 10, 2),
            "multiplier": ParamDef("float", 1.0, 3.0, 2.0, 0.5),
        },
        output_fields=["upper", "middle", "lower"],
        supported_conditions=["price_above", "price_below"],
    ),
    "Donchian": IndicatorDef(
        category="volatility",
        params={"period": ParamDef("int", 5, 50, 20, 2)},
        output_fields=["upper", "middle", "lower"],
        supported_conditions=["price_above", "price_below"],
    ),

    # ══════ volume (3) ══════
    "OBV": IndicatorDef(
        category="volume",
        params={},
        output_fields=["obv"],
        supported_conditions=["gt", "lt", "cross_above", "cross_below"],
    ),
    "CMF": IndicatorDef(
        category="volume",
        params={"period": ParamDef("int", 5, 30, 20, 2)},
        output_fields=["cmf"],
        supported_conditions=["gt", "lt"],
    ),
    "MFI": IndicatorDef(
        category="volume",
        params={"period": ParamDef("int", 5, 30, 14, 2)},
        output_fields=["mfi"],
        supported_conditions=["lt", "gt"],
    ),

    # ══════ trend_strength (2) ══════
    "ADX": IndicatorDef(
        category="trend_strength",
        params={"period": ParamDef("int", 7, 50, 14, 2)},
        output_fields=["adx"],
        supported_conditions=["gt", "lt"],
        guard_only=True,
    ),
    "PSAR": IndicatorDef(
        category="trend_strength",
        params={
            "step": ParamDef("float", 0.01, 0.05, 0.02, 0.01),
            "max_step": ParamDef("float", 0.1, 0.3, 0.2, 0.05),
        },
        output_fields=["psar"],
        supported_conditions=["price_above", "price_below"],
        guard_only=True,
    ),
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_interchangeable(indicator_name: str) -> List[str]:
    """Return indicators in the same category (excludes self)."""
    if indicator_name not in INDICATOR_REGISTRY:
        return []
    category = INDICATOR_REGISTRY[indicator_name].category
    return [
        name for name, defn in INDICATOR_REGISTRY.items()
        if defn.category == category and name != indicator_name
    ]


# ---------------------------------------------------------------------------
# Computation engine
# ---------------------------------------------------------------------------

# Default parameter sets for pre-computation
_DEFAULT_PARAMS: Dict[str, List[Dict[str, Any]]] = {
    "EMA": [{"period": p} for p in [10, 20, 50, 100, 200]],
    "SMA": [{"period": p} for p in [10, 20, 50, 100, 200]],
    "RSI": [{"period": p} for p in [7, 14, 21]],
    "MACD": [{"fast": 12, "slow": 26, "signal": 9}],
    "BB": [{"period": 20, "std": 2.0}],
    "ATR": [{"period": 14}],
    "ADX": [{"period": 14}],
}


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

    return result


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
