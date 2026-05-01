# B13 模拟交易系统

## 逻辑

模拟交易系统把进化产出的策略 DNA 投入实时 Bar-by-Bar 交易模拟。它是回测引擎的"实时版"——回测用 vectorbt 一次性跑完所有 Bar，模拟交易用纯 Python 状态机逐 Bar 处理，支持暂停/恢复/停止，并实时推送持仓变化。

系统由 3 层组成：
1. **PositionManager** (`core/trading/position.py`, 317 行)：纯 Python 仓位状态机，镜像回测引擎 `order_func_nb` 的逻辑
2. **TradingRunner** (`core/trading/runner.py`, 469 行)：后台守护线程，轮询 DB 获取 pending 任务，通过 PM 执行，持久化状态
3. **API + WS** (`api/routes/trading.py` 191 行 + `api/routes/ws.py`)：REST CRUD/控制 + WebSocket 实时推送

数据流：`策略库 DNA -> POST /api/trading/tasks -> TradingRunner -> Parquet 历史 + Futures 实时 -> PositionManager 逐 Bar -> DB 持久化 + WS 推送 -> 前端展示`

## 链路

### 创建任务

```
前端 POST /api/trading/tasks {dna_json, symbol, timeframe, ...}
  -> trading.py:62 create_task()
    -> uuid.uuid4().hex[:12] 生成 task_id
    -> db_ext.save_paper_trading_task() 写入 paper_trading_task 表
    -> 返回 PaperTradingTaskResponse (status="pending")
```

### Runner 拾取并执行

```
TradingRunner.run() [runner.py:113]
  -> while not stop: _tick()
    -> _find_pending_task() [runner.py:141] 查 DB
    -> _run_task() [runner.py:162]
      -> _execute_task() [runner.py:189]
        1. update_paper_trading_task(status="running")
        2. StrategyDNA.from_json(dna_json)
        3. PositionManager(dna, init_cash, fee)
        4. _restore_pm_state(pm, task_row)  [runner.py:339]
        5. _load_data() 加载 Parquet [runner.py:312]
        6. compute_all_indicators() + dna_to_signal_set()
        7. 历史回放: for i in range(start_idx, len(df)):
             pm.process_bar(...) -> events
             _log_events() -> save_paper_trade()
        8. _save_pm_state(pm, task_id, df) [runner.py:352]
        9. 实时循环: while not controller.stop_requested:
             _fetch_and_update() -> 新 Bar
             逐 Bar process_bar() + _save_pm_state()
             controller._stop_event.wait(poll_wait)
```

### 停止/暂停/恢复

```
POST /stop  -> trading.py:110
  -> controller.request_stop() (协作中断)
  -> update_paper_trading_task(status="stopped", stop_reason="user_stop")

POST /pause -> trading.py:133
  -> controller.request_stop() (中断执行循环)
  -> update_paper_trading_task(status="paused")

POST /resume -> trading.py:154
  -> update_paper_trading_task(status="pending")
  -> Runner 下一轮 tick 重新拾取
```

## 机制/算法

### PositionManager 处理优先级

每根 Bar 的处理顺序（镜像 `engine.py order_func_nb`）：

1. **清算检查** (leverage > 1)：`equity < init_cash * (1 - 0.9 / leverage^2)` 时触发
2. **SL/TP**：使用 `bar_high`/`bar_low`（非 close），SL 先于 TP
   - Long SL: `bar_low <= entry * (1 - sl)`
   - Long TP: `bar_high >= entry * (1 + tp)`
   - Short SL: `bar_high >= entry * (1 + sl)`
   - Short TP: `bar_low <= entry * (1 - tp)`
3. **Exit 信号**
4. **Entry 信号**（仅 position == None，单向模式）
5. **Reduce 信号**（不改变 entry_price，按比例释放 margin）
6. **Add 信号**（加权平均价：`(old_ep * old_qty + price * add_qty) / new_qty`）
7. **Funding 扣除**：`cost_rate = 0.001 * (hours/8) * ((leverage-1)/leverage)`
8. **快照**：`_snapshot()` 记录 equity 快照用于权益曲线

### 与回测引擎的关键差异

| 维度 | 回测引擎 (Numba) | PositionManager (Python) |
|------|-----------------|--------------------------|
| 执行时机 | 信号 shift(1) 后执行 | 当前 Bar 立即执行 |
| Funding | 事后统一计算 | 每 Bar 实时扣除 |
| 余额跟踪 | vectorbt 内部 | 显式 balance/margin |
| 性能 | JIT 编译，~1000x | 纯 Python，单线程够用 |

### 状态持久化

`_save_pm_state()` (runner.py:352) 每次处理完新 Bar 后调用，将 PM 状态写入 DB：
- 有持仓时：`position_side/entry/quantity/margin/funding` + `unrealized_pnl` + `balance` + `last_bar_time/close` + 交易统计
- 无持仓时：`position_side=NULL` + `balance` + 交易统计

`_restore_pm_state()` (runner.py:339) 在任务恢复时调用：
- 仅在 `position_side != None` 时恢复 balance + position
- flat 状态下 balance 保持 init_cash（不恢复 DB 记录的值）

## 接口

### REST API

| 端点 | 方法 | 请求 | 响应 | 状态码 |
|------|------|------|------|--------|
| `/api/trading/tasks` | POST | `PaperTradingTaskCreate` | `PaperTradingTaskResponse` | 201 |
| `/api/trading/tasks` | GET | `?status=&limit=50&offset=0` | `PaperTradingTaskListResponse` | 200 |
| `/api/trading/tasks/{id}` | GET | - | `PaperTradingTaskResponse` | 200/404 |
| `/api/trading/tasks/{id}/stop` | POST | - | `PaperTradingTaskResponse` | 200/400 |
| `/api/trading/tasks/{id}/pause` | POST | - | `PaperTradingTaskResponse` | 200/400 |
| `/api/trading/tasks/{id}/resume` | POST | - | `PaperTradingTaskResponse` | 200/400 |
| `/api/trading/tasks/{id}/trades` | GET | `?limit=100` | `PaperTradeListResponse` | 200/404 |
| `/api/trading/runner-status` | GET | - | `{is_alive, active_task_id}` | 200 |

### PositionManager 核心方法

```python
class PositionManager:
    def __init__(self, dna, init_cash=100000, fee=0.001, slippage=0.0)
    def process_bar(self, bar_time, bar_high, bar_low, bar_close,
                    entry_signal=False, exit_signal=False,
                    add_signal=False, reduce_signal=False,
                    direction=1.0) -> List[dict]

    # 属性
    balance: float           # 当前余额
    position: Position|None  # 当前持仓
    closed_trades: List[ClosedTrade]
    equity_snapshots: List[EquitySnapshot]
```

### WebSocket 协议 (`/ws/trading/{task_id}`)

```
Server -> Client:
  {"type": "subscribed", "task_id": "..."}
  {"type": "task_snapshot", "task_id": "...", "status": "...", ...}
  {"type": "task_started", "task_id": "..."}
  {"type": "position_update", "task_id": "...", "position": {...},
   "balance": ..., "equity": ..., "unrealized_pnl": ..., "total_trades": ..., "total_pnl": ...}

Client -> Server:
  {"type": "ping"}  ->  {"type": "pong"}
```

## 参数

### PositionManager 构造参数

| 参数 | 默认值 | 来源 | 设计意图 |
|------|--------|------|---------|
| `init_cash` | 100,000 | API 请求 | 与回测默认一致，方便对比 |
| `fee` | 0.001 (0.1%) | API 请求 | 币安合约 taker fee |
| `slippage` | 0.0 | 构造参数 | 预留但未使用，模拟交易用 close 价执行 |
| `leverage` | 1 | DNA risk_genes | 1x=无杠杆，回测引擎一致 |
| `position_size` | 0.3 | DNA risk_genes | 每次开仓/加仓使用 30% 余额 |
| `stop_loss` | 0.05 | DNA risk_genes | 5% 止损 |
| `take_profit` | 0.10 | DNA risk_genes | 10% 止盈 |

### TradingRunner 参数

| 参数 | 默认值 | 设计意图 |
|------|--------|---------|
| `poll_interval` | 2.0s | 轮询 DB 的间隔，平衡响应速度和 CPU 占用 |
| 实时轮询间隔 | `min(bar_interval, 60)s` | 4h 周期每 60s 检查一次新数据，1m 周期每 60s 检查 |
| Funding 费率 | 0.001/8h | 币安永续合约费率 |

### DB 表

**paper_trading_task** (schema_version 10, DDL 在 `db_ext.py:_create_paper_trading_tables()`):

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | TEXT PK | 12 位 hex |
| status | TEXT | pending/running/paused/stopped |
| dna_json | TEXT | 策略 DNA 序列化 |
| symbol, timeframe | TEXT | 交易对和周期 |
| initial_cash, fee, leverage, direction | REAL/INT | 交易参数 |
| position_side, position_entry, position_quantity, position_margin, position_funding | 可空 | 持仓状态 |
| balance, unrealized_pnl | REAL | 余额和未实现盈亏 |
| total_trades, total_pnl, win_count, loss_count | INT/REAL | 交易统计 |
| last_bar_time, last_bar_close | 可空 | 最后处理的 Bar |
| started_at, stopped_at, heartbeat_at | TEXT ISO | 时间戳 |

**paper_trade** (schema_version 10, 同上):

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK AUTOINCREMENT | 自增 ID |
| task_id | TEXT FK | 关联任务 |
| bar_time, side, action, price, quantity | TEXT/REAL | 交易细节 |
| pnl, fee_paid | REAL 可空 | 盈亏和手续费 |
| reason | TEXT 可空 | 平仓原因 (signal/sl/tp/liquidation) |

## 约定

- **TaskController + threading.Event**：协作式中断，不 kill 线程。`check_stop()` 在每根 Bar 前调用，抛出 `TaskStopRequested` 异常
- **WS 推送桥接**：`asyncio.run_coroutine_threadsafe()` 把同步 runner 线程的推送桥接到 FastAPI 的 async 事件循环
- **Stop 双信号**：用户点停止时，同时 `controller.request_stop()` + `update_paper_trading_task(status="stopped")`，确保即使 runner 线程阻塞也能生效
- **崩溃恢复**：`recover_stale_trading_tasks()` 在 API 启动时把所有 running 任务标记为 stopped (stop_reason="crash_recovery")
- **交易记录排序**：`list_paper_trades()` 返回 DESC order（最新的在前），前端展示最近交易
- **数据源**：使用 Binance Futures API (`client.futures_historical_klines()`)，与回测使用的 spot API 返回相同 12-field 格式
