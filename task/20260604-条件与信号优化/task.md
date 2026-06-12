# 进化引擎条件类型与信号组合优化

> 日期: 2026-06-04
> 状态: 推理链构建中

---

## 研究第 1 轮

### 限制 2：固定条件类型的深入分析

**现状**：`evaluate_condition()` (executor.py:31-107) 支持 16 种条件类型，分四个阶段：

| 阶段 | 条件类型 | 数量 |
|------|----------|------|
| Phase 1 基础比较 | eq, lt, gt, le, ge, cross_above, cross_below, price_above, price_below | 9 |
| Phase 2 动态交叉 | cross_above_series, cross_below_series | 2 |
| Phase 3 回看窗口 | lookback_any, lookback_all | 2 |
| Phase 4 支撑/阻力 | touch_bounce, role_reversal, wick_touch | 3 |

**Profile 推荐中缺失的条件类型**（6 种）：
- `cross_above_series` / `cross_below_series`：双指标交叉（5 个指标支持）
- `lookback_any` / `lookback_all`：回看窗口条件（3 个指标支持）
- `le` / `ge`：不等式（仅 RSI 支持）

**种群中条件类型的实际生成路径**：

| 来源 | 比例 | 条件类型范围 |
|------|------|-------------|
| 硬编码模板 | 40% | 模板固定，不受 Profile/自由探索影响 |
| Profile 引导 | 28%（40%×70%） | 仅推荐中的 8 种基础类型 |
| 自由探索（Profile 失效时） | 12%（40%×30%） | 该指标的 supported_conditions 全部类型 |
| 纯自由探索 | 20% | 该指标的 supported_conditions 全部类型 |

因此 **32% 的种群可以访问所有支持的 16 种条件类型**。Profile 缺失高级条件不是结构性锁死，是引导偏差。

**进一步分析**：高级条件在自由探索中能被选中但概率低。以 EMA 为例：
- `cross_above_series` 概率 = 30% × 1/6 = 5%（仅在自由探索时才可能）
- 如果 Profile 加入 `cross_above_series`，概率可提升到约 17.5%

**根因**：不是引擎限制，是 Profile 配置不完整。

### 限制 3：AND/OR 信号组合的深入分析

**现状**：系统已有双通道设计：
1. **entries/exits**（布尔）：决定"是否交易" — `combine_signals()` AND/OR
2. **confidence**（浮点 [0.1, 1.0]）：决定"交易多大" — `_compute_confidence()` 加权评分

MTF 引擎的加权评分模型 (mtf_engine.py:599-619)：
```python
confidence = confluence * 0.5 + momentum * 0.3 + |direction| * 0.2
```

这个模型**已经在工作**，用于跨层综合。单层内仍是 AND/OR。

**升级到浮点 entries 的影响**：

| 模块 | 需要改动 | 风险 |
|------|----------|------|
| `executor.py:combine_signals()` | `&`/`|` 运算符对浮点截断为 0/1 | 需要新的组合函数 |
| `backtest/engine.py:419` | `.astype(bool)` 会截断浮点值 | 需要改为 `.fillna(0.0)` |
| `mtf_engine.py:684` | `entries & direction_pass` 布尔与 | 需要改为 `entries * direction_pass` |
| `types.py:84` | `bool(sig_set.entries)` | 需要改为保留浮点 |
| `trading/pipeline.py:153` | BarSignals 布尔转换 | 需要改为浮点 |
| `executor.py:resample_signals()` | `.astype(bool)` | 需要用 `resample_values()` |

6 个模块需要改动，且 `order_func_nb` (engine.py:249) 的 `entries > 0.5` 虽然兼容浮点，但语义变为"置信度 0.6 的 entry 和 0.9 的 entry 都触发交易"——区分度被丢弃。要利用置信度差异调整仓位大小，需要进一步修改 order 逻辑。

**关键发现**：`confidence` 通道已经在做仓位缩放（order_generator.py:94: `entry_pct *= max(signals.confidence, 0.1)`）。也就是说，加权评分的价值已经在被提取——只是发生在 `confidence` 字段而不是 `entries` 字段上。

### 决策

**限制 2 是真问题但优先级低**：Profile 缺失高级条件类型可以通过配置修复，不改引擎代码。但 S1（按需计算）已大幅扩展参数空间，高级条件的边际收益需要实际运行数据评估。

**限制 3 在当前设计下已被缓解**：双通道设计（布尔 entries + 浮点 confidence）已经分离了"是否交易"和"交易多大"的决策。升级 entries 为浮点的 6 模块重构，收益是"单层内也做加权评分"，但 MTF 引擎已经在跨层做这件事了。

进入推理链构建。

---

## 推理链

### 一、任务定义

为 Profile 推荐条件类型补充高级条件（cross_above_series, lookback_any, lookback_all 等），让 Profile 引导路径也能探索更丰富的条件组合。同时评估信号组合升级的必要性和时机。

### 二、现状定位

**限制 2 的关键点**：Profile 引导（70% 概率）只推荐 8 种基础条件类型 [代码设计问题]

代码证据：
- indicator_profile.py：recommended_conditions 仅使用 lt/gt/cross_above/cross_below/price_above/price_below/eq/touch_bounce/role_reversal
- operators.py:88：自由探索使用 `random.choice(reg.supported_conditions)`，可访问所有 16 种
- 但 32% 的种群（自由探索）可以访问高级条件，68% 不能

影响量化：以支持 `cross_above_series` 的 5 个指标（EMA, SMA, WMA, DEMA, TEMA, Aroon, VWMA）为例，在 Profile 引导路径中这些指标永远不会生成双指标交叉条件。而双指标交叉（如 EMA 短期穿长期）是经典趋势跟踪信号的核心。

**限制 3 的关键点**：双通道设计已部分缓解加权评分需求 [架构设计已覆盖]

代码证据：
- mtf_engine.py:599-619：`_compute_confidence()` 已实现 confluence*0.5 + momentum*0.3 + |direction|*0.2
- mtf_engine.py:622-709：`apply_decision_gate()` 用布尔门控过滤 entries，但保留 confidence 浮点值
- order_generator.py:94：`entry_pct *= max(signals.confidence, 0.1)` 已使用 confidence 做仓位缩放
- executor.py:272-288：`combine_signals()` 是纯 AND/OR，单层内无加权

### 三、解决策略

**S1：补充 Profile 高级条件推荐**（限制 2 的修复）

为支持高级条件的指标在 Profile 中添加推荐。策略是"窄而精"——只为语义明确的指标-条件组合添加推荐，不为所有指标泛化。

选择原因：
- 最小改动（仅修改 indicator_profile.py 配置，不改引擎代码）
- 风险为零（不改变计算逻辑，只改变引导概率）
- 高级条件已在自由探索中被验证可用（引擎支持，只是 Profile 不推荐）

排除的方案：
- 为所有指标添加所有支持的条件类型：过度泛化，很多组合无交易语义（如 OBV 的 touch_bounce）
- 移除 Profile 引导（让进化 100% 自由探索）：Profile 引导的 70% 命中率确保了已知有效路径不被浪费

**S2：信号组合暂不升级**（限制 3 的决策）

在当前阶段，限制 3 不做代码改动。原因：
1. 双通道设计（布尔 entries + 浮点 confidence）已覆盖"加权评分"需求
2. MTF 引擎的 `_compute_confidence()` 已在跨层做加权评分
3. 单层 AND/OR 在 S1 按需计算大幅扩展参数空间后，可能已经够用
4. 6 模块重构风险高、收益不确定

需要等待 S1（按需计算）+ S1 本次改动实际运行进化后的数据来验证 AND/OR 是否成为瓶颈。

### 四、范围边界

**改动文件**：

| 文件 | 改动内容 | 原因 |
|------|----------|------|
| `core/features/indicator_profile.py` | 为趋势类指标添加 cross_above_series 推荐条件；为 BB 等添加 lookback 推荐条件 | 限制 2 的直接修复 |
| `tests/test_evolution_effectiveness.py` | 添加高级条件推荐对齐验证 | 测试 |

**不改的文件**：

| 文件 | 排除原因 |
|------|----------|
| `core/strategy/executor.py` | combine_signals AND/OR 不改动（限制 3 暂不修复） |
| `core/strategy/mtf_engine.py` | 置信度模型已工作 |
| `core/backtest/engine.py` | 布尔信号兼容浮点（> 0.5 阈值） |
| `core/evolution/operators.py` | 条件生成逻辑正确，只需修改 Profile 输入 |
| `core/evolution/engine.py` | 进化引擎无 bug |

### 五、行为规格

#### S1: Profile 高级条件补充

**S1.1 趋势类指标添加 cross_above_series 推荐** `[代码审查]`
- 行为：EMA, SMA, WMA, DEMA, TEMA, VWMA 的 recommended_conditions 包含 cross_above_series 和 cross_below_series
- 后置：Profile 引导路径中这些指标可以生成双指标交叉条件
- 具体：ConditionPreset("cross_above_series", []) 和 ConditionPreset("cross_below_series", [])

**S1.2 BB 添加 lookback_any/all 推荐** `[代码审查]`
- 行为：BB 的 recommended_conditions 包含 lookback_any 和 lookback_all
- 后置：BB 相关策略可以使用回看窗口条件

**S1.3 Profile 条件类型必须在该指标的 supported_conditions 中** `[测试验证]`
- 不变量：每个 Profile recommended_conditions 中的条件类型，都在 INDICATOR_REGISTRY 中该指标的 supported_conditions 列表中有对应条目
- 前置：验证已有此测试（test_evolution_effectiveness.py:TestProfileParameterAlignment.test_profile_conditions_use_supported_types）

### 六、风险披露

| 风险 | 确定性 | 影响 | 缓解 |
|------|--------|------|------|
| 添加高级条件推荐可能降低基础条件的选中率 | 确定 | cross_above_series 与 cross_above 共享概率，但 cross_above_series 是更有表达力的条件，这是正向权衡 | 添加后 cross_above 概率降低是预期行为 |
| cross_above_series 需要目标指标参数 | 确定 | operators.py:91-110 中 _pick_series_target() 已实现目标选取逻辑 | 已有实现 |
| lookback 条件需要内层条件 | 确定 | operators.py:131-143 已实现内层条件随机生成 | 已有实现 |
| 限制 3 暂不修复可能遗漏问题 | 不确定 | AND/OR 在更大参数空间中是否够用，需要运行时数据验证 | 标记为后续评估项 |

### 七、实施顺序

```
Step 1: S1 Profile 高级条件补充 [低风险]
  ├─ 1a: 为 EMA/SMA/WMA/DEMA/TEMA/VWMA 添加 cross_above_series/cross_below_series
  ├─ 1b: 为 BB 添加 lookback_any/lookback_all
  ├─ 1c: 为 Aroon 添加 cross_above_series（Aroon 支持，语义为 Aroon Up 穿越 Aroon Down）
  └─ 1d: 验证测试通过
  → 依赖：无
  → 验证：test_profile_conditions_use_supported_types 通过

Step 2: 运行全量测试
  └─ 2a: 确认无回归
  → 依赖：Step 1
```
