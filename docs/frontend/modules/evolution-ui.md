# F2: 进化中心 UI

## 定位

`web/src/components/evolution/` (12 个组件) + `pages/Evolution.tsx` 构成进化中心页面——前端两大核心交互区之一。用户在这里配置、启动、监控遗传算法进化任务，查看实时进度和发现策略。

## 文件职责

| 文件 | 行数 | 职责 |
|------|------|------|
| `Evolution.tsx` (page) | 633 | 页面主组件：5 区布局、状态管理、WS 订阅 |
| `AutoConfigForm.tsx` | 498 | 自动模式配置表单（指标池/时间周期池/评分模板/高级参数） |
| `SeedConfigForm.tsx` | 699 | 种子模式配置表单（手动构建多层 DNA 结构） |
| `ProgressPanel.tsx` | 238 | 实时进度面板（代数进度/分数/冠军 DNA/暂停恢复控制） |
| `ScoreTrendChart.tsx` | 283 | Recharts 评分趋势图（best/cumulative/avg/target/冠军变化标记） |
| `StrategyList.tsx` | 548 | 发现策略排名列表（Top 3 高亮、展开详情、4 个操作按钮） |
| `StrategyDetail.tsx` | 276 | DNA 策略只读详情视图（多层层结构/信号条件/风控/评分维度） |
| `TaskDetailDrawer.tsx` | 399 | 历史任务详情抽屉（3 个 Tab: 概览/曲线/快照） |
| `HistoryTable.tsx` | 158 | 历史任务表格（行 hover 显示操作按钮） |
| `AlgorithmLog.tsx` | 120 | 专家模式变异日志面板（变异记录 + 种群多样性进度条） |
| `QuickPresets.tsx` | 76 | 快速预设按钮（RSI 超卖/EMA 趋势/多周期共振） |
| `SegmentedControl.tsx` | 64 | 自动/种子模式切换控件 |
| `BacktestDrawer.tsx` | 334 | 策略回测抽屉（K 线图 + 权益曲线 + 指标面板） |

## 页面布局

```
Evolution 页面 (5 区 GlassCard 布局)
  │
  ├─ Area 1: 配置区
  │   ├─ SegmentedControl (auto / seed 切换)
  │   ├─ AutoConfigForm (自动模式)
  │   └─ SeedConfigForm (种子模式)
  │
  ├─ Area 2: 进度区
  │   ├─ ProgressPanel (有活跃任务时)
  │   │   └─ 暂停/恢复/停止按钮
  │   ├─ ScoreTrendChart (评分趋势)
  │   └─ QuickPresets (无活跃任务时的空态)
  │
  ├─ Area 3: 发现策略区
  │   └─ StrategyList (排名列表)
  │       └─ 每行: 指标类型 + 5 个指标 + 展开详情
  │           └─ 操作: 查看 / 视觉验证 / 保存 / 种子进化
  │
  ├─ Area 4: 算法日志区
  │   └─ AlgorithmLog (专家模式，可折叠)
  │
  └─ Area 5: 历史任务区
      └─ HistoryTable (已完成/已停止的任务)
          └─ 操作: 查看详情 / 种子进化

浮动组件:
  ├─ TaskDetailDrawer (3 Tab: 概览/曲线/快照)
  └─ ConfirmDialog (停止任务确认)
```

## 状态管理

**没有用 Zustand**。全部状态是 `Evolution.tsx` 页面组件的本地 `useState`，通过 props 向下传递：

| 状态 | 类型 | 用途 |
|------|------|------|
| selectedMode | `"auto" \| "seed"` | 配置模式切换 |
| seedDna | `DNA \| null` | 种子 DNA（来自其他页面的路由 state） |
| expandedStrategyId | `string \| null` | 策略列表中展开的行 |
| stopTarget | `string \| null` | 确认停止的任务 ID |
| configCollapsed | `boolean` | 配置区折叠状态 |
| lastActiveTaskId | `string \| null` | 上次活跃任务 ID（优化查询） |
| mutationLog | `MutationEntry[]` | 变异日志数据 |
| detailTaskId | `string \| null` | 打开详情抽屉的任务 ID |

服务端状态全部通过 react-query 管理（任务列表/详情/历史/策略/数据源），自动缓存和失效。

## API 交互

### react-query Hooks（来自 `@/hooks/useEvolution`）

| Hook | 用途 |
|------|------|
| `useEvolutionTasks({ limit })` | 列出所有进化任务 |
| `useEvolutionTask(taskId)` | 获取单个任务详情 |
| `useEvolutionHistory(taskId)` | 逐代评分历史 |
| `useEvolutionWebSocket(taskId)` | WebSocket 实时推送订阅 |
| `useDiscoveredStrategies(taskId)` | 发现策略列表 |
| `useCreateEvolutionTask()` | 创建任务 (mutation) |
| `useStopEvolutionTask()` | 停止任务 (mutation) |
| `usePauseEvolutionTask()` | 暂停任务 (mutation) |
| `useResumeEvolutionTask()` | 恢复任务 (mutation) |

### WebSocket 消息类型

| type | 触发时机 | 前端处理 |
|------|----------|----------|
| `generation_complete` | 每代结束 | 更新 react-query 缓存 |
| `strategy_discovered` | 高分策略自动提取 | 刷新策略列表 |
| `population_started` | 连续进化新种群启动 | 更新进度显示 |
| `evolution_complete` | 进化结束 | 刷新任务状态 |

## 关键组件细节

### AutoConfigForm

13+ 个本地 state 管理：symbol, timeframePool, indicatorPool, scoreTemplate, populationSize, maxGenerations, targetScore, leverage, direction, dataStart, dataEnd, walkForwardEnabled, strategyThreshold。

时间周期池最多 4 个，按从长到短排序。指标池至少选 2 个才能提交。高级参数区可折叠。

### SeedConfigForm

支持最多 3 个时间周期层，每层可动态增删条件。`inferRole()` 根据时间周期排序自动分配角色（趋势过滤/确认/入场信号）。`useRef(prevSeedRef)` 检测 seedDna 变化并重置表单。

### StrategyList

**两个 StrategyDetail 实现**: `StrategyDetail.tsx` 导出共享组件被 `TaskDetailDrawer` 使用，`StrategyList.tsx` 内有一个本地 `StrategyDetail` 函数渲染展开行——两者逻辑重叠但有差异。

Top 3 策略用琥珀色高亮边框。每行 4 个操作按钮：查看详情 / 视觉验证（导航到 `/lab`） / 保存到策略库 / 作为种子进化。

### ScoreTrendChart

用 Recharts `ComposedChart`，数据转换委托给 `@/utils/evolutionChart`。包含：best score 线、cumulative best 线、avg score 线、target 参考线、种群边界标记、冠军变化散点。

### BacktestDrawer

**当前未被 Evolution 页面使用**——视觉验证改用导航到 `/lab` 路由实现。此组件可能是独立功能或计划中的集成。包含 K 线图（`KlineChart`）、权益曲线（动态 import `lightweight-charts`）、指标面板。

## 涉及文件

| 文件 | 核心内容 |
|------|---------|
| `pages/Evolution.tsx` | 5 区页面布局、本地状态、WS 订阅 |
| `components/evolution/*.tsx` | 12 个子组件 |
| `hooks/useEvolution.ts` | react-query hooks 封装 |
| `services/evolution.ts` | API 调用封装 |
| `utils/evolutionChart.ts` | 评分趋势图数据转换 |
| `lib/strategy-utils.ts` | 策略名称/类型推断 |
| `lib/constants.ts` | TF_LAYER_ROLES 等常量 |
