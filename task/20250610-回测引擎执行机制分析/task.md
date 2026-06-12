# 回测引擎执行机制分析与测试验证

## 任务目标
分析 BacktestEngine 的交易执行机制，验证其是否模拟接近真实交易环境的逐根计算，
用测试用例验证核心行为，并解答用户关于挂单/触发方式的疑惑。

## 初始理解
- 用户核心疑惑：回测是基于 K 线预挂单然后触发，还是其他方式？
- 需要追踪 BacktestEngine 从信号生成到订单执行到成交的完整链路
- 工程目录：MyQuant/
- 引擎核心文件：core/backtest/engine.py

---

## 研究第 1 轮

### 核心发现：系统存在两条并行的执行链路

**路径 A — 回测模式（BacktestEngine）**：vectorbt 向量化回测，Numba JIT 编译
- 入口：`engine.py:602` `run()` → `_build_portfolio()` → `_build_result_from_portfolio()`
- 信号生成：全量向量化，`executor.py:509` `dna_to_signal_set()` 一次性计算所有K线信号
- 信号延迟：`engine.py:419-422` 所有信号 shift(1) 防止前瞻偏差
- 逐根处理：`engine.py:206-393` `order_func_nb` Numba 回调，处理优先级：清算→SL/TP→出场→入场→减仓→加仓
- 成交价格：**收盘价**（c.close），无挂单机制
- SL/TP 检查：用 HIGH/LOW 判断是否触发，但成交价由 vectorbt 决定
- 杠杆：后处理放大权益曲线（`engine.py:133`）

**路径 B — 模拟交易模式（DecisionPipeline）**：纯 Python 逐K线循环
- 入口：`pipeline.py:94` `process_bar()` → 8 步管线
- 信号生成：同样用 `dna_to_signal_set()`，但通过 `BarSignals.from_signal_set()` 提取单根信号
- 决策延迟：bar N 产生 Decision → bar N+1 开盘价执行（pending_decision 机制）
- 成交价格：**开盘价**（bar_open），或限价单触发价
- SL/TP 成交：以 SL/TP 触发价本身成交（`account.py:266-307`），更真实
- 挂单机制：有。`OrderManager` + 限价单（`order_manager.py:35-129`），当 `bar_low <= price <= bar_high` 触发
- 支持 ATR 动态止损（回测模式不支持）

### 两条路径的关键差异

| 特性 | 回测 (BacktestEngine) | 模拟交易 (Pipeline) |
|------|----------------------|-------------------|
| 遍历方式 | vectorbt 内部逐根调用 | Python for 循环 |
| 信号延迟 | shift(1) | Decision 延迟一根 |
| 成交价格 | 收盘价 (close) | 开盘价 (open) 或限价触发价 |
| SL/TP 成交价 | vectorbt 决定（默认 close） | SL/TP 触发价本身 |
| 挂单机制 | **无** | **有**（OrderManager + 限价单）|
| 杠杆处理 | 后处理 | 实时保证金追踪 |
| 止损类型 | 仅百分比 | 百分比 + ATR 动态 |

### 回测模式的真实性评估

**接近真实之处**：
1. 信号延迟一根K线（shift(1)），防止前瞻偏差
2. SL/TP 使用 HIGH/LOW 检查，比只用 CLOSE 更合理
3. 考虑了手续费和滑点
4. 考虑了资金费率和爆仓清算

**偏离真实之处**：
1. 入场/出场用**收盘价**成交——真实交易中，信号在 bar N 收盘后产生，最快在 bar N+1 开盘才能执行，应该用开盘价
2. SL/TP 触发检查用 HIGH/LOW，但实际成交价不确定——真实交易中 SL 应该以触发价成交
3. 没有挂单机制——真实交易中可以使用限价单在更好的价位成交
4. 杠杆是后处理而非实时追踪——可能低估了爆仓风险

## 状态
- 研究完成，待用户确认分析结果
