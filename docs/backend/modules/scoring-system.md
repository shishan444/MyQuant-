# B7: 评分系统

## 定位

`core/scoring/` 是"标尺"——把回测结果变成 0-100 的综合评分。四阶段管道: 原始数据 -> 12 项原始指标 -> 标准化分数(0-100) -> 加权总分。`score_strategy()` 的返回值直接决定 DNA 在进化中的生死。

## 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `metrics.py` | 162 | 12 项原始指标计算 |
| `normalizer.py` | 71 | 指标标准化 (0-100) |
| `scorer.py` | 102 | 加权评分 + 惩罚 |
| `templates.py` | 143 | 7 个评分模板定义 |

## 关键链路

### 评分主链路

```
scorer.py:16 score_strategy(metrics, template_name, liquidated)
  L34  get_template(template_name) 解析模板
  L37  0 trades -> return 0
  L48  liquidated -> return 0
  L63-66  循环 template.weights, normalize(dim, raw_val) per dimension
  L69-72  标准化维度分加权求和
  L75-80  回撤梯度惩罚:
    DD > 90%: score *= 0.05 (致命)
    DD 50%-90%: 线性惩罚
  L84-92  Sigmoid 交易数量惩罚:
    min_trades = max(10, total_bars//500)
    penalty = 1/(1+exp(-0.2*(count-midpoint)))
  L94-101  返回 {total_score, dimension_scores, raw_metrics, ...}
```

### 标准化映射

| 指标 | 映射方式 | 有效范围 |
|------|---------|---------|
| annual_return | 对数 `log1p(v+1)/log1p(6)*100` | [-1, +5] -> [0, 100] |
| sharpe_ratio | 线性 [0, 3.0]; 负值 `50+v*10` | 负~3.0 |
| max_drawdown | `(1+v)*100` + 超 20% 平方惩罚 | 0~1.0 |
| win_rate | 线性 [0.3, 0.7] | 30%~70% |
| calmar_ratio | 线性 [0, 5.0] | 0~5 |
| sortino_ratio | 线性 [0, 4.0]; 负值同 sharpe | 0~4 |
| profit_factor | 分段: [0,1) `v*30`, [1,+) `30+(v-1)/2*70` | 0~+inf |
| max_consecutive_losses | `100 - v*10` | 0~10 |
| monthly_consistency | `v*100` | 0~1 |
| r_squared | `v*100` | 0~1 |

## 关键机制

### 交易级别 Sharpe 优先 (metrics.py:60-76)

优先用交易级别回报计算 Sharpe。只有 trade_returns=None 且 total_trades>=5 时才回退 K 线级别。交易级别更精确。

### 梯度回撤惩罚 (scorer.py:74-80)

两阶段: >90% DD 致命(0.05); 50%-90% 线性惩罚。阈值设计: 50% 回撤开始惩罚是保守选择，防止高风险策略得高分。

### Sigmoid 交易数量惩罚 (scorer.py:82-92)

`min_trades = max(10, total_bars//500)` 动态调整。防止少量交易得高分（如只做 2 笔赚了 50%）。

### R 平方线性度量 (metrics.py:135-146)

OLS 计算: 1 - SS_res/SS_tot。捕获权益曲线"平滑度"。

## 接口定义

| 函数 | 签名 |
|------|------|
| `compute_metrics` | `(equity_curve, total_trades=0, bars_per_year=2190, ...) -> dict` |
| `normalize` | `(metric_name, value) -> float` |
| `score_strategy` | `(metrics, template_name="profit_first", ...) -> Dict` |
| `get_template` | `(name) -> ScoringTemplate` |

## 关键参数

| 参数 | 位置 | 默认值 | 设计意图 |
|------|------|--------|---------|
| bars_per_year | metrics.py:11 | 2190 | 4h K 线年化基数 |
| _DRAWDOWN_PENALTY_THRESHOLD | scorer.py:12 | 0.50 | 50% DD 开始惩罚 |
| _DRAWDOWN_FATAL | scorer.py:13 | 0.90 | 90% DD 致命 |
| min_trades (动态) | scorer.py:85 | max(10, bars//500) | 按数据量调整 |

## 约定与规则

- **不可变输出**: 所有函数返回新 dict/float
- **NaN 防护**: max_drawdown/sharpe/sortino 等检查 NaN
- **权重和=1.0**: 每个模板权重总和 1.00
- **分数钳制 [0, 100]**: normalizer.py:70
- **空数据合同**: len(equity)<2 或 trades==0 返回全零
- **模板别名**: profit_first=aggressive, steady=balanced (向后兼容)
