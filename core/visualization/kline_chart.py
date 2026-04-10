"""K-line (candlestick) chart with buy/sell markers and optional indicator overlays."""

from __future__ import annotations

from typing import List, Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def build_kline_chart(
    ohlcv_df: pd.DataFrame,
    entries: pd.Series,
    exits: pd.Series,
    indicator_columns: Optional[List[str]] = None,
    title: str = "BTC/USDT 4H",
) -> go.Figure:
    """Build a candlestick chart with buy/sell markers and indicator overlays.

    Layout:
      - Top subplot (70%): Candlestick + buy/sell markers + indicator lines
      - Bottom subplot (30%): RSI with 30/70 levels (if available), else hidden

    Args:
        ohlcv_df: DataFrame with open/high/low/close/volume + indicator columns.
        entries: Boolean Series marking buy signals.
        exits: Boolean Series marking sell signals.
        indicator_columns: Optional list of indicator column names to overlay on price chart.
        title: Chart title.

    Returns:
        Plotly Figure object.
    """
    has_rsi = _find_rsi_column(ohlcv_df) is not None
    row_heights = [0.7, 0.3] if has_rsi else [1.0]
    n_rows = 2 if has_rsi else 1

    fig = make_subplots(
        rows=n_rows,
        cols=1,
        shared_xaxes=True,
        row_heights=row_heights,
        vertical_spacing=0.03,
    )

    # --- Candlestick ---
    fig.add_trace(
        go.Candlestick(
            x=ohlcv_df.index,
            open=ohlcv_df["open"],
            high=ohlcv_df["high"],
            low=ohlcv_df["low"],
            close=ohlcv_df["close"],
            name="K",
            showlegend=False,
        ),
        row=1,
        col=1,
    )

    # --- Buy markers ---
    buy_mask = entries.reindex(ohlcv_df.index).fillna(False)
    buy_df = ohlcv_df.loc[buy_mask]
    if not buy_df.empty:
        fig.add_trace(
            go.Scatter(
                x=buy_df.index,
                y=buy_df["low"] * 0.998,
                mode="markers",
                marker=dict(symbol="triangle-up", size=12, color="#00cc44"),
                name="Buy",
                hovertemplate="Buy<br>Price: %{y:.2f}<extra></extra>",
            ),
            row=1,
            col=1,
        )

    # --- Sell markers ---
    sell_mask = exits.reindex(ohlcv_df.index).fillna(False)
    sell_df = ohlcv_df.loc[sell_mask]
    if not sell_df.empty:
        fig.add_trace(
            go.Scatter(
                x=sell_df.index,
                y=sell_df["high"] * 1.002,
                mode="markers",
                marker=dict(symbol="triangle-down", size=12, color="#ff3333"),
                name="Sell",
                hovertemplate="Sell<br>Price: %{y:.2f}<extra></extra>",
            ),
            row=1,
            col=1,
        )

    # --- Indicator overlays ---
    if indicator_columns:
        for col_name in indicator_columns:
            if col_name in ohlcv_df.columns:
                series = ohlcv_df[col_name].dropna()
                fig.add_trace(
                    go.Scatter(
                        x=series.index,
                        y=series.values,
                        mode="lines",
                        line=dict(width=1.2),
                        name=col_name,
                        opacity=0.8,
                    ),
                    row=1,
                    col=1,
                )

    # --- RSI subplot ---
    if has_rsi:
        rsi_col = _find_rsi_column(ohlcv_df)
        rsi_series = ohlcv_df[rsi_col].dropna()
        fig.add_trace(
            go.Scatter(
                x=rsi_series.index,
                y=rsi_series.values,
                mode="lines",
                line=dict(width=1.2, color="#7b68ee"),
                name="RSI",
            ),
            row=2,
            col=1,
        )
        # 30/70 levels
        fig.add_hline(y=30, line_dash="dash", line_color="gray", row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="gray", row=2, col=1)
        fig.update_yaxes(title_text="RSI", row=2, col=1, range=[0, 100])

    # --- Layout ---
    fig.update_layout(
        title=title,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        height=700,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_yaxes(title_text="Price", row=1, col=1)

    return fig


def _find_rsi_column(df: pd.DataFrame) -> Optional[str]:
    """Find the first RSI column in the DataFrame."""
    for col in df.columns:
        if col.startswith("rsi_"):
            return col
    return None
