# B13 模拟交易系统

## 逻辑

模拟交易系统把进化产出的策略 DNA 投入实时 Bar-by-Bar 交易模拟。它是回测引擎的"实时版"——回测用 vectorbt 一次性跑完所有 Bar，模拟交易用纯 Python 状态机逐 Bar 处理，支持暂停/恢复/停止，并实时推送持仓变化。

系统由 3 层组成：
1. **PositionManager** (`core/trading/position.py`, 348 行)：纯 Python 仓位状态机，镜像回测引擎 `order_func_nb` 的逻辑，含滑点成本
2. **TradingRunner** (`core/trading/runner.py`, 494 行)：后台守护线程，轮询 DB 获取 pending 任务，通过 PM 执行，持久化状态，含回放阶段信号 shift(1) 和渐进式 checkpoint
3. **API + WS** (`api/routes/trading.py` 200 行 + `api/routes/ws.py`)：REST CRUD/控制 + dna_json 校验 + 分页 total + WebSocket 实时推送

数据流：`策略库 DNA -> POST /api/trading/tasks (dna_json 校验) -> TradingRunner -> Parquet 历史 (shift1 回放 + 500bar checkpoint) + Futures 实时 (无 shift) -> PositionManager (含滑点) -> DB 持久化 (累计统计) + WS 推送 -> 前端展示`

## 链路

### 创建任务

```
前端 POST /api/trading/tasks {dna_json, symbol, timeframe, ...}
  -> trading.py:63 create_task()
    -> StrategyDNA.from_json(body.dna_json)  [校验，失败返回 422]
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
        3. PositionManager(dna, init_cash, fee, slippage=0.0005)
        4. _restore_pm_state(pm, task_row)  [runner.py:359]
           - 始终恢复累计统计 (_prior_trades/pnl/wins/losses)
           - 仅在 position_side 非 None 时恢复 balance + position
        5. _load_data() 加载 Parquet [runner.py:332]
        6. compute_all_indicators() + dna_to_signal_set()
        7. 信号 shift(1) 防前瞻偏差:
           replay_entries = sig_set.entries.shift(1).fillna(False)
           replay_exits/exits/adds/reduces/direction 同理
        8. 历史回放: for i in range(start_idx, len(df)):
             pm.process_bar(...) -> events (使用 shifted 信号)
             _log_events() -> save_paper_trade()
             每 500 bar: _save_pm_state() + _push_position_update() (checkpoint)
        9. _save_pm_state(pm, task_id, df) [runner.py:378]
           - unrealized_pnl: 使用实际 df close price
           - last_bar_close: 使用实际 df close price
           - 统计: 使用 PM 累计属性 (prior + current)
        10. 实时循环: while not controller.stop_requested:
              _fetch_and_update() -> 新 Bar
              逐 Bar process_bar() (使用原始信号，不 shift)
              _save_pm_state() + _push_position_update()
              controller._stop_event.wait(poll_wait)
```

### 停止/暂停/恢复

```
POST /stop  -> trading.py:119
  -> controller.request_stop() (协作中断)
  -> update_paper_trading_task(status="stopped", stop_reason="user_stop")

POST /pause -> trading.py:142
  -> controller.request_stop() (中断执行循环)
  -> update_paper_trading_task(status="paused")

POST /resume -> trading.py:163
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

### 滑点成本模型

PM 在所有交易操作中应用滑点作为额外成本（不修改 entry_price，避免影响 SL/TP 计算）：

| 操作 | 滑点公式 | 影响 |
|------|---------|------|
| 开仓 (Entry) | `slippage * quantity * price` | balance 额外扣除 |
| 平仓 (Close) | `slippage * quantity * price` | balance 和 pnl 额外扣除 |
| 加仓 (Add) | `slippage * add_qty * price` | balance 额外扣除 |
| 减仓 (Reduce) | `slippage * reduce_qty * price` | balance 和 pnl 额外扣除 |

slippage 默认值 `0.0005` (0.05%)，与回测引擎默认值一致（`engine.py:400`）。

### 累计统计恢复机制

PM 通过 `_prior_*` 字段保存历史 session 的统计数据，确保 resume 后统计不丢失：

```python
# PositionManager 属性（自动合并 prior + current session）
total_trades = _prior_trades + len(closed_trades)
total_pnl    = _prior_pnl + sum(t.pnl for t in closed_trades)
win_count    = _prior_wins + sum(1 for t in closed_trades if t.pnl > 0)
loss_count   = _prior_losses + sum(1 for t in closed_trades if t.pnl <= 0)
```

恢复时 `_restore_pm_state()` 从 DB 加载 `total_trades/total_pnl/win_count/loss_count` 写入 `_prior_*` 字段。`_save_pm_state()` 使用 PM 的属性而非直接计算 `closed_trades`，确保统计跨 session 累计。

### 信号时序对齐

回测引擎对信号做 `shift(1)` 防前瞻偏差。模拟交易系统在不同阶段使用不同策略：

| 阶段 | 信号处理 | 原因 |
|------|---------|------|
| 历史回放 | `shift(1).fillna(False)` | 与回测引擎对齐，防止前瞻偏差 |
| 实时交易 | 原始信号，不 shift | 信号产生后立即执行是正确行为 |

回放阶段的 `shift(1)` 对所有信号类型（entries/exits/adds/reduces/entry_direction）统一应用。

### 回放渐进式保存

历史回放 10000+ Bar 时，每 500 根 Bar 保存一次 checkpoint：

```
if (i - start_idx + 1) % 500 == 0:
    self._save_pm_state(pm, task_id, df)
    self._push_position_update(pm, task_id)
```

崩溃恢复后从最后 checkpoint 的 `last_bar_time` 继续（`_find_replay_start` 找到下一个未处理的 Bar）。

### 与回测引擎的关键差异

| 维度 | 回测引擎 (Numba) | PositionManager (Python) |
|------|-----------------|--------------------------|
| 执行时机 | 信号 shift(1) 后执行 | 回放阶段 shift(1)，实时阶段立即执行 |
| Funding | 事后统一计算 | 每 Bar 实时扣除 |
| 滑点 | 由 vectorbt 参数控制 | 显式计算，0.0005 固定 |
| 余额跟踪 | vectorbt 内部 | 显式 balance/margin |
| 统计恢复 | 不需要 | 通过 _prior_* 字段跨 session 累计 |
| 性能 | JIT 编译，~1000x | 纯 Python，单线程够用 |

### 状态持久化

`_save_pm_state()` (runner.py:378) 每次处理完新 Bar 后调用，将 PM 状态写入 DB：
- `last_close` 从 `df.iloc[-1]["close"]` 获取（不依赖 equity snapshot 推导）
- `unrealized_pnl` 使用实际 close price 计算
- 统计字段使用 PM 的累计属性（含 prior session 数据）

`_restore_pm_state()` (runner.py:359) 在任务恢复时调用：
- **始终恢复**累计统计（`_prior_trades/pnl/wins/losses`）
- 仅在 `position_side != None` 时恢复 balance + position
- flat 状态下 balance 保持 init_cash（DB 中的 balance 值不被恢复）

## 接口

### REST API

| 端点 | 方法 | 请求 | 响应 | 状态码 |
|------|------|------|------|--------|
| `/api/trading/tasks` | POST | `PaperTradingTaskCreate` | `PaperTradingTaskResponse` | 201 / 422 (dna_json 无效) |
| `/api/trading/tasks` | GET | `?status=&limit=50&offset=0` | `PaperTradingTaskListResponse` | 200 |
| `/api/trading/tasks/{id}` | GET | - | `PaperTradingTaskResponse` | 200/404 |
| `/api/trading/tasks/{id}/stop` | POST | - | `PaperTradingTaskResponse` | 200/400 |
| `/api/trading/tasks/{id}/pause` | POST | - | `PaperTradingTaskResponse` | 200/400 |
| `/api/trading/tasks/{id}/resume` | POST | - | `PaperTradingTaskResponse` | 200/400 |
| `/api/trading/tasks/{id}/trades` | GET | `?limit=100` | `PaperTradeListResponse` | 200/404 |
| `/api/trading/runner-status` | GET | - | `{is_alive, active_task_id}` | 200 |

### PositionManager 核心接口

```python
class PositionManager:
    def __init__(self, dna, init_cash=100000, fee=0.001, slippage=0.0)
    def process_bar(self, bar_time, bar_high, bar_low, bar_close,
                    entry_signal=False, exit_signal=False,
                    add_signal=False, reduce_signal=False,
                    direction=1.0) -> List[dict]

    # 状态
    balance: float           # 当前余额
    position: Position|None  # 当前持仓
    closed_trades: List[ClosedTrade]  # 本次 session 的交易
    equity_snapshots: List[EquitySnapshot]

    # 累计统计 (prior + current session)
    @property total_trades -> int
    @property total_pnl -> float
    @property win_count -> int
    @property loss_count -> int
```

### WebSocket 协议 (`/ws/trading/{task_id}`)

```
Server -> Client:
  {"type": "subscribed", "task_id": "..."}
  {"type": "task_snapshot", "task_id": "...", "status": "...", ...}
  {"type": "task_started", "task_id": "..."}
  {"type": "position_update", "task_id": "...", "position": {...},
   "balance": ..., "equity": ..., "unrealized_pnl": ...,
   "total_trades": ..., "total_pnl": ...}

Client -> Server:
  {"type": "ping"}  ->  {"type": "pong"}
```

## 参数

### PositionManager 构造参数

| 参数 | 默认值 | 来源 | 设计意图 |
|------|--------|------|---------|
| `init_cash` | 100,000 | API 请求 | 与回测默认一致，方便对比 |
| `fee` | 0.001 (0.1%) | API 请求 | 币安合约 taker fee |
| `slippage` | 0.0005 (0.05%) | runner 硬编码 | 与回测引擎默认值一致（engine.py:400），作为额外成本不修改 entry_price |
| `leverage` | 1 | DNA risk_genes | 1x=无杠杆，回测引擎一致 |
| `position_size` | 0.3 | DNA risk_genes | 每次开仓/加仓使用 30% 余额 |
| `stop_loss` | 0.05 | DNA risk_genes | 5% 止损 |
| `take_profit` | 0.10 | DNA risk_genes | 10% 止盈 |

### TradingRunner 参数

| 参数 | 默认值 | 设计意图 |
|------|--------|---------|
| `poll_interval` | 2.0s | 轮询 DB 的间隔，平衡响应速度和 CPU 占用 |
| 实时轮询间隔 | `min(bar_interval, 60)s` | 4h 周期每 60s 检查一次新数据，1m 周期每 60s 检查 |
| 回放 checkpoint | 每 500 Bar | 平衡持久化开销和崩溃恢复粒度 |
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
| total_trades, total_pnl, win_count, loss_count | INT/REAL | 累计交易统计（跨 session） |
| last_bar_time, last_bar_close | 可空 | 最后处理的 Bar（close 为实际价格） |
| started_at, stopped_at, heartbeat_at | TEXT ISO | 时间戳 |

**paper_trade** (schema_version 10, 同上):

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK AUTOINCREMENT | 自增 ID |
| task_id | TEXT FK | 关联任务 |
| bar_time, side, action, price, quantity | TEXT/REAL | 交易细节 |
| pnl, fee_paid | REAL 可空 | 盈亏和手续费（含滑点成本） |
| reason | TEXT 可空 | 平仓原因 (signal/sl/tp/liquidation) |

## 约定

- **TaskController + threading.Event**：协作式中断，不 kill 线程。`check_stop()` 在每根 Bar 前调用，抛出 `TaskStopRequested` 异常
- **WS 推送桥接**：`asyncio.run_coroutine_threadsafe()` 把同步 runner 线程的推送桥接到 FastAPI 的 async 事件循环
- **Stop 双信号**：用户点停止时，同时 `controller.request_stop()` + `update_paper_trading_task(status="stopped")`，确保即使 runner 线程阻塞也能生效
- **崩溃恢复**：`recover_stale_trading_tasks()` 在 API 启动时把所有 running 任务标记为 stopped (stop_reason="crash_recovery")
- **交易记录排序**：`list_paper_trades()` 返回 DESC order（最新的在前），前端展示最近交易
- **数据源**：使用 Binance Futures API (`client.futures_historical_klines()`)，与回测使用的 spot API 返回相同 12-field 格式
- **dna_json API 校验**：创建任务时 `StrategyDNA.from_json()` 校验格式，无效返回 422（避免延迟到 runner 拾取时才发现）
- **分页 total**：`list_tasks` 使用 `count_paper_trading_tasks()` 返回实际总数，不是当前页数量
- **统计不可丢失**：`_save_pm_state()` 始终使用 PM 的累计属性（含 `_prior_*`），resume 时 `_restore_pm_state()` 恢复 prior 统计
- **滑点不修改 entry_price**：滑点作为额外成本从 balance 扣除，保持 entry_price 干净以确保 SL/TP 计算不受影响
