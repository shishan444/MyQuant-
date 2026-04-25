# B5: 回测引擎

## 定位

`core/backtest/` 是"裁判"——用历史数据验证策略可行性和收益。封装 vectorbt `Portfolio.from_order_func()`，支持双向交易、杠杆资金费率扣除和爆仓检查。

## 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `engine.py` | 500 | BacktestEngine 主类 + Numba JIT 订单回调 |

## 关键链路

### 回测主链路 (BacktestEngine.run)

```
engine.py:460 run(dna, enhanced_df, dfs_by_timeframe, signal_set)
  L468  _build_portfolio(dna, enhanced_df, ...)
    L308  dna_to_signal_set(dna, enhanced_df, dfs_by_timeframe)
           -> if mtf_mode: run_mtf_engine()
           -> else: evaluate_layer() per layer
    L311-314  signals.shift(1) 防偷看
    L328-340  构建 2D numpy arrays (Numba 兼容)
    L342-363  vbt.Portfolio.from_order_func(close, order_func_nb, ...)
  L479  _build_result_from_portfolio(portfolio, dna, enhanced_df, ...)
    L376  提取 equity_curve
    L382-385  爆仓检测
    L390-393  _apply_funding_costs() 资金费率
    L395-418  提取 total_trades, trade_pnl
    L422-427  compute_metrics() + score_strategy()
    L440-458  返回 BacktestResult
```

### 逐K线订单回调 (order_func_nb, L111-285)

```
@njit 编译，不可使用 Python 对象
  L131  已爆仓? -> 强制平仓
  L144-151  有 entry signal + 足够资金? -> 重置爆仓标志
  L156-166  杠杆爆仓检测: value < maintenance
  L169-217  SL/TP 检测 (用 HIGH/LOW 触发):
    Long: SL = entry*(1-sl), TP = entry*(1+tp)
    Short: SL = entry*(1+sl), TP = entry*(1-tp)
  L220-227  Exit signal -> 平仓
  L230-249  Entry signal -> 开仓
    L233-242  mixed 模式: 从 direction_signal 判断方向
  L252-259  Reduce signal -> 按比例减仓
  L262-283  Add signal -> 加仓 + 更新加权平均 entry_price
```

## 关键机制

### Numba JIT 编译 (L97-285)

`pre_sim_func_nb` 和 `order_func_nb` 用 `@njit` 装饰。所有参数必须是 numpy 数组或标量，不能用 Python 对象。bool Series 转 float64 的 (N,1) 数组，>0.5 视为 True。

### 止损止盈使用 HIGH/LOW 触发 (L168-217)

不用收盘价，用 K 线最高/最低价检测。Long SL: bar_low <= entry*(1-sl)。比收盘价更接近真实。

### 爆仓机制 (L156-166)

maintenance = init_cash * (1 - 0.9/leverage)。leverage=10 时 9% 亏损就爆仓，比真实交易所更严格。

### 信号延迟防偷看 (L311-314)

所有信号 shift(1) 后输入回测引擎。

### 杠杆资金费率 (_apply_funding_costs, L42-94)

RATE_PER_8H = 0.1%。费率 = RATE * (hours_per_bar/8) * (leverage-1)/leverage。通过 trades_df 构建持仓掩码，仅持仓 K 线扣费。

### 混合方向支持 (L232-242)

direction=2(mixed) 时，从 direction_signal 数组读取 +1/-1 动态决定方向。

## 接口定义

| 函数 | 签名 | 说明 |
|------|------|------|
| `BacktestEngine.__init__` | `(init_cash=100000, fee=0.001, slippage=0.0005)` | 初始化 |
| `BacktestEngine.run` | `(dna, df, dfs=None, signal_set=None) -> BacktestResult` | 主入口 |
| `BacktestEngine.run_with_portfolio` | `(dna, df, dfs=None) -> (BacktestResult, Portfolio)` | 返回 portfolio |
| `_apply_funding_costs` | `(equity, leverage, tf, trades_df) -> (Series, float)` | 资金费率 |
| `order_func_nb` | `@njit` | Numba 逐K线回调 |

BacktestResult (dataclass): 15 个字段 (return, sharpe, max_dd, win_rate, trades, equity_curve, signals 等)。

## 关键参数

| 参数 | 默认值 | 设计意图 |
|------|--------|---------|
| init_cash | 100000 | 初始资金 USDT |
| fee | 0.001 | 手续费 0.1% |
| slippage | 0.0005 | 滑点 0.05% |
| RATE_PER_8H | 0.001 | 8h 资金费率 0.1% |
| bars_per_year | 2190 | 4h K 线年化基数 |
| maintenance | init_cash * (1 - 0.9/leverage) | 爆仓维持保证金 |

## 约定与规则

- **Numba 兼容性**: order_func_nb 内部不能用 dict/list 等 Python 对象
- **信号传递**: bool Series -> float64 (N,1) 数组，>0.5 为 True
- **Entry+Exit 冲突优先 Exit**: mtf_engine.py:763 和 executor.py:464 都有处理
- **方向编码**: 0=long, 1=short, 2=mixed
- **资金费率仅持仓时扣除**: 通过 trades_df 构建 position_mask
