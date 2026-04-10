"""Equity curve chart: strategy vs benchmark."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def build_equity_curve(
    strategy_equity: pd.Series,
    benchmark_close: pd.Series,
    title: str = "Equity Curve",
) -> go.Figure:
    """Build equity curve chart comparing strategy vs buy-and-hold benchmark.

    Both series are normalized to start at the same value for fair comparison.

    Args:
        strategy_equity: Series of portfolio equity values over time.
        benchmark_close: Close price series used as buy-and-hold benchmark.
        title: Chart title.

    Returns:
        Plotly Figure with two traces: strategy (solid blue) and benchmark (dashed gray).
    """
    # Align indices
    common_idx = strategy_equity.index.intersection(benchmark_close.index)
    equity = strategy_equity.reindex(common_idx).dropna()
    benchmark = benchmark_close.reindex(common_idx).dropna()

    if len(equity) == 0 or len(benchmark) == 0:
        fig = go.Figure()
        fig.update_layout(title=title, template="plotly_dark")
        fig.add_annotation(text="No data available", showarrow=False)
        return fig

    # Normalize benchmark to start at same equity level
    normalized_benchmark = (benchmark / benchmark.iloc[0]) * equity.iloc[0]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=equity.index,
        y=equity.values,
        mode="lines",
        line=dict(width=2, color="#00bfff"),
        name="Strategy",
    ))

    fig.add_trace(go.Scatter(
        x=normalized_benchmark.index,
        y=normalized_benchmark.values,
        mode="lines",
        line=dict(width=1.5, color="#888888", dash="dash"),
        name="Buy & Hold",
    ))

    fig.update_layout(
        title=title,
        template="plotly_dark",
        height=400,
        xaxis_title="Date",
        yaxis_title="Equity",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return fig
