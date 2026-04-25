# F6: 状态管理

## 定位

`web/src/stores/` (Zustand) + `web/src/hooks/` (react-query) 构成前端的状态层。Zustand 管理客户端 UI 状态（持久化到 localStorage），react-query 管理服务端数据（自动缓存/重验证）。

## Zustand Stores

### app.ts (25 行) -- 全局 UI 状态

```
useAppStore (persist key: "myquant-app")
  state: sidebarCollapsed: boolean
  actions: toggleSidebar(), setSidebarCollapsed(bool)
```

只持久化 `sidebarCollapsed`。

### chart-settings.ts (149 行) -- 图表指标配置

```
useChartSettings (persist key: "chart-indicator-settings")
  state:
    emaList: EmaEntry[]     // {period, color, enabled}
    boll: BollConfig        // {enabled, period, std, color}
    rsi: RsiConfig          // {enabled, period, overbought, oversold}
    vol: VolConfig          // {enabled, position: "overlay"|"separate"}
  actions:
    addEma(period), removeEma(index), updateEma(index, updates), reorderEma(from, to)
    setBoll(updates), setRsi(updates), setVol(updates), resetToDefaults()
  derived:
    getEmaPeriods(), getBollParams(), getIndicatorParams() -> ChartIndicatorConfig
```

默认配置：EMA(10,20,50)、BOLL(20,2.0)、RSI(14,70,30)、VOL(overlay)。

### lab.ts (53 行) -- 实验室配置

```
useLabStore (无持久化)
  state: config: LabConfig
    {datasetId, symbol: "BTCUSDT", timeframe: "1h", indicators: [],
     scoreTemplate: "profit_first", initCash: 100000, fee: 0.001, slippage: 0.0005}
  actions: setConfig(updates), addIndicator(ind), removeIndicator(id),
           updateIndicator(id, updates), resetConfig()
```

## react-query Hooks

### useEvolution.ts (226 行) -- 最大最复杂的 hook

导出 10 个 hook/工具：

**查询**：`useEvolutionTasks`, `useEvolutionTask`, `useEvolutionHistory`, `useDiscoveredStrategies`

**变更**：`useCreateEvolutionTask`, `useStopEvolutionTask`, `usePauseEvolutionTask`, `useResumeEvolutionTask`

**WebSocket**：`useEvolutionWebSocket(taskId)` -- 核心实时更新机制
- 连接 `/ws/evolution/{taskId}`
- 处理 4 种消息：population_started, strategy_discovered, generation_complete, evolution_complete
- 实时更新 react-query 缓存（无需重新请求）
- 2 秒 debounce 批量 invalidation
- 断线自动重连

**Query Key 工厂**：`evolutionKeys.all / .tasks(filters) / .task(id) / .history(id) / .discovered(id)`

### useDatasets.ts (84 行)

导出 8 个 hook：`useDatasets`, `useDataset`, `useOhlcv`, `useImportCsv`, `useImportCsvBatch`, `useDeleteDataset`, `useAvailableSources` (staleTime: 5min)。

成功变更后自动 invalidation + toast 提示。

### useStrategies.ts (65 行)

导出 6 个 hook：`useStrategies`, `useStrategy`, `useRunBacktest`, `useCreateStrategy`, `useDeleteStrategy`。

### useValidation.ts (24 行)

导出 2 个 mutation：`useValidateHypothesis`, `useValidateRules`。

### useScene.ts (20 行)

导出 1 个 mutation：`useVerifyScene`。0 触发器时 toast info 提示。

### queries/chartQueries.ts (101 行)

独立查询配置文件：
- `ohlcvOptions(symbol, tf, dateRange?)` -- staleTime: 60s, limit: 10000
- `chartIndicatorOptions(symbol, tf, subChartType, params, options?)` -- staleTime: 60s

### useChartIndicators.ts (184 行)

组合 hook：串联两个查询（先 OHLCV，再指标）。
- 从 Zustand `useChartSettings` 读取配置
- 构建 API 参数（ema_periods, boll_enabled, rsi_enabled 等）
- 转换响应为图表数据：candleData, chartIndicators, chartBollData, volumeData, macdData, kdjData

支持的子图类型：volume, macd, rsi, kdj。

## 涉及文件

| 文件 | 行数 | 核心内容 |
|------|------|---------|
| `web/src/stores/app.ts` | 25 | 全局 UI 状态 |
| `web/src/stores/chart-settings.ts` | 149 | 图表指标配置 |
| `web/src/stores/lab.ts` | 53 | 实验室配置 |
| `web/src/hooks/useEvolution.ts` | 226 | 进化相关 hooks + WebSocket |
| `web/src/hooks/useDatasets.ts` | 84 | 数据集 hooks |
| `web/src/hooks/useStrategies.ts` | 65 | 策略 hooks |
| `web/src/hooks/useValidation.ts` | 24 | 验证 hooks |
| `web/src/hooks/useScene.ts` | 20 | 场景验证 hook |
| `web/src/hooks/queries/chartQueries.ts` | 101 | 图表查询配置 |
| `web/src/hooks/useChartIndicators.ts` | 184 | 图表指标组合 hook |
