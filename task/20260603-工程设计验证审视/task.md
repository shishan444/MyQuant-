# 工程设计全局验证审视

> 日期: 2026-06-03
> 状态: 实施完成，全量测试通过

---

## 任务定义

从代码层验证 MyQuant 工程设计的实际有效性，用全局思维审视"发现策略 → 验证策略 → 使用策略"三大板块的真实状态。

核心验证问题：
1. 进化中心的指标是否真正在工程中被使用并产生价值
2. 进化的组合方式是否合理，工程是否具备理解设计合理性的能力
3. 系统从全局视角看，当前的设计方向是否正确，应该如何收束聚焦

---

## 研究第 1 轮

### 任务结构性理解

系统模块边界清晰：进化引擎是纯元启发式框架（通过 evaluate_fn 回调解耦），评分系统是纯函数，回测引擎封装 vectorbt。但模块之间的契约（特别是预计算列名约定）是隐式的字符串匹配，没有编译时保障。

**三层结构性断裂**：

1. **策略模板层面**：7 个模板中 5 个是"死策略"，永远无法产生交易信号。
   - mean_reversion：BB percent 列不存在，entry_trigger + exit_trigger 双断裂
   - trend_breakout：BB bandwidth 列不存在，AND 逻辑下 entry 全 False
   - dual_ma_cross：cross_above/cross_below 无 threshold 返回全 False（语义错误）
   - multi_tf_trend：同上，cross_above/cross_below 无 threshold
   - volatility：BB bandwidth 列不存在，AND 逻辑下 entry 全 False
   - 只有 trend_ema 完全有效，momentum 部分有效（exit_guard 断裂但 exit_trigger 正常）
   - 代码证据：population.py:22-146, executor.py:62-73, indicators.py:114-121

2. **Profile 引导层面**：推荐参数与 `_DEFAULT_PARAMS` 预计算集合的匹配率只有 70%（40/57），不是之前假设的 100%。
   - 3 个指标完全断裂：TEMA (0%)、Aroon (0%)、VWAP (无计算逻辑)
   - 10 个指标存在部分断裂：EMA (80%)、CCI (50%)、ROC (33%)、Keltner (33%)、Donchian (50%)、VROC (50%)、TRIX (50%)
   - 代码证据：indicator_profile.py vs indicators.py:32-83

3. **自由探索层面**：变异产生的参数几乎必然超出预计算范围。
   - EMA 断裂率 87.5%、RSI 88%、BB ~99%、MACD ~99%
   - 断裂基因被 `except ValueError: continue` 静默丢弃
   - 代码证据：executor.py:690-698, indicators.py:32-83

**进化资源效率估算**：
- 40% 模板种群 × 14% 有效 (1/7) = 5.6% 有效个体
- 40% Profile 引导 × 70% 匹配 = 28% 有效个体
- 20% 自由探索 × ~10% 匹配 = 2% 有效个体
- 总体有效评估约 35.6%，约 65% 的回测计算资源被浪费

### 任务认知变化

之前讨论认为"发现能力已足够，瓶颈在闭环管道"。代码验证揭示了更根本的问题：**发现能力本身有严重的结构性效率问题**。

关键发现：
1. 5/7 策略模板是死的（代码证据：population.py:22-146），这不只是"效率低"而是"进化的起点就是有缺陷的"
2. Profile 引导不是安全港（70% 匹配率），即使"引导"路径也有 30% 断裂
3. 系统没有样本外验证机制，进化找到的"好策略"无法排除过拟合

这三层问题叠加后，进化的实际搜索效率远低于设计意图。系统不是在"高效搜索策略空间"，而是在"浪费大部分资源评估无效个体"。

### 待消解的不确定性

1. **变异是否可能修复死模板** — mutate_indicator 替换 BB 为其他 volatility 指标时，field_name 会被重置。但 fallback 机制（population.py:634-637）保留了死模板 seed。需要量化修复概率。
   - 初步判断：修复概率低（需要特定变异序列），但不为零。这不改变主要结论。

2. **过拟合的实际严重程度** — 没有 train/test 分割是理论风险。如果策略搜索空间中有效策略密度极低（考虑到布尔逻辑的表达力限制），那即使找到 fitness>=1.0 的策略，大概率是历史数据的巧合。
   - 这无法通过代码验证回答，需要运行时数据。

3. **布尔信号组合的表达力是否足够** — AND/OR 逻辑将连续市场状态降维为 True/False。MTF 引擎的连续评分是改善，但仅限跨层。这是设计选择还是设计限制？
   - 这涉及量化策略的表达能力边界，需要讨论。

### 决策

研究完成。三个待消解的不确定性中，#1 可以通过代码分析初步判断（修复概率低，不改变结论），#2 和 #3 是设计层面的讨论问题，不需要更多代码验证。进入推理链构建。

---

## 推理链

### 一、任务定义

修复进化引擎"发现策略"板块的三层结构性断裂（死模板 + Profile 参数不匹配 + 无效指标），将进化评估资源有效率从 ~35% 提升到 ~90% 以上。

### 二、现状定位

进化引擎通过 `evaluate_fn` 回调与评估流程解耦，模块边界清晰。但"DNA 参数 → 预计算列名"这条隐式契约存在三层断裂：

**断裂层 1：策略模板 5/7 死策略** [代码设计问题]

population.py:22-146 中 7 个模板有 5 个永远无法产生交易信号：

| 模板 | 死因 | 断裂基因 | 代码证据 |
|------|------|----------|----------|
| mean_reversion | BB `percent` 列不存在 | entry_trigger + exit_trigger | population.py:59-73, indicators.py:114-121 |
| trend_breakout | BB `bandwidth` 列不存在 | entry_guard (AND 逻辑) | population.py:74-91 |
| dual_ma_cross | `cross_above` 无 threshold 返回全 False | entry_trigger + exit_trigger (语义错误，应用 cross_above_series) | population.py:92-109, executor.py:63-67 |
| multi_tf_trend | `cross_above` 无 threshold 返回全 False | entry_trigger + exit_trigger | population.py:110-127 |
| volatility | BB `bandwidth` 列不存在 | entry_guard (AND 逻辑) | population.py:128-146 |

这 5 个模板在种群初始化时（population.py:618，占 40% 种群）产生的个体永远不交易，浪费评估资源且污染种群多样性。

**断裂层 2：Profile 推荐参数 30% 不在预计算集合内** [代码设计问题]

indicator_profile.py 中 57 个推荐参数值有 17 个不在 indicators.py:32-83 的 `_DEFAULT_PARAMS` 中（匹配率 70%）。断裂的指标：

| 指标 | 推荐值 | 预计算值 | 匹配率 |
|------|--------|----------|--------|
| TEMA | 9, 25 | 10, 20, 50 | 0% |
| Aroon | 14 | 25 | 0% |
| VWAP | 无参数 | 无计算逻辑 | N/A (无实现) |
| EMA | 7 | 10, 20, 50, 100, 200 | 80% |
| CCI | 14 | 20 | 50% |
| ROC | 9, 14 | 12 | 33% |
| Keltner | mult 1.0, 1.5 | mult 2.0 | 33% |
| Donchian | 50 | 20 | 50% |
| VROC | 20 | 14 | 50% |
| TRIX | 25 | 12 | 50% |

**断裂层 3：无效指标出现在进化可选范围** [架构设计问题]

3 个指标在进化中必然失败但可被选中：
- VWAP：INDICATOR_REGISTRY 有定义，但 `_compute_indicator()` 无计算分支，`_DEFAULT_PARAMS` 无条目（registry.py:87-93, indicators.py 全文无 VWAP）
- FractalEntropy：`compute_mode="lazy"` + `skip_lazy=True`，默认不计算（registry.py:403-412）
- MultifactorOsc：同上（registry.py:413-420）

### 三、解决策略

**核心策略：向下对齐，不做向上扩展。** 将 Profile 推荐参数和模板对齐到已有的 `_DEFAULT_PARAMS` 预计算集合，而不是扩展 `_DEFAULT_PARAMS` 来覆盖所有推荐。原因：

1. 增加预计算参数意味着每个指标多算 N 组列，增加内存和计算时间
2. 很多断裂的推荐参数与预计算值差异很小（如 EMA period=7 vs 10，CCI period=14 vs 20），对进化搜索价值有限
3. 向下对齐只需修改 Profile 和模板配置，不改计算引擎，风险和复杂度最低

**排除的方案**：
- 按需计算指标（DNA 请求什么参数就实时计算）：需要重构整个预计算架构，风险太大，超出"修复地基"的范围
- 扩展 `_DEFAULT_PARAMS` 覆盖所有推荐：增加计算开销，且不解决模板语义错误
- 重写信号组合逻辑（将 AND/OR 改为连续评分）：超出修复范围，属于设计演进

**具体策略**：

**S1：修复 5 个死模板** — 用有效的指标/字段/条件替换断裂基因，保持每个模板的策略语义（趋势跟踪、均值回归、动量、突破、波动率）

**S2：对齐 Profile 推荐参数到 `_DEFAULT_PARAMS`** — 将断裂的推荐参数替换为最近的预计算值

**S3：清理无效指标** — 确保进化引擎不会选中无法计算的指标

### 四、范围边界

**改动文件**：

| 文件 | 改动内容 | 原因 |
|------|----------|------|
| `core/evolution/population.py` | 修复 STRATEGY_TEMPLATES 中 5 个死模板的基因定义 | 断裂层 1 的直接修复 |
| `core/features/indicator_profile.py` | 将断裂的推荐参数对齐到 `_DEFAULT_PARAMS` | 断裂层 2 的直接修复 |
| `core/features/registry.py` | 标记无法计算的指标，或从进化可选池中排除 | 断裂层 3 的直接修复 |
| `core/features/indicators.py` | 可选：为 BB 添加 percent/bandwidth 计算或确认删除策略 | 修复 BB 字段缺失 |

**不改的文件**：

| 文件 | 排除原因 |
|------|----------|
| `core/evolution/engine.py` | 进化引擎逻辑无 bug，不依赖具体指标 |
| `core/strategy/executor.py` | 信号生成逻辑正确，断裂的根源不在 executor |
| `core/backtest/engine.py` | 回测引擎无问题 |
| `core/scoring/scorer.py` | 评分逻辑无问题 |
| `api/runner.py` | Runner 编排逻辑无问题 |
| `web/` 前端 | 本次修复不涉及前端变更 |

### 五、行为规格

#### S1: 策略模板修复

**S1.1 mean_reversion 模板修复** `[测试验证]`
- 前置：模板中所有 SignalGene 引用的指标列必须存在于预计算 DataFrame
- 行为：entry_trigger 和 exit_trigger 使用有效的指标和字段（非 BB percent）
- 后置：模板生成的 DNA 在回测中能产生非零交易信号

**S1.2 trend_breakout 模板修复** `[测试验证]`
- 行为：entry_guard 使用有效的指标列（非 BB bandwidth）
- 后置：AND 逻辑下 entry 信号不全为 False

**S1.3 dual_ma_cross 模板修复** `[测试验证]`
- 行为：使用 `cross_above_series` 条件类型（带 target_indicator）替代无 threshold 的 `cross_above`
- 后置：EMA(9) 穿越 EMA(21) 时产生正确的交叉信号

**S1.4 multi_tf_trend 模板修复** `[测试验证]`
- 行为：同 S1.3，使用正确的交叉信号条件
- 后置：entry_trigger 和 exit_trigger 能产生非全 False 信号

**S1.5 volatility 模板修复** `[测试验证]`
- 行为：entry_guard 使用有效的波动率指标（非 BB bandwidth）
- 后置：AND 逻辑下 entry 信号不全为 False

**S1.6 模板验证** `[测试验证]`
- 不变量：所有 7 个模板的每个 SignalGene 都能在预计算 DataFrame 中找到对应列
- 不变量：所有模板在标准回测数据上能产生非零交易信号

#### S2: Profile 参数对齐

**S2.1 推荐参数对齐到 `_DEFAULT_PARAMS`** `[代码审查]`
- 行为：indicator_profile.py 中每个指标的 `recommended_params` 值都在 `_DEFAULT_PARAMS` 中有对应条目
- 后置：Profile 引导路径（70% 概率）产生的 DNA 基因参数 100% 能找到预计算列
- 具体对齐规则：
  - EMA period=7 → period=10（最近的预计算值）
  - TEMA period=9 → period=10, period=25 → period=20
  - Aroon period=14 → period=25
  - CCI period=14 → period=20
  - ROC period=9 → period=12, period=14 → period=12
  - Keltner mult=1.0 → mult=2.0, mult=1.5 → mult=2.0
  - Donchian period=50 → period=20
  - VROC period=20 → period=14
  - TRIX period=25 → period=12

**S2.2 对齐后验证** `[测试验证]`
- 不变量：Profile 推荐的每个参数组合，`resolve_indicator_column()` 生成的列名都能在 `compute_all_indicators()` 产出的 DataFrame 中找到

#### S3: 无效指标清理

**S3.1 VWAP 处理** `[代码审查]`
- 行为：VWAP 在进化中不可被选中（作为 trigger 或 guard）
- 实现：确认 VWAP 已有 `guard_only=True`（registry.py:93），验证其在 `create_random_dna()` 的 trigger_indicators 列表中被排除（population.py:400-403）

**S3.2 ML 指标处理** `[代码审查]`
- 行为：FractalEntropy 和 MultifactorOsc 在 `compute_mode="lazy"` 期间不被进化引擎选中
- 实现方案选择：
  - 方案 A：在 INDICATOR_REGISTRY 中为这两个指标添加 `evolution_available=False` 标记
  - 方案 B：将 `compute_mode` 改为 `"eager"` 使其参与预计算
  - 方案 C：在 `create_random_dna()` 中过滤 `compute_mode="lazy"` 的指标

**S3.3 清理后验证** `[测试验证]`
- 不变量：进化引擎可选指标池中的每个指标，在 `compute_all_indicators(skip_lazy=True)` 产出的 DataFrame 中都有对应的预计算列

### 六、风险披露

| 风险 | 确定性 | 影响 | 缓解 |
|------|--------|------|------|
| 模板修复改变进化搜索方向 | 确定 | 5 个模板的语义从"死"变为"活的替代策略"，可能影响进化收敛特性 | 修复后的模板保持原策略类别语义（趋势/均值回归/动量/突破/波动率） |
| Profile 对齐减少搜索多样性 | 确定 | 部分参数被合并到最近的预计算值（如 EMA 7→10），搜索空间缩小 | 缩小的参数差异本身对策略效果影响极小（EMA 7 vs 10 行为高度相似） |
| S3 ML 指标处理的方案选择 | 待确认 | 方案 B（改为 eager）增加预计算开销，方案 A/C 保持 lazy 但牺牲进化覆盖 | 取决于 ML 指标的计算成本和实际价值判断 |
| 修复后进化效率提升但过拟合风险仍在 | 确定 | 本次修复只解决效率问题，不解决可靠性问题 | 样本外验证属于第二优先，不在本次范围 |

### 七、实施顺序

```
Step 1: S1 策略模板修复 [高风险，核心]
  ├─ 1a: mean_reversion — 替换 BB percent 为有效字段
  ├─ 1b: trend_breakout — 替换 BB bandwidth 为有效指标
  ├─ 1c: dual_ma_cross — 修复 cross_above 语义错误
  ├─ 1d: multi_tf_trend — 修复 cross_above 语义错误
  ├─ 1e: volatility — 替换 BB bandwidth 为有效指标
  └─ 1f: 编写模板验证测试
  → 依赖：无
  → 验证：每个模板生成的 DNA 在回测中产生非零交易

Step 2: S2 Profile 参数对齐 [中风险]
  ├─ 2a: 修改 indicator_profile.py 推荐参数
  └─ 2b: 编写参数匹配验证测试
  → 依赖：无（与 Step 1 独立）
  → 验证：推荐参数 100% 在 _DEFAULT_PARAMS 中

Step 3: S3 无效指标清理 [低风险]
  ├─ 3a: 确认 VWAP guard_only 机制有效
  ├─ 3b: 处理 ML 指标（待确认方案）
  └─ 3c: 编写指标池有效性验证测试
  → 依赖：无
  → 验证：可选指标池中每个指标都有对应预计算列

Step 4: 集成验证
  └─ 4a: 运行全量测试确认无回归
  └─ 4b: 运行一次短进化验证策略产出有效性
  → 依赖：Step 1, 2, 3 全部完成
```
