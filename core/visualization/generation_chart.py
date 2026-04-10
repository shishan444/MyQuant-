"""Generation score chart for evolution monitoring."""

from __future__ import annotations

from typing import Dict, List, Optional

import plotly.graph_objects as go


def build_generation_chart(
    history: List[Dict],
    target_score: Optional[float] = None,
    title: str = "Evolution Progress",
) -> go.Figure:
    """Build a line chart showing best/avg scores per generation.

    Args:
        history: List of dicts with keys: generation, best_score, avg_score.
        target_score: Optional target score shown as horizontal line.
        title: Chart title.

    Returns:
        Plotly Figure with best_score (green), avg_score (orange), target (red dashed).
    """
    fig = go.Figure()

    if not history:
        fig.update_layout(
            title=title,
            template="plotly_dark",
            height=400,
            annotations=[dict(text="No evolution data yet", showarrow=False)],
        )
        return fig

    generations = [h["generation"] for h in history]
    best_scores = [h["best_score"] for h in history]
    avg_scores = [h["avg_score"] for h in history]

    fig.add_trace(go.Scatter(
        x=generations,
        y=best_scores,
        mode="lines+markers",
        line=dict(width=2, color="#00cc44"),
        marker=dict(size=4),
        name="Best Score",
    ))

    fig.add_trace(go.Scatter(
        x=generations,
        y=avg_scores,
        mode="lines+markers",
        line=dict(width=1.5, color="#ff8c00", dash="dash"),
        marker=dict(size=3),
        name="Avg Score",
    ))

    if target_score is not None:
        fig.add_hline(
            y=target_score,
            line_dash="dot",
            line_color="#ff4444",
            annotation_text=f"Target: {target_score}",
            annotation_position="top left",
        )

    fig.update_layout(
        title=title,
        template="plotly_dark",
        height=400,
        xaxis_title="Generation",
        yaxis_title="Score",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return fig
