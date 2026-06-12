# 方向判定机制分析与改进

## 任务目标
从架构设计视角重新理解 StrategyDNA 的方向判定机制，分析其工程能力和局限性，列出改进方案供用户决策。

---

## 一、架构定位

方向判定完全属于**策略层**（core/strategy/）。策略层的职责是"DNA → 信号翻译"，输出 SignalSet。SignalSet 中的 entry_direction 字段（+1 做多 / -1 做空）是评估层消费方向信息的唯一接口。

数据流：
```
StrategyDNA (risk_genes.direction + DIRECTION 信号基因)
    |
    v  策略层翻译
SignalSet.entry_direction (pd.Series, 逐 bar +1/-1)
    |
    +---> 向量回测引擎 (backtest/engine.py) → order_func_nb 逐 bar 决定买卖
    +---> 模拟交易管线 (trading/pipeline.py) → BarSignals.direction → Decision.direction
```

两条评估路径**只消费 entry_direction 的符号**（+1 或 -1），不关心方向是如何决定的。这是策略层的内部事务。

---

## 二、当前方向判定的三种路径

### 路径 1：固定方向（long / short）

- **触发条件**：`risk_genes.direction` 为 "long" 或 "short"
- **行为**：所有 bar 统一方向，不做动态判定
- **设计意图**：用户明确知道只做多或只做空时使用，简单可靠
- **代码位置**：executor.py:732-737

### 路径 2：DIRECTION 基因（mixed 模式的主路径）

- **触发条件**：`risk_genes.direction == "mixed"` 且存在 `role=SignalRole.DIRECTION` 的信号基因
- **行为**：用趋势指标（EMA/SMA 等）与价格比较，price_above → 做多(+1)，price_below → 做空(-1)
- **设计意图**：方向判定可进化——指标类型、参数、条件都是基因编码，进化算法可以优化
- **代码位置**：executor.py:690-696, population.py:149-200
- **当前能力**：
  - 11 个可选指标：EMA, SMA, WMA, DEMA, TEMA, VWAP, PSAR, BB, Keltner, Donchian, VWMA
  - 仅 2 种条件：price_above, price_below
  - 每个策略最多 1 个 DIRECTION 基因（executor.py:724 取 direction_genes[0]）

### 路径 3：动量兜底（mixed 模式的安全网）

- **触发条件**：`risk_genes.direction == "mixed"` 但没有 DIRECTION 信号基因
- **行为**：`close.pct_change(5)` ≥ 0 → 做多，< 0 → 做空
- **设计意图**：防止进化过程中 DIRECTION 基因丢失导致方向信息缺失
- **代码位置**：executor.py:726-731
- **关键问题**：**这段代码不可进化**。5 bar 回望期是硬编码的，不在 DNA 编码中，进化算法无法优化它

---

## 三、问题分析

### 问题 P1：动量兜底违背系统设计哲学

**现状**：系统的核心设计是"一切可进化"——所有交易决策都通过基因编码表示，进化算法可以搜索最优组合。但动量兜底是一个**代码级别的硬编码判断**，绕过了基因编码层。

**影响**：
- 进化过程中，如果变异操作（如 mutate_add_signal 的删除分支）移除了 DIRECTION 基因，策略不会失败，而是静默降级到不可进化的动量兜底
- 进化算法无法区分"有 DIRECTION 基因的 mixed 策略"和"无 DIRECTION 基因的 mixed 策略"的性能差异来源——可能是方向判定本身的问题，也可能是动量兜底的问题
- 搜索空间出现"暗区"：动量兜底的参数（5 bar 回望期）不在搜索空间内

**范围**：仅策略层（executor.py）。修复方式是确保 mixed 策略始终有 DIRECTION 基因，或在无 DIRECTION 基因时让策略 fitness 自然降低（而非用不可进化的兜底掩盖问题）

### 问题 P2：DIRECTION 基因表达能力受限

**现状**：DIRECTION 基因只支持 price_above/price_below 两种条件，只与 11 个趋势类指标比较。

**限制分析**：

| 维度 | 当前能力 | 缺失能力 |
|------|----------|----------|
| 条件类型 | price_above, price_below | cross_above, cross_below, gt, lt（数值阈值比较）|
| 指标类型 | 11 个趋势类指标 | 动量类（RSI, MACD, Stochastic）、波动率类（ATR）、趋势强度（ADX）|
| 基因数量 | 最多 1 个 | 多基因投票/共识机制 |
| 条件语义 | 价格 vs 指标线 | 指标 vs 指标（如 MACD signal 交叉）、指标 vs 固定阈值（如 RSI > 50）|

**影响**：
- 搜索空间受限：进化算法只能在 11 个指标 × 2 种条件中搜索方向判定策略
- 缺少动量类指标意味着 DIRECTION 基因无法表达"RSI 超卖反弹做多"这类逻辑
- 单基因限制意味着无法表达"EMA 趋势向上 AND RSI 未超买"这种复合方向判断

**范围**：仅策略层和进化层（executor.py 的方向判定逻辑 + population.py 的基因创建 + operators.py 的变异操作）。评估层无需修改。

### 问题 P3：方向无置信度

**现状**：entry_direction 是二值（+1 或 -1），没有中间状态。

**限制**：策略无法表达"强烈看多"和"微弱看多"的区别。评估层收到的信息只有方向，没有强度。

**范围**：这个改进**会跨越层边界**。如果只是策略层输出连续值，评估层不消费置信度，那输出连续值没有意义。要让置信度有意义，评估层需要用它来调节仓位大小或过滤弱信号。这意味着策略层 + 评估层（两条路径：backtest + trading）都需要修改。

---

## 四、进化层面的补充问题

### 问题 P4：direction 被进化引擎强制锁定

**现状**：进化引擎每代评估前执行 `ind.risk_genes.direction = self.direction`（engine.py:248），将所有个体的 direction 强制设为任务级值。

**影响**：
- `mutate_risk` 中 15% 的 direction 变异（operators.py:641-643）在效果上被抵消——变异出的 "short" 或 "mixed" 会在下一代被强制覆写回引擎设定值
- direction 作为一个进化维度被完全冻结，进化算法无法在这个维度上搜索

**是否需要修复**：这取决于产品设计意图。如果 direction 是用户明确指定的约束（"我只想要做多策略"），那强制锁定是合理的。如果希望进化算法能自由探索方向，那这个锁定应该改为"允许变异但不强制覆写"。

---

## 五、改进方案对比

| 方案 | 描述 | 架构影响 | 工程量 | 优先级建议 |
|------|------|----------|--------|------------|
| P1 | 消除动量兜底，确保 mixed 策略始终有 DIRECTION 基因 | 仅策略层 | ~30 行 | 高 |
| P2 | 扩展 DIRECTION 基因表达力：更多条件类型、更多指标、支持多基因 | 策略层 + 进化层 | ~150 行 | 中 |
| P3 | 方向置信度（连续值） | 策略层 + 评估层（跨层） | ~300+ 行 | 低 |
| P4 | 解除 direction 进化锁定 | 仅进化层 | ~5 行 | 独立决策 |

### P1 详细方案

目标：让 mixed 策略在没有 DIRECTION 基因时不再静默降级，而是以明确的失败信号让进化算法淘汰它。

改动点：
1. executor.py:726-731：删除动量兜底，改为 `entry_direction = pd.Series(0.0, ...)` 或抛出异常
2. population.py：确保 `create_random_dna` 和 `_dna_from_template` 在 direction="mixed" 时**始终**创建 DIRECTION 基因（当前已基本做到，但 mutate 删除基因的路径可能产生无 DIRECTION 基因的 mixed 策略）
3. operators.py 的 `mutate_remove_signal`：当删除的是 DIRECTION 基因且 direction="mixed" 时，拒绝删除或立即补充新 DIRECTION 基因

### P2 详细方案

目标：让 DIRECTION 基因能表达更丰富的方向判断逻辑。

改动点：
1. executor.py:690-696：DIRECTION 基因支持 gt/lt/cross_above/cross_below 等条件类型（不只是 price_above/price_below）
2. population.py:149-200：`_create_direction_gene` 扩展条件类型和指标池
3. executor.py:722-724：支持多个 DIRECTION 基因，用多数投票（majority vote）合成方向
4. operators.py：变异操作适配新的 DIRECTION 基因结构

### P3 详细方案（需谨慎评估）

目标：方向判定输出连续置信度 [-1, +1]，评估层根据置信度调节行为。

改动点（跨层）：
1. 策略层：entry_direction 从 ±1 改为连续值 [-1, +1]
2. 回测引擎：order_func_nb 用置信度调节仓位大小或设置入场阈值
3. 模拟交易：Decision/Pipeline 用置信度调节行为

### P4 详细方案

目标：让 direction 维度可进化。

改动点：
1. engine.py:248：移除 `ind.risk_genes.direction = self.direction` 强制覆写
2. 或者改为：仅在用户明确锁定时覆写，默认允许进化

---

## 六、待用户决策

请决策以下事项：
1. P1（消除动量兜底）是否实施？
2. P2（扩展 DIRECTION 基因表达力）是否实施？如果实施，需要哪些条件类型和指标？
3. P3（方向置信度）是否纳入？还是作为未来迭代？
4. P4（解除 direction 进化锁定）是否实施？当前锁定是设计意图还是遗留限制？
5. 实施顺序偏好？
