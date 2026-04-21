"""vectorbt backtest engine wrapper."""

from __future__ import annotations

import math
import numpy as np
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import pandas as pd
import vectorbt as vbt

from core.strategy.dna import StrategyDNA
from core.strategy.executor import dna_to_signals, dna_to_signal_set


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
    total_funding_cost: float = 0.0
    liquidated: bool = False
    data_bars: int = 0
    trade_win_rate: float | None = None
    trade_returns: np.ndarray | None = None
    bars_per_year: int = 2190
    add_count: int = 0
    reduce_count: int = 0
    metrics_dict: dict | None = None


def _apply_funding_costs(
    equity_curve: pd.Series, leverage: int, timeframe: str,
) -> tuple[pd.Series, float]:
    """Deduct leveraged funding costs; return adjusted curve and total cost."""
    if leverage <= 1:
        return equity_curve, 0.0

    RATE_PER_8H = 0.001
    hours_per_bar = {
        "1m": 1/60, "5m": 5/60, "15m": 0.25, "30m": 0.5,
        "1h": 1, "4h": 4, "1d": 24, "3d": 72,
    }[timeframe]
    periods_per_bar = math.ceil(hours_per_bar / 8)
    borrowed_ratio = (leverage - 1) / leverage
    cost_rate = RATE_PER_8H * periods_per_bar * borrowed_ratio

    # Use numpy array for fast element-wise access (avoids pandas iloc overhead)
    adjusted = equity_curve.values.astype(np.float64).copy()
    total_cost = 0.0
    for i in range(1, len(adjusted)):
        cost = adjusted[i - 1] * cost_rate
        total_cost += cost
        adjusted[i] -= cost
    return pd.Series(adjusted, index=equity_curve.index), total_cost


def _check_liquidation(
    equity_curve: pd.Series, leverage: int, init_cash: float,
) -> bool:
    """Force-liquidate when margin loss exceeds 90% of effective capital."""
    if leverage <= 1:
        return False
    maintenance = init_cash * (1 - 0.9 / leverage)
    liquidated = equity_curve < maintenance
    if liquidated.any():
        idx = liquidated.idxmax()
        equity_curve.loc[idx:] = 0
        return True
    return False


class BacktestEngine:
    """Wraps vectorbt Portfolio.from_signals() with configured fees and slippage."""

    def __init__(self, init_cash: float = 100000, fee: float = 0.001,
                 slippage: float = 0.0005):
        self.init_cash = init_cash
        self.fee = fee
        self.slippage = slippage

    def _build_portfolio(
        self,
        dna: StrategyDNA,
        enhanced_df: pd.DataFrame,
        dfs_by_timeframe: Optional[Dict[str, pd.DataFrame]] = None,
        signal_set=None,
    ):
        """Construct a vectorbt Portfolio from DNA signals.

        Uses SignalSet for add/reduce support.
        """
        if signal_set is not None:
            sig_set = signal_set
        else:
            sig_set = dna_to_signal_set(dna, enhanced_df, dfs_by_timeframe=dfs_by_timeframe)

        entries = sig_set.entries
        exits = sig_set.exits
        adds = sig_set.adds
        reduces = sig_set.reduces

        close = enhanced_df["close"]
        open_ = enhanced_df["open"]
        high = enhanced_df["high"]
        low = enhanced_df["low"]

        direction_map = {"long": 0, "short": 1}
        size = dna.risk_genes.position_size * dna.risk_genes.leverage

        # Combine entries and adds for vectorbt (accumulate=True for adds)
        # Use accumulate to allow multiple entries (adds)
        all_entries = entries | adds
        accumulate = bool(adds.any())

        # Reduce signals become additional exits
        all_exits = exits | reduces

        portfolio_kwargs = dict(
            close=close,
            entries=all_entries,
            exits=all_exits,
            open=open_,
            high=high,
            low=low,
            init_cash=self.init_cash,
            fees=self.fee,
            slippage=self.slippage,
            sl_stop=dna.risk_genes.stop_loss,
            tp_stop=dna.risk_genes.take_profit,
            size=size,
            size_type="percent",
            accumulate=accumulate,
            direction=direction_map.get(dna.risk_genes.direction, 0),
        )

        return vbt.Portfolio.from_signals(**portfolio_kwargs), int(adds.sum()), int(reduces.sum())

    def run(
        self,
        dna: StrategyDNA,
        enhanced_df: pd.DataFrame,
        dfs_by_timeframe: Optional[Dict[str, pd.DataFrame]] = None,
        signal_set=None,
    ) -> BacktestResult:
        """Run backtest for a single strategy DNA.

        Args:
            dna: Strategy genome.
            enhanced_df: DataFrame with OHLCV + indicator columns.
            dfs_by_timeframe: Optional dict of {timeframe: DataFrame} for MTF signals.
            signal_set: Optional precomputed SignalSet to avoid redundant signal computation.

        Returns:
            BacktestResult with key metrics computed from adjusted equity curve.
        """
        build_result = self._build_portfolio(dna, enhanced_df, dfs_by_timeframe=dfs_by_timeframe, signal_set=signal_set)
        if isinstance(build_result, tuple):
            portfolio, add_count, reduce_count = build_result
        else:
            portfolio = build_result
            add_count, reduce_count = 0, 0

        equity_curve = portfolio.value()
        if isinstance(equity_curve, pd.DataFrame):
            equity_curve = equity_curve.iloc[:, 0]

        # Funding costs for leveraged positions
        timeframe = dna.execution_genes.timeframe
        equity_curve, total_funding_cost = _apply_funding_costs(
            equity_curve, dna.risk_genes.leverage, timeframe,
        )

        # Liquidation check
        liquidated = _check_liquidation(
            equity_curve, dna.risk_genes.leverage, self.init_cash,
        )

        # Trade count from portfolio (vectorbt tracks this accurately)
        total_trades_val = portfolio.trades.count()
        if isinstance(total_trades_val, pd.Series):
            total_trades_val = int(total_trades_val.sum())
        total_trades_val = int(total_trades_val) if not pd.isna(total_trades_val) else 0

        # Compute ALL metrics using trade-level data where available
        from core.scoring.metrics import compute_metrics
        bars_per_year_map = {"15m": 365 * 96, "30m": 365 * 48, "1h": 365 * 24,
                             "4h": 365 * 6, "1d": 365, "3d": 365 // 3}
        bars_per_year = bars_per_year_map.get(timeframe, 365 * 6)

        # Extract trade-level data from vectorbt
        trade_win_rate = None
        trade_returns = None
        if total_trades_val > 0:
            try:
                trade_pnl = portfolio.trades.pnl
                if hasattr(trade_pnl, 'values'):
                    pnl_arr = np.array(trade_pnl.values).flatten()
                else:
                    pnl_arr = np.array(trade_pnl).flatten()

                if len(pnl_arr) > 0:
                    winning = int((pnl_arr > 0).sum())
                    trade_win_rate = winning / len(pnl_arr)
                    trade_returns = pnl_arr / self.init_cash
                    # Deduct funding costs from trade returns for consistency
                    # with post-funding equity_curve
                    if total_funding_cost > 0:
                        cost_per_trade = total_funding_cost / len(pnl_arr)
                        trade_returns = trade_returns - (cost_per_trade / self.init_cash)
            except Exception:
                pass

        metrics = compute_metrics(
            equity_curve, total_trades=total_trades_val,
            bars_per_year=bars_per_year,
            trade_win_rate=trade_win_rate,
            trade_returns=trade_returns,
        )

        sharpe = metrics["sharpe_ratio"]
        max_dd = metrics["max_drawdown"]
        win_rate = metrics["win_rate"]

        # Also compute raw total_return from adjusted curve for display
        if len(equity_curve) >= 2 and equity_curve.iloc[0] > 0:
            raw_return = float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1)
        else:
            raw_return = 0.0

        trades = portfolio.trades.records_readable if hasattr(portfolio.trades, "records_readable") else None

        return BacktestResult(
            total_return=raw_return,
            sharpe_ratio=float(sharpe),
            max_drawdown=float(max_dd),
            win_rate=float(win_rate),
            total_trades=total_trades_val,
            equity_curve=equity_curve,
            trades_df=trades,
            total_funding_cost=total_funding_cost,
            liquidated=liquidated,
            data_bars=len(enhanced_df),
            trade_win_rate=trade_win_rate,
            trade_returns=trade_returns,
            bars_per_year=bars_per_year,
            add_count=add_count,
            reduce_count=reduce_count,
            metrics_dict=metrics,
        )

    def run_with_portfolio(
        self,
        dna: StrategyDNA,
        enhanced_df: pd.DataFrame,
        dfs_by_timeframe: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> Tuple["BacktestResult", object]:
        """Run backtest and return (BacktestResult, vectorbt Portfolio) tuple.

        The Portfolio object exposes .plot() for quick visualization.
        """
        build_result = self._build_portfolio(dna, enhanced_df, dfs_by_timeframe=dfs_by_timeframe)
        if isinstance(build_result, tuple):
            portfolio = build_result[0]
        else:
            portfolio = build_result
        result = self.run(dna, enhanced_df, dfs_by_timeframe=dfs_by_timeframe)
        return result, portfolio
