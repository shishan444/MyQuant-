"""Walk-Forward validation to prevent overfitting.

Slides a training window over historical data and evaluates strategy
on randomly selected out-of-sample months. All strategies in the
same generation share the same validation months for fairness.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from core.strategy.dna import StrategyDNA
from core.backtest.engine import BacktestEngine, BacktestResult
from core.scoring.metrics import compute_metrics
from core.scoring.scorer import score_strategy


@dataclass
class WFRound:
    """Result of a single Walk-Forward round."""
    round_num: int
    train_start: str
    train_end: str
    val_month: str
    train_score: float
    val_score: float
    combined_score: float


class WalkForwardValidator:
    """Walk-Forward cross-validator for trading strategies.

    Args:
        train_months: Training window size in months.
        slide_months: Slide step in months.
        train_weight: Weight for training score (default 0.4).
        val_weight: Weight for validation score (default 0.6).
    """

    def __init__(
        self,
        train_months: int = 3,
        slide_months: int = 1,
        train_weight: float = 0.4,
        val_weight: float = 0.6,
        template_name: str = "profit_first",
    ):
        self.train_months = train_months
        self.slide_months = slide_months
        self.train_weight = train_weight
        self.val_weight = val_weight
        self.template_name = template_name

    def validate(
        self,
        dna: StrategyDNA,
        enhanced_df: pd.DataFrame,
        val_months: Optional[List[str]] = None,
    ) -> Dict:
        """Run Walk-Forward validation on a strategy.

        Args:
            dna: Strategy to validate.
            enhanced_df: DataFrame with OHLCV + indicator columns.
            val_months: Pre-generated validation months (for shared validation).
                        If None, generates random months.

        Returns:
            Dict with wf_score, n_rounds, rounds (list of WFRound details).
        """
        engine = BacktestEngine()

        # Convert index to monthly periods
        df_index = enhanced_df.index
        if not isinstance(df_index, pd.DatetimeIndex):
            return {"wf_score": 0.0, "n_rounds": 0, "rounds": []}

        # Get date range
        start_date = df_index.min()
        end_date = df_index.max()

        # Generate month boundaries
        month_starts = pd.date_range(start=start_date, end=end_date, freq="MS")
        if len(month_starts) < self.train_months + 1:
            # Not enough data for WF
            return {"wf_score": 0.0, "n_rounds": 0, "rounds": []}

        # Generate training windows
        rounds: List[Dict] = []
        n_rounds = len(month_starts) - self.train_months

        for i in range(0, n_rounds, self.slide_months):
            if i + self.train_months >= len(month_starts):
                break

            train_start = month_starts[i]
            train_end = month_starts[i + self.train_months]

            # Select validation month (outside training window)
            # Available months: those not in training window
            all_months = list(range(len(month_starts)))
            train_month_indices = set(range(i, i + self.train_months))
            available = [m for m in all_months if m not in train_month_indices]

            if not available:
                continue

            if val_months is not None and i < len(val_months):
                val_month_str = val_months[i]
                val_month_ts = pd.Timestamp(val_month_str)
                # Find matching month_start
                val_idx = None
                for m_idx in available:
                    if month_starts[m_idx].year == val_month_ts.year and \
                       month_starts[m_idx].month == val_month_ts.month:
                        val_idx = m_idx
                        break
                if val_idx is None:
                    val_idx = random.choice(available)
            else:
                val_idx = random.choice(available)

            val_start = month_starts[val_idx]
            val_end = val_start + pd.DateOffset(months=1)

            # Get train data
            train_mask = (df_index >= train_start) & (df_index < train_end)
            train_df = enhanced_df[train_mask]

            # Get val data
            val_mask = (df_index >= val_start) & (df_index < val_end)
            val_df = enhanced_df[val_mask]

            if len(train_df) < 20 or len(val_df) < 5:
                continue

            # Run backtests
            train_result = engine.run(dna, train_df)
            val_result = engine.run(dna, val_df)

            # Compute scores
            train_metrics = compute_metrics(train_result.equity_curve,
                                            train_result.total_trades)
            val_metrics = compute_metrics(val_result.equity_curve,
                                          val_result.total_trades)

            train_score = score_strategy(train_metrics, self.template_name)["total_score"]
            val_score = score_strategy(val_metrics, self.template_name)["total_score"]

            combined = train_score * self.train_weight + val_score * self.val_weight

            rounds.append({
                "round_num": len(rounds),
                "train_start": str(train_start.date()),
                "train_end": str(train_end.date()),
                "val_month": str(val_start.date()),
                "train_score": train_score,
                "val_score": val_score,
                "combined_score": combined,
            })

        if not rounds:
            return {"wf_score": 0.0, "n_rounds": 0, "rounds": []}

        # WF score = average of combined scores
        wf_score = np.mean([r["combined_score"] for r in rounds])

        return {
            "wf_score": round(float(wf_score), 2),
            "n_rounds": len(rounds),
            "rounds": rounds,
        }
