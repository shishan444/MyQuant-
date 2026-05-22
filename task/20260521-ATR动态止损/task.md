# ATR 动态止损/止盈

## 任务定义

为 VirtualAccount 添加 ATR 挂钩的动态止损/止盈模式。当 `RiskGenes.sl_mode == "atr"` 时，SL/TP 价格基于入场时的 ATR 值计算（如 entry_price - 2*ATR），而非固定百分比。默认保持 `sl_mode="pct"` 不变，确保向后兼容。

## 现状定位

### SL/TP 百分比的13个引用点

**定义层**：
- `dna.py:152-153` — RiskGenes: `stop_loss: float = 0.05`, `take_profit: Optional[float] = None`（固定百分比）

**存储层**：
- `account.py:52-53` — `self._stop_loss = dna.risk_genes.stop_loss`, `self._take_profit = dna.risk_genes.take_profit`

**SL/TP 价格计算（check_sl_tp）**：
- `account.py:276` — Long SL: `ep * (1.0 - self._stop_loss)`
- `account.py:277-278` — Long TP: `ep * (1.0 + self._take_profit)`
- `account.py:286` — Short SL: `ep * (1.0 + self._stop_loss)`
- `account.py:287-288` — Short TP: `ep * (1.0 - self._take_profit)`

**Tranche chase 边界（_process_tranches）**：
- `account.py:328` — `max_chase_price = entry_price * (1 + self._stop_loss * plan.max_chase_pct)`
- `account.py:357,366` — `min_chase = entry_price * (1 - self._stop_loss * plan.max_chase_pct)`

**外部调用者**：
- `pipeline.py:67,153` — `stop_loss_pct` 参数传递给 `PositionPlan.from_prediction`（实际未使用，死代码）
- `replay.py:129` — `stop_loss_pct=dna.risk_genes.stop_loss or 0.05`
- `runner.py:398` — `stop_loss_pct=dna.risk_genes.stop_loss or 0.05`

**已废弃模块**：
- `position.py:96-97,243-257` — 旧 PositionManager 中同样的百分比逻辑

### ATR 可用性分析

- ATR 在 `indicators.py:122-124` 计算，period=14，列名 `atr_14`
- ATR 存在于所有经过 `compute_all_indicators()` 的 DataFrame 中
- `pipeline.process_bar()` 接收 `df` 参数（包含 ATR 列），但未向下游传递
- `VirtualAccount` 完全无法访问 ATR 数据（无 df 参数）
- 核心断点：ATR 数据在 DataFrame 中始终存在，但在 pipeline → account 的调用链中没有任何环节提取并传递

### 关键架构约束

1. VirtualAccount 是无状态的执行单元，不应该知道 DataFrame 的存在
2. DecisionPipeline 是协调者，拥有 df 和 dna_risk_genes，是提取 ATR 的正确位置
3. Position 对象不存储 SL/TP 价格，每次 check_sl_tp 从百分比重新计算
4. 三条开仓路径（execute_decision, fill_order, _process_tranches）都需支持

## 解决策略

**核心思路：在 Position 中存储 SL/TP 绝对价格，由 Pipeline 根据模式计算后传入。**

原因：
- 解耦"怎么计算 SL/TP"和"怎么检查 SL/TP"——账户不关心价格怎么来的，只用价格判断
- Position 知道自己的止损/止盈水平，是自然的归属
- 对新增模式（未来 trailing stop 等）开放，只需设置不同的价格
- 向后兼容：sl_price/tp_price 为 None 时回退到百分比计算

排除的替代方案：
- **方案 B：每 bar 传 ATR 给 check_sl_tp** — 混淆了账户和数据层的职责，且 ATR 不应该每 bar 变化（标准 ATR stop 是入场时固定）
- **方案 C：账户自己计算 ATR** — 账户不应该依赖 DataFrame

## 范围边界

### 改动文件

| 文件 | 操作 | 说明 |
|------|------|------|
| core/strategy/dna.py | 修改 | RiskGenes 添加 sl_mode, atr_period 字段 |
| core/trading/position.py | 修改 | Position 添加 sl_price, tp_price 字段 |
| core/trading/account.py | 修改 | _open_position/check_sl_tp/execute_decision/fill_order 接受并使用存储价格 |
| core/trading/pipeline.py | 修改 | 提取 ATR、计算 SL/TP 价格、传递给账户方法 |
| tests/test_virtual_account.py | 扩展 | ATR 模式的 SL/TP 测试 |
| tests/test_pipeline.py | 扩展 | Pipeline ATR 集成测试 |
| tests/test_replay.py | 扩展 | ReplayRunner ATR 模式端到端测试 |

### 排除项

- `position.py`（已废弃的 PositionManager）— 不修改，不在范围
- `runner.py` — 不修改，pipeline 处理 ATR 提取，runner 只传参数
- 进化引擎（evolver）— 本次不处理 `sl_mode` 的进化变异，留后续任务
- `_process_tranches` 的 tranche 价格 — 保持基于 prediction 的定价逻辑不变，只改 chase 边界

## 行为规格

### S1: RiskGenes 新增字段 [代码审查]

- `sl_mode: str = "pct"` — 取值 "pct" | "atr"，默认 "pct" 保持现有行为
- `atr_period: int = 14` — ATR 回看周期
- `to_dict()` / `from_dict()` 序列化包含新字段
- 当 `sl_mode == "atr"` 时，`stop_loss` 语义从百分比变为 ATR 乘数（如 2.0 表示 2倍ATR 止损距离）

### S2: Position 存储止损/止盈价格 [测试验证]

- 新增 `sl_price: Optional[float] = None`, `tp_price: Optional[float] = None`
- 默认值 None 表示未设置（回退到百分比计算）
- 非 None 时为绝对价格值（如 95000.0 而非百分比）

### S3: VirtualAccount 使用存储价格 [测试验证]

- `_open_position(side, price, size_pct, sl_price=None, tp_price=None)` — 接受并存储到 Position
- `check_sl_tp(bar_high, bar_low)`:
  - 当 `position.sl_price is not None` → 使用存储价格
  - 当 `position.sl_price is None` → 使用百分比计算（现有逻辑，不变）
  - tp_price 同理
- `execute_decision(decision, open_price, sl_price=None, tp_price=None)` — 透传给 _open_position
- `fill_order(order, sl_price=None, tp_price=None)` — 透传给 _open_position
- `_process_tranches` chase 边界：当 `position.sl_price is not None` 时，用 `abs(entry_price - sl_price)` 作为止损距离计算 chase 边界，而非 `self._stop_loss`

### S4: Pipeline 计算 ATR 止损价格 [测试验证]

- 当 `dna_risk_genes.sl_mode == "atr"` 且 `df is not None` 时：
  - 从 df 中提取 `atr_{atr_period}` 列的当前 bar 值
  - Long SL: `entry_price - stop_loss * ATR`（stop_loss 在 ATR 模式下是乘数）
  - Long TP: `entry_price + take_profit * ATR`（take_profit 在 ATR 模式下是乘数）
  - Short SL: `entry_price + stop_loss * ATR`
  - Short TP: `entry_price - take_profit * ATR`
- ATR 值为 NaN 或 0 时，回退到百分比模式（降级而非报错）
- 将计算结果传递给 account 的 execute_decision / fill_order

### S5: 向后兼容保证 [测试验证]

- `sl_mode="pct"`（默认）时，所有行为与改动前完全一致
- 现有测试不修改断言值，全部通过
- Position 的 sl_price/tp_price 默认 None → check_sl_tp 走百分比路径

### S6: ReplayRunner ATR 模式端到端 [集成测试]

- 传入 `sl_mode="atr"` 的 DNA 进行回放
- 回放正常完成，产生有效的 equity_curve 和 trades
- SL/TP 事件中的 exit_price 基于 ATR 计算而非固定百分比

## 风险披露

**确定有风险**：
1. `_add_position` 改变 entry_price 但 SL/TP 价格保持不变 → 加仓后 SL 距离可能变大。影响：功能行为而非 bug，这是标准做法（保持原始止损）。缓解：在文档和测试中明确此行为。
2. `_process_tranches` 的 chase 边界依赖 `self._stop_loss`，ATR 模式下语义变化 → 可能导致 chase 范围异常。影响：实际交易中的挂单行为。缓解：改为使用 Position 存储的 sl_price 计算距离。

**不确定**：
1. 进化引擎是否已处理未知字段（sl_mode, atr_period）。不处理时会怎样。缓解：验证 `EvolutionEngine.mutate_risk_genes()` 是否会忽略未知字段。如果不忽略，本次任务不涉及进化路径，记录为后续任务。
2. `sl_mode="atr"` 时 `stop_loss=2.0` 与进化引擎的参数范围（通常 0.01-0.2）不兼容。影响：进化产生的 ATR 乘数可能过小。缓解：本次不处理进化路径，记录为后续任务。

## 实施顺序

1. **S1 + S2: RiskGenes 和 Position 数据结构** — 无依赖，最基础的改动
2. **S3: VirtualAccount 使用存储价格** — 依赖 S2（Position 新字段）
3. **S4: Pipeline 计算 ATR 止损价格** — 依赖 S1（sl_mode 字段）+ S3（account 接受 sl_price）
4. **S5: 向后兼容验证** — 依赖 S1-S3，运行全部现有测试
5. **S6: ReplayRunner 端到端测试** — 依赖 S4，完整集成验证

## 状态：推理链已冻结（2026-05-22 用户确认）
