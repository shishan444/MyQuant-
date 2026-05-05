# F8: 模拟交易页面

## 定位

模拟交易系统前端 -- 在 `web/src/pages/Trading.tsx` + `hooks/useTrading.ts` + `services/trading.ts` + `components/trading/`(5 组件) 的组合中，提供模拟交易任务的创建入口（策略库导航 + 确认对话框）、实时监控（Master-Detail 布局 + 双通道刷新）、指标看板、权益曲线和交易记录查看。

## 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `pages/Trading.tsx` | 476 | 页面组件：route state -> CreateTaskDialog 确认 -> Master-Detail 布局 + 删除确认 |
| `hooks/useTrading.ts` | 270 | React Query hooks：7 个查询 + 5 个变更 + WebSocket 实时推送 |
| `services/trading.ts` | 166 | API 服务函数 + 8 个本地类型定义 |
| `components/trading/TradingChart.tsx` | 51 | K 线图 + 买卖标记（基于 KlineChart + useChartIndicators） |
| `components/trading/EquityCurve.tsx` | 91 | 权益曲线面积图（Recharts AreaChart + 渐变填充） |
| `components/trading/MetricsDashboard.tsx` | 83 | 6 个指标卡片网格（Total PnL/Return/Win Rate/Profit Factor/Max Drawdown/Trades） |
| `components/trading/CreateTaskDialog.tsx` | 79 | 任务创建确认对话框（策略名 + 市场 + 初始资金预览） |
| `components/trading/RunnerStatusBadge.tsx` | 20 | 后台 Runner 在线/离线状态指示灯 |

## 逻辑

### 数据流

```
Strategies.tsx (策略库) -- navigate("/trading", {state: {dna, symbol, timeframe, strategyName}}) -->
Trading.tsx (页面)
  |-- useEffect: 检测 location.state.dna -> setPendingCreate() + setDialogOpen(true)
  |-- CreateTaskDialog: 用户确认 -> handleConfirmCreate() -> createTask.mutate()
  |-- useTradingTasks() ───> services/trading.ts listTradingTasks() ───> GET /api/trading/tasks
  |-- useRunnerStatus() ───> GET /api/trading/runner-status (10s 轮询)
  |-- useTradingWebSocket(activeTaskId) ───> WS /ws/trading/{taskId}
  |       |
  |       v  (position_update / task_started)
  |   scheduleInvalidation() (2s debounce)
  |       |
  |       v
  |   queryClient.invalidateQueries() ───> 触发 refetch (tasks/task/trades/equity/metrics)
  |
  |-- TaskListItem (sidebar) ───> useDeleteTradingTask() (仅 stopped 任务显示删除按钮)
  |-- TaskDetailPanel (right) ───> useTradingTrades(100) + useTradingEquity + useTradingMetrics
```

### Master-Detail 布局

```
┌──────────────────┬─────────────────────────────────────────────┐
│  Sidebar (w-72)  │  Detail Panel (flex-1)                      │
│                  │                                              │
│  Tasks header    │  Task header + status/position badges       │
│  RunnerStatus    │  + controls (Pause/Resume/Stop)             │
│                  │                                              │
│  TaskListItem 1  │  MetricsDashboard (6 cards)                 │
│  TaskListItem 2  │                                              │
│  TaskListItem 3  │  TradingChart (K-line + trade markers)      │
│  ...             │                                              │
│                  │  EquityCurve (Recharts area)                 │
│                  │                                              │
│                  │  Trade History table (up to 50 rows)        │
└──────────────────┴─────────────────────────────────────────────┘
```

自动选择逻辑：`selectedTaskId ?? tasks.find(t => t.status === "running")?.task_id ?? null`

### 双通道刷新机制

页面同时运行两种数据刷新机制：

1. **WebSocket 推送**（主动）：连接 `/ws/trading/{taskId}`，收到 `position_update` 或 `task_started` 消息后，触发 2 秒防抖的 `invalidateQueries()`，覆盖 5 个 query key（tasks/task/trades/equity/metrics）
2. **轮询**（兜底）：`tradingTasksOptions()` 在有 running/pending 任务时每 5 秒轮询；`tradingTaskOptions()` 在单个任务活跃时每 3 秒轮询；`runnerStatusOptions()` 每 10 秒轮询

WebSocket 不是直接更新状态，而是作为"失效触发器"让 React Query 重新走 HTTP 请求刷新数据。`useTradingWebSocket` 返回 `boolean` 表示连接状态，用于渲染 WS 指示灯。

### 策略库 -> 模拟交易创建链路（含确认对话框）

```
Strategies.tsx 策略行 "模拟交易" 按钮 (Zap icon)
  -> handlePaperTrade(strategy)
    -> navigate("/trading", {state: {dna, symbol, timeframe, strategyName}})
      -> Trading.tsx useEffect
        -> setPendingCreate({dna, symbol, timeframe, strategyName})
        -> setDialogOpen(true)
          -> CreateTaskDialog 弹出，显示策略名/市场/初始资金
            -> 用户点击 "Create Task"
              -> handleConfirmCreate()
                -> createTask.mutate({dna_json, symbol, timeframe, strategy_name})
                  -> POST /api/trading/tasks
        -> window.history.replaceState({}, "")  // 清除 route state 防重复创建
```

`dna` 字段从 Strategy 对象获取（可能是 object），在 Trading.tsx 中通过 `typeof state.dna === "string" ? state.dna : JSON.stringify(state.dna)` 统一转为 string。

### 页面渲染分支

| 条件 | 渲染内容 |
|------|---------|
| 任务列表加载中 | 居中 "Loading..." 文本 |
| 任务列表为空 | EmptyState 组件 + "Go to Strategies" 按钮（`navigate("/strategies")`） |
| 有任务 | Master-Detail 布局：左侧 w-72 任务列表 + 右侧详情面板 |

### 任务列表项 (TaskListItem)

每个 TaskListItem 展示：
- 头部：策略名 + symbol/timeframe/leverage + 状态 Badge
- 底部：当前余额 + 收益率百分比（颜色编码：profit/loss/muted）
- 已停止任务：显示删除按钮（Trash2 icon），点击弹出 AlertDialog 确认

### 任务详情面板 (TaskDetailPanel)

| 区域 | 内容 |
|------|------|
| Header | 策略名 + 状态 Badge + 持仓方向 Badge + WS 指示灯 + 操作按钮 |
| MetricsDashboard | 6 个 StatCard（Total PnL / Return / Win Rate / Profit Factor / Max Drawdown / Trades） |
| TradingChart | K 线图 + volume 副图 + 买卖信号标记（基于 lightweight-charts createSeriesMarkers） |
| EquityCurve | 权益曲线面积图（Recharts AreaChart + 渐变填充，盈利绿色/亏损红色） |
| Trade History | 交易记录表格（最多 50 行），列：Time/Side/Action/Price/Qty/PnL/Reason |

操作按钮仅在 running/paused/pending 状态显示：
- running: Pause + Stop
- paused: Resume + Stop
- 所有按钮在 mutation pending 时 disabled

### 删除流程

```
TaskListItem (stopped 任务) 删除按钮
  -> setDeleteTarget(taskId)
    -> AlertDialog 弹出（"This will permanently delete..."）
      -> 用户点击 "Delete"
        -> deleteMut.mutate(deleteTarget) [useDeleteTradingTask, 顶层声明]
        -> 清除 selectedTaskId（如果匹配）
        -> setDeleteTarget(null)
```

## 链路

### WebSocket 连接生命周期

```
useTradingWebSocket(taskId) (useTrading.ts:198-270)
  1. 构建 WS URL: ws://host/ws/trading/{taskId}
     - 协议自动检测 (wss/ws)
     - Host 从 VITE_WS_URL 或 window.location.host 获取
  2. connect() 创建 WebSocket 实例
  3. onopen: setIsConnected(true)
  4. onmessage: 解析 JSON，type 为 position_update 或 task_started 时触发 scheduleInvalidation()
  5. onclose: setIsConnected(false), 3 秒后自动重连
  6. onerror: 调用 ws.close() 触发 onclose -> 重连
  7. cleanup: 关闭 WS、清除引用、清除重连定时器
  返回: isConnected (boolean)
```

## 机制

### Query Key Factory

```typescript
tradingKeys = {
  all:         ["trading"] as const,
  tasks:       () => [...tradingKeys.all, "tasks"] as const,
  task:        (id: string) => [...tradingKeys.all, "task", id] as const,
  trades:      (id: string) => [...tradingKeys.all, "trades", id] as const,
  equity:      (id: string) => [...tradingKeys.all, "equity", id] as const,
  metrics:     (id: string) => [...tradingKeys.all, "metrics", id] as const,
  runnerStatus: () => [...tradingKeys.all, "runnerStatus"] as const,
}
```

与 evolution、strategies 的 hook 使用相同的 key factory 模式，确保缓存隔离和精准失效。

### 条件轮询

`refetchInterval` 使用回调函数检查 `query.state.data`：
- `tradingTasksOptions()`：遍历 tasks 数组，有 running/pending 任务时返回 5000ms，否则返回 false
- `tradingTaskOptions(taskId)`：检查单个任务状态，活跃时返回 3000ms
- `runnerStatusOptions()`：无条件 10000ms 轮询

### Badge 映射

Trading.tsx 内部定义了两个静态映射（英文标签 + Tailwind className）：

```typescript
POSITION_BADGE_MAP = {
  long:  { label: "Long",  className: "text-profit border-profit/30" },
  short: { label: "Short", className: "text-loss border-loss/30" },
  flat:  { label: "Flat",  className: "text-text-muted border-border-default" },
}
STATUS_BADGE_MAP = {
  pending: { label: "Pending", className: "text-accent-gold border-accent-gold/30" },
  running: { label: "Running", className: "text-profit border-profit/30" },
  paused:  { label: "Paused",  className: "text-accent-gold border-accent-gold/30" },
  stopped: { label: "Stopped", className: "text-loss border-loss/30" },
}
```

未知状态 fallback 到 `stopped` 的样式。不存在 `completed` 状态。

### 类型定义

`services/trading.ts` 内联定义所有交易相关类型：

| 类型 | 字段数 | 说明 |
|------|--------|------|
| `TradingTask` | 28 | 完整任务状态（含持仓、余额、统计、时间戳） |
| `TradingTaskList` | 2 | `{ tasks, total }` |
| `PaperTrade` | 10 | 单笔交易记录（含 fee_paid, reason） |
| `PaperTradeList` | 2 | `{ trades, total }` |
| `CreateTradingTaskParams` | 9 | 仅 `dna_json` 必填，其余可选（含 `strategy_name`） |
| `EquitySnapshot` | 7 | 权益快照（id, task_id, timestamp, equity, balance, unrealized_pnl, position_side） |
| `EquitySnapshotList` | 2 | `{ snapshots, total }` |
| `TradingMetrics` | 12 | 交易指标（total_return, total_return_pct, win_rate, profit_factor, max_drawdown 等） |

## 接口

### Service API 函数

| 函数 | 方法 | 端点 | 返回类型 |
|------|------|------|---------|
| `listTradingTasks(params?)` | GET | `/api/trading/tasks` | `TradingTaskList` |
| `getTradingTask(taskId)` | GET | `/api/trading/tasks/{taskId}` | `TradingTask` |
| `createTradingTask(params)` | POST | `/api/trading/tasks` | `TradingTask` |
| `stopTradingTask(taskId)` | POST | `/api/trading/tasks/{taskId}/stop` | `TradingTask` |
| `pauseTradingTask(taskId)` | POST | `/api/trading/tasks/{taskId}/pause` | `TradingTask` |
| `resumeTradingTask(taskId)` | POST | `/api/trading/tasks/{taskId}/resume` | `TradingTask` |
| `getTradingTrades(taskId, limit?)` | GET | `/api/trading/tasks/{taskId}/trades` | `PaperTradeList` |
| `getTradingRunnerStatus()` | GET | `/api/trading/runner-status` | `{ is_alive, active_task_id }` |
| `getTradingEquity(taskId)` | GET | `/api/trading/tasks/{taskId}/equity` | `EquitySnapshotList` |
| `getTradingMetrics(taskId)` | GET | `/api/trading/tasks/{taskId}/metrics` | `TradingMetrics` |
| `deleteTradingTask(taskId)` | DELETE | `/api/trading/tasks/{taskId}` | `{ deleted: boolean }` |

### React Query Hooks

| Hook | 类型 | 说明 |
|------|------|------|
| `useTradingTasks()` | Query | 任务列表，条件轮询 5s |
| `useTradingTask(taskId)` | Query | 单个任务，条件轮询 3s |
| `useTradingTrades(taskId, limit?)` | Query | 交易记录，无轮询 |
| `useTradingEquity(taskId)` | Query | 权益快照，无轮询 |
| `useTradingMetrics(taskId)` | Query | 交易指标，无轮询 |
| `useRunnerStatus()` | Query | Runner 状态，10s 轮询 |
| `useCreateTradingTask()` | Mutation | 创建任务 |
| `useStopTradingTask()` | Mutation | 停止任务 |
| `usePauseTradingTask()` | Mutation | 暂停任务 |
| `useResumeTradingTask()` | Mutation | 恢复任务 |
| `useDeleteTradingTask()` | Mutation | 删除任务（仅 stopped 可删） |
| `useTradingWebSocket(taskId)` | Effect | WS 连接 + 2s 防抖失效，返回 `boolean` (isConnected) |

### 导出的 Query Options

| 函数 | 说明 |
|------|------|
| `tradingTasksOptions()` | 任务列表 query options |
| `tradingTaskOptions(taskId)` | 单任务 query options |
| `tradingTradesOptions(taskId, limit)` | 交易记录 query options |
| `tradingEquityOptions(taskId)` | 权益快照 query options |
| `tradingMetricsOptions(taskId)` | 交易指标 query options |
| `runnerStatusOptions()` | Runner 状态 query options |

## 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| WS 重连延迟 | 3000ms | WebSocket 断开后自动重连间隔 |
| WS 失效防抖 | 2000ms | 收到 WS 消息后触发 invalidateQueries 的延迟 |
| 任务列表轮询 | 5000ms | 有活跃任务时的列表刷新间隔 |
| 单任务轮询 | 3000ms | 有活跃任务时的详情刷新间隔 |
| Runner 状态轮询 | 10000ms | Runner 在线/离线检测间隔 |
| 交易记录 limit | 50 (hook 默认) / 100 (TaskDetailPanel 传参) | 获取最近交易记录数量，显示截取前 50 条 |
| 侧边栏宽度 | w-72 (288px) | 任务列表固定宽度 |

## 约定

- **类型内联**：交易相关类型定义在 `services/trading.ts` 而非 `types/` 目录，与 discovery.ts 模式一致（领域服务自带类型）
- **WS 作为失效触发器**：WebSocket 不直接更新 React 状态，而是触发 React Query 缓存失效（覆盖 5 个 query key），复用现有 HTTP 请求管道
- **Route state 单次消费**：`window.history.replaceState({}, "")` 在创建任务后立即清除 route state，防止刷新页面重复创建
- **确认对话框**：从策略库导航过来的创建请求不自动执行，弹出 CreateTaskDialog 让用户确认后再创建
- **Mutation 状态管理**：所有 mutation 按钮（Pause/Resume/Stop/Delete）在 pending 时 disabled，防止重复点击
- **删除确认**：删除操作通过 AlertDialog 二次确认，删除按钮仅对 stopped 状态的任务显示
- **Error Boundary**：Trading 页面被 `components/ErrorBoundary.tsx` 包裹，崩溃时显示重试 UI，不影响其他页面
- **停止 propagation**：任务列表项操作按钮使用 `e.stopPropagation()` 防止按钮点击触发列表项选中
- **策略库按钮**：Strategies.tsx 使用 Zap 图标，hover 时 accent-gold 颜色
- **空状态导航**：Trading 页面空状态的 "Go to Strategies" 按钮调用 `navigate("/strategies")` 跳转
