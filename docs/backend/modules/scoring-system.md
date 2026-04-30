# B7: 评分系统

## 定位

`core/scoring/` 是进化的"标尺"——把回测结果变成 0-100 的综合评分。四阶段管道: 原始数据 -> 原始指标(15 项) -> 6 维归一化分数(0-100) -> 模板加权总分。`score_strategy()` 的返回值直接决定 DNA 在进化中的生死。

## 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `metrics.py` | 179 | 15 项原始指标计算，含 Alpha（超额收益）|
| `normalizer.py` | 122 | 分段线性归一化（核心 5 维 + Alpha）+ 兼容旧维度 |
| `scorer.py` | 131 | 模板加权 + 硬约束 + Sigmoid 交易数量惩罚 |
| `templates.py` | 94 | 3 套差异化模板 + 7 个别名映射 |

## 关键链路

### 评分主链路

```
scorer.py:27 score_strategy(metrics, template_name="explorer", liquidated=False)
  L44-45  get_template(template_name) 解析模板（自动解析别名）
  L48     total_trades == 0 -> return {total_score: 0.0}
  L59     liquidated == True -> return {total_score: 0.0}（保留维度分数供诊断）
  L77-104 hard_constraints 检查（仅 optimizer 模板）
            ├ max_drawdown < -0.60 -> 0 分
            └ annual_return < 0.10 -> 0 分
  L107-115 循环 template.weights:
            ├ "trade_count_penalty" -> _compute_trade_factor() * 100
            └ 其余维度 -> normalize(dim, metrics[dim])
  L118-121 加权求和: sum(score * weight)
  L123-130 返回 {total_score, dimension_scores, template_name, raw_metrics, ...}
```

### Alpha 计算链路（新增）

```
metrics.py:154-160  alpha 计算
  前置: benchmark_close 参数由回测引擎自动传入（engine.py:565）
  L157-158  bm_total_return = benchmark_close[-1] / benchmark_close[0] - 1
            market_annual_return = (1 + bm_total_return) ^ (1/years) - 1
  L160      alpha = annual_return - market_annual_return
            关键: benchmark 是无杠杆买入持有，策略收益含杠杆效应
            这是 Alpha 能区分"牛市躺赢"和"真正选股能力"的基础

normalizer.py:100-101  alpha 归一化
  使用 _ALPHA_BREAKPOINTS 分段线性:
  alpha=0.0 -> 40分（跑平大盘不是优秀，只是尚可）
  alpha=0.5 -> 80分
  alpha=1.0 -> 95分
```

### 标准化映射（核心维度）

所有核心维度使用 `piecewise_normalize()`（normalizer.py:64-83）做分段线性归一化。每对相邻断点之间线性插值，超出范围钳位到端点。

| 维度 | 断点设计 | 设计意图 |
|------|---------|---------|
| annual_return | [-1→0, 0→10, 10%→30, 30%→60, 50%→80, 100%→95, 300%→100] | 核心区间 [0%, 50%] 梯度最陡；50% 以上快速饱和 |
| sharpe_ratio | [-1→0, 0→5, 0.5→20, 1.0→50, 1.5→75, 2.0→90, 3.0→100] | 核心区间 [0.5, 1.5] 梯度最陡 |
| max_drawdown | [0→100, 10%→80, 20%→60, 30%→40, 50%→15, 80%→0] | 纯线性，无平方惩罚。`normalize()` 用 `abs(value)` 转正值 |
| profit_factor | [0→0, 0.5→10, 1.0→30, 1.5→60, 2.0→80, 3.0→100] | PF>1 后陡升，区分盈利质量 |
| alpha | [-0.5→0, -0.2→15, 0→40, 0.2→60, 0.5→80, 1.0→95, 3.0→100] | alpha=0 不是 50 分而是 40 分——跑平大盘只算尚可 |
| monthly_consistency | `value * 100` | 已是 0-1 范围，直接映射 |

**为什么用分段线性而不是 log 或线性**: 分段线性允许在每个区间独立控制敏感度。比如 annual_return 在 [0%, 50%] 区间分配了 70 分的梯度（10→80），让进化算法在这个核心区间有足够的区分度；而 [100%, 300%] 只分配了 5 分，避免高分饱和。这比 log 映射更直观、可调。

## 三套模板设计

### 模板对比

| 维度 | explorer（收益探索）| optimizer（稳健收益）| max_return（极致收益）|
|------|-------------------|--------------------|-----------------------|
| annual_return | **0.25** | 0.15 | **0.40** |
| alpha | **0.15** | 0.10 | **0.15** |
| sharpe_ratio | 0.20 | **0.25** | 0.15 |
| profit_factor | 0.15 | 0.10 | **0.20** |
| max_drawdown | 0.10 | **0.15** | -- |
| monthly_consistency | 0.10 | **0.20** | -- |
| trade_count_penalty | 0.05 | 0.05 | 0.10 |
| **合计** | **1.00** | **1.00** | **1.00** |
| hard_constraints | 无 | annual_return>=10%, max_drawdown>=-60% | 无 |
| threshold | 50.0 | 65.0 | 40.0 |

### 模板差异化逻辑

三套模板不是简单的权重重排，它们回答三个不同的业务问题:

- **explorer** — "能不能赚钱？" 年化 + Alpha 合计 40%，适合探索新市场/品种
- **optimizer** — "给我一个能实盘用的策略？" sharpe + monthly_consistency 合计 45%，还有硬约束挡住低收益/高回撤
- **max_return** — "我要最高收益，不怕波动。" 没有 max_drawdown 和 monthly_consistency 维度，完全不惩罚回撤

### 别名映射（向后兼容）

| 旧名称 | 映射到 | 映射理由 |
|--------|--------|---------|
| profit_first, aggressive | explorer | 收益优先 ≈ 收益探索 |
| steady, balanced, conservative, risk_first, custom | optimizer | 稳健/风险控制 ≈ 稳健收益 |

### 硬约束机制 (scorer.py:76-104)

仅 `optimizer` 模板有硬约束。在评分之前检查，不通过直接返回 0 分:

```python
hard_constraints = {
    "annual_return": 0.10,    # 年化 < 10% -> 0 分（连通胀都跑不赢）
    "max_drawdown": -0.60,    # 回撤 > 60% -> 0 分（不可接受的风险）
}
```

max_drawdown 的比较逻辑（scorer.py:80-83）: 原始值是负数（如 -0.65），threshold 也是负数（-0.60），`raw_val < threshold` 表示回撤更严重。

## 关键机制

### Alpha: 市场基准感知（新增）

**解决什么问题**: 之前评分完全不考虑市场环境。年化 126% 的策略在牛市可能只是跑平大盘，但能得 96 分；同一策略在熊市跑赢大盘 100% 也只得 60 分。Alpha 维度修复了这个不合理。

**计算方式** (metrics.py:154-160):
- 回测引擎把 `enhanced_df["close"]`（无杠杆原始价格）传给 `compute_metrics(benchmark_close=...)`
- `market_annual_return` = 买入持有年化（无杠杆）
- `alpha` = `annual_return - market_annual_return`
- 回撤引擎使用 `abs(value)` 处理，归一化用正序断点

**注意**: 策略的 annual_return 含杠杆效应，但 benchmark 是无杠杆的。这意味着 3x 杠杆策略在牛市天然有正 Alpha（因为杠杆放大了收益），在熊市天然有负 Alpha。

### Sigmoid 交易数量惩罚 (scorer.py:12-24)

`trade_count_penalty` 不是直接的维度分数，而是一个 0-100 的惩罚分:
```
min_trades = max(10, total_bars // 500)
factor = 1 / (1 + exp(-0.2 * (trade_count - midpoint)))
score = factor * 100
```
动态阈值 `total_bars // 500`: 15m 策略 10000 bars -> min=20；4h 策略 2000 bars -> min=10。这防止了用不同周期数据时惩罚标准不一致。

### 交易级别 Sharpe 优先 (metrics.py:66-81)

优先用交易级别回报（`trade_returns`）计算 Sharpe。回退条件: `trade_returns is None` 且 `total_trades >= 5` 时用 K 线级别。交易级别更精确因为每笔交易才是独立的决策事件。

## 接口定义

| 函数 | 签名 |
|------|------|
| `compute_metrics` | `(equity_curve, total_trades=0, bars_per_year=2190, trade_win_rate=None, trade_returns=None, benchmark_close=None) -> dict` |
| `normalize` | `(metric_name: str, value: float) -> float` |
| `piecewise_normalize` | `(value: float, breakpoints: List[Tuple[float, float]]) -> float` |
| `score_strategy` | `(metrics, template_name="explorer", template=None, liquidated=False) -> Dict` |
| `get_template` | `(name: str) -> ScoringTemplate` |
| `list_template_names` | `() -> list[str]` |

## 关键参数

| 参数 | 位置 | 默认值 | 设计意图 |
|------|------|--------|---------|
| bars_per_year | metrics.py:11 | 2190 | 4h K 线年化基数（365*6）。实际值由回测引擎根据 timeframe 覆盖 |
| alpha breakpoints | normalizer.py:53-61 | 0→40 | alpha=0 给 40 分而不是 50 分——跑平大盘不等于"中等水平" |
| drawdown breakpoints | normalizer.py:33-40 | 纯线性 | 没有平方惩罚（v1.0 之前的 bug 已修复） |
| min_trades (动态) | scorer.py:19 | max(10, bars//500) | 按数据量调整，避免高频策略被误判为交易不足 |
| hard_constraints | templates.py:50-53 | 仅 optimizer | 收益/风险底线，不过关直接 0 分 |

## 约定与规则

- **不可变输出**: 所有函数返回新 dict/float，不修改输入
- **NaN 防护**: max_drawdown/sharpe 等检查 NaN 并回退
- **权重和=1.0**: 每个模板权重总和 1.00（由测试 `test_template_weights_sum_to_1` 保证）
- **分数钳制 [0, 100]**: normalizer.py:121
- **空数据合同**: len(equity)<2 或 trades==0 返回全零 dict（含 alpha=0, market_annual_return=0）
- **模板别名**: 旧名自动解析（profit_first→explorer, steady→optimizer 等）
- **metrics.py 仍计算所有旧指标**: sortino/calmar/win_rate/r_squared/max_consecutive_losses 继续计算并返回，供 API 展示用，但评分模板不再引用它们
- **归一化用 `abs(value)` 处理 max_drawdown**: 断点是正值升序（0→100, 0.8→0），`normalize("max_drawdown", -0.3)` 先取 abs 得 0.3 再查表得 40
