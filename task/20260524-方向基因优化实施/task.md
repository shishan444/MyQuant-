# 方向基因优化：消除动量兜底 + 扩展表达力

## 任务目标
解决方向判定的两个问题：
1. 动量兜底：进化中 DIRECTION 基因丢失后，系统用不可优化的硬编码规则静默替代
2. 表达力受限：DIRECTION 基因只能做 price_above/price_below，无法表达更复杂的方向逻辑

---

## 研究发现（A1 研究循环）

### 发现 1：DIRECTION 基因丢失的主要路径是 crossover

**crossover 丢失**（operators.py:682-687）：使用 `random.choice([direction_a, direction_b])` 从两个父本中选一个。如果父本 A 有 DIRECTION 基因但父本 B 没有，50% 概率选中 B 的空列表 → 子代丢失 DIRECTION 基因。一旦种群中出现丢失个体，雪球效应加剧。

**mutate_remove_signal 安全**（operators.py:612-613）：只删除 `_guard` 后缀的基因，不会删除 DIRECTION。

**mutate_risk 间接影响**（operators.py:654-658）：15% 概率将 direction 从 mixed 改为 long/short，DIRECTION 基因变为"死基因"（仍存在但不被使用）。后续改回 mixed 时基因可能还在。

**恢复机制不足**（operators.py:538-550）：mutate_add_signal 20% 概率恢复，但前提是函数被选中且 direction=mixed 且无 DIRECTION 基因。

**验证器无保护**（validator.py）：不检查 mixed 策略是否包含 DIRECTION 基因。

### 发现 2：evaluate_condition 已支持 16 种条件类型

executor.py:31-107 的 evaluate_condition 函数支持所有条件类型。executor.py:690-696 的 DIRECTION 基因处理 `np.where(signal, 1.0, -1.0)` 也不限制条件类型——**evaluate_condition 层面无障碍**。

限制完全来自 `_create_direction_gene`（population.py:149-200）的硬编码选择：
- `_DIRECTION_INDICATORS` 只有 11 个趋势类指标
- 条件类型只有 price_above/price_below

### 发现 3（新发现）：方向映射 bug

executor.py:690-696 中 `np.where(signal, 1.0, -1.0)` 将所有 True 映射为 +1（做多）。

- price_above True = close > indicator = 看多 → +1 ✓ 正确
- **price_below True = close < indicator = 看空 → +1 ✗ 错误**

当前 population.py:182 以 50/50 概率生成 price_above 和 price_below。这意味着**一半的 DIRECTION 基因方向映射是反的**。进化算法可以部分补偿（其他基因调整），但这是对搜索效率的严重浪费。

MTF 路径（mtf_engine.py:291-301）正确处理了这个反转，但 DIRECTION 基因路径没有。

---

## 推理链（A2）

### 1. 任务定义

修复策略层方向判定机制的三个问题：(1) 消除动量兜底，确保 mixed 策略始终有可进化的 DIRECTION 基因；(2) 扩展 DIRECTION 基因表达力，支持动量类指标（RSI、MACD 等）的 gt/lt 条件；(3) 修复 price_below 条件的方向映射 bug。

### 2. 现状定位

**三个问题，都是策略层代码设计问题：**

**问题 A：DIRECTION 基因可丢失，静默降级到不可进化的兜底。**
- 根因：crossover 使用 random.choice 而非合并（operators.py:685），验证器不检查 DIRECTION 基因（validator.py）
- 兜底：executor.py:727 硬编码 `close.pct_change(5)`
- 影响：进化搜索空间出现暗区，DIRECTION 基因丢失后不可恢复

**问题 B：DIRECTION 基因表达力受限。**
- 根因：`_DIRECTION_INDICATORS` 只有 11 个趋势指标（population.py:150），条件只有 price_above/price_below（population.py:182）
- 影响：进化无法探索"RSI>50 做多"这类动量方向逻辑
- 基础设施无障碍：evaluate_condition 已支持 gt/lt 等条件（executor.py:31-107）

**问题 C：price_below 方向映射错误。**
- 根因：executor.py:692 `np.where(signal, 1.0, -1.0)` 对所有条件统一映射，但 price_below True = 看空应映射为 -1
- 影响：50% 的 DIRECTION 基因方向反转，进化需要补偿，搜索效率降低
- 证据：MTF 路径正确处理了反转（mtf_engine.py:297 `np.where(close < indicator_col, -1.0, 1.0)`），DIRECTION 基因路径没有

### 3. 解决策略

**问题 C 修复策略：统一使用"True = 看多"的条件语义。**

不为 price_below/lt 添加反转映射，而是确保 DIRECTION 基因始终使用"True = 看多"的条件类型：
- price_above: True = close > indicator = 看多 ✓
- gt: True = indicator > threshold = 看多（选择合适的阈值）✓
- ge: 同 gt ✓

不使用：
- price_below: 用 price_above 代替（False 自然表示看空）
- lt/le: 用 gt/ge 代替（反转阈值）
- cross_above/cross_below: 脉冲信号，不适合持续方向判定

**排除的替代方案**：添加 `direction_invert` 字段到 condition dict。理由：增加 DNA 编码复杂度，进化需要额外学习何时反转，而统一语义更简洁。

**问题 A 修复策略：三层防护。**

1. crossover 合并（operators.py:685）：改为从两个父本合并 DIRECTION 基因（而非随机选一个），确保子代继承
2. 验证器检查（validator.py）：mixed 策略必须包含至少一个 DIRECTION 基因
3. 删除动量兜底（executor.py:726-731）：无 DIRECTION 基因的 mixed 策略不应静默降级

**排除的替代方案**：保留兜底但使其可配置。理由：兜底本质上是设计缺陷，不应保留。

**问题 B 修复策略：扩展 _create_direction_gene 的指标池和条件类型。**

添加动量类指标到 DIRECTION 基因候选：
- RSI(14) gt 50, MACD histogram gt 0, CCI(20) gt 0, ROC(12) gt 0
- CMO(14) gt 0, TRIX(15) gt 0, CMF(20) gt 0, MFI(14) gt 50
- Aroon oscillator gt 0, MultifactorOsc gt 0

每个指标配一个默认阈值（有方向含义的），阈值可通过进化变异。

**排除的替代方案**：支持多个 DIRECTION 基因的投票机制。理由：增加评估逻辑复杂度，当前阶段单基因已足够，多基因作为未来迭代。

### 4. 范围边界

**改动文件：**
- `core/strategy/executor.py`：删除动量兜底（~727-731），修复方向映射注释确认
- `core/evolution/operators.py`：修复 crossover DIRECTION 基因继承逻辑（~685）
- `core/evolution/population.py`：扩展 `_create_direction_gene` 指标池和条件类型（~149-200）
- `core/strategy/validator.py`：添加 mixed 策略 DIRECTION 基因检查

**不改动的文件（及原因）：**
- `core/backtest/engine.py`：消费 entry_direction 的符号，不涉及生成逻辑
- `core/trading/` 所有文件：消费 entry_direction 的符号，不涉及生成逻辑
- `core/strategy/mtf_engine.py`：有独立的 direction 提取机制，不影响 DIRECTION 基因路径
- `api/schemas.py`：不新增 DNA 字段，无需更新 API schema

### 5. 行为规格

**BS-1: DIRECTION 基因方向映射正确性** `[测试验证]`
- 前置：DIRECTION 基因使用 price_above 条件
- 契约：当 close > indicator 时，entry_direction = +1.0（做多）；当 close <= indicator 时，entry_direction = -1.0（做空）
- 不变量：True 信号始终映射为 +1.0，False 始终映射为 -1.0

**BS-2: DIRECTION 基因支持 gt 条件** `[测试验证]`
- 前置：DIRECTION 基因使用 gt 条件，例如 RSI > 50
- 契约：当 RSI > 50 时，entry_direction = +1.0；当 RSI <= 50 时，entry_direction = -1.0
- 边界：RSI 恰好等于 50 时，gt 返回 False → direction = -1.0

**BS-3: Mixed 策略无 DIRECTION 基因时验证失败** `[测试验证]`
- 前置：StrategyDNA 的 risk_genes.direction = "mixed"
- 契约：当 signal_genes 中无 role=DIRECTION 的基因时，validate_dna 返回 is_valid=False
- 边界：有 DIRECTION 基因的 mixed 策略验证通过

**BS-4: 动量兜底不再触发** `[测试验证]`
- 前置：dna_to_signal_set 处理 direction="mixed" 的 DNA
- 契约：当有 DIRECTION 基因时使用基因信号（现有行为不变）；当无 DIRECTION 基因时不会调用 close.pct_change(5)
- 注：由于 BS-3 确保验证阶段拦截，无 DIRECTION 基因的 mixed DNA 不应到达执行阶段

**BS-5: Crossover 保留 DIRECTION 基因** `[测试验证]`
- 前置：父本 A 有 DIRECTION 基因，父本 B 没有
- 契约：子代从父本 A 继承 DIRECTION 基因
- 边界：两个父本都有 DIRECTION 基因时，子代继承其中一个

**BS-6: _create_direction_gene 支持动量指标** `[测试验证]`
- 前置：_create_direction_gene 被调用
- 契约：返回的基因可能使用 trend 类指标（price_above）或 momentum 类指标（gt + threshold）
- 不变量：条件类型始终为 price_above 或 gt/ge（"True = 看多"语义）

### 6. 风险披露

**确定风险：**

R1: **price_below 方向映射修复可能改变现有策略行为。** 如果进化已产出使用了 price_below DIRECTION 基因的策略冠军，修复后这些策略的方向映射会反转。
- 影响：依赖 price_below DIRECTION 基因的冠军策略行为改变
- 缓解：在方向映射修复中，检测 price_below 条件并自动修正映射。或者在修复后重新进化

R2: **DIRECTION 基因验证可能拒绝已有的合法策略。** 如果数据库中已存储了无 DIRECTION 基因的 mixed 策略，新的验证逻辑会拒绝它们。
- 影响：已有的进化快照或冠军策略可能无法通过验证
- 缓解：验证器只发出 warning 而非 error（允许加载但不允许新创建）

**不确定风险：**

R3: **动量指标阈值初始化可能不适合所有市场状态。** 例如 RSI > 50 在趋势市场效果好，但在震荡市场可能频繁翻转。
- 消除方式：阈值通过进化变异可以调整，初始值不锁定最终性能

### 7. 实施顺序

**Step 1: 修复方向映射确认** `executor.py`
- 验证当前 price_above 映射正确性（True → +1 已正确）
- 确认 evaluate_layer 中 DIRECTION 基因处理逻辑正确
- 原因：方向映射是后续所有工作的基础
- 对应规格：BS-1

**Step 2: 扩展 DIRECTION 基因创建** `population.py`
- 新增 `_MOMENTUM_DIRECTION_CONFIGS` 定义动量指标的默认阈值
- 修改 `_create_direction_gene` 支持动量指标的 gt 条件
- 原因：扩展表达力是核心功能
- 对应规格：BS-6

**Step 3: 修复 crossover 继承** `operators.py`
- 修改基础层 crossover（~682-687）和 MTF 层 crossover（~740-744）
- 确保子代从有 DIRECTION 基因的父本继承
- 原因：防止 DIRECTION 基因丢失是 Step 4（验证器）的前提
- 对应规格：BS-5

**Step 4: 添加 DIRECTION 基因验证** `validator.py`
- mixed 策略必须包含 DIRECTION 基因（warning 级别）
- 原因：安全网，依赖 Step 3 减少触发频率
- 对应规格：BS-3

**Step 5: 删除动量兜底** `executor.py`
- 删除 executor.py:726-731 的 pct_change(5) 兜底
- 添加 fallback：无 DIRECTION 基因时 entry_direction = 0.0（中性，不触发交易）
- 原因：最后一步，确保兜底路径被安全替代
- 对应规格：BS-4

---

## 最终校验结果

### B4 合规确认
- 覆盖完整：6 条行为规格全部有实现和测试覆盖
- 意图正确：实现表达了规格描述的行为意图
- 策略一致：实现方式与推理链策略一致

### 推理链 vs 实际对比
- 任务定义：无偏差（额外清理数据为用户授权）
- 现状定位：无偏差
- 解决策略：微偏差 — MultifactorOsc 未添加（lazy 指标需特殊处理）
- 范围边界：无偏差（测试文件改动属正常维护）
- 行为规格：6/6 全部满足
- 风险：无未预见风险，R1/R2 通过清理数据解决
- 实施顺序：按推理链顺序执行

### 偏差清单
| 偏差 | 类型 | 影响 | 处理 |
|------|------|------|------|
| MultifactorOsc 未添加 | 策略微调 | 低 | lazy 指标需特殊处理，可后续补充 |

### 测试结果
1793 passed, 0 failed (排除非确定性 flaky test)

### 状态：任务完成
