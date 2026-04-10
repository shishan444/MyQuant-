"""Metrics display component for Streamlit."""

from __future__ import annotations

from typing import Dict, Optional

import streamlit as st

from MyQuant.core.backtest.engine import BacktestResult


def render_metrics_card(
    result: BacktestResult,
    score_detail: Optional[Dict] = None,
) -> None:
    """Render key backtest metrics as a card.

    Args:
        result: BacktestResult with performance data.
        score_detail: Optional scoring detail dict from score_strategy().
    """
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Return", f"{result.total_return:.2%}")
    with col2:
        st.metric("Sharpe Ratio", f"{result.sharpe_ratio:.2f}")
    with col3:
        st.metric("Max Drawdown", f"{result.max_drawdown:.2%}")
    with col4:
        st.metric("Win Rate", f"{result.win_rate:.1%}")

    col5, col6, col7 = st.columns(3)
    with col5:
        st.metric("Total Trades", f"{result.total_trades}")
    with col6:
        if score_detail:
            st.metric("Total Score", f"{score_detail.get('total_score', 0):.1f}")
        else:
            st.metric("Total Score", "N/A")
    with col7:
        if score_detail:
            template_name = score_detail.get("template_name", "N/A")
            st.metric("Template", template_name)
        else:
            st.metric("Template", "N/A")

    if score_detail and score_detail.get("dimension_scores"):
        render_score_breakdown(score_detail)


def render_score_breakdown(score_detail: Dict) -> None:
    """Render dimension score breakdown in an expander."""
    dimensions = score_detail.get("dimension_scores", {})
    if not dimensions:
        return

    with st.expander("Score Breakdown", expanded=False):
        cols = st.columns(len(dimensions))
        for i, (dim, score) in enumerate(dimensions.items()):
            with cols[i]:
                label = dim.replace("_", " ").title()
                st.metric(label, f"{score:.1f}")
