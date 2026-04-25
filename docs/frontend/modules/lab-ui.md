# F3: 策略实验室 UI

## 定位

`web/src/components/lab/` + `pages/Lab.tsx` 构成策略实验室页面。三个互斥模式面板: 假设验证(规则构建器)、策略回测、场景验证。前端两大核心交互区之一。

## 文件清单

| 文件 | 职责 |
|------|------|
| `pages/Lab.tsx` | 页面容器 (~600 行) |
| `components/lab/` | 22 个子组件 (按 index.ts 统一导出) |

组件按功能分类:
- **条件输入**: RuleConditionGroup, ConditionInput 等
- **结果显示**: TriggerTable, DistributionChart, ValidationConclusion
- **场景验证**: SceneModePanel, SceneConfig 等
- **回测**: BacktestModePanel, BacktestMetricsPanel, EquityCurveChart

## 关键链路

### 规则验证

```
RuleConditionGroup 收集条件
  -> useValidateRules (hooks/useValidation.ts:15)
  -> POST /api/validate/rules
  -> RuleValidateResponse: buy/sell signals, trades, win_rate, total_return
  -> TriggerTable + DistributionChart + ValidationConclusion
```

### 回测

```
BacktestModePanel 触发
  -> POST /api/strategies/backtest (timeout 60s)
  -> BacktestResult: equity_curve, signals, total_return, sharpe_ratio
  -> BacktestMetricsPanel + EquityCurveChart
```

### K 线图表数据

```
useChartIndicators (hooks/useChartIndicators.ts:65)
  查询 1: ohlcvOptions -> OHLCV (staleTime 60s, limit 10000)
  查询 2: chartIndicatorOptions -> 指标 (依赖 candleData 非空)
  合并: candleData + chartIndicators + chartBollData + volumeData + macdData + kdjData
```

### 保存策略

```
SaveStrategyDialog -> useCreateStrategy -> POST /api/strategies
```

### 跳转进化

```
navigate("/evolution", { state: { seedDna } })
```

## 关键机制

### DNA 生成 (lib/dna-generator.ts:64)

从 WHEN/THEN 条件生成 DNA。WHEN -> entry_trigger, THEN -> exit_trigger。CONDITION_TYPE_MAP (12 种映射): touch->price_above, spike->gt, breakout->cross_above 等。默认参数: RSI(14), EMA(20), MACD(12,26,9)。风险硬编码: SL=5%, TP=10%, position=30%。

### 策略类型推导 (lib/strategy-utils.ts:18)

根据 entry_trigger 的 indicator 查 INDICATOR_TYPE_MAP 得类型 (趋势/动量/波动/量价)。名称: `{indicator}{type} {direction} {timeframe}`。

## 接口定义

| 接口 | 说明 |
|------|------|
| RuleCondition | logic(IF/AND/OR), timeframe, subject, action, target |
| RuleValidateRequest | pair, timeframe, start, end, entry_conditions, exit_conditions |
| RuleValidateResponse | buy_signals, sell_signals, trades, win_rate, total_return_pct |
| UseChartIndicatorsParams | symbol, timeframe, dateRange, subChartType?, enabled? |
| UseChartIndicatorsResult | candleData, chartIndicators, chartBollData, volumeData, macdData, kdjData |

## 关键参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| symbol | "BTCUSDT" | |
| timeframe | "1h" | |
| initCash | 100000 | |
| fee | 0.001 | |
| slippage | 0.0005 | |
| OHLCV limit | 10000 | 单次查询上限 |
| 回测 timeout | 60s | |

## 约定与规则

- 所有组件通过 `index.ts` 统一导出
- 条件类型: 中文标签 + 英文值 (label: "金叉", value: "cross_above")
- 图表指标从 Zustand chart-settings 读取，通过 useChartIndicators 封装
- 场景验证使用独立 scene 服务
