# B5: 回测引擎

## 定位

`core/backtest/` 是"裁判"——用历史数据验证策略可行性和收益。封装 vectorbt `Portfolio.from_order_func()`，支持双向交易、杠杆资金费率扣除、爆仓检查，以及市场基准收益计算（Alpha 维度的数据来源）。

## 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `engine.py` | ~500 | BacktestEngine 主类 + Numba JIT 订单回调 + 批量回测 + 基准传递 |

## 关键链路

### 回测主链路 (BacktestEngine.run)

```
engine.py:599 run(dna, enhanced_df, dfs_by_timeframe, signal_set)
  L608  _build_portfolio(dna, enhanced_df, ...)
    L405  dna_to_signal_set(dna, enhanced_df, dfs_by_timeframe)
           -> if mtf_mode: run_mtf_engine()
           -> else: evaluate_layer() per layer
    L428-429  direction_map: {long:0, short:1, mixed:2}
    L444-454  mixed 模式构建 entry_direction 信号
    L463  vbt.Portfolio.from_order_func(close, order_func_nb, ...)
  L478  _build_result_from_portfolio(portfolio, dna, enhanced_df, ...)
    L497  提取 equity_curve
    L500-503  爆仓检测
    L505-508  _apply_funding_costs() 资金费率
    L510-540  提取 total_trades, trade_pnl
    L539-566  compute_metrics(equity_curve, ..., benchmark_close=enhanced_df["close"])
              [关键] 自动把原始 OHLCV close 列传给评分系统作为基准
    L579-600  返回 BacktestResult（含 market_annual_return, alpha）
```

### 基准传递链路（新增）

```
BacktestEngine._build_result_from_portfolio()
  L561-566  compute_metrics(
              equity_curve,
              benchmark_close=enhanced_df["close"],  # 无杠杆原始价格
            )
  -> metrics 包含:
     market_annual_return: 买入持有年化（无杠杆）
     alpha: annual_return - market_annual_return
     backtest_years: 实际回测年数

  L596-600  BacktestResult(
              ...,
              market_annual_return=metrics.get("market_annual_return", 0.0),
              alpha=metrics.get("alpha", 0.0),
            )
```

**为什么用 `enhanced_df["close"]`**: 这是原始 OHLCV 的 close 列，不含杠杆效应。策略的 equity_curve 包含杠杆放大效果。两者对比才能算出真正的超额收益。如果用杠杆后的曲线作为基准，Alpha 就没有意义了。

### 逐K线订单回调 (order_func_nb)

```
@njit 编译，不可使用 Python 对象
  已爆仓? -> 强制平仓
  有 entry signal + 足够资金? -> 重置爆仓标志
  杠杆爆仓检测: value < maintenance
  SL/TP 检测 (用 HIGH/LOW 触发):
    Long: SL = entry*(1-sl), TP = entry*(1+tp)
    Short: SL = entry*(1+sl), TP = entry*(1-tp)
  Exit signal -> 平仓
  Entry signal -> 开仓
    mixed 模式: 从 direction_signal 判断方向 (+1=long, -1=short)
  Reduce signal -> 按比例减仓
  Add signal -> 加仓 + 更新加权平均 entry_price
```

### 批量回测 (BacktestEngine.batch_run)

```
batch_run(individuals, enhanced_df, dfs_by_timeframe)
  对多个 DNA 并行构建信号集
  构建 2D direction_vals 数组 (每个 DNA 一列)
  统一 Portfolio.from_order_func 批量执行
  每个个体独立计算 metrics（含 benchmark_close 传递）
  返回 List[BacktestResult]
```

## 关键机制

### Numba JIT 编译

`pre_sim_func_nb` 和 `order_func_nb` 用 `@njit` 装饰。所有参数必须是 numpy 数组或标量，不能用 Python 对象。bool Series 转 float64 的 (N,1) 数组，>0.5 视为 True。

### 止损止盈使用 HIGH/LOW 触发

不用收盘价，用 K 线最高/最低价检测。Long SL: bar_low <= entry*(1-sl)。比收盘价更接近真实。

### 爆仓机制

maintenance = init_cash * (1 - 0.9/leverage)。leverage=10 时 9% 亏损就爆仓，比真实交易所更严格。

### 信号延迟防偷看

所有信号 shift(1) 后输入回测引擎。

### 杠杆资金费率 (_apply_funding_costs)

RATE_PER_8H = 0.1%。费率 = RATE * (hours_per_bar/8) * (leverage-1)/leverage。通过 trades_df 构建持仓掩码，仅持仓 K 线扣费。

### 混合方向支持

direction=2(mixed) 时，从 direction_signal 数组读取 +1/-1 动态决定方向。如果 direction="mixed" 但没有 entry_direction 信号，默认做多并输出警告日志。

### bars_per_year 动态映射 (engine.py:540-541)

```python
bars_per_year_map = {"15m": 365*96, "30m": 365*48, "1h": 365*24,
                     "4h": 365*6, "1d": 365, "3d": 365//3}
```
根据 DNA 的 `execution_genes.timeframe` 动态选择，影响 annual_return 和 sharpe 的年化计算。默认 2190（4h）。

## 接口定义

| 函数 | 签名 | 说明 |
|------|------|------|
| `BacktestEngine.__init__` | `(init_cash=100000, fee=0.001, slippage=0.0005)` | 初始化 |
| `BacktestEngine.run` | `(dna, df, dfs=None, signal_set=None) -> BacktestResult` | 主入口 |
| `BacktestEngine.batch_run` | `(individuals, df, dfs=None) -> List[BacktestResult]` | 批量回测 |
| `BacktestEngine.run_with_portfolio` | `(dna, df, dfs=None) -> (BacktestResult, Portfolio)` | 返回 portfolio |
| `_apply_funding_costs` | `(equity, leverage, tf, trades_df) -> (Series, float)` | 资金费率 |
| `order_func_nb` | `@njit` | Numba 逐K线回调 |

BacktestResult (dataclass): 17 个字段。核心字段: total_return, sharpe_ratio, max_drawdown, win_rate, total_trades, equity_curve, metrics_dict。新增字段: **market_annual_return**, **alpha**。

## 关键参数

| 参数 | 默认值 | 设计意图 |
|------|--------|---------|
| init_cash | 100000 | 初始资金 USDT |
| fee | 0.001 | 手续费 0.1% |
| slippage | 0.0005 | 滑点 0.05% |
| RATE_PER_8H | 0.001 | 8h 资金费率 0.1% |
| bars_per_year | 动态 | 根据 timeframe 映射，4h=2190, 15m=35040 |
| maintenance | init_cash * (1 - 0.9/leverage) | 爆仓维持保证金 |

## 约定与规则

- **Numba 兼容性**: order_func_nb 内部不能用 dict/list 等 Python 对象
- **信号传递**: bool Series -> float64 (N,1) 数组，>0.5 为 True
- **Entry+Exit 冲突优先 Exit**: mtf_engine 和 executor 都有处理
- **方向编码**: 0=long, 1=short, 2=mixed
- **资金费率仅持仓时扣除**: 通过 trades_df 构建 position_mask
- **benchmark_close 自动传递**: `_build_result_from_portfolio` 总是把 `enhanced_df["close"]` 传给 compute_metrics，不需要调用方显式传入
- **Alpha 计算对杠杆透明**: 策略 annual_return 含杠杆效应，benchmark 不含。这是设计意图——杠杆是策略选择，不是市场给的
