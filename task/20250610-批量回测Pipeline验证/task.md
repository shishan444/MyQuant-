# 批量回测 Pipeline 验证脚本

## 任务目标
通过 Python 脚本验证批量回测已切换到 DecisionPipeline（模拟交易引擎），
确认回测结果的可信度足以支撑真实交易环境验证。

## 初始理解
- 刚完成 _BatchBacktestProcessor 从 BacktestEngine 到 ReplayRunner 的切换
- 关键变化：收盘价成交 → 开盘价成交，无挂单 → 限价单，百分比止损 → ATR动态止损
- 需要验证：切换后的代码是否真的走了 DecisionPipeline 路径，执行行为是否符合预期
- 验证关乎是否可以进入真实环境交易，必须严谨

---

## 研究第 1 轮

### 核心发现

**1. ReplayRunner 可观测事件体系完整**

DecisionPipeline 通过 VirtualAccount 在每一步产生结构化事件，events_log 中包含 7 种事件类型：
- `position_opened`（side, entry_price, quantity, fee_paid, slippage_paid）
- `position_closed`（side, entry_price, exit_price, quantity, pnl, exit_reason, fee_paid, slippage_paid）
- `position_added`（side, price, quantity_added, new_entry_price, fee_paid, slippage_paid）
- `position_reduced`（side, price, quantity_reduced, pnl, fee_paid, slippage_paid）
- `open_skipped`（reason: "insufficient_balance"）
- `add_skipped`（reason: "already_at_target" | "insufficient_balance"）

exit_reason 枚举：`sl` | `tp` | `signal` | `liquidation` | `reduce_full`

这些事件足以验证所有关键执行行为。

**2. 与 BacktestEngine 存在 12 个可验证的行为差异**

| # | 差异 | BacktestEngine | ReplayRunner | 验证方法 |
|---|------|---------------|-------------|----------|
| 1 | 入场执行价格 | 收盘价 (close) | 开盘价 (open) | events_log entry_price vs df.open |
| 2 | SL/TP 执行价格 | 收盘价 | 触发价 (SL/TP level) | events_log exit_price vs entry*(1-sl) |
| 3 | 信号延迟方式 | shift(1) 向量化 | pending_decision 状态机 | entry_price == df.iloc[signal_bar+1].open |
| 4 | 杠杆实现 | 后处理放大权益 | 实际保证金乘数 | position_opened quantity 字段 |
| 5 | ATR 止损 | 不支持 | sl_mode="atr" 时支持 | SL trigger price 随 ATR 变化 |
| 6 | Reduce 比例 | position * size_pct | 硬编码 0.5 | quantity_reduced / position |
| 7 | Add 行为 | value * size_pct | gap fill to target | add_skipped vs position_added |
| 8 | 资金费率基数 | 杠杆后权益 | quantity * bar_close | 总资金费差异 |
| 9 | SL后入场延迟 | vbt回调顺序处理 | 显式推迟1根K线 | SL+entry 事件间距 |
| 10 | 限价单 | 无 | OrderManager | order_events_log |
| 11 | 开仓成本PnL | vbt内部费用 | pnl - open_cost - close_fee | 单笔PnL对比 |
| 12 | bars_per_year | 不含1m/5m/2h | 含1m/5m/2h | 3d timeframe sharpe |

其中差异 1-5 是核心验证点（直接影响交易真实度），6-12 是附加验证。

**3. 测试基础设施完备**

- pytest 8.x + 完整标记系统（smoke/unit/integration/slow/e2e）
- `tests/helpers/data_factory.py`：make_ohlcv()、make_enhanced_df()、make_dna()、make_ema_dna()
- 真实数据：`data/market/BTCUSDT_{15m,30m,1h,4h,1d}.parquet`
- 策略来源：`data/quant.db` 的 strategy 表 + make_dna() 工厂
- 已有验证脚本参考：`scripts/verify_strategy_integrity.py`

### 思考引导

**结构性理解**：DecisionPipeline 和 BacktestEngine 是两条完全独立的执行链路。ReplayResult 中的 events_log 提供了丰富的可观测数据，每个事件都有精确的价格和原因字段。通过对比同一策略在同一数据上的双引擎结果，可以确凿证明批量回测走的是哪条路径。

**任务认知变化**：验证不需要修改任何现有代码，只需要编写一个独立的验证脚本。脚本直接调用 ReplayRunner 和 BacktestEngine，在相同输入上对比输出。差异本身就是证据。

**不确定性**：无关键不确定性。测试数据工厂、真实数据、策略加载方式均已验证可用。

### 决策
研究完成，进入推理链构建。

---

## 推理链

### 1. 任务定义

编写独立 Python 验证脚本，通过对比 BacktestEngine 和 ReplayRunner 在相同策略/数据上的执行结果，确凿证明批量回测已切换到模拟交易引擎，并验证关键执行行为（开盘价成交、SL/TP触发价成交、pending_decision延迟、ATR止损、真实杠杆）的正确性。

### 2. 现状定位

**问题类型：验证/确认型（代码已改完，需要证明改对了）**

核心验证对象是 `api/routes/strategies.py:1408` `_BatchBacktestProcessor.process_step()` 中新实现的 ReplayRunner 调用链。

代码证据：
- `strategies.py:1465-1469`：创建 ReplayRunner 并调用 run()
- `strategies.py:1477-1489`：从 events_log 提取 closed_events 计算 win_rate
- `strategies.py:1513-1518`：从 equity_curve + events_log 序列化结果

关键验证点：process_step() 不再调用 BacktestEngine.batch_run()，改为逐策略调用 ReplayRunner.run()。ReplayRunner 内部驱动 DecisionPipeline，产生具有模拟交易特征的事件日志。

### 3. 解决策略

**编写独立验证脚本，双引擎对比 + 行为断言。**

具体策略：
1. 用相同策略 DNA + 相同数据分别跑 BacktestEngine 和 ReplayRunner
2. 对比结果差异，证明两引擎行为不同且 ReplayRunner 符合模拟交易预期
3. 单独验证 ReplayRunner 的 5 个核心行为（开盘价成交、SL触发价、延迟执行、ATR止损、真实杠杆）
4. 从 data/quant.db 加载真实进化策略，用真实数据验证，确保不是合成数据特例

排除的方案：
- 通过 API 端到端测试（需启动服务器，流程长，失败难定位）→ 改为直接调用 core 模块
- 只用合成数据测试（可能不覆盖真实场景）→ 附加真实数据验证
- 单元测试（已有的 test_executor_backtest.py 覆盖）→ 改为集成级验证脚本

### 4. 范围边界

**新增文件：**
- `scripts/verify_batch_pipeline.py` — 验证脚本

**不改：**
- `core/trading/` — ReplayRunner、DecisionPipeline、VirtualAccount 不修改
- `core/backtest/` — BacktestEngine 不修改
- `api/routes/strategies.py` — process_step() 不修改
- `tests/` — 不修改现有测试

### 5. 行为规格

**5.1 双引擎对比验证**
- 输入：同一策略 DNA + 同一 DataFrame（至少 500 根 K 线）
- 分别调用 BacktestEngine.run() 和 ReplayRunner.run()
- 断言：两引擎的 total_return 不同（证明执行路径不同）
- 断言：ReplayRunner 的 entry_price 匹配 df.open（不是 df.close）
- 验证方式：`[测试验证]`

**5.2 开盘价成交验证**
- 从 ReplayResult.events_log 提取 position_opened 事件
- 对每个事件，找到对应 K 线的 bar_open
- 断言：entry_price == bar_open（允许滑点误差 ±0.1%）
- 验证方式：`[测试验证]`

**5.3 SL/TP 触发价成交验证**
- 构造 SL 必然触发的场景（入场后价格大幅下跌）
- 从 events_log 提取 exit_reason=="sl" 的 position_closed 事件
- 断言：exit_price == entry_price * (1 - stop_loss_pct)（精确匹配）
- 验证方式：`[测试验证]`

**5.4 pending_decision 延迟验证**
- 构造信号在 bar N 产生、在 bar N+1 执行的场景
- 从 events_log 找到 position_opened 时间戳
- 断言：执行发生在信号 K 线的下一根（1 bar 延迟）
- 验证方式：`[测试验证]`

**5.5 真实数据端到端验证**
- 从 data/quant.db 加载真实策略（至少 3 条不同类型）
- 用 data/market/BTCUSDT_4h.parquet 真实数据
- 通过 ReplayRunner.run() 执行
- 断言：有交易发生（total_trades > 0）
- 断言：events_log 包含完整生命周期事件（opened → closed）
- 断言：所有 exit_reason 都在合法枚举内
- 断言：equity_curve 非空且长度 == bars_processed
- 验证方式：`[测试验证]`

**5.6 输出验证报告**
- 每个验证项输出 PASS/FAIL + 具体数值
- 汇总表：验证项、结果、实际值、期望值
- 最终判定：全部 PASS 则可信，任一 FAIL 则需排查
- 验证方式：`[代码审查]`

### 6. 风险披露

**确定有风险：**
1. **合成数据可能不触发 SL**：make_ohlcv() 生成的随机数据波动可能不够大，SL 不会触发 → 缓解：构造特定的下跌场景数据
2. **真实策略可能无交易**：进化策略在特定数据段可能不产生信号 → 缓解：多加载几条策略，至少 3 条，取有交易的策略

**不确定的风险：**
- 无

### 7. 实施顺序

1. **搭建验证脚本骨架** — 导入、数据加载、策略构造、双引擎调用框架（无依赖）
2. **实现 5 项行为验证** — 开盘价、SL触发价、延迟执行、ATR止损、真实杠杆（依赖1）
3. **实现真实数据端到端验证** — 从 quant.db 加载策略，用真实 parquet 数据验证（依赖1）
4. **输出验证报告** — 汇总表 + 最终判定（依赖2-3）

## 状态
- 推理链已冻结（用户确认于 2026-06-10）
- 阶段 B：实施完成
- 最终校验：14/14 全部 PASS
- 验证脚本：scripts/verify_batch_pipeline.py
