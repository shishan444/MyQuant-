# B5: 回测引擎

## 定位

`core/backtest/` 负责把 DNA 信号变成可量化的交易成绩。核心是 vectorbt `Portfolio.from_order_func()` 的封装，支持双向交易（long/short/mixed）、杠杆资金费率扣除和爆仓检查。Walk-Forward 验证器在此基础上做滑动窗口交叉验证，给进化引擎提供抗过拟合评分。

## 文件职责

| 文件 | 行数 | 职责 |
|------|------|------|
| `engine.py` | 499 | vectorbt 封装：信号→Portfolio→BacktestResult，含双向交易、资金费率和爆仓逻辑 |
| `walk_forward.py` | 177 | Walk-Forward 交叉验证：滑动训练窗口 + 随机样本外月份 |
| `__init__.py` | 空 | 无导出 |

## BacktestResult 数据结构

`BacktestResult` 是回测的标准输出，被评分系统（B7）和 API 层消费：

| 字段 | 类型 | 含义 |
|------|------|------|
| total_return | float | 从**调整后**权益曲线算的收益率（扣除了资金费率和爆仓） |
| sharpe_ratio | float | 年化 Sharpe，由 `compute_metrics()` 计算 |
| max_drawdown | float | 最大回撤 |
| win_rate | float | 胜率 |
| total_trades | int | vectorbt 统计的交易次数 |
| equity_curve | pd.Series | 调整后的权益曲线 |
| trades_df | DataFrame/None | vectorbt 交易记录 |
| total_funding_cost | float | 累计资金费率成本 |
| liquidated | bool | 是否触发爆仓 |
| data_bars | int | 回测数据条数 |
| trade_win_rate | float/None | 从逐笔 PnL 算的胜率（比 win_rate 更精确） |
| trade_returns | np.ndarray/None | 逐笔收益率数组 |
| bars_per_year | int | 按时间周期换算的年 K 线数 |
| add_count / reduce_count | int | 加仓/减仓信号触发次数 |
| degraded_layers | int | MTF 层因数据缺失被跳过的数量 |
| metrics_dict | dict/None | `compute_metrics()` 的完整输出 |

**关键区分**: `win_rate` 来自 `compute_metrics()`（可能基于权益变化推算），`trade_win_rate` 直接从 vectorbt 的逐笔 PnL 计算（`pnl > 0` 的比例）。当 `trade_win_rate` 可用时，它比 `win_rate` 更准确。

## BacktestEngine

### 初始化参数

```python
BacktestEngine(init_cash=100000, fee=0.001, slippage=0.0005)
```

- 初始资金 10 万 USDT
- 手续费 0.1%（双边）
- 滑点 0.05%

### _build_portfolio(): 信号→Portfolio 的映射

使用 `Portfolio.from_order_func()` 替代 `from_signals()`，通过自定义 `order_func_nb` (Numba JIT) 实现实时风控（止损/止盈/加仓/减仓/爆仓）。

**方向映射**:

| dna.direction | direction_val | 行为 |
|---------------|--------------|------|
| "long" | 0 | 只做多 |
| "short" | 1 | 只做空 |
| "mixed" | 2 | 由 direction_signal 逐 bar 决定 |

mixed 模式下 `direction_signal` 从 `SignalSet.entry_direction` 构建（+1=做多, -1=做空），延迟 1 bar 防止前瞻偏差。

### order_func_nb: Numba JIT 交易执行函数

核心交易执行逻辑，在 vectorbt 的每 bar 循环中被调用：

**入场逻辑**：
- 检查信号类型（entry/add/reduce/exit）
- long 模式：entry 信号触发做多
- short 模式：entry 信号触发做空
- mixed 模式：根据 direction_signal 决定做多或做空

**止损/止盈**（由 vectorbt 的 `sl_stop`/`tp_stop` 参数驱动）：
- 做多止损：bar_low <= entry_price * (1 - sl_stop) 时触发
- 做多止盈：bar_high >= entry_price * (1 + tp_stop) 时触发
- 做空止损：bar_high >= entry_price * (1 + sl_stop) 时触发
- 做空止盈：bar_low <= entry_price * (1 - tp_stop) 时触发

**加仓**：add 信号触发时以混合均价（blended average）更新入场价。

**信号延迟**：entry/exit/add/reduce 信号均延迟 1 bar（`shift(1)`），防止前瞻偏差。

**仓位大小**: `position_size * leverage`，类型为 `"percent"`。例如 position_size=0.5, leverage=3 → vectorbt 每次开仓用 150% 资金。

**加仓/减仓处理**:
```
all_entries = entries | adds     # 加仓信号合并到入场
all_exits = exits | reduces      # 减仓信号合并到出场
accumulate = bool(adds.any())    # 有加仓信号时启用累积模式
```
vectorbt 的 `accumulate=True` 允许同一方向多次开仓（金字塔加仓）。减仓没有专门的 accumulate 机制——它被当作普通出场信号。

**止损/止盈**: 直接传 `sl_stop` 和 `tp_stop` 给 vectorbt，由 vectorbt 引擎内部执行。

### _apply_funding_costs(): 杠杆资金费率

仅 leverage > 1 时生效。逻辑：

1. 按 8 小时费率 0.01% 计（`RATE_PER_8H = 0.001`），根据时间周期换算每根 K 线的费率周期数
2. `borrowed_ratio = (leverage - 1) / leverage` — 只对借入部分收费
3. `cost_rate = RATE_PER_8H * periods_per_bar * borrowed_ratio`
4. 逐 bar 从权益中扣除：`adjusted[i] -= adjusted[i-1] * cost_rate`
5. 用 numpy 数组而非 pandas Series 做逐元素操作（注释说避免 `iloc` 开销）

**时间周期到小时数的映射**:
```
1m→1/60h, 5m→5/60h, 15m→0.25h, 30m→0.5h,
1h→1h, 4h→4h, 1d→24h, 3d→72h
```
`periods_per_bar` 向上取整到 8 小时的整数倍（`math.ceil`）。

### _check_liquidation(): 爆仓检查

仅 leverage > 1 时检查：

- 维持保证金 = `init_cash * (1 - 0.9 / leverage)`
- 当权益曲线低于维持保证金时，从第一个触发的 bar 开始把权益全部置零
- 返回 `True` 表示已爆仓

这意味着：leverage=10 时，维持保证金 = `init_cash * 0.91`——只要亏损超过 9% 就爆仓。这个计算方式**不是**真实的交易所保证金逻辑（真实交易所看的是未实现亏损 vs 保证金余额），而是一个简化模型。

### run(): 主流程

```
_build_portfolio(dna, df, signal_set)
  ↓
equity_curve = portfolio.value()
  ↓
_apply_funding_costs()   → 调整权益曲线
  ↓
_check_liquidation()     → 可能截断曲线
  ↓
portfolio.trades.count() → 交易次数
  ↓
portfolio.trades.pnl     → 逐笔 PnL（提取 trade_win_rate, trade_returns）
  ↓
compute_metrics()        → sharpe/max_dd/win_rate 等
  ↓
total_return = equity_curve[-1] / equity_curve[0] - 1  ← 从调整后曲线算
  ↓
BacktestResult(...)
```

**一个微妙之处**: `total_return` 不是 vectorbt portfolio 的原始回报率，而是从资金费率调整后、爆仓检查后的权益曲线算的。这意味着如果有杠杆，回报率已经被资金费率"拖累"过。

### run_with_portfolio()

同时返回 `BacktestResult` 和 vectorbt `Portfolio` 对象的元组。当需要直接操作 Portfolio 对象（如可视化）时使用。

### run() 方法

接受 `StrategyDNA`、`enhanced_df` 和可选的 `dfs_by_timeframe`：

1. 调用 `dna_to_signal_set()` 获取 SignalSet
2. 调用 `_build_portfolio()` 构建 vectorbt Portfolio
3. 获取权益曲线并应用资金费率调整
4. 检查爆仓
5. 构建并返回 BacktestResult

## WalkForwardValidator

### 参数

| 参数 | 默认值 | 含义 |
|------|--------|------|
| train_months | 3 | 训练窗口大小（月） |
| slide_months | 1 | 滑动步长（月） |
| train_weight | 0.4 | 训练评分权重 |
| val_weight | 0.6 | 验证评分权重 |
| template_name | "profit_first" | 评分模板 |

验证权重 (0.6) 大于训练权重 (0.4)，这个设计偏好样本外表现。

### validate() 流程

```
生成月份边界 (pd.date_range freq="MS")
  ↓
逐窗口滑动:
  ├─ 训练窗口 [month_starts[i], month_starts[i+train_months])
  ├─ 验证月份: 从训练窗口外的月份中随机选一个
  ├─ engine.run(dna, train_df) → score_strategy → train_score
  ├─ engine.run(dna, val_df)   → score_strategy → val_score
  └─ combined = train_score * 0.4 + val_score * 0.6
  ↓
wf_score = mean(combined_scores)
```

**共享验证月份**: `val_months` 参数允许外部传入预生成的验证月份列表。进化引擎同一代的所有个体共享相同的验证月份，保证比较公平。如果不传，每个窗口独立随机选验证月。

**MTF 支持**: Walk-Forward 的每个窗口切片会独立加载对应时间段的 MTF 数据，避免跨窗口数据泄漏。

**最少数据要求**: 训练集 < 20 条或验证集 < 5 条的窗口被跳过。总月份数 < train_months + 1 时直接返回零分。

**评分依赖**: Walk-Forward 直接调用 `score_strategy()`（B7 评分系统）和 `compute_metrics()`（B7 指标计算），不是独立算分。

## 数据流

```
StrategyDNA + Enhanced DataFrame (OHLCV + 100+ 指标列) + dfs_by_timeframe (MTF)
    ↓
executor.dna_to_signal_set() / mtf_engine.run_mtf_engine()
  → SignalSet { entries, exits, adds, reduces, entry_direction, mtf_diagnostics }
    ↓
BacktestEngine._build_portfolio() → vectorbt Portfolio (from_order_func)
    ↓
portfolio.value() → 原始权益曲线
    ↓
_apply_funding_costs() → 扣除杠杆资金费率
_check_liquidation()  → 爆仓截断
    ↓
compute_metrics() + portfolio.trades → BacktestResult
    ↓
(可选) WalkForwardValidator.validate()
  → 多轮 train/val → wf_score
```

## 涉及文件

| 文件 | 核心内容 |
|------|---------|
| `core/backtest/engine.py` | BacktestEngine、BacktestResult、资金费率、爆仓检查 |
| `core/backtest/walk_forward.py` | WalkForwardValidator 滑动窗口验证 |
