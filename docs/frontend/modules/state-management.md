# F6: 状态管理

## 定位

`web/src/stores/` (Zustand) + `web/src/hooks/` (react-query) 构成前端状态层。Zustand 管理客户端 UI 状态（持久化到 localStorage），react-query 管理服务端数据（自动缓存/重验证）。

## Zustand Stores

### app.ts (25 行) -- 全局 UI

```
useAppStore (persist key: "myquant-app")
  state: sidebarCollapsed
  actions: toggleSidebar(), setSidebarCollapsed(bool)
```

### chart-settings.ts (149 行) -- 图表指标

```
useChartSettings (persist key: "chart-indicator-settings")
  state: emaList[], boll{enabled,period,std,color}, rsi{enabled,period,ob,os}, vol{enabled,position}
  actions: addEma, removeEma, updateEma, reorderEma, setBoll, setRsi, setVol, resetToDefaults
  derived: getEmaPeriods(), getBollParams(), getIndicatorParams() -> ChartIndicatorConfig
```

默认: EMA(10,20,50), BOLL(20,2.0), RSI(14,70,30), VOL(overlay)。

### lab.ts (53 行) -- 实验室配置

```
useLabStore (无持久化)
  state: config {datasetId, symbol:"BTCUSDT", timeframe:"1h", indicators:[], scoreTemplate:"profit_first", initCash:100000, fee:0.001, slippage:0.0005}
  actions: setConfig, addIndicator, removeIndicator, updateIndicator, resetConfig
```

## React Query Hooks

### useEvolution.ts (226 行) -- 最大最复杂

导出 10 个 hook/工具:
- **查询**: useEvolutionTasks, useEvolutionTask, useEvolutionHistory, useDiscoveredStrategies
- **变更**: useCreateEvolutionTask, useStopEvolutionTask, usePauseEvolutionTask, useResumeEvolutionTask
- **WebSocket**: useEvolutionWebSocket(taskId) -- 连接 /ws/evolution/{taskId}, 处理 4 种消息, 2s debounce, 断线 3s 重连
- **Key 工厂**: evolutionKeys.all / .tasks(filters) / .task(id) / .history(id) / .discovered(id)

### 其他 hooks

| Hook | 说明 |
|------|------|
| useDatasets (84行) | 8 个 hook, availableSources staleTime 5min |
| useStrategies (65行) | 6 个 hook |
| useValidation (24行) | 2 个 mutation |
| useScene (20行) | 1 个 mutation, 0 触发器时 toast info |
| queries/chartQueries (101行) | ohlcvOptions(staleTime 60s), chartIndicatorOptions |
| useChartIndicators (184行) | 组合 hook, 串联 OHLCV + 指标查询 |

## 关键机制

### Query Key 工厂模式

每个 hook 导出 `xxxKeys` 层级结构: `["domain", "action", params]`。

### Mutation 统一模式

onSuccess + qc.invalidateQueries 刷新列表 + toast.success/error。

### Chart Indicators 查询链

从 Zustand chart-settings 读取配置 -> 构建参数 -> 查询 OHLCV (staleTime 60s) -> 查询指标 (依赖 candleData) -> 转换为图表数据。

## 关键参数

| 参数 | 值 | 说明 |
|------|-----|------|
| EMA 颜色轮 | 6 色 | #3B82F6, #10B981, #F59E0B, #8B5CF6, #EF4444, #EC4899 |
| Chart 默认 | EMA 10/20/50, BOLL 20/2, RSI 14/70/30 | |
| Lab 默认 | initCash 100000, fee 0.001, slippage 0.0005 | |
| OHLCV limit | 10000 | |

## 约定与规则

- Store: `create()(persist(...))` 模式，`partialize` 仅选择需持久化字段
- React Query key: 层级 `["domain", "action", params]`
- Mutation: 统一 toast 反馈 (sonner)
- useEvolutionWebSocket: mounted ref 防卸载后更新
- useScene: total_triggers===0 时 toast info
