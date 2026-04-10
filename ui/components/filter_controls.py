"""Sidebar filter controls component for Streamlit."""

from __future__ import annotations

from typing import Dict, Any

import streamlit as st
import yaml
from pathlib import Path


def render_sidebar_controls() -> Dict[str, Any]:
    """Render sidebar controls for symbol, timeframe, and scoring template.

    Reads defaults from config.yaml and stores selections in session_state.

    Returns:
        Dict with selected symbol, timeframe, template values.
    """
    config = _load_config()

    data_config = config.get("data", {})
    symbols = data_config.get("symbols", ["BTCUSDT", "ETHUSDT"])
    timeframes = data_config.get("timeframes", ["1h", "4h", "1d"])

    templates = ["profit_first", "robust", "risk_aware", "custom"]

    st.sidebar.header("Settings")

    symbol = st.sidebar.selectbox(
        "Symbol",
        options=symbols,
        index=0,
        key="selected_symbol",
    )

    timeframe = st.sidebar.selectbox(
        "Timeframe",
        options=timeframes,
        index=timeframes.index("4h") if "4h" in timeframes else 0,
        key="selected_timeframe",
    )

    template = st.sidebar.selectbox(
        "Scoring Template",
        options=templates,
        index=0,
        key="selected_template",
    )

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "template": template,
    }


def _load_config() -> dict:
    """Load config.yaml from the project root."""
    config_path = Path(__file__).resolve().parents[2] / "config.yaml"
    if config_path.exists():
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}
