# F8: 模拟交易页面

## 定位

模拟交易系统前端 -- 在 `web/src/pages/Trading.tsx` 页面组件 + `hooks/useTrading.ts` 数据层 + `services/trading.ts` API 层 三文件组合中，提供模拟交易任务的创建入口、实时监控、持仓展示和交易记录查看。

## 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `pages/Trading.tsx` | 408 | 页面组件：route state 自动创建任务 + 任务卡片网格 + 任务详情面板 + 交易记录表格 |
| `hooks/useTrading.ts` | 183 | React Query hooks：查询/变更 + WebSocket 实时推送 |
| `services/trading.ts` | 122 | API 服务函数 + 本地类型定义（30+ 字段 TradingTask 类型） |

## 逻辑

### 数据流

```
Strategies.tsx (策略库) -- navigate("/trading", {state: {dna, symbol, timeframe, strategyName}}) -->
Trading.tsx (页面)
  |-- useEffect: 检测 location.state.dna -> createTask.mutate() -> POST /api/trading/tasks
  |-- useTradingTasks() ───> services/trading.ts listTradingTasks() ───> GET /api/trading/tasks
  |-- useTradingWebSocket(activeTaskId) ───> WS /ws/trading/{taskId}
  |       |
  |       v  (position_update / task_started)
  |   scheduleInvalidation() (2s debounce)
  |       |
  |       v
  |   queryClient.invalidateQueries() ───> 触发 refetch
  |
  |-- TaskCard ───> useStopTradingTask / usePauseTradingTask / useResumeTradingTask
  |-- TaskDetail ───> useTradingTrades(taskId, 20)
```

### 双通道刷新机制

页面同时运行两种数据刷新机制：

1. **WebSocket 推送**（主动）：连接 `/ws/trading/{taskId}`，收到 `position_update` 或 `task_started` 消息后，触发 2 秒防抖的 `invalidateQueries()`
2. **轮询**（兜底）：`tradingTasksOptions()` 在有 running/pending 任务时每 5 秒轮询；`tradingTaskOptions()` 在单个任务活跃时每 3 秒轮询

WebSocket 不是直接更新状态，而是作为"失效触发器"让 React Query 重新走 HTTP 请求刷新数据。

### 策略库 -> 模拟交易创建链路

```
Strategies.tsx 策略行 "模拟交易" 按钮 (Zap icon)
  -> handlePaperTrade(strategy)
    -> navigate("/trading", {state: {dna, symbol, timeframe, strategyName}})
      -> Trading.tsx useEffect
        -> createTask.mutate({dna_json, symbol, timeframe, strategy_name})
          -> POST /api/trading/tasks
        -> window.history.replaceState({}, "")  // 清除 route state 防重复创建
```

`dna` 字段从 Strategy 对象获取（可能是 object），在 Trading.tsx 中通过 `typeof state.dna === "string" ? state.dna : JSON.stringify(state.dna)` 统一转为 string。

### 页面渲染分支

| 条件 | 渲染内容 |
|------|---------|
| 任务列表加载中 | 居中 "加载中..." 文本 |
| 任务列表为空 | EmptyState 组件 + "前往策略库" 按钮（`navigate("/strategies")`） |
| 有任务 | 响应式任务卡片网格（1/2/3 列）+ 选中任务的详情面板 |

### 任务卡片 (TaskCard)

每个任务卡片展示：
- 头部：策略名 + symbol/timeframe/leverage + 状态 Badge + 持仓方向 Badge
- 余额行：当前余额 + 收益率百分比（颜色编码）
- 进度条：高度 1.5，颜色跟随趋势方向，值为 `abs(returnRate) * 100` 上限 100
- 统计行：交易次数 + 胜/负次数
- 操作按钮（仅 running/paused 状态）：暂停/恢复切换 + 停止按钮

自动选择逻辑：未手动选择时，自动选中第一个 running 状态的任务。

## 链路

### 从策略库创建交易任务

```
Strategies.tsx (策略行 "模拟交易" 按钮)
  -> handlePaperTrade(strategy) [Strategies.tsx:455]
    -> navigate("/trading", {state: {dna, symbol, timeframe, strategyName}})
      -> Trading.tsx useEffect [Trading.tsx:73-91]
        -> createTask.mutate({dna_json, symbol, timeframe, strategy_name})
          -> services/trading.ts createTradingTask()
            -> POST /api/trading/tasks
        -> window.history.replaceState({}, "")
```

### 暂停/恢复/停止

```
TaskCard 操作按钮 -> usePauseTradingTask() / useResumeTradingTask() / useStopTradingTask()
  -> trading.ts pauseTradingTask(taskId) 等
    -> POST /api/trading/tasks/{id}/pause | /resume | /stop
  -> onSuccess: invalidateQueries(tradingKeys.task + tradingKeys.tasks)
```

### WebSocket 连接生命周期

```
useTradingWebSocket(taskId) (useTrading.ts:124-182)
  1. 构建 WS URL: ws://host/ws/trading/{taskId}
     - 协议自动检测 (wss/ws)
     - Host 从 VITE_WS_URL 或 window.location.host 获取
  2. connect() 创建 WebSocket 实例
  3. onmessage: 解析 JSON，type 为 position_update 或 task_started 时触发 scheduleInvalidation()
  4. onclose: 3 秒后自动重连 (setTimeout(connect, 3000))
  5. onerror: 调用 ws.close() 触发 onclose -> 重连
  6. cleanup: 关闭 WS、清除引用、清除重连定时器
```

### 交易记录查看

```
TaskDetail 组件 (Trading.tsx:288-328)
  -> useTradingTrades(taskId, 20)
    -> GET /api/trading/tasks/{taskId}/trades?limit=20
  -> 渲染表格: 时间/方向/动作/价格/数量/盈亏/原因
```

## 机制

### Query Key Factory

```typescript
tradingKeys = {
  all:    ["trading"],
  tasks:  ["trading", "tasks"],
  task:   ["trading", "task", id],
  trades: ["trading", "trades", id],
}
```

与 evolution、strategies 的 hook 使用相同的 key factory 模式，确保缓存隔离和精准失效。

### 条件轮询

`refetchInterval` 使用回调函数检查 `query.state.data`：
- `tradingTasksOptions()`：遍历 tasks 数组，有 running/pending 任务时返回 5000ms，否则返回 false
- `tradingTaskOptions(taskId)`：检查单个任务状态，活跃时返回 3000ms

### 本地类型定义

`services/trading.ts` 内联定义了所有交易相关类型，未放在 `types/` 目录：

| 类型 | 字段数 | 说明 |
|------|--------|------|
| `TradingTask` | 28 | 完整任务状态（含持仓、余额、统计、时间戳） |
| `TradingTaskList` | 2 | `{ tasks, total }` |
| `PaperTrade` | 9 | 单笔交易记录 |
| `PaperTradeList` | 2 | `{ trades, total }` |
| `CreateTradingTaskParams` | 10 | 仅 `dna_json` 必填，其余可选（含 `strategy_name`） |

### Badge 映射

Trading.tsx 内部定义了两个静态映射：

```typescript
POSITION_BADGE_MAP = { long: "多", short: "空", flat: "空仓" }
STATUS_BADGE_MAP   = { pending: "等待中", running: "运行中", paused: "已暂停", stopped: "已停止", completed: "已完成" }
```

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

### React Query Hooks

| Hook | 类型 | 说明 |
|------|------|------|
| `useTradingTasks()` | Query | 任务列表，条件轮询 5s |
| `useTradingTask(taskId)` | Query | 单个任务，条件轮询 3s |
| `useTradingTrades(taskId, limit?)` | Query | 交易记录，无轮询 |
| `useCreateTradingTask()` | Mutation | 创建任务（Strategies -> Trading 自动创建使用） |
| `useStopTradingTask()` | Mutation | 停止任务 |
| `usePauseTradingTask()` | Mutation | 暂停任务 |
| `useResumeTradingTask()` | Mutation | 恢复任务 |
| `useTradingWebSocket(taskId)` | Effect | WS 连接 + 2s 防抖失效 |

## 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| WS 重连延迟 | 3000ms | WebSocket 断开后自动重连间隔 |
| WS 失效防抖 | 2000ms | 收到 WS 消息后触发 invalidateQueries 的延迟 |
| 任务列表轮询 | 5000ms | 有活跃任务时的列表刷新间隔 |
| 单任务轮询 | 3000ms | 有活跃任务时的详情刷新间隔 |
| 交易记录 limit | 50 (hook 默认) / 20 (TaskDetail 传参) | 获取最近交易记录数量 |

## 约定

- **类型内联**：交易相关类型定义在 `services/trading.ts` 而非 `types/` 目录，与 discovery.ts 模式一致（领域服务自带类型）
- **WS 作为失效触发器**：WebSocket 不直接更新 React 状态，而是触发 React Query 缓存失效，复用现有 HTTP 请求管道
- **Route state 单次消费**：`window.history.replaceState({}, "")` 在创建任务后立即清除 route state，防止刷新页面重复创建
- **停止 propagation**：任务卡片操作按钮使用 `e.stopPropagation()` 防止按钮点击触发卡片选中
- **策略库按钮**：Strategies.tsx 使用 Zap 图标，hover 时 accent-gold 颜色，与回测按钮（Play, profit 绿色）视觉区分
- **空状态导航**：Trading 页面空状态的"前往策略库"按钮调用 `navigate("/strategies")` 跳转
