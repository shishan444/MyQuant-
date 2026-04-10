"""Quick preview chart wrapping vectorbt Portfolio.plot()."""

from __future__ import annotations

import plotly.graph_objects as go


def build_quick_preview(portfolio) -> go.Figure:
    """Build a quick preview chart from a vectorbt Portfolio object.

    Falls back to a placeholder figure if the portfolio has no trades.

    Args:
        portfolio: vectorbt Portfolio object.

    Returns:
        Plotly Figure.
    """
    try:
        trades_count = portfolio.trades.count()
        if isinstance(trades_count, int) and trades_count == 0:
            return _empty_figure("No trades in this strategy")

        fig = portfolio.plot(show=False)
        if fig is None:
            return _empty_figure("Portfolio plot unavailable")
        fig.update_layout(
            template="plotly_dark",
            height=500,
            title="Quick Preview",
        )
        return fig
    except Exception:
        return _empty_figure("Unable to generate preview")


def _empty_figure(message: str) -> go.Figure:
    """Create a placeholder figure with a text message."""
    fig = go.Figure()
    fig.update_layout(
        template="plotly_dark",
        height=400,
        annotations=[dict(text=message, showarrow=False, font=dict(size=16))],
    )
    return fig
