"""Chart builder: orchestrates DNA -> signals -> backtest -> multiple charts."""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go

from core.backtest.engine import BacktestEngine, BacktestResult
from core.strategy.dna import StrategyDNA
from core.strategy.executor import dna_to_signals
from core.visualization.kline_chart import build_kline_chart
from core.visualization.equity_curve import build_equity_curve
from core.visualization.generation_chart import build_generation_chart
from core.visualization.quick_preview import build_quick_preview


def build_champion_report(
    dna: StrategyDNA,
    enhanced_df: pd.DataFrame,
    backtest_result: Optional[BacktestResult] = None,
    engine: Optional[BacktestEngine] = None,
) -> Dict[str, go.Figure]:
    """Build all charts for a champion strategy.

    Pipeline: DNA -> signals -> (optional backtest) -> kline + equity + preview.

    Args:
        dna: Champion strategy DNA.
        enhanced_df: DataFrame with OHLCV + indicators.
        backtest_result: Optional pre-computed result. If None, runs backtest.
        engine: Optional BacktestEngine. Uses default if not provided.

    Returns:
        Dict with keys: "kline", "equity", "quick_preview".
    """
    if engine is None:
        engine = BacktestEngine()

    # Generate signals
    entries, exits = dna_to_signals(dna, enhanced_df)

    # Run backtest if result not provided
    if backtest_result is None:
        backtest_result, portfolio = engine.run_with_portfolio(dna, enhanced_df)
    else:
        _, portfolio = engine.run_with_portfolio(dna, enhanced_df)

    # Detect indicator columns to overlay (exclude OHLCV and RSI)
    base_cols = {"open", "high", "low", "close", "volume"}
    indicator_cols = [
        c for c in enhanced_df.columns
        if c not in base_cols and not c.startswith("rsi_")
    ]
    # Only include trend/volatility overlays (not all indicators)
    overlay_cols = _select_overlay_indicators(dna, indicator_cols)

    kline_fig = build_kline_chart(
        ohlcv_df=enhanced_df,
        entries=entries,
        exits=exits,
        indicator_columns=overlay_cols,
        title=f"{dna.execution_genes.symbol} {dna.execution_genes.timeframe} - Champion",
    )

    equity_fig = build_equity_curve(
        strategy_equity=backtest_result.equity_curve,
        benchmark_close=enhanced_df["close"],
        title="Equity Curve",
    )

    preview_fig = build_quick_preview(portfolio)

    return {
        "kline": kline_fig,
        "equity": equity_fig,
        "quick_preview": preview_fig,
    }


def build_evolution_dashboard(
    history: List[Dict],
    target_score: float,
    title: str = "Evolution Dashboard",
) -> Dict[str, go.Figure]:
    """Build charts for the evolution monitoring dashboard.

    Args:
        history: List of generation records with best_score/avg_score.
        target_score: Target score for the target line.
        title: Dashboard title.

    Returns:
        Dict with key: "generation".
    """
    generation_fig = build_generation_chart(
        history=history,
        target_score=target_score,
        title=title,
    )

    return {
        "generation": generation_fig,
    }


def _select_overlay_indicators(
    dna: StrategyDNA,
    available_cols: List[str],
) -> List[str]:
    """Select indicator columns that are relevant to the DNA for overlay.

    Only picks columns matching indicators used in signal_genes.
    """
    overlay = []
    for gene in dna.signal_genes:
        indicator = gene.indicator
        params = gene.params

        # Build expected column prefixes based on indicator
        prefixes = []
        if indicator in ("EMA", "SMA", "WMA", "DEMA", "TEMA"):
            prefix = f"{indicator.lower()}_{params.get('period', '')}"
            prefixes.append(prefix)
        elif indicator == "BB":
            period = params.get("period", 20)
            std = params.get("std", 2.0)
            std_str = str(std).replace(".0", "")
            prefixes.append(f"bb_lower_{period}_{std_str}")
            prefixes.append(f"bb_upper_{period}_{std_str}")
            prefixes.append(f"bb_middle_{period}_{std_str}")

        for col in available_cols:
            for prefix in prefixes:
                if col.startswith(prefix) and col not in overlay:
                    overlay.append(col)

    return overlay[:5]  # Limit overlays to avoid clutter
