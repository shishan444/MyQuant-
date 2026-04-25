# F2: 进化中心 UI

## 定位

`web/src/components/evolution/` + `pages/Evolution.tsx` 构成进化中心页面。用户在这里配置、启动、监控遗传算法进化任务，查看实时进度和发现策略。前端两大核心交互区之一。

## 文件清单

| 文件 | 职责 |
|------|------|
| `pages/Evolution.tsx` | 页面容器 (5 区域: 配置/进度/策略/日志/历史) |
| `components/evolution/SegmentedControl.tsx` | auto/seed 模式切换 |
| `AutoConfigForm.tsx` | 自动探索配置表单 |
| `SeedConfigForm.tsx` | 种子探索配置表单 |
| `ProgressPanel.tsx` | 进化进度面板 |
| `ScoreTrendChart.tsx` | 评分趋势图 |
| `StrategyList.tsx` | 发现策略列表 |
| `AlgorithmLog.tsx` | 变异算法日志 |
| `HistoryTable.tsx` | 历史探索任务表 |
| `TaskDetailDrawer.tsx` | 任务详情抽屉 |
| `QuickPresets.tsx` | 3 个快速预设 |

## 关键链路

### 数据流

```
useEvolutionTasks -> activeTask = 第一个活跃任务
  -> useEvolutionTask(activeTaskId) -> 详细数据
  -> useEvolutionWebSocket(activeTaskId) -> 实时更新
  -> useEvolutionHistory(historyTaskId) -> 分数数据
  -> useDiscoveredStrategies(historyTaskId) -> 发现策略
```

### 创建任务 (Auto 模式)

```
AutoConfigForm.tsx:130 handleSubmit -> onSubmit
Evolution.tsx:186 handleStartAuto -> createTask.mutateAsync
  services/evolution.ts:24 POST /api/evolution/tasks
成功: configCollapsed=true + mutationLog=[]
```

### 创建任务 (Seed 模式)

```
SeedConfigForm.tsx:237 handleSubmit -> 构建 DNA (layers 转 TimeframeLayerModel[])
Evolution.tsx:231 handleStartSeed -> createTask.mutateAsync
```

### WebSocket 实时更新 (useEvolution.ts:108)

```
连接 ws://host/ws/evolution/{taskId}
消息: population_started / strategy_discovered / generation_complete / evolution_complete
generation_complete: qc.setQueryData 直接更新缓存
断线: 3s 后重连
批量刷新: scheduleInvalidation 2s 防抖
```

### 路由间通信

Lab -> Evolution: `navigate("/evolution", { state: { seedDna } })`
Evolution 接收: `location.state.seedDna` (Evolution.tsx:62)

## 关键机制

### 配置自动折叠 (Evolution.tsx:168)

任务活跃时 configCollapsed=true，完成后自动展开。

### DNA 构建 (SeedConfigForm.tsx:237)

将用户填写的多层条件转为 DNA 对象。layers 按 TF_ORDER 排序，最短周期为 execution_genes.timeframe。

### 进化图表 5 趟扫描 (utils/evolutionChart.ts:90)

(1) 映射原始数据+解析 diagnostics (2) 检测种群边界 (3) 累计最优 (4) 冠军变化 (5) 停滞计数。

### 快速预设 (QuickPresets.tsx:13)

3 个: RSI超卖反弹, EMA趋势跟踪, 多周期趋势共振。

## 接口定义

| Props | 说明 |
|-------|------|
| AutoConfigFormProps | disabled, isPending, symbolOptions?, onSubmit(config) -- 11 字段 |
| SeedConfigFormProps | disabled, isPending, seedDna?, onSubmit(config) -- initialDna |
| ProgressPanelProps | task, onPause, onResume, onStop |
| StrategyListProps | strategies, expandedId, onToggleExpand, onSeedEvolve, onVisualVerify |

## 关键参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| symbol | "BTCUSDT" | |
| timeframePool | ["4h"] | 最多 4 个周期 |
| indicatorPool | 所有 21 个 | 至少 2 个 |
| scoreTemplate | "profit_first" | |
| populationSize | 15 | |
| maxGenerations | 200 | |
| targetScore | 80 | |
| strategyThreshold | 80 | 自动提取阈值 |

## 约定与规则

- 组件使用 memo: HistoryRow, StrategyRow
- 周期排序: sortTimeframesLongestFirst
- 变异颜色: AlgorithmLog.tsx:19 OPERATION_COLORS 10 种
- 状态判断: isActiveStatus (lib/constants.ts)
- 任务互斥: 创建前检查 activeTask
