# F7: 类型与工具

## 定位

`web/src/types/` (TypeScript 接口定义)、`web/src/lib/` (业务工具)、`web/src/utils/` (通用工具) 构成前端的基础设施层。

## 类型定义

### types/api.ts (407 行) -- 核心接口

与后端 API 的类型契约，定义了 35+ 个接口：

**DNA 相关**：`SignalGene`, `LogicGenes`, `ExecutionGenes`, `RiskGenes`, `TimeframeLayerModel`, `DNA`
- `RiskGenes.direction` 接受 "long" / "short" / "mixed"
- `SignalGene.condition.type` 支持 8 种条件类型

**策略相关**：`Strategy`, `BacktestResult`, `StrategyMetrics`
- `BacktestResult` 包含 18 个字段（result_id 到 liquidated）
- `StrategyMetrics` 包含 11 个可选指标（annual_return 到 r_squared）

**进化相关**：`EvolutionTask` (25+ 字段), `EvolutionHistoryRecord`, `GenerationUpdate`, `DiscoveredStrategy`, `EvolvedStrategy`, `MutationRecord`
- `EvolutionTaskStatus`: union type (pending/running/paused/stopped/completed)
- `GenerationUpdate`: WebSocket 消息类型，包含 population_diversity, champion_dna 等

**数据相关**：`Dataset`, `OhlcvData`, `AvailableSource`, `ChartIndicatorsResponse`
- `Dataset.quality_status`: "complete" / "warning" / "error" / "unknown"

**验证相关**：`ValidateRequest`, `ValidateResponse`, `RuleValidateRequest`, `RuleValidateResponse`
- `ValidateResponse` 包含 match_rate, triggers, distribution, percentiles, concentration 等

**分页**：`PaginatedResponse<T>`, `StrategyListResponse`, `EvolutionTaskListResponse`, `DatasetListResponse`

### types/chart.ts (48 行)

图表相关接口：`OhlcvDataPoint`, `ChartThemeConfig`, `LegendItem`, `EquitySeries`, `BollingerBandData`, `MTFIndicatorData`, `LegendGroup`

### types/scene.ts (59 行)

场景验证接口：`SceneTypeInfo`, `SceneVerifyRequest`, `HorizonSummary`, `SceneTriggerDetail`, `SceneVerifyResponse`

### types/strategy.ts (42 行)

实验室配置接口：`IndicatorConfig`, `LabConfig`
- `ScoreTemplate`: "profit_first" | "steady" | "risk_first" | "custom"
- `INDICATOR_OPTIONS`: 11 个指标选项
- `TIMEFRAME_OPTIONS`: 6 个时间周期选项

## 业务工具库

### lib/constants.ts (337 行) -- 全局常量

| 常量 | 内容 |
|------|------|
| SYMBOL_OPTIONS | 4 个交易对 (BTC/ETH/BNB/SOL vs USDT) |
| TIMEFRAME_POOL_OPTIONS | 8 个时间周期 |
| TF_DURATION | 14 个周期的分钟数映射 |
| TF_LAYER_ROLES | 4 种 MTF 角色配置 |
| INDICATOR_GROUPS | 6 组 ~40 个指标（含中文标签） |
| CONDITION_OPTIONS | 14 种条件类型 |
| SCORE_TEMPLATE_LABELS | 3 个评分模板 |
| OPTIMIZE_TARGETS | 3 个优化目标配置 |
| LEVERAGE_OPTIONS | 1x-10x |
| DIRECTION_OPTIONS | long/short/mixed |
| CHART_INDICATOR_DEFAULTS | EMA(10,20,50) + BOLL(20,2) + RSI(14) + VOL |
| MTF_TIMEFRAME_COLORS | 5 个周期的颜色映射 |

工具函数：`sortTimeframesLongestFirst(tfs)`, `isActiveStatus(status)`

### lib/dna-generator.ts (104 行)

`generateDnaFromValidation(when, then, pair, timeframe) -> DNA`

从 Lab 页面的 WHEN/THEN 条件生成 DNA 结构。有损转换：将前端 ConditionInput 映射为 DNA SignalGene。`CONDITION_TYPE_MAP` 定义 13 种映射。

默认参数：RSI(14), EMA(20), MACD(12,26,9)。

### lib/strategy-utils.ts (36 行)

- `getStrategyType(dna)`: 返回中文分类（趋势/动量/波动率/成交量/混合）
- `getStrategyName(dna)`: 生成展示名如 "EMA趋势 做多 4H"

### lib/utils.ts (50 行)

通用格式化工具：
- `cn(...inputs)`: Tailwind merge (clsx + twMerge)
- `formatPercent(value)`: "+5.0%" / "-3.2%"
- `formatCurrency(value)`: "$100,000"
- `formatNumber(value, decimals)`: 固定小数
- `formatDuration(start, end)`: "X秒"/"X分钟"/"X小时"
- `formatDateTime(t)`: 中文 locale 日期时间

## 通用工具

### utils/evolutionChart.ts (183 行)

进化评分图表数据转换：

- `parseDiagnostics(top3Summary?)`: 解析管道分隔字符串 "best=85.2|pop=2|diag={...}"
- `transformChartData(records)`: 5 步转换
  1. 映射原始记录 + 解析诊断
  2. 检测种群边界（代数重置点）
  3. 计算累计最佳分数
  4. 追踪冠军变更（全时间最佳改进）
  5. 计算停滞计数（在边界处重置）

产出 `ChartTransformResult`: data points, champion changes, population boundaries, stats。

## 涉及文件

| 文件 | 行数 | 核心内容 |
|------|------|---------|
| `web/src/types/api.ts` | 407 | 35+ API 接口定义 |
| `web/src/types/chart.ts` | 48 | 图表类型 |
| `web/src/types/scene.ts` | 59 | 场景验证类型 |
| `web/src/types/strategy.ts` | 42 | 实验室配置类型 |
| `web/src/lib/constants.ts` | 337 | 全局常量 + 枚举 |
| `web/src/lib/dna-generator.ts` | 104 | 条件 -> DNA 转换 |
| `web/src/lib/strategy-utils.ts` | 36 | 策略分类和命名 |
| `web/src/lib/utils.ts` | 50 | 格式化工具 |
| `web/src/utils/evolutionChart.ts` | 183 | 进化图表数据转换 |
