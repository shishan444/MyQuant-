"""vectorbt backtest engine wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import pandas as pd
import vectorbt as vbt

from core.strategy.dna import StrategyDNA
from core.strategy.executor import dna_to_signals


@dataclass
class BacktestResult:
    """Structured result from a backtest run."""
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    equity_curve: pd.Series
    trades_df: pd.DataFrame | None = None


class BacktestEngine:
    """Wraps vectorbt Portfolio.from_signals() with configured fees and slippage."""

    def __init__(self, init_cash: float = 100000, fee: float = 0.001,
                 slippage: float = 0.0005):
        self.init_cash = init_cash
        self.fee = fee
        self.slippage = slippage

    def run(self, dna: StrategyDNA, enhanced_df: pd.DataFrame) -> BacktestResult:
        """Run backtest for a single strategy DNA.

        Args:
            dna: Strategy genome.
            enhanced_df: DataFrame with OHLCV + indicator columns.

        Returns:
            BacktestResult with key metrics.
        """
        entries, exits = dna_to_signals(dna, enhanced_df)

        close = enhanced_df["close"]
        open_ = enhanced_df["open"]
        high = enhanced_df["high"]
        low = enhanced_df["low"]

        portfolio = vbt.Portfolio.from_signals(
            close=close,
            entries=entries,
            exits=exits,
            open=open_,
            high=high,
            low=low,
            init_cash=self.init_cash,
            fees=self.fee,
            slippage=self.slippage,
            sl_stop=dna.risk_genes.stop_loss,
        )

        # Extract equity curve (value() is a method in vectorbt 0.28)
        equity_curve = portfolio.value()
        if isinstance(equity_curve, pd.DataFrame):
            equity_curve = equity_curve.iloc[:, 0]

        total_return = float(portfolio.total_return())
        if pd.isna(total_return):
            total_return = 0.0

        total_trades_val = portfolio.trades.count()
        if isinstance(total_trades_val, pd.Series):
            total_trades_val = int(total_trades_val.sum())
        total_trades_val = int(total_trades_val) if not pd.isna(total_trades_val) else 0

        # Compute metrics directly
        sharpe = 0.0
        max_dd = 0.0
        win_rate = 0.0

        if total_trades_val > 0:
            try:
                stats = portfolio.stats()
                sharpe = stats.get("Sharpe Ratio", 0.0)
                if pd.isna(sharpe) or sharpe is None:
                    sharpe = 0.0

                max_dd_val = stats.get("Max Drawdown [%]", 0.0)
                if pd.isna(max_dd_val) or max_dd_val is None:
                    max_dd_val = 0.0
                max_dd = -abs(float(max_dd_val)) / 100

                wr_val = stats.get("Win Rate [%]", 0.0)
                if pd.isna(wr_val) or wr_val is None:
                    wr_val = 0.0
                win_rate = float(wr_val) / 100
            except Exception:
                pass

        # Extract trades
        trades = portfolio.trades.records_readable if hasattr(portfolio.trades, "records_readable") else None

        return BacktestResult(
            total_return=total_return,
            sharpe_ratio=float(sharpe),
            max_drawdown=float(max_dd),
            win_rate=float(win_rate),
            total_trades=total_trades_val,
            equity_curve=equity_curve,
            trades_df=trades,
        )

    def run_with_portfolio(
        self, dna: StrategyDNA, enhanced_df: pd.DataFrame,
    ) -> Tuple["BacktestResult", object]:
        """Run backtest and return (BacktestResult, vectorbt Portfolio) tuple.

        The Portfolio object exposes .plot() for quick visualization.
        """
        entries, exits = dna_to_signals(dna, enhanced_df)

        close = enhanced_df["close"]
        open_ = enhanced_df["open"]
        high = enhanced_df["high"]
        low = enhanced_df["low"]

        portfolio = vbt.Portfolio.from_signals(
            close=close,
            entries=entries,
            exits=exits,
            open=open_,
            high=high,
            low=low,
            init_cash=self.init_cash,
            fees=self.fee,
            slippage=self.slippage,
            sl_stop=dna.risk_genes.stop_loss,
        )

        result = self.run(dna, enhanced_df)
        return result, portfolio
