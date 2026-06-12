# 模拟交易模式真实性评估与功能规划

## 任务目标
深入分析模拟交易模式（DecisionPipeline + VirtualAccount）的执行机制，
评估其是否符合和接近真实交易环境，识别差距并规划改进。

## 初始理解
- 上一轮研究已发现系统存在两条并行链路：回测模式（vectorbt）和模拟交易模式（Pipeline）
- 模拟交易模式更接近真实：开盘价成交、限价单、ATR止损、实时保证金
- 需要深入评估：订单生命周期、风控机制、资金管理、与真实交易所的差异
- 核心模块：core/trading/{pipeline, account, order_manager, order_generator, judgment, replay, runner, types}.py

### 真实性总体评估

**设计良好之处（接近真实）：**
1. pending_decision 机制正确模拟 1 根K线延迟（`pipeline.py:182-197`）
2. 以开盘价（bar_open）执行，而非收盘价
3. SL/TP 用 HIGH/LOW 检查触发（`account.py:282-306`）
4. 支持 ATR 动态止损（`pipeline.py:75-92`）
5. 限价单机制 + OrderManager 生命周期管理
6. 资金费率（简化但存在）
7. 爆仓清算检查
8. 多空方向（long/short/mixed）
9. 加仓/减仓/平仓完整仓位管理

**关键差距（12 项偏差）：**

| # | 偏差 | 代码位置 | 严重度 |
|---|------|---------|--------|
| 1 | SL/TP 以精确触发价成交，无滑点 | `account.py:291,303` | 高 |
| 2 | 限价单不考虑成交量/订单簿深度 | `order_manager.py:58` | 高 |
| 3 | 零延迟假设（无网络/API延迟） | 全局架构 | 高 |
| 4 | 清算公式简化（基于 init_cash） | `account.py:313` | 高 |
| 5 | 无维持保证金逐级递增 | `account.py:309-314` | 中 |
| 6 | 市价单以 (high+low)/2 成交 | `order_manager.py:69` | 中 |
| 7 | 资金费率固定 0.1%/8h | `account.py:15,323` | 中 |
| 8 | **疑似 bug**：open_cost 在 PnL 中重复扣除 | `account.py:134 vs 162` | 高 |
| 9 | 不支持部分成交 | `order_manager.py:58-65` | 中 |
| 10 | ATR 止损静态，无移动止损 | `pipeline.py:75-92` | 低 |
| 11 | 减仓固定 50% | `account.py:219` | 低 |
| 12 | SL/TP 同K线触发始终选 SL | `account.py:290-293` | 低 |

### 疑似 Bug 详细说明

**编号 8**：`_open_position()` 第 162 行 `balance -= margin + open_fee + open_slippage`，
费用已从余额扣除。但 `_close_position()` 第 134 行 `pnl = pnl - pos.open_cost - close_fee - slippage_cost`，
`open_cost`（包含开仓费用和滑点）又从 PnL 中扣除。开仓手续费和滑点被扣了两次。

## 状态
- 研究完成，待用户确认分析方向
