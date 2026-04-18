"""Indicator registry: data structures and indicator definitions.

Defines ParamDef, IndicatorDef, INDICATOR_REGISTRY, and get_interchangeable().
Extracted from indicators.py to keep file sizes within the 800-line limit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


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
# Indicator Registry (30 indicators, 6 categories)
# ---------------------------------------------------------------------------

INDICATOR_REGISTRY: Dict[str, IndicatorDef] = {
    # == trend (6) ==
    "EMA": IndicatorDef(
        category="trend",
        params={"period": ParamDef("int", 5, 200, 50, 5)},
        output_fields=["ema"],
        supported_conditions=["price_above", "price_below", "cross_above", "cross_below",
                              "cross_above_series", "cross_below_series"],
    ),
    "SMA": IndicatorDef(
        category="trend",
        params={"period": ParamDef("int", 5, 200, 50, 5)},
        output_fields=["sma"],
        supported_conditions=["price_above", "price_below", "cross_above", "cross_below",
                              "cross_above_series", "cross_below_series"],
    ),
    "WMA": IndicatorDef(
        category="trend",
        params={"period": ParamDef("int", 5, 200, 50, 5)},
        output_fields=["wma"],
        supported_conditions=["price_above", "price_below", "cross_above", "cross_below",
                              "cross_above_series", "cross_below_series"],
    ),
    "DEMA": IndicatorDef(
        category="trend",
        params={"period": ParamDef("int", 5, 200, 50, 5)},
        output_fields=["dema"],
        supported_conditions=["price_above", "price_below", "cross_above", "cross_below",
                              "cross_above_series", "cross_below_series"],
    ),
    "TEMA": IndicatorDef(
        category="trend",
        params={"period": ParamDef("int", 5, 200, 50, 5)},
        output_fields=["tema"],
        supported_conditions=["price_above", "price_below", "cross_above", "cross_below",
                              "cross_above_series", "cross_below_series"],
    ),
    "VWAP": IndicatorDef(
        category="trend",
        params={},
        output_fields=["vwap"],
        supported_conditions=["price_above", "price_below"],
    ),

    # == momentum (9) ==
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
    "Aroon": IndicatorDef(
        category="momentum",
        params={"period": ParamDef("int", 10, 50, 25, 5)},
        output_fields=["aroon_up", "aroon_down", "aroon_osc"],
        supported_conditions=["cross_above", "cross_below", "gt", "lt",
                              "cross_above_series", "cross_below_series"],
    ),
    "CMO": IndicatorDef(
        category="momentum",
        params={"period": ParamDef("int", 2, 50, 14, 2)},
        output_fields=["cmo"],
        supported_conditions=["gt", "lt", "cross_above", "cross_below"],
    ),
    "TRIX": IndicatorDef(
        category="momentum",
        params={"period": ParamDef("int", 5, 50, 12, 2)},
        output_fields=["trix"],
        supported_conditions=["gt", "lt", "cross_above", "cross_below"],
    ),

    # == volatility (4) ==
    "BB": IndicatorDef(
        category="volatility",
        params={
            "period": ParamDef("int", 5, 50, 20, 2),
            "std": ParamDef("float", 1.0, 3.0, 2.0, 0.5),
        },
        output_fields=["upper", "middle", "lower", "bandwidth", "percent"],
        supported_conditions=["price_above", "price_below", "lookback_any", "lookback_all",
                              "touch_bounce", "role_reversal", "wick_touch"],
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
        supported_conditions=["price_above", "price_below",
                              "touch_bounce", "role_reversal", "wick_touch"],
    ),
    "Donchian": IndicatorDef(
        category="volatility",
        params={"period": ParamDef("int", 5, 50, 20, 2)},
        output_fields=["upper", "middle", "lower"],
        supported_conditions=["price_above", "price_below",
                              "touch_bounce", "role_reversal", "wick_touch"],
    ),

    # == volume (8) ==
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
    "RVOL": IndicatorDef(
        category="volume",
        params={"period": ParamDef("int", 5, 100, 20, 5)},
        output_fields=["rvol"],
        supported_conditions=["gt", "lt", "lookback_any", "lookback_all"],
    ),
    "VROC": IndicatorDef(
        category="volume",
        params={"period": ParamDef("int", 5, 50, 14, 5)},
        output_fields=["vroc"],
        supported_conditions=["gt", "lt", "lookback_any", "lookback_all"],
    ),
    "AD": IndicatorDef(
        category="volume",
        params={},
        output_fields=["ad"],
        supported_conditions=["gt", "lt", "cross_above", "cross_below"],
    ),
    "CVD": IndicatorDef(
        category="volume",
        params={},
        output_fields=["cvd"],
        supported_conditions=["gt", "lt", "cross_above", "cross_below"],
    ),
    "VWMA": IndicatorDef(
        category="volume",
        params={"period": ParamDef("int", 5, 200, 20, 5)},
        output_fields=["vwma"],
        supported_conditions=["price_above", "price_below", "cross_above", "cross_below",
                              "cross_above_series", "cross_below_series"],
    ),

    # == trend_strength (2) ==
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

    # == structure (1) ==
    "VolumeProfile": IndicatorDef(
        category="structure",
        params={
            "bins": ParamDef("int", 20, 100, 50, 10),
            "lookback": ParamDef("int", 20, 200, 60, 20),
        },
        output_fields=["vp_poc", "vp_vah", "vp_val"],
        supported_conditions=["touch_bounce", "role_reversal"],
        guard_only=True,
    ),
}


def get_interchangeable(indicator_name: str) -> List[str]:
    """Return indicators in the same category (excludes self)."""
    if indicator_name not in INDICATOR_REGISTRY:
        return []
    category = INDICATOR_REGISTRY[indicator_name].category
    return [
        name for name, defn in INDICATOR_REGISTRY.items()
        if defn.category == category and name != indicator_name
    ]
