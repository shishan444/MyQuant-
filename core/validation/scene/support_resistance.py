"""Support/resistance detector: price touches computed support or resistance levels."""
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .base import SceneDetector, TriggerPoint
from .top_pattern import _extract_snapshot


class SupportResistanceDetector(SceneDetector):

    @property
    def name(self) -> str:
        return "support_resistance"

    @property
    def default_params(self) -> Dict[str, Any]:
        return {
            "level_source": "bb",
            "direction": "support",
            "proximity_pct": 1.0,
            "min_spacing": 10,
        }

    def detect(self, df: pd.DataFrame, params: Dict[str, Any]) -> List[TriggerPoint]:
        p = {**self.default_params, **params}
        level_source = str(p["level_source"])
        direction = str(p["direction"])
        proximity = float(p["proximity_pct"])
        min_spacing = int(p["min_spacing"])

        # Resolve level columns
        level_col = _resolve_sr_column(level_source, direction, df.columns)
        if level_col is None:
            return []
        level_vals = df[level_col].values

        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values

        triggers: List[TriggerPoint] = []
        last_bar = -min_spacing - 1

        for i in range(1, len(df)):
            if np.isnan(level_vals[i]):
                continue

            touched = False
            if direction in ("support", "both"):
                # Price low touches or dips below support, then proximity check
                proximity_dist = abs(lows[i] - level_vals[i]) / level_vals[i] * 100
                if proximity_dist <= proximity:
                    touched = True

            if direction == "resistance" and not touched:
                proximity_dist = abs(highs[i] - level_vals[i]) / level_vals[i] * 100
                if proximity_dist <= proximity:
                    touched = True

            if not touched:
                continue
            if i - last_bar < min_spacing:
                continue

            trigger_row = df.iloc[i]
            snapshot = _extract_snapshot(trigger_row)
            snapshot["level_value"] = round(float(level_vals[i]), 4)
            snapshot["proximity_pct"] = round(proximity_dist, 2) if touched else 0

            triggers.append(TriggerPoint(
                id=len(triggers) + 1,
                timestamp=str(df.index[i]),
                trigger_price=float(closes[i]),
                bar_index=i,
                indicator_snapshot=snapshot,
            ))
            last_bar = i

        return triggers


def _resolve_sr_column(
    source: str, direction: str, columns: pd.Index,
) -> str | None:
    """Find the indicator column for a support/resistance level."""
    direction_map = {
        "support": ["lower", "l", "support"],
        "resistance": ["upper", "u", "resistance"],
    }
    dir_keywords = direction_map.get(direction, ["lower", "upper"])

    source_map = {
        "bb": ["bb_", "bbu_", "bbl_"],
        "dc": ["dc_", "donchian_"],
        "keltner": ["keltner_", "kc_"],
    }
    src_prefixes = source_map.get(source, [source])

    for col in columns:
        has_src = any(col.startswith(p) or p in col for p in src_prefixes)
        has_dir = any(k in col.lower() for k in dir_keywords)
        if has_src and has_dir:
            return col

    return None
