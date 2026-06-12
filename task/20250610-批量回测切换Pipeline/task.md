# 批量回测切换到模拟交易引擎

## 任务目标
将批量回测的执行引擎从 BacktestEngine（收盘价成交）切换到 DecisionPipeline（开盘价成交+限价单+ATR止损），
提升回测结果的真实性。

## 初始理解
- BacktestEngine 用 vectorbt + 收盘价成交，偏向乐观结果
- DecisionPipeline 用开盘价成交、限价单、ATR止损、实时保证金，更接近真实
- 需要了解 ReplayRunner 如何调用 DecisionPipeline，然后设计批量回测的调用方式
- SSE 流式推送模式不变，后端处理器需要重写
- 前端展示可能需要适配新的结果格式

## 研究第 1 轮

### 核心发现

**1. ReplayRunner 已有完整的单策略回测能力**

ReplayRunner（`replay.py:58-161`）封装了 DecisionPipeline 的完整调用链：
- 创建 VirtualAccount + DecisionPipeline + PriceRangePredictor
- 逐K线调用 `pipeline.process_bar(bar_high, bar_low, bar_open, bar_close, ...)`
- 收集 `equity_snapshots`（每K线净值）和 `closed_trades`（已平仓交易）
- 返回 `ReplayResult`（total_return, equity_curve, events_log, order_events_log）

**2. 当前 _BatchBacktestProcessor 的可复用部分（~70%）**

| 组件 | 可复用性 | 原因 |
|------|---------|------|
| BatchBacktestRequest | ✅ 复用 | 纯输入契约 |
| SSE 事件格式 | ✅ 复用 | 传输协议 |
| save/get_backtest_result | ✅ 复用 | 通用 JSON 存储 |
| 详情端点 GET | ✅ 复用 | 无状态读取 |
| init() 策略加载分组 | ✅ 复用 | 无引擎依赖 |
| finalize() 汇总逻辑 | ✅ 复用 | 只依赖 strategy_period_data |
| 前端全部组件 | ✅ 复用 | 只关心结果格式 |
| **process_step() 核心循环** | ❌ 重写 | batch_run() → ReplayRunner.run() |
| **权益曲线序列化** | ❌ 调整 | pd.Series → list[EquitySnapshot] |
| **信号序列化** | ❌ 调整 | trades_df → events_log/closed_trades |

**3. 结果格式映射**

ReplayResult → BatchBacktestResultItem 的关键映射：
- `total_return` → 直接映射
- `equity_curve`（list[float]）→ 需加时间戳序列化为 [{timestamp, value}]
- `closed_trades`（List[ClosedTrade]）→ 需转换为 signals 格式
- `sharpe_ratio/max_drawdown/win_rate` → **需从 equity_curve 用 compute_metrics() 计算**
- `fitness` → 需用 compute_fitness() 计算
- `events_log` → 可统计 add_count, reduce_count, liquidated

**4. 性能权衡**

- BacktestEngine.batch_run()：向量化，N 策略一次 vbt 调用（快）
- ReplayRunner.run()：逐K线逐策略（慢），N 策略 × M K线 次循环
- 可接受：SSE 后台流式推送，用户已有等待预期
- 优化空间：同 group（相同 symbol/timeframe）的策略共享数据加载和信号计算

---

## 推理链

### 1. 任务定义

将批量回测的执行引擎从 BacktestEngine（收盘价成交、向量化）切换到 DecisionPipeline（开盘价成交、限价单、ATR止损），提升回测结果的真实性。

### 2. 现状定位

**问题类型：架构设计改进（从简化模型升级到仿真模型）**

核心差异（代码证据）：
- 当前：`strategies.py:1464` 调用 `self.engine.batch_run(dnas, enhanced_df)` → 收盘价成交
- 目标：调用 `ReplayRunner.run(dna, df)` → 开盘价成交 + 限价单 + ATR止损

改动范围集中在 `process_step()` 方法（strategies.py:1413-1574），其余 70% 代码可复用。

### 3. 解决策略

**在 _BatchBacktestProcessor.process_step() 中用 ReplayRunner 替换 BacktestEngine。**

具体策略：
1. process_step() 内部循环每个策略，调用 ReplayRunner.run()
2. 从 ReplayResult + VirtualAccount 提取指标，用 compute_metrics() 补充缺失指标
3. 将 equity_snapshots 和 closed_trades 序列化为现有 JSON 格式
4. 复用 save_backtest_result 存储结果

排除的方案：
- 创建新的 BatchPipelineRunner 类：过度设计，ReplayRunner 已有完整能力
- 并行执行多策略：DecisionPipeline 是纯 Python 逐K线，GIL 限制并行收益

### 4. 范围边界

**改动文件：**
- `api/routes/strategies.py` — _BatchBacktestProcessor 类重写 process_step() + 辅助方法

**不改：**
- `core/trading/` — ReplayRunner、DecisionPipeline、VirtualAccount 不做修改
- `core/backtest/engine.py` — BacktestEngine 保持不变（Lab 页面仍使用）
- `api/schemas.py` — BatchBacktestRequest/ResultItem/SummaryItem 不变
- `api/db_ext.py` — save/get_backtest_result 不变
- `web/src/` — 前端全部不变

### 5. 行为规格

**5.1 process_step() 执行逻辑**
- 每个 step = (group_key, group_strategies, date_range)
- 加载数据、计算指标（复用现有逻辑）
- 对每个策略：创建 ReplayRunner → run() → 提取结果
- 使用 compute_metrics() 从 equity_curve 计算夏普/回撤/胜率等
- 使用 compute_fitness() 计算 fitness 和 qualified
- 序列化权益曲线和交易记录，调用 save_backtest_result 存储
- 构建 BatchBacktestResultItem，返回进度数据
- 验证方式：`[集成测试]`（端到端 SSE 流测试）

**5.2 权益曲线序列化**
- 输入：VirtualAccount.equity_snapshots（List[EquitySnapshot]，含 timestamp+equity）
- 输出：[{timestamp: str, value: float}] JSON 格式（与现有格式一致）
- 验证方式：`[代码审查]`

**5.3 交易信号序列化**
- 输入：VirtualAccount.closed_trades（List[ClosedTrade]）
- 输出：[{type: "entry"/"exit", timestamp: str, price: float, reason: str}] JSON 格式
- 入场信号：entry_price + entry 方向
- 出场信号：exit_price + exit_reason（signal/sl/tp/liquidation）
- 验证方式：`[代码审查]`

**5.4 指标计算**
- 从 equity_curve（list[float]）构建 pd.Series，调用 compute_metrics()
- 补充：total_funding_cost 从 events_log 统计或从 balance 变化推算
- liquidated 从 events_log 检查 exit_reason=="liquidation"
- 验证方式：`[代码审查]`

**5.5 SSE 流式行为**
- 格式、事件类型、payload 结构完全不变
- 进度信息不变（current/total/group/range）
- 前端无需任何修改
- 验证方式：`[代码审查]`

### 6. 风险披露

**确定有风险：**
1. **性能下降**：ReplayRunner 逐K线逐策略执行，比 BacktestEngine 向量化慢 10-100 倍。10 个策略 × 1 年数据可能需要 30-60 秒 vs 当前 3-5 秒 → 缓解：SSE 流式推送，用户可看到实时进度；同 group 策略共享数据加载
2. **ReplayRunner 初始化参数差异**：默认 init_cash=10000 vs 当前批量回测默认 100000 → 缓解：显式传入用户配置的 init_cash

**不确定的风险：**
1. PriceRangePredictor 的 warmup 是否影响结果质量（ReplayRunner 默认 warmup_bars=50）→ 需要确认数据量足够
2. DecisionPipeline 的 pending_decision 机制是否需要 JudgmentConfig 参数调优 → 使用默认配置，后续迭代优化

### 7. 实施顺序

1. **重写 process_step()** — 用 ReplayRunner 替换 BacktestEngine.batch_run()（依赖 ReplayRunner 已存在）
2. **重写权益曲线和信号序列化** — 适配 EquitySnapshot 和 ClosedTrade 到现有 JSON 格式（依赖 1）
3. **补充指标计算** — 从 equity_curve 计算 sharpe/max_drawdown/win_rate + fitness（依赖 1）
4. **端到端验证** — 通过前端页面运行批量回测，确认 SSE 流和结果展示正常（依赖 1-3）

## 状态
- 推理链已冻结（用户确认于 2026-06-10）
- 阶段 B：实施完成
  - process_step() 已用 ReplayRunner 替换 BacktestEngine
  - 权益曲线序列化改用 _build_equity_json_from_curve（从 ReplayResult.equity_curve + df.index 重建）
  - 信号序列化改用 _build_signals_json_from_events（从 ReplayResult.events_log 提取 position_closed 事件）
  - 修复关键 bug：runner._last_account 不存在，改为从 ReplayResult 数据重建
  - 添加 pandas import
- 服务已重启，API 健康检查通过
- 待端到端验证（通过前端运行批量回测）
