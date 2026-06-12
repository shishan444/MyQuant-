# MTF 工作引擎 -- 最终设计方案

> 日期: 2026-04-25
> 状态: 设计已确认，待实施
> 前置: Phase E-K bug 修复已完成（V1~V9 全部修复，669 tests passing）
> 说明: 本文档是完整、自包含的设计方案。不引用任何外部文档，所有细节均在本文件内。

---

## 一、是什么：MTF 工作引擎的逻辑描述

### 1.1 现在系统的问题

进化系统生成一个多周期策略（如 3d EMA + 4h BB + 15m RSI），执行时每个周期只能回答"该不该交易"，答案是"是"或"否"。三个周期的"是/否"用 AND 或 OR 组合得出最终决策。

**问题**：每个周期把丰富的指标数值（EMA 在 60000、BB 下轨在 60500）烧成了一个简单的"是/否"。三个周期之间只能用"是/否"交流，无法传递"价格在什么位置"、"趋势是什么方向"等关键信息。

### 1.2 MTF 引擎是什么

一个**多周期综合决策工具**。它让每个时间周期不仅能回答"该不该交易"，还能告诉系统"我关注的价格位置在哪里"、"我看到的方向是什么"。然后综合所有周期的信息，计算一个评分：**当前价格位置，有多少个周期在同时关注它？**

### 1.3 它做了三件事

1. **让每个周期说出判断依据**：3d 层不仅说"是"，还说"趋势向上，EMA200 在 60000"
2. **综合所有周期的依据**：检查价格 60300 是否同时接近 3d 的 60000 和 4h 的 60500，计算区间重合度
3. **用综合评分门控决策**：15m 说"该入场" AND 方向一致 AND 区间重合度达标，才执行交易

### 1.4 与什么结合产生什么价值

| 结合对象 | 结合方式 | 产生的价值 |
|---------|---------|-----------|
| 现有信号管线 | 管线是"时机轨道"（什么时候该交易），完全不变。MTF 引擎新增"上下文轨道"（当前价格位置是否合理）。两个轨道并行工作 | 不破坏已有逻辑，只在原有信号上增加过滤 |
| 进化系统 | 进化可以探索不同的多周期协作模式（只用方向过滤、只用价格位共振、组合使用） | 进化搜索空间更大，能发现更精细的交易逻辑 |
| 回测引擎 | MTF 引擎在 Python 端完成计算，产出布尔信号传入 Numba 回测引擎，接口不变 | 零风险集成，VectorBT 和 Numba 函数无需修改 |
| 指标系统 | 所有指标数值已在 DataFrame 中预计算，MTF 引擎只是读取这些数值并提取语义信息 | 不增加计算开销，复用已有基础设施 |

---

## 二、解决什么问题：根因分析

### 2.1 根本原因：evaluate_condition() 是信息黑洞

当前 MTF 信号管线的完整数据流：

```
SignalGene (DNA定义)
  -> _get_indicator_column(df, gene)     -> pd.Series (数值)    <- 数值仍存在
  -> evaluate_condition(series, close, condition) -> pd.Series (布尔)  <- 数值在此被烧毁
  -> combine_signals([bool], AND/OR)     -> pd.Series (布尔)
  -> SignalSet (entries/exits/adds/reduces, 全部布尔)
  -> BacktestEngine._build_portfolio()   -> 布尔数组
  -> order_func_nb (Numba JIT)           -> 交易执行
```

### 2.2 六个具体问题（代码级验证）

| # | 问题 | 代码证据 | 影响 |
|---|------|---------|------|
| 1 | **evaluate_condition() 是信息黑洞** | executor.py L28-104：所有分支返回布尔值。L423-424：indicator_col 是局部变量，调用后丢弃 | 所有指标的语义信息（方向、价格位、动量、强度）在评估后全部丢失 |
| 2 | **层与层之间完全隔离** | executor.py L567：每层独立调用 evaluate_layer()，返回的 SignalSet 只含布尔 | 不同周期的层无法传递任何数值信息 |
| 3 | **跨层组合只有 AND/OR** | executor.py L637-669：用 combine_signals() 对布尔做 AND/OR | 无法表达"方向一致且价格区间重合"等复合条件 |
| 4 | **无指标类型系统** | dna.py SignalGene：无 MTF 信息类型声明。registry.py IndicatorDef：无 MTF 能力声明 | 系统不知道 EMA 能提供方向、BB 能提供价格区间 |
| 5 | **角色只有 trend/execution** | dna.py L162：role 只接受 "trend"/"execution"/None | 无法区分"提供方向"的结构层和"提供价格区间"的判断层 |
| 6 | **进化盲目选择指标** | operators.py L197：mutate_add_layer() 始终设置 role="execution"，随机选指标 | 进化不知道 BB 放在判断层比放在执行层更有价值 |

### 2.3 交易需求的差距

用户描述的多周期协作逻辑：

- 3d 层（结构层）-> 趋势方向 + 关键价格位
- 4h 层（判断层）-> 价格区间参考
- 15m 层（执行层）-> 入场/出场时机
- 多层价格区间重合时信号可信度最高

当前系统无法实现以上任何一种协作，因为：
1. 无法传递价格值（只能传 True/False）
2. 无法判断"价格是否同时接近多个周期的关注区域"
3. 无法衡量"重合程度"（只有 0 或 1）

---

## 三、怎么设计的：双轨道 + 三阶段管线

### 3.1 核心架构

```
当前架构（单轨道）:
  SignalGene -> evaluate_condition() -> boolean -> combine(AND/OR) -> SignalSet

新架构（双轨道 + 三阶段）:
  SignalGene --+-> evaluate_condition() -> boolean (时机轨道，不变)
               +-> extract_context()     -> typed info (上下文轨道，新增)
                     |
               LayerResult = {时机布尔 + 上下文信息}
                     |
               Stage 2: 跨层综合 -> MTFSynthesis {各维度分数}
                     |
               Stage 3: 决策门控 -> final SignalSet (布尔)
                     |
               BacktestEngine (接口不变，仍收布尔数组)
```

### 3.2 Stage 1: 层评估（Layer Evaluation）

**输入**：每个时间周期层的 SignalGene 列表 + 对应 DataFrame

**处理**：对每个 SignalGene 并行执行两条轨道

- **时机轨道**（已有，不变）：`evaluate_condition()` -> 布尔信号
- **上下文轨道**（新增）：`extract_context()` -> 类型化信息

**输出**：`LayerResult`

```python
@dataclass
class LayerResult:
    """单层评估结果：时机信号 + MTF 上下文"""
    # 时机轨道（已有逻辑的产出）
    signal_set: SignalSet                    # entries/exits/adds/reduces 布尔

    # 上下文轨道（新增）
    direction: pd.Series | None              # 方向信号 (+1/-1)
    price_levels: list[pd.Series]            # 价格位数值列表
    momentum: pd.Series | None               # 动量方向 (+1/-1)
    strength: pd.Series | None               # 强度值 (0~1)
    volatility: pd.Series | None             # 波动率状态 (0~1)
```

### 3.3 Stage 2: 跨层综合（Cross-Layer Synthesis）

**输入**：所有层的 LayerResult（已重采样到执行周期索引）

**处理**：按维度计算各层信息的综合分数

- 方向维度 -> direction_score
- 价格位维度 -> confluence_score（s% + 区间重合法）
- 动量维度 -> momentum_score
- 强度维度 -> strength_multiplier

**输出**：`MTFSynthesis`

```python
@dataclass
class MTFSynthesis:
    """多周期综合评估结果（每根执行层 bar 一组值）"""
    direction_score: pd.Series       # 方向一致性 (-1.0 ~ +1.0)
    confluence_score: pd.Series      # 价格位区间重合 (0.0 ~ 1.0)
    momentum_score: pd.Series        # 动量对齐 (0.0 ~ 1.0)
    strength_multiplier: pd.Series   # 强度乘数 (0.0 ~ 1.0)
```

### 3.4 Stage 3: 决策门控（Decision Gate）

**输入**：执行层时机信号 + MTFSynthesis + 策略 DNA 配置

**处理**：根据 DNA 中的 `mtf_mode` 配置，决定激活哪些维度进行门控

```
entry = exec_timing_signal (来自时机轨道)
if mtf_mode includes "direction":
    entry &= direction_score agrees with trade_direction
if mtf_mode includes "confluence":
    entry &= confluence_score >= confluence_threshold
if mtf_mode includes "momentum":
    entry &= momentum_score >= momentum_threshold
```

**输出**：`SignalSet`（布尔，与现有接口完全一致）

### 3.5 三个角色的职责

| 角色 | 周期范围 | 职责 | 产出 |
|------|---------|------|------|
| structure（结构层） | 1d, 3d | 趋势方向 + 关键价格位 | 方向(+1/-1) + 支撑/阻力价格序列 |
| zone（判断层） | 1h, 4h | 价格区间参考 | 布林带/KC/DC 上下轨价格序列 |
| execution（执行层） | 15m, 30m | 入场/出场时机 | 布尔信号 + K线形态触发 |

角色从周期自动推导：
```
>= 1d -> structure (结构层)
>= 1h -> zone (判断层)
执行周期 -> execution (执行层)
```

层级规则：最少 1 层（单周期），最多 3 层。

### 3.6 三种组合类型

| 类型 | 层配置 | 角色覆盖 | 综合维度 | 方向来源 |
|------|-------|---------|---------|---------|
| A（完整） | 3d + 4h + 15m | structure + zone + execution | 方向 + 价格位 + 动量 + 强度 | structure 层条件推导 |
| B（部分） | 4h + 15m | zone + execution | 价格位 + 动量 | dna.risk_genes.direction 继承 |
| C（单周期） | 15m | execution | 无综合 | dna.risk_genes.direction |

自动推导规则：
```
if layers 中有 >= 1d 周期 -> 分配 structure 角色
if layers 中有 >= 1h 周期 -> 分配 zone 角色
执行周期层（由 execution_genes.timeframe 决定）-> execution 角色

Type A: 有 structure + zone + execution -> 完整共振
Type B: 有 zone + execution（无 structure）-> zone 价格位共振，方向从 DNA 继承
Type C: 只有 execution -> 跳过共振，走原始单周期路径
```

---

## 四、细节：核心算法

### 4.1 指标的 MTF 能力声明

每种指标有固定的 MTF 信息能力，这是客观事实，不需要进化去发现：

| 指标类别 | 代表指标 | 方向 | 价格位 | 动量 | 强度 | 统计位置 | 波动率 |
|---------|---------|:---:|:-----:|:---:|:---:|:------:|:----:|
| 均线类 | EMA/SMA/WMA | Y | Y | - | Y(距离) | Y | - |
| 通道类 | BB/KC/DC | Y(中轨) | Y(上下轨) | - | - | Y(%B) | Y(带宽) |
| 振荡器类 | RSI/MACD/Stoch | Y(方向) | - | Y | - | Y | - |
| 强度类 | ADX | - | - | - | Y | - | - |
| 追踪类 | PSAR | Y | Y | - | Y(距离) | - | - |
| 成交量类 | VP | - | Y(POC/VAH/VAL) | - | - | - | - |
| 波动率类 | ATR | - | - | - | - | - | Y |
| 形态类 | Patterns | - | - | - | - | - | - |

能力来源：利用已有的 `IndicatorDef.category`（registry.py）和 `IndicatorDef.output_fields`（registry.py）推导。

**已验证的支撑/阻力指标覆盖**：

| 方法 | S/R 来源 | 是否已支持 | 适用角色 |
|------|---------|:---------:|---------|
| 布林带 | 上轨=阻力，下轨=支撑，中轨=SMA20 | Y | zone/structure |
| 移动均线 | EMA200 等作为动态趋势线 | Y | structure |
| 唐奇安通道 | N 周期最高/最低价=天然 S/R | Y | zone |
| Keltner 通道 | ATR 通道上下轨 | Y | zone |
| PSAR | 抛物线止损=动态 S/R | Y | structure |
| Volume Profile | POC/VAH/VAL=成交量聚集区 | Y | zone |

结论：已有指标覆盖 structure 和 zone 层的支撑/阻力需求，无需新增指标。

### 4.2 价格位提取逻辑

每个层的 signal_genes 中，使用以下条件类型的基因会产生价格级输出：

| 条件类型 | 价格位来源 | 示例 |
|---------|-----------|------|
| `price_above` | 指标值本身（如 EMA_200 值） | EMA 作为趋势线 |
| `price_below` | 指标值本身 | EMA 作为压力线 |
| `touch_bounce` | 指标值（BB 下轨=支撑，上轨=阻力） | BB 带接触反弹 |
| `role_reversal` | 指标值 | 支撑/阻力互换 |
| `wick_touch` | 指标值 | 影线触及 |

非价格级条件（`lt`, `gt`, `cross_above`, `eq` 等，对应 RSI/MACD 等振荡器）不提取价格位，只产生布尔信号。

### 4.3 接近度计算（百分比幅度法 s%，已确认）

**设计过程**：

经过三轮方案演变：
- 方案 A（简单 ATR 阈值）：固定价格距离，BTC 6万和 ETH 3千需要不同参数 -> 否决
- 方案 B（交叉周期价差 ATR）：基于跨周期指标值差异的历史均值 -> 用户反馈"不对，应该是价格的幅度占比，而非固定值" -> 否决
- 方案 C（百分比幅度法 s%）：最终确认

**最终算法**：

```
对每根执行层 bar：
  s% = (ATR_14 / close) * proximity_mult    # ATR_14 已在 DataFrame 中预计算
  接近阈值 = close * s%                      # 转为价格距离

如果 |当前价格 - 参考价格位| <= 接近阈值 -> 该价格位"接近"

示例：close=60300, ATR_14=800, proximity_mult=1.5
  s% = (800 / 60300) * 1.5 = 1.99%
  接近阈值 = 60300 * 0.0199 = 1200
```

**自适应特性**：
- 高波动市场 -> ATR 大 -> s% 大 -> 阈值自动放宽
- 低波动市场 -> ATR 小 -> s% 小 -> 阈值自动收紧
- 高价资产（BTC 6万）和低价资产（ETH 3千）用同样的百分比逻辑，无需手动调参
- `proximity_mult` 默认 1.5，可通过进化调整（范围 0.5~3.0）

### 4.4 共振分数（区间重合法，已确认）

**设计过程**：

经过三轮方案演变：
- 方案 A（按价格位计数）：接近的价格位数量/总数量 -> 用户反馈"不合适，没有理解共振的作用和使用场景" -> 否决
- 方案 B（按层级计数）：有至少1个价格位接近的层数/总层数 -> 否决
- 方案 C（区间重合法）：最终确认。用户确认"区间重合方案合理"

**最终算法**：

```
Step 1：构建每层的关注区间
  对每个层的每个价格位 P：
    区间上界 = P * (1 + s%)
    区间下界 = P * (1 - s%)
  层关注区间 = 该层所有价格位区间的并集

Step 2：计算区间重合度
  所有层的关注区间取交集 -> 重合区域
  如果交集为空 -> 共振分数 = 0.0（各层关注的价位完全不同）
  如果交集存在 -> 计算重合区域宽度占最大层区间宽度的比例

Step 3：检查当前价格是否在重合区域内
  如果当前价格在重合区域内 -> 共振分数 = 重合度
  如果当前价格不在重合区域内 -> 共振分数 = 0.0
```

**直觉解释**：每个层级通过指标值告诉我们"我在关注什么价格区域"。当多个层级关注的价格区域有交集，且价格刚好在那个交集中 -> 共振。这比简单的"价格位计数"更准确，因为它衡量的是"区间重叠程度"而非"有多少个点恰好被触及"。

分数范围 [0.0, 1.0]：
- 0.0 = 各层关注的价格区域没有交集，或价格不在交集内
- 1.0 = 所有层的关注区间完全重合，且价格在其中
- 中间值 = 部分重叠，反映共振的强弱程度

### 4.5 入场/出场门槛

```
最终入场 = 执行层时机信号(15m)
          AND 共振分数 >= confluence_threshold
          AND 方向与结构层一致（Type A 必须，Type B 从 DNA 继承）

最终出场 = 执行层出场信号（不受共振限制，确保止损及时）

加仓 = 执行层加仓信号 AND 共振分数 >= confluence_threshold * 0.8
减仓 = 执行层减仓信号（不受共振限制，确保风险控制及时）
```

`confluence_threshold` 默认 0.3，可通过进化调整（范围 0.1~0.9）。

**设计决策说明**：
- 加仓需要共振分数稍低（threshold * 0.8），因为加仓是在已有仓位的基础上，价格已经接近关注区域
- 减仓和出场不受共振限制，因为风险控制的及时性比多周期确认更重要

---

## 五、已识别的四个设计缺口及解决方案

### 缺口 A：Add/Reduce 信号缺少 MTF 门控

**问题**：当前 MTF 分支中，adds 信号直接用 OR 组合（executor.py L654），没有 MTF 上下文过滤。这意味着即使价格远离多周期关注区域，加仓信号也可能执行。

**解决方案**：
- 加仓（adds）：需要共振分数 >= confluence_threshold * 0.8（低于入场门槛，因为价格已在关注区域附近）
- 减仓（reduces）：不受共振限制（风险控制优先）
- 出场（exits）：不受共振限制（止损优先）

### 缺口 B：单层 Type B 的共振降级

**问题**：Type B（4h + 15m）只有 1 个非执行层提供价格位，无法计算"区间交集"（至少需要 2 个层）。

**解决方案**：当只有 1 个非执行层时，退化为"接近度评分"（proximity score）：
```
proximity_score = 接近当前价格的价格位数量 / 该层总价格位数量
```
这仍然提供了价格位维度的信息，只是不如多层的区间重合那么精确。

### 缺口 C：多结构层方向冲突

**问题**：如果策略有多个 >= 1d 周期的层（如 3d 和 1d 都提供方向），可能出现方向不一致（3d 看多，1d 看空）。

**解决方案**：当有多个 structure 层时，**最高周期优先**。即 3d 的方向优先于 1d 的方向。
```
if 多个 structure 层方向冲突:
    direction_score = 最高周期层的方向
```

### 缺口 D：缺少 MTF 诊断信息

**问题**：当前 SignalSet 只传递布尔信号，没有 MTF 维度的评分信息。无法在回测结果中看到共振分数、方向一致性等诊断数据。

**解决方案**：在 SignalSet 中添加可选的 `mtf_diagnostics` 字典：
```python
@dataclass
class SignalSet:
    entries: pd.Series
    exits: pd.Series
    adds: pd.Series
    reduces: pd.Series
    entry_direction: pd.Series | None
    degraded_layers: int = 0
    # 新增
    mtf_diagnostics: dict | None = None  # 包含各维度分数的 Series
```

传播路径：SignalSet.mtf_diagnostics -> BacktestResult.metrics_dict（已有的字段）。

---

## 六、完整数据流走查

以真实的 3 层策略为例，追踪数据从 DNA 到最终交易的完整路径。

### 6.1 DNA 定义

```python
StrategyDNA(
    execution_genes=ExecutionGenes(timeframe="15m"),
    mtf_mode="direction+confluence",
    confluence_threshold=0.3,
    proximity_mult=1.5,
    layers=[
        TimeframeLayer(timeframe="3d", signal_genes=[
            SignalGene("EMA", {"period": 200}, ENTRY_TRIGGER, None, {"type": "price_above"}),
        ], role="structure"),
        TimeframeLayer(timeframe="4h", signal_genes=[
            SignalGene("BB", {"period": 20, "std": 2}, ENTRY_TRIGGER, "lower", {"type": "price_below"}),
            SignalGene("RSI", {"period": 14}, EXIT_TRIGGER, None, {"type": "gt", "threshold": 70}),
        ], role="zone"),
        TimeframeLayer(timeframe="15m", signal_genes=[
            SignalGene("RSI", {"period": 14}, ENTRY_TRIGGER, None, {"type": "lt", "threshold": 30}),
            SignalGene("RSI", {"period": 14}, EXIT_TRIGGER, None, {"type": "gt", "threshold": 70}),
        ], role="execution"),
    ],
)
```

### 6.2 Stage 1: 层评估

**3d 结构层：**

```
时机轨道：evaluate_condition(ema_200, close, {type: "price_above"})
  -> close > ema_200 -> 布尔 entries

上下文轨道：extract_context("EMA", {period:200}, "price_above")
  -> 调用 _get_indicator_column(df, gene) -> 获取 ema_200 数值 Series
  -> EMA 属于 "trend" 类别，条件为 price_above
  -> 输出：
    direction = +1 (where close > ema_200), -1 (where close < ema_200)
    price_levels = [ema_200 values]
    strength = (close - ema_200) / close
```

**4h 判断层：**

```
时机轨道：evaluate_condition(bb_lower_20_2, close, {type: "price_below"})
  -> close < bb_lower -> 布尔
  evaluate_condition(rsi_14, close, {type: "gt", threshold: 70})
  -> rsi > 70 -> 布尔 exits

上下文轨道：extract_context("BB", {period:20, std:2}, "price_below")
  -> BB 属于 "volatility" 类别
  -> _get_all_columns() 遍历 IndicatorDef.output_fields -> 获取 bb_upper/middle/lower 全部值
  -> 输出：
    price_levels = [bb_upper_20_2, bb_middle_20_2, bb_lower_20_2]
    volatility = (bb_upper - bb_lower) / bb_middle
```

**15m 执行层：**

```
时机轨道：evaluate_condition(rsi_14, close, {type: "lt", threshold: 30})
  -> rsi < 30 -> 布尔 entries

上下文轨道：执行层不需要上下文信息（只提供时机信号）
```

### 6.3 Stage 2: 跨层综合

```
对每根 15m bar：

1. 重采样 3d 和 4h 的上下文信息到 15m 索引
   resample_values(3d_direction, 15m_index) -> 15m 上的方向序列
   resample_values(3d_price_levels, 15m_index) -> 15m 上的 EMA200 值
   resample_values(4h_price_levels, 15m_index) -> 15m 上的 BB 上下中轨值

2. 方向维度：
   3d EMA200: close > ema_200 -> direction = +1 (做多)
   -> direction_score = +1

3. 价格位维度（s% + 区间重合）：
   s% = (15m_atr_14 / 15m_close) * 1.5

   3d EMA200=60000 -> 关注区间 [60000*(1-s%), 60000*(1+s%)]
   4h BB 下轨=60500, 中轨=62000, 上轨=63500
     -> 关注区间 [60500*(1-s%), 63500*(1+s%)] (三轨并集)

   计算交集 -> 重合区域
   检查当前价格是否在重合区域内 -> confluence_score

4. 强度维度：
   3d strength = (close - ema_200) / close -> strength_multiplier
```

### 6.4 Stage 3: 决策门控

```
mtf_mode = "direction+confluence"

对每根 15m bar：
  exec_entry = rsi_14 < 30  (时机轨道的布尔信号)

  if exec_entry:  # 时机信号存在，进一步检查上下文
    if direction_score (+1) 与 dna.direction (long) 一致: pass
    if confluence_score >= confluence_threshold (0.3): pass
    -> 最终 entry = True
    else:
    -> 最终 entry = False  (时机到了但上下文不满足)
  else:
    -> 最终 entry = False  (时机未到)

  exit 信号不受门控限制（确保止损及时）
```

### 6.5 传入 VectorBT

```
最终 entry = 布尔 Series (15m 索引)
最终 exit = 布尔 Series (15m 索引)

BacktestEngine._build_portfolio() 不变：
  entries_2d = entries.astype(np.float64).reshape(-1, 1)
  exits_2d = exits.astype(np.float64).reshape(-1, 1)

Portfolio.from_order_func(close, order_func_nb, entries_2d, exits_2d, ...)
  -> order_func_nb 只看到布尔数组，完全不知道 MTF 引擎的存在
```

---

## 七、共振计算完整示例

场景：BTC 3d 结构层 + 4h 判断层 + 15m 执行层

```
3d 结构层：
  - EMA_200 值 = 60000（支撑位）
  - 当前趋势：做多（+1）
  -> 导出价格位：[60000], 方向：+1

4h 判断层：
  - BB 下轨 = 60500, 中轨 = 62000, 上轨 = 63500
  -> 导出价格位：[60500, 62000, 63500]

15m 执行层：
  - 某根 bar：close = 60300
  - ATR_14 = 800
  - proximity_mult = 1.5

Step 1: 计算 s%
  s% = (800 / 60300) * 1.5 = 1.99%

Step 2: 构建每层的关注区间
  3d 层 EMA200 区间：[60000*(1-0.0199), 60000*(1+0.0199)] = [58806, 61194]
  4h 层 BB下轨区间：[60500*(0.9801), 60500*(1.0199)] = [59296, 61704]
  4h 层 BB中轨区间：[60778, 63222]
  4h 层 BB上轨区间：[62234, 64766]

  3d 层关注区间（并集）：[58806, 61194]
  4h 层关注区间（并集）：[59296, 64766]

Step 3: 计算区间重合
  重合区域 = [58806, 61194] intersect [59296, 64766] = [59296, 61194]
  重合宽度 = 61194 - 59296 = 1898
  最大层区间宽度 = max(61194-58806, 64766-59296) = max(2388, 5470) = 5470
  重合度 = 1898 / 5470 = 0.347

Step 4: 检查当前价格
  close=60300 在重合区域 [59296, 61194] 内
  -> confluence_score = 0.347

如果 confluence_threshold = 0.3：
  -> 0.347 >= 0.3 通过共振门控
  -> 方向 = +1（做多）
  -> 若 15m RSI < 30 -> 执行做多入场

价格解读：
  60300 位于 3d 支撑位区间和 4h BB 下轨区间的重叠区域
  -> 3d 和 4h 两个周期的关注区间在此价格附近重合
  -> 多周期共识，信号可信度较高
```

---

## 八、与现有工程的结合

### 8.1 核心原则：只改 MTF 分支，不动其他部分

```
+-------------------------------------------------------------+
| 现有代码 (完全不变)                                           |
|                                                               |
|  evaluate_condition()  --- 时机轨道 --------------------------|
|  _get_indicator_column() --- 指标值提取 ----------------------|
|  combine_signals() --- 层内布尔组合 --------------------------|
|  compute_all_indicators() --- 所有指标预计算 ------------------|
|  load_mtf_data() --- 多周期数据加载 --------------------------|
|  order_func_nb (Numba) --- 交易执行 --------------------------|
|  BacktestEngine._build_portfolio() --- 回测构建 ---------------|
|                                                               |
|  单周期路径 (dna_to_signal_set L689-745) --- 不变 -------------|
+-------------------------------------------------------------+
| 新增代码                                                      |
|                                                               |
|  extract_context() --- 上下文轨道 -----------------------------|
|  resample_values() --- 数值型重采样 ---------------------------|
|  _get_all_columns() --- 多字段批量提取 ------------------------|
|  LayerResult --- 层评估结果数据结构 ---------------------------|
|  MTFSynthesis --- 跨层综合结果数据结构 ------------------------|
|  mtf_engine.py --- 三阶段管线主逻辑 --------------------------|
|                                                               |
|  MTF路径 (dna_to_signal_set L536-687) --- 替换 ---------------|
+-------------------------------------------------------------+
```

### 8.2 VectorBT 结合方式

**关键点：MTF 综合在 Python 端完成，Numba 端只收布尔数组。**

```
MTF Engine (Python端)                    VectorBT (Numba端)
---------------------                    ------------------
extract_context() -> 数值
  |
跨层综合 -> 各维度分数
  |
决策门控 -> 布尔 SignalSet                order_func_nb()
  |                                        |
BacktestEngine._build_portfolio()         只处理布尔数组：
  entries_2d = bool -> np.float64          entries[i,col] > 0.5 -> 入场
  exits_2d = bool -> np.float64            exits[i,col] > 0.5  -> 出场
  |
Portfolio.from_order_func(close,
  order_func_nb, entries_2d, ...)
```

**VectorBT 不需要任何修改**。共振评分、方向判断、动量对齐全部在 Python 端预计算，最终产出布尔 entries/exits/adds/reduces 数组，传入 `order_func_nb` 的方式与现在完全相同。

### 8.3 已有组件的复用清单

| 已有组件 | 文件位置 | 复用方式 |
|---------|---------|---------|
| `evaluate_condition()` | executor.py L28 | 时机轨道完全不变，原样调用 |
| `evaluate_layer()` | executor.py L407 | 时机轨道的层评估不变 |
| `_get_indicator_column()` | executor.py L278 | extract_context() 内部调用，获取单个指标列的数值 |
| `combine_signals()` | executor.py L259 | 层内布尔信号组合不变 |
| `resample_signals()` 的 reindex+ffill 逻辑 | executor.py L482 | 数值重采样复用同一对齐逻辑，去掉 `.astype(bool)` |
| `IndicatorDef.output_fields` | registry.py L163 | BB=["upper","middle","lower"...]，用于批量提取多字段 |
| `IndicatorDef.category` | registry.py | "trend"/"momentum"/"volatility"，用于推导 MTF 能力 |
| `compute_all_indicators()` | indicators.py L340 | ATR/BB/EMA/RSI 等已预计算，不需要任何改动 |
| `load_mtf_data()` | mtf_loader.py | 多周期数据加载不变 |
| `order_func_nb` | engine.py L110 | Numba 函数完全不变 |
| `BacktestEngine._build_portfolio()` | engine.py L297 | 仍然把布尔 SignalSet 转为 2D 数组传入 VectorBT |

### 8.4 新增组件清单

| 新增组件 | 职责 | 基于什么构建 |
|---------|------|------------|
| `resample_values()` | 数值型重采样（forward-fill 高周期数值到执行周期） | 复用 `resample_signals()` 的 reindex+ffill，去掉 `.astype(bool)` |
| `_get_all_columns()` | 批量提取多输出指标的所有字段值 | 遍历已有的 `IndicatorDef.output_fields` + 复用 `_get_indicator_column()` 的列名构建逻辑 |
| `extract_context()` | 从 SignalGene 提取 MTF 上下文信息 | 调用 `_get_indicator_column()` 获取数值，根据 `IndicatorDef.category` 推导信息类型 |
| `LayerResult` | 层评估结果数据结构（时机布尔 + 上下文信息） | 包含已有的 `SignalSet` |
| `MTFSynthesis` | 跨层综合结果数据结构 | 各维度分数的 Series |
| `mtf_engine.py` | 三阶段管线主逻辑 | 组合上述组件 |
| `mtf_mode` DNA 字段 | 控制激活哪些 MTF 维度 | 新增到 StrategyDNA，from_dict() 兼容旧记录 |

---

## 九、文件修改清单

### 新建文件

| 文件 | 内容 |
|------|------|
| `core/strategy/mtf_engine.py` | MTF 工作引擎：LayerResult/MTFSynthesis 数据结构 + extract_context() + resample_values() + _get_all_columns() + 跨层综合 + 决策门控 |

### 修改文件

| 文件 | 修改内容 | 影响程度 |
|------|---------|---------|
| `core/strategy/dna.py` | 添加 LayerRole 枚举（structure/zone/execution）；StrategyDNA 添加 mtf_mode、confluence_threshold、proximity_mult；TimeframeLayer.role 扩展；"trend" -> "structure" 兼容映射 | 中 |
| `core/strategy/executor.py` | SignalSet 添加 mtf_diagnostics 字段；dna_to_signal_set() MTF 分支（L536-687）替换为调用 mtf_engine | 大 |
| `core/strategy/validator.py` | 接受新角色 structure/zone/execution；校验新参数；非执行层放宽信号要求 | 小 |
| `core/evolution/operators.py` | mutate_add_layer() 角色感知（根据周期推导角色）；新增 mutate_mtf_mode()；更新 crossover() | 中 |

### 不修改文件

| 文件 | 原因 |
|------|------|
| `core/backtest/engine.py` order_func_nb | Numba 函数接口不变，共振过滤在 Python 端预计算后传入布尔数组 |
| `core/backtest/engine.py` BacktestEngine._build_portfolio() | 仍把布尔 SignalSet 转为 2D 数组传入 VectorBT，逻辑不变 |
| `core/data/mtf_loader.py` | 数据加载不变，每个周期返回完整增强的 DataFrame |
| `core/features/indicators.py` | 指标计算不变，ATR/BB/EMA/RSI 等已预计算 |
| `core/features/registry.py` | IndicatorDef 不变，output_fields 和 category 已有，直接复用 |
| `core/features/indicator_profile.py` | 不变，MTF 能力声明在 mtf_engine.py 中基于 category 推导 |

---

## 十、向后兼容

| 场景 | 兼容方式 |
|------|---------|
| **单周期策略** | `dna_to_signal_set()` 单周期分支（L689-745）完全不变 |
| **旧 MTF DNA** | 有 `cross_layer_logic` 但无 `mtf_mode` 的 DNA 走旧的 AND/OR 路径 |
| **Numba 接口** | `order_func_nb` 签名和语义完全不变 |
| **JSON 序列化** | 新字段（mtf_mode, confluence_threshold, proximity_mult）都是基础类型，不破坏 JSON |
| **VectorBT Portfolio** | 仍通过 `from_order_func()` 构建，所有参数类型不变 |
| **旧角色名称** | `from_dict()` 将 `"trend"` 映射为 `"structure"`，缺少新字段使用默认值 |

---

## 十一、实施阶段

### Phase L: MTF 引擎核心（基础设施）

1. `dna.py`：添加 LayerRole 枚举 + mtf_mode + confluence_threshold + proximity_mult
2. 新建 `mtf_engine.py`：extract_context() + resample_values() + _get_all_columns() + LayerResult + MTFSynthesis + 跨层综合函数 + 决策门控函数
3. 单元测试 `tests/test_mtf_engine.py`

**验证标准**：
- extract_context()：EMA -> direction + price_levels；BB -> price_levels + volatility；RSI -> momentum
- resample_values()：4h 数值正确 forward-fill 到 15m 索引
- s% 计算：ATR=800, close=60000, mult=1.5 -> s%=0.02
- 区间重合：完全重合->高分，部分重合->中间值，无重合->0.0

### Phase M: 信号管线集成

4. `executor.py`：SignalSet 添加 mtf_diagnostics；替换 dna_to_signal_set() MTF 分支为调用 mtf_engine
5. `validator.py`：新角色 + 新参数校验
6. 集成测试 `tests/test_mtf_integration.py`

**验证标准**：
- 单周期策略结果不变
- 2 层（zone+execution）决策门控正确
- 3 层（structure+zone+execution）完整流水线
- 不同 mtf_mode 产生不同交易行为
- 不同 confluence_threshold 影响交易频率

### Phase N: 进化集成

7. `operators.py`：角色感知的层添加 + 新变异算子 + crossover 更新
8. 进化测试 `tests/test_mtf_evolution.py`

**验证标准**：
- 进化能生成 structure/zone/execution 三种角色的层
- mutate_mtf_mode() 能切换不同的 MTF 模式
- crossover 正确处理不同角色的层

### Phase O: 回归与 Bug 修复

9. 全量现有测试通过（669 tests）
10. 旧 MTF DNA 走兼容路径
11. 审计发现的 P0 Bug 在新架构中自然消除：
    - BUG-1（trend exit 持续触发）：新架构中结构层不再产生 exit 信号，自然消除
    - BUG-2（mixed 无 trend 退化为做多）：新架构中结构层强制提供方向，自然消除
    - BUG-3（单 layer MTF 路径异常）：新架构中角色从周期自动推导，自然消除
    - BUG-4（load_mtf_data 降级问题）：旧 MTF DNA 走旧路径，新 MTF DNA 走共振路径

---

## 十二、注意事项

### 12.1 工程风险

| 风险 | 缓解措施 |
|------|---------|
| extract_context() 提取逻辑复杂 | 基于 IndicatorDef.category 推导，类别固定（6 类），逻辑简单 |
| 多字段提取影响性能 | 每层指标数量少（2-4 个），DataFrame 列访问是 O(1) |
| 新旧 MTF 路径共存复杂 | 通过 mtf_mode 是否存在判断走新路径还是旧路径 |
| 进化搜索空间增大 | 维度固定（方向+价格位初期），mtf_mode 选项有限（3-4 种） |
| 价格位区间并集计算 | 每层价格位数量少（1-5 个），合并排序即可，无需复杂算法 |

### 12.2 关键设计约束

1. **Numba 函数不可修改**：`order_func_nb` 是 @njit 编译的，所有 MTF 逻辑必须在 Python 端完成
2. **DataFrame 列名格式固定**：`_get_indicator_column()` 构建的列名格式（如 `bb_lower_20_2`）是约定，不能随意变更
3. **信号延迟 1 bar 不变**：所有信号在 `_build_portfolio()` 中 shift(1) 防止前瞻偏差，MTF 的上下文信息也应同步延迟
4. **区间重合法的数值重采样**：必须使用 forward-fill（不是插值），因为高周期数据只在 bar 收盘时更新

### 12.3 后续扩展方向（不在本次实施范围）

- Pivot Points：前日 HLC 计算 S1-S3/R1-R3
- 斐波那契回撤：23.6%~78.6% 回撤位
- Ichimoku Cloud：云带作为未来支撑/阻力
- 这三个指标的架构已预留扩展空间，只需在 registry.py 添加定义 + indicators.py 添加计算 + MTF 能力表添加声明
