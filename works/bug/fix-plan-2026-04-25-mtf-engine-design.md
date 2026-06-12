# MTF 工作引擎设计文档

> 日期: 2026-04-25
> 状态: 方案已确认
> 前置: Phase E-K bug 修复已完成（V1~V9 全部修复，669 tests passing）
> 关联文档: `wroks/bug/fix-plan-2026-04-25-mtf-confluence-redesign.md`（前期讨论记录）

---

## 〇、设计意图（逻辑描述）

### 现在系统的问题

进化系统生成一个多周期策略（如 3d EMA + 4h BB + 15m RSI），执行时每个周期只能回答"该不该交易"，答案是"是"或"否"。三个周期的"是/否"用 AND 或 OR 组合得出最终决策。

**问题**：每个周期把丰富的指标数值（EMA 在 60000、BB 下轨在 60500）烧成了一个简单的"是/否"。三个周期之间只能用"是/否"交流，无法传递"价格在什么位置"、"趋势是什么方向"等关键信息。

### MTF 引擎是什么

一个**多周期综合决策工具**。它让每个时间周期不仅能回答"该不该交易"，还能告诉系统"我关注的价格位置在哪里"、"我看到的方向是什么"。然后综合所有周期的信息，计算一个评分：**当前价格位置，有多少个周期在同时关注它？**

### 它做了三件事

1. **让每个周期说出判断依据**：3d 层不仅说"是"，还说"趋势向上，EMA200 在 60000"
2. **综合所有周期的依据**：检查价格 60300 是否同时接近 3d 的 60000 和 4h 的 60500 → 计算区间重合度
3. **用综合评分门控决策**：15m 说"该入场" AND 方向一致 AND 区间重合度达标 → 执行交易

### 怎么用

- **与现有信号管线结合**：现有管线是"时机轨道"（什么时候该交易），完全不变。MTF 引擎新增"上下文轨道"（当前价格位置是否合理）。两个轨道并行工作。
- **与进化系统结合**：进化可以探索不同的多周期协作模式（只用方向过滤、只用价格位共振、组合使用）。
- **与回测引擎结合**：MTF 引擎在 Python 端完成计算，产出布尔信号传入 Numba 回测引擎，接口不变。
- **与指标系统结合**：所有指标数值已在 DataFrame 中预计算，MTF 引擎只是读取这些数值并提取语义信息。

### 产生什么价值

- **策略质量**：多维度评估比布尔 AND/OR 能表达更精细的交易逻辑
- **进化效率**：指标能力声明减少无效探索
- **系统扩展性**：新增维度只需添加新的评估函数
- **可解释性**：每个维度有独立分数，便于理解策略行为

---

## 一、问题背景

### 1.1 工程现状

当前 MTF（多时间周期）信号管线的完整数据流：

```
SignalGene (DNA定义)
  → _get_indicator_column(df, gene)     → pd.Series (数值)    ← 数值仍存在
  → evaluate_condition(series, close, condition) → pd.Series (布尔)  ← 数值在此被烧毁
  → combine_signals([bool], AND/OR)     → pd.Series (布尔)
  → SignalSet (entries/exits/adds/reduces, 全部布尔)
  → BacktestEngine._build_portfolio()   → 布尔数组
  → order_func_nb (Numba JIT)           → 交易执行
```

### 1.2 根因分析（代码级验证）

| # | 问题 | 代码证据 | 影响 |
|---|------|---------|------|
| 1 | **evaluate_condition() 是信息黑洞** | executor.py L28-104 全部返回布尔；L423-424 indicator_col 是局部变量，调用后丢弃 | 所有指标的语义信息（方向、价格位、动量、强度）在评估后全部丢失 |
| 2 | **层与层之间完全隔离** | executor.py L567 每层独立调用 evaluate_layer()，返回的 SignalSet 只含布尔 | 不同周期的层无法传递任何数值信息 |
| 3 | **跨层组合只有 AND/OR** | executor.py L637-669 用 combine_signals() 对布尔做 AND/OR | 无法表达"方向一致且价格区间重合"等复合条件 |
| 4 | **无指标类型系统** | dna.py SignalGene 无 MTF 信息类型声明；registry.py IndicatorDef 无 MTF 能力声明 | 系统不知道 EMA 能提供方向、BB 能提供价格区间 |
| 5 | **角色只有 trend/execution** | dna.py L162 `role: Optional[str]` 只有 "trend"/"execution" | 无法区分"提供方向"的结构层和"提供价格区间"的判断层 |
| 6 | **进化盲目选择指标** | operators.py L197 mutate_add_layer() 始终设置 role="execution"，随机选指标 | 进化不知道 BB 放在判断层比放在执行层更有价值 |

### 1.3 交易需求

用户描述的多周期协作逻辑：

- 3d 层（结构层）→ 趋势方向 + 关键价格位
- 4h 层（判断层）→ 价格区间参考
- 15m 层（执行层）→ 入场/出场时机
- 多层价格区间重合时信号可信度最高

MTF 协作不只有"区间重合"一种模式，还包括：
- **方向一致性**：高周期方向过滤低周期交易方向
- **价格位接近度**：多周期价格区间的重合程度
- **动量对齐**：多周期动量方向是否一致
- **趋势强度**：高周期趋势强度作为置信度

---

## 二、设计目标

### 做什么

在现有信号管线中**新增一条并行的"上下文轨道"**，让 MTF 引擎不仅能获得布尔时机信号，还能获得跨周期的类型化信息（方向、价格位、动量等），进行多维度的综合评估后做出交易决策。

### 达到什么目的

1. MTF 策略的组合方式从"布尔 AND/OR"升级为"多维度评分门控"
2. 进化系统可以探索不同的 MTF 协作模式（方向过滤、区间重合、动量对齐等）
3. 每种指标根据其固有特性贡献不同维度的信息
4. 向后兼容现有单周期策略和旧 MTF DNA 记录

### 产生什么价值

1. **策略质量**：多维度评估比布尔 AND/OR 能表达更精细的交易逻辑，进化搜索空间更大
2. **进化效率**：指标能力声明减少无效探索（不会把 RSI 放在需要价格位的层）
3. **系统扩展性**：新增 MTF 维度只需添加新的评估函数，不影响已有维度
4. **可解释性**：每个维度有独立分数，便于理解策略为什么在某个时点入场

---

## 三、架构设计

### 3.1 核心思想：双轨道并行 + 三阶段管线

```
当前架构（单轨道）:
  SignalGene → evaluate_condition() → boolean → combine(AND/OR) → SignalSet

新架构（双轨道 + 三阶段）:
  SignalGene ─┬→ evaluate_condition() → boolean (时机轨道，不变)
              └→ extract_context()     → typed info (上下文轨道，新增)
                    ↓
              LayerResult = {时机布尔 + 上下文信息}
                    ↓
              Stage 2: 跨层综合 → MTFSynthesis {各维度分数}
                    ↓
              Stage 3: 决策门控 → final SignalSet (布尔)
                    ↓
              BacktestEngine (接口不变，仍收布尔数组)
```

### 3.2 三阶段管线详解

#### Stage 1: 层评估（Layer Evaluation）

**输入**：每个时间周期层的 SignalGene 列表 + 对应 DataFrame

**处理**：对每个 SignalGene 并行执行两条轨道

- **时机轨道**（已有，不变）：`evaluate_condition()` → 布尔信号
- **上下文轨道**（新增）：`extract_context()` → 类型化信息

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

#### Stage 2: 跨层综合（Cross-Layer Synthesis）

**输入**：所有层的 LayerResult（已重采样到执行周期索引）

**处理**：按维度计算各层信息的综合分数

- 方向维度 → direction_score
- 价格位维度 → confluence_score（s% + 区间重合法）
- 动量维度 → momentum_score
- 强度维度 → strength_multiplier

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

#### Stage 3: 决策门控（Decision Gate）

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

### 3.3 指标的 MTF 能力声明

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

### 3.4 三种组合类型

| 类型 | 层配置 | 角色覆盖 | 综合维度 |
|------|-------|---------|---------|
| A（完整） | 3d + 4h + 15m | structure + zone + execution | 方向 + 价格位 + 动量 + 强度 |
| B（部分） | 4h + 15m | zone + execution | 价格位 + 动量（方向从 DNA 继承） |
| C（单周期） | 15m | execution | 无综合，走原始单周期路径 |

角色从周期自动推导：
```
>= 1d → structure (结构层)
>= 1h → zone (判断层)
执行周期 → execution (执行层)
```

### 3.5 接近度计算（百分比幅度法 s%，已确认）

```
对每根执行层 bar：
  s% = (ATR_14 / close) * proximity_mult
  接近阈值 = close * s%

  如果 |当前价格 - 参考价格位| <= 接近阈值 → 该价格位"接近"
```

- `proximity_mult` 默认 1.5，可通过进化调整（范围 0.5~3.0）
- ATR_14 已在每个周期的 DataFrame 中预计算（indicators.py L106-108）
- 自适应：高波动市场阈值自动放宽，低波动市场自动收紧

### 3.6 共振分数（区间重合法，已确认）

```
Step 1：对每个层的每个价格位 P，构建关注区间 [P*(1-s%), P*(1+s%)]
Step 2：每层的所有价格位区间取并集 → 层关注区间
Step 3：所有层的关注区间取交集 → 重合区域
Step 4：confluence_score =
    重合区域为空 → 0.0
    当前价格不在重合区域内 → 0.0
    否则 → 重合区域宽度 / 最大层区间宽度
```

---

## 四、与 VectorBT + 现有工程的结合

### 4.1 核心原则：只改 MTF 分支，不动其他部分

```
┌─────────────────────────────────────────────────────┐
│ 现有代码 (完全不变)                                   │
│                                                       │
│  evaluate_condition()  ─── 时机轨道 ──────────────────┤
│  _get_indicator_column() ─── 指标值提取 ──────────────┤
│  combine_signals() ─── 层内布尔组合 ──────────────────┤
│  compute_all_indicators() ─── 所有指标预计算 ─────────┤
│  load_mtf_data() ─── 多周期数据加载 ──────────────────┤
│  order_func_nb (Numba) ─── 交易执行 ──────────────────┤
│  BacktestEngine._build_portfolio() ─── 回测构建 ──────┤
│                                                       │
│  单周期路径 (dna_to_signal_set L689-745) ─── 不变 ────┤
├───────────────────────────────────────────────────────┤
│ 新增代码                                              │
│                                                       │
│  extract_context() ─── 上下文轨道 ────────────────────┤
│  resample_values() ─── 数值型重采样 ──────────────────┤
│  _get_all_columns() ─── 多字段批量提取 ───────────────┤
│  LayerResult ─── 层评估结果数据结构 ──────────────────┤
│  MTFSynthesis ─── 跨层综合结果数据结构 ───────────────┤
│  mtf_engine.py ─── 三阶段管线主逻辑 ─────────────────┤
│                                                       │
│  MTF路径 (dna_to_signal_set L536-687) ─── 替换 ──────┤
└───────────────────────────────────────────────────────┘
```

### 4.2 VectorBT 结合方式

**关键点：MTF 综合在 Python 端完成，Numba 端只收布尔数组。**

```
MTF Engine (Python端)                    VectorBT (Numba端)
─────────────────────                    ──────────────────
extract_context() → 数值
  ↓
跨层综合 → 各维度分数
  ↓
决策门控 → 布尔 SignalSet                order_func_nb()
  ↓                                        ↓
BacktestEngine._build_portfolio()         只处理布尔数组：
  entries_2d = bool → np.float64          entries[i,col] > 0.5 → 入场
  exits_2d = bool → np.float64            exits[i,col] > 0.5  → 出场
  ↓
Portfolio.from_order_func(close,          接口签名完全不变
  order_func_nb, entries_2d, ...)
```

**VectorBT 不需要任何修改**。共振评分、方向判断、动量对齐全部在 Python 端预计算，最终产出布尔 entries/exits/adds/reduces 数组，传入 `order_func_nb` 的方式与现在完全相同。

### 4.3 已有组件的复用清单

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

### 4.4 新增组件清单

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

## 五、数据流走查

以真实的 3 层策略为例，追踪数据从 DNA 到最终交易的完整路径：

### 5.1 DNA 定义

```python
StrategyDNA(
    execution_genes=ExecutionGenes(timeframe="15m"),
    mtf_mode="direction+confluence",
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

### 5.2 Stage 1: 层评估

**3d 结构层：**

```
时机轨道：evaluate_condition(ema_200, close, {type: "price_above"})
  → close > ema_200 → 布尔 entries

上下文轨道：extract_context("EMA", {period:200}, "price_above")
  → 调用 _get_indicator_column(df, gene) → 获取 ema_200 数值 Series
  → EMA 属于 "trend" 类别，条件为 price_above
  → 输出：
    direction = +1 (where close > ema_200), -1 (where close < ema_200)
    price_levels = [ema_200 values]
    strength = (close - ema_200) / close
```

**4h 判断层：**

```
时机轨道：evaluate_condition(bb_lower_20_2, close, {type: "price_below"})
  → close < bb_lower → 布尔
  evaluate_condition(rsi_14, close, {type: "gt", threshold: 70})
  → rsi > 70 → 布尔 exits

上下文轨道：extract_context("BB", {period:20, std:2}, "price_below")
  → BB 属于 "volatility" 类别
  → _get_all_columns() 遍历 IndicatorDef.output_fields → 获取 bb_upper/middle/lower 全部值
  → 输出：
    price_levels = [bb_upper_20_2, bb_middle_20_2, bb_lower_20_2]
    volatility = (bb_upper - bb_lower) / bb_middle
```

**15m 执行层：**

```
时机轨道：evaluate_condition(rsi_14, close, {type: "lt", threshold: 30})
  → rsi < 30 → 布尔 entries

上下文轨道：执行层不需要上下文信息（只提供时机信号）
```

### 5.3 Stage 2: 跨层综合

```
对每根 15m bar：

1. 重采样 3d 和 4h 的上下文信息到 15m 索引
   resample_values(3d_direction, 15m_index) → 15m 上的方向序列
   resample_values(3d_price_levels, 15m_index) → 15m 上的 EMA200 值
   resample_values(4h_price_levels, 15m_index) → 15m 上的 BB 上下中轨值

2. 方向维度：
   3d EMA200: close > ema_200 → direction = +1 (做多)
   → direction_score = +1

3. 价格位维度（s% + 区间重合）：
   s% = (15m_atr_14 / 15m_close) * 1.5

   3d EMA200=60000 → 关注区间 [60000*(1-s%), 60000*(1+s%)]
   4h BB 下轨=60500, 中轨=62000, 上轨=63500
     → 关注区间 [60500*(1-s%), 63500*(1+s%)] (三轨并集)

   计算交集 → 重合区域
   检查当前价格是否在重合区域内 → confluence_score

4. 强度维度：
   3d strength = (close - ema_200) / close → strength_multiplier
```

### 5.4 Stage 3: 决策门控

```
mtf_mode = "direction+confluence"

对每根 15m bar：
  exec_entry = rsi_14 < 30  (时机轨道的布尔信号)

  if exec_entry:  # 时机信号存在，进一步检查上下文
    if direction_score (+1) 与 dna.direction (long) 一致: ✓
    if confluence_score >= confluence_threshold (0.3): ✓
    → 最终 entry = True
    else:
    → 最终 entry = False  (时机到了但上下文不满足)
  else:
    → 最终 entry = False  (时机未到)

  exit 信号不受门控限制（确保止损及时）
```

### 5.5 传入 VectorBT

```
最终 entry = 布尔 Series (15m 索引)
最终 exit = 布尔 Series (15m 索引)

BacktestEngine._build_portfolio() 不变：
  entries_2d = entries.astype(np.float64).reshape(-1, 1)
  exits_2d = exits.astype(np.float64).reshape(-1, 1)

Portfolio.from_order_func(close, order_func_nb, entries_2d, exits_2d, ...)
  → order_func_nb 只看到布尔数组，完全不知道 MTF 引擎的存在
```

---

## 六、价格位区间重合计算示例

场景：BTC 3d 结构层 + 4h 判断层 + 15m 执行层

```
3d 结构层：
  - EMA_200 值 = 60000（支撑位）
  - 当前趋势：做多（+1）
  → 导出价格位：[60000], 方向：+1

4h 判断层：
  - BB 下轨 = 60500, 中轨 = 62000, 上轨 = 63500
  → 导出价格位：[60500, 62000, 63500]

15m 执行层：
  - 某根 bar：close = 60300
  - ATR_14 = 800
  - proximity_mult = 1.5

Step 1: 计算 s%
  s% = (800 / 60300) * 1.5 = 1.99%

Step 2: 构建每层的关注区间
  3d EMA200 区间：[60000*(1-0.0199), 60000*(1+0.0199)] = [58806, 61194]
  4h BB下轨区间：[60500*(0.9801), 60500*(1.0199)] = [59296, 61704]
  4h BB中轨区间：[60778, 63222]
  4h BB上轨区间：[62234, 64766]

  3d 层关注区间（并集）：[58806, 61194]
  4h 层关注区间（并集）：[59296, 64766]

Step 3: 计算区间重合
  重合区域 = [58806, 61194] ∩ [59296, 64766] = [59296, 61194]
  重合宽度 = 61194 - 59296 = 1898
  最大层区间宽度 = max(61194-58806, 64766-59296) = max(2388, 5470) = 5470
  重合度 = 1898 / 5470 = 0.347

Step 4: 检查当前价格
  close=60300 在重合区域 [59296, 61194] 内 ✓
  → confluence_score = 0.347

如果 confluence_threshold = 0.3：
  → 0.347 >= 0.3 ✓ 通过共振门控
  → 方向 = +1（做多）
  → 若 15m RSI < 30 → 执行做多入场

价格解读：
  60300 位于 3d 支撑位区间和 4h BB 下轨区间的重叠区域
  → 3d 和 4h 两个周期的关注区间在此价格附近重合
  → 多周期共识，信号可信度较高
```

---

## 七、文件修改清单

### 新建文件

| 文件 | 内容 |
|------|------|
| `core/strategy/mtf_engine.py` | MTF 工作引擎：LayerResult/MTFSynthesis 数据结构 + extract_context() + resample_values() + _get_all_columns() + 跨层综合 + 决策门控 |

### 修改文件

| 文件 | 修改内容 | 影响程度 |
|------|---------|---------|
| `core/strategy/dna.py` | 添加 LayerRole 枚举（structure/zone/execution）；StrategyDNA 添加 mtf_mode、confluence_threshold、proximity_mult；TimeframeLayer.role 扩展；"trend" → "structure" 兼容映射 | 中 |
| `core/strategy/executor.py` | dna_to_signal_set() MTF 分支（L536-687）替换为调用 mtf_engine | 大 |
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

## 八、向后兼容

| 场景 | 兼容方式 |
|------|---------|
| **单周期策略** | `dna_to_signal_set()` 单周期分支（L689-745）完全不变 |
| **旧 MTF DNA** | 有 `cross_layer_logic` 但无 `mtf_mode` 的 DNA 走旧的 AND/OR 路径 |
| **Numba 接口** | `order_func_nb` 签名和语义完全不变 |
| **JSON 序列化** | 新字段（mtf_mode, confluence_threshold, proximity_mult）都是基础类型，不破坏 JSON |
| **VectorBT Portfolio** | 仍通过 `from_order_func()` 构建，所有参数类型不变 |

---

## 九、实施阶段

### Phase L: MTF 引擎核心（基础设施）

1. `dna.py`：添加 LayerRole 枚举 + mtf_mode + confluence_threshold + proximity_mult
2. 新建 `mtf_engine.py`：extract_context() + resample_values() + _get_all_columns() + LayerResult + MTFSynthesis + 跨层综合函数 + 决策门控函数
3. 单元测试 `tests/test_mtf_engine.py`

### Phase M: 信号管线集成

4. `executor.py`：替换 dna_to_signal_set() MTF 分支为调用 mtf_engine
5. `validator.py`：新角色 + 新参数校验
6. 集成测试 `tests/test_mtf_integration.py`

### Phase N: 进化集成

7. `operators.py`：角色感知的层添加 + 新变异算子 + crossover 更新
8. 进化测试 `tests/test_mtf_evolution.py`

### Phase O: 回归与 Bug 修复

9. 全量现有测试通过
10. 旧 MTF DNA 走兼容路径
11. 审计发现的 P0 Bug 在新架构中自然消除

---

## 十、验证策略

### 单元测试

- extract_context()：EMA → direction + price_levels；BB → price_levels + volatility；RSI → momentum + stat_position
- resample_values()：4h 数值正确 forward-fill 到 15m 索引
- _get_all_columns()：BB 提取 upper/middle/lower 三个字段
- s% 计算：ATR=800, close=60000, mult=1.5 → s%=0.02
- 区间重合：完全重合→高分，部分重合→中间值，无重合→0.0

### 集成测试

- 单周期策略结果不变
- 2 层（zone+execution）决策门控正确
- 3 层（structure+zone+execution）完整流水线
- 不同 mtf_mode 产生不同交易行为
- 不同 confluence_threshold 影响交易频率

### 回归测试

- 全量现有测试通过（669 tests）
- 旧 MTF DNA 走兼容路径，结果与修复前一致

---

## 十一、风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| extract_context() 提取逻辑复杂 | 基于 IndicatorDef.category 推导，类别固定（6 类），逻辑简单 |
| 多字段提取影响性能 | 每层指标数量少（2-4 个），DataFrame 列访问是 O(1) |
| 新旧 MTF 路径共存复杂 | 通过 mtf_mode 是否存在判断走新路径还是旧路径 |
| 进化搜索空间增大 | 维度固定（方向+价格位初期），mtf_mode 选项有限（3-4 种） |
