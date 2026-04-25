# F7: 类型与工具

## 定位

`web/src/types/` (TypeScript 接口) + `web/src/lib/` (业务工具) + `web/src/utils/` (通用工具) 构成前端基础设施层。提供类型契约、全局常量、格式化工具和数据转换。

## 类型定义

### types/api.ts (407 行) -- 核心接口

**DNA 结构**:
```
DNA
  signal_genes: SignalGene[]
  logic_genes: LogicGenes { entry_logic, exit_logic }
  execution_genes: ExecutionGenes { timeframe, symbol }
  risk_genes: RiskGenes { stop_loss, take_profit, position_size, leverage, direction }
  layers?: TimeframeLayerModel[]
  cross_layer_logic?: "AND" | "OR"
```

**SignalGene.condition**: 8 种 (lt, gt, le, ge, cross_above, cross_below, price_above, price_below)

**EvolutionTask** (30+ 字段): champion_dna, champion_metrics, continuous, population_count, strategy_threshold, exploration_efficiency

**BacktestResult**: equity_curve, signals, total_return, sharpe_ratio, dimension_scores, liquidated 等 18 字段

**其他**: Strategy, Dataset, ValidateResponse, RuleValidateResponse, ChartIndicatorsResponse, PaginatedResponse\<T\>

### types/chart.ts (48 行)

LegendGroup, BollingerBandData, MTFIndicatorData, OhlcvDataPoint, EquitySeries

### types/scene.ts (59 行)

SceneTypeInfo, SceneVerifyRequest, HorizonSummary, SceneTriggerDetail, SceneVerifyResponse

### types/strategy.ts (42 行)

IndicatorConfig, LabConfig, ScoreTemplate ("profit_first"|"steady"|"risk_first"|"custom")

## 业务工具库

### lib/constants.ts (337 行) -- 全局常量

| 常量 | 内容 |
|------|------|
| SYMBOL_OPTIONS | 4 个交易对 |
| TIMEFRAME_POOL_OPTIONS | 8 个时间周期 |
| TF_DURATION | 15 个周期->分钟映射 |
| TF_LAYER_ROLES | 4 种 MTF 角色配置 |
| INDICATOR_GROUPS | 6 组 37 个指标 (含中文标签) |
| CONDITION_OPTIONS | 14 种条件类型 |
| SCORE_TEMPLATE_LABELS | 3 个模板 |
| LEVERAGE_OPTIONS | 1x-10x |
| CHART_INDICATOR_DEFAULTS | EMA(10,20,50) + BOLL(20,2) + RSI(14) + VOL |
| MTF_TIMEFRAME_COLORS | 5 周期颜色 |

工具: `sortTimeframesLongestFirst(tfs)`, `isActiveStatus(status)`

### lib/dna-generator.ts (104 行)

`generateDnaFromValidation(when, then, pair, tf) -> DNA`。CONDITION_TYPE_MAP 12 种映射。默认参数: RSI(14), EMA(20), MACD(12,26,9)。

### lib/strategy-utils.ts (36 行)

- `getStrategyType(dna)`: 中文分类 (趋势/动量/波动率/成交量/混合)
- `getStrategyName(dna)`: "EMA趋势 做多 4H"

### lib/utils.ts (50 行)

`cn()` (tailwind-merge), `formatPercent`, `formatCurrency`, `formatNumber`, `formatDuration`, `formatDateTime`

## 通用工具

### utils/evolutionChart.ts (183 行)

5 趟扫描: (1) 映射+解析 diagnostics (2) 种群边界 (3) 累计最优 (4) 冠军变化 (5) 停滞计数。产出 ChartTransformResult。

### Diagnostics 解析 (evolutionChart.ts:50)

解析 `top3_summary` 格式 "best=85.2|pop=2|diag={...}"。支持 diversity 为数字或对象。

## 关键参数

### 评分模板权重 (constants.ts:232)

| 模板 | 年化 | 夏普 | 回撤 | 其他 |
|------|------|------|------|------|
| profit_first | 35% | 25% | 25% | 胜率15% |
| steady | 20% | 35% | 35% | 卡玛10% |
| risk_first | 10% | 30% | 40% | 卡玛20% |

### MTF 周期颜色 (constants.ts:272)

15m=蓝, 1h=绿, 4h=黄, 1d=紫, 3d=红

## 约定与规则

- 类型按领域划分: api.ts (snake_case 字段, 对应后端), chart.ts, scene.ts, strategy.ts (camelCase)
- 常量 `as const` 保证类型安全
- 工具按关注点分: lib/(全局) vs utils/(特定功能)
- 格式化函数处理边界: formatDuration 捕获异常返回 "-"
