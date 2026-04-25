# B7: 评分系统

## 定位

`core/scoring/` 把回测结果的原始指标转换为 0-100 的综合评分。是进化引擎筛选个体的核心判据——`score_strategy()` 的返回值直接决定 DNA 的生死。

## 文件职责

| 文件 | 行数 | 职责 |
|------|------|------|
| `metrics.py` | 162 | 从权益曲线和逐笔数据提取 11 个原始指标 |
| `normalizer.py` | 71 | 将原始指标值归一化到 0-100 |
| `templates.py` | 143 | 7 种评分模板定义（权重 + 阈值） |
| `scorer.py` | 102 | 组合评分：归一化 → 加权求和 → 惩罚修正 |

## 原始指标 (metrics.py)

`compute_metrics()` 从权益曲线 + 逐笔交易数据提取 11 个指标：

| 指标 | 类型 | 计算方式 |
|------|------|----------|
| annual_return | 收益 | `(1 + total_return)^(1/years) - 1`，复利年化 |
| sharpe_ratio | 风险调整 | 优先逐笔：(mean_return / std) * sqrt(trades/year)；回退 bar 级别 |
| max_drawdown | 风险 | `(equity - cummax) / cummax` 的最小值（负数） |
| win_rate | 胜率 | 优先逐笔 `trade_win_rate`；回退 bar 级别 `pct_change > 0` |
| calmar_ratio | 风险调整 | `annual_return / abs(max_drawdown)` |
| sortino_ratio | 风险调整 | 类 Sharpe 但只惩罚下行偏差 |
| profit_factor | 效率 | 总盈利 / 总亏损（全胜 = 10.0） |
| max_consecutive_losses | 风险 | 最大连续亏损交易数 |
| monthly_consistency | 稳定性 | 盈利月份占比（按月重采样 `resample('ME')`） |
| r_squared | 稳定性 | 权益曲线线性度（1.0 = 完美线性增长） |
| total_bars | 信息 | 数据总 bar 数 |

**数据来源优先级**: Sharpe/win_rate/sortino/profit_factor/max_consecutive_losses 优先从逐笔 `trade_returns` 计算（更精确），不可用时回退到 bar 级别的权益曲线推算。

## 归一化 (normalizer.py)

每个指标有独立的 0-100 映射规则：

| 指标 | 映射规则 | 零分点 | 满分点 |
|------|----------|--------|--------|
| annual_return | 对数映射 `log1p(v+1)/log1p(6)*100` | -100% | +500% |
| sharpe_ratio | 线性 `[0,3.0]→[0,100]`；负值 `50+v*10` | 负值 | >= 3.0 |
| max_drawdown | `(1+dd)*100`，>20% 额外平方惩罚 | >= 50% | 0% |
| win_rate | 线性 `[0.3,0.7]→[0,100]` | 30% | 70% |
| calmar_ratio | 线性 `[0,5.0]→[0,100]` | 0 | >= 5.0 |
| sortino_ratio | 线性 `[0,4.0]→[0,100]` | 负值 | >= 4.0 |
| profit_factor | 分段：PF<1 → `v*30`；>=1 → `30+(v-1)/2*70` | <= 0 | >= 3.0 |
| max_consecutive_losses | `100 - v*10` | >= 10 | 0 |
| monthly_consistency | 直接 `v*100` | 0% | 100% |
| r_squared | 直接 `v*100`（负值截断为0） | 0 | 1.0 |
| 未知指标 | 固定 50 分 | — | — |

annual_return 用对数映射而非线性——因为 +500% 和 +1000% 的策略在"好"的方向上差异不大，但 -50% 和 -90% 的差异很大。

## 评分模板 (templates.py)

7 种模板，每种定义 10 个维度的权重和阈值：

| 模板 | 年化收益权重 | 最大回撤权重 | 阈值 | 备注 |
|------|-------------|-------------|------|------|
| profit_first | 0.25 | 0.10 | 55 | 默认模板，与 aggressive 相同 |
| aggressive | 0.25 | 0.10 | 55 | 重收益 |
| steady | 0.15 | 0.15 | 65 | 与 balanced 相同 |
| balanced | 0.15 | 0.15 | 65 | 均衡 |
| risk_first | 0.05 | 0.25 | 75 | 重风控 |
| conservative | 0.05 | 0.25 | 75 | 与 risk_first 相同 |
| custom | 0.12 | 0.12 | 70 | 接近均衡 |

**profit_first = aggressive**，**steady = balanced**，**risk_first = conservative**——它们是别名对。权重之和均为 1.0。

## 组合评分 (scorer.py)

```
score_strategy(metrics, template_name, liquidated)
  ↓
零交易 → 0 分（直接返回）
爆仓 → 0 分（仍计算 dimension_scores 供诊断）
  ↓
逐维度归一化: normalize(dim, raw_val) → 0-100
  ↓
加权求和: sum(score * weight)
  ↓
回撤惩罚:
  max_dd >= 90% → total *= 0.05（接近清零）
  max_dd >= 50% → 渐进惩罚，最高扣 95%
  ↓
交易次数惩罚（Sigmoid）:
  min_trades = max(10, total_bars // 500)
  trades < min_trades → total *= sigmoid衰减因子
  ↓
返回 { total_score, dimension_scores, template_name, threshold, raw_metrics, liquidated }
```

### 回撤惩罚

严重的最大回撤会额外惩罚总分：
- 50%-90% 之间：线性插值，最高扣掉 95%
- >= 90%：只保留 5% 分数

### 交易次数惩罚

交易太少意味着统计不可靠。`min_trades` 根据数据量动态计算（`max(10, total_bars/500)`）。低于阈值的策略用 Sigmoid 函数衰减分数，midpoint = min_trades - 5。

## 数据流

```
BacktestResult (from BacktestEngine.run)
  ↓ equity_curve + total_trades + trade_win_rate + trade_returns
  ↓
compute_metrics() → 11 个原始指标 dict
  ↓
score_strategy(metrics, template_name)
  ↓
normalize() × 10 维度 → dimension_scores (各 0-100)
  ↓
加权求和 + 回撤惩罚 + 交易次数惩罚
  ↓
total_score (0-100)
  ↓
进化引擎: total_score 决定个体选择/淘汰
API: total_score + dimension_scores 返回前端
```

## 涉及文件

| 文件 | 核心内容 |
|------|---------|
| `core/scoring/metrics.py` | 11 个原始指标计算 |
| `core/scoring/normalizer.py` | 原始值→0-100 归一化规则 |
| `core/scoring/templates.py` | 7 种评分模板（权重+阈值） |
| `core/scoring/scorer.py` | 组合评分（归一化+加权+惩罚） |
