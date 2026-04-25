# B4.1: MTF 共振引擎

## 定位

`core/strategy/mtf_engine.py` (789 行) 是 MTF (Multi-TimeFrame) 共振引擎的核心实现。它替代了旧引擎的 `cross_layer_logic` AND/OR 布尔组合，改用**双轨道 + 三阶段管线**：

- **时机轨道**（继承旧引擎）：每层独立评估信号基因，产出布尔 entries/exits
- **上下文轨道**（新增）：从指标数值中提取方向、价格位、动量等语义信息
- **跨层综合**：将上下文信息合成为多维评分（direction_score, confluence_score, momentum_score）
- **决策门控**：用评分过滤时机信号，产出最终 SignalSet

激活条件：`dna.mtf_mode is not None` 时走此引擎，否则走 `executor.py` 的旧 MTF 路径。

## 核心数据结构

### LayerResult

每个层评估后的完整产出：

| 字段 | 类型 | 来源 |
|------|------|------|
| signal_set | SignalSet | `evaluate_layer()` 产出（时机轨道，布尔信号） |
| direction | pd.Series (+1/-1) | trend 类指标的 price_above/price_below 条件 |
| price_levels | List[pd.Series] | trend/volatility 类指标的输出列（如 EMA 值、BB 上下轨） |
| momentum | pd.Series | momentum 类指标的原始值（如 RSI 值） |
| strength | pd.Series | 预留字段，当前未填充 |
| volatility | pd.Series | 预留字段，当前未填充 |

### MTFSynthesis

跨层综合评分，用于决策门控：

| 字段 | 类型 | 范围 | 含义 |
|------|------|------|------|
| direction_score | pd.Series | +1 / -1 / 0 | 结构层方向共识（最高周期优先） |
| confluence_score | pd.Series | 0.0 ~ 1.0 | 多层价格区间重合度 |
| momentum_score | pd.Series | 0.0 ~ 1.0 | 动量归一化评分 |
| strength_multiplier | pd.Series | 0.0 ~ 1.0+ | 预留字段，当前恒为 1.0 |

## 三阶段管线

### Stage 1: 层评估 (`evaluate_layer_with_context`)

对每个 `TimeframeLayer` 执行：

1. 调用 `evaluate_layer(layer, df)` 获取基础 SignalSet（复用旧引擎）
2. 遍历层的每个 `SignalGene`，调用 `extract_context()` 提取上下文
3. 对 structure/zone 层，用 `resample_values()` 将数值 ffill 到执行周期索引

`extract_context()` 按指标类别提取不同信息：

| 指标类别 | 提取内容 | 条件类型约束 |
|----------|---------|-------------|
| trend | direction (+1/-1) + price_levels | 需要 price_above/price_below 条件 |
| volatility | price_levels | 无条件约束 |
| momentum | momentum（原始值） | 无条件约束 |

### Stage 2: 跨层综合 (`synthesize_cross_layer`)

将所有 LayerResult 合成为 MTFSynthesis：

**方向评分** (`direction_score`)：
- 收集所有层（不只是 structure 层）的 direction 信息
- 多个结构层方向冲突时，最高时间周期胜出 (`resolve_direction_conflict`)
- 无 structure 层时，从 `dna.risk_genes.direction` 继承：long->+1, short->-1, mixed->0

**共振评分** (`confluence_score`)：
- 需要至少 2 个非执行层有 price_levels
- 对每根 bar：计算 s% 接近度 -> 构建价格区间 -> 区间交集 -> 评分
- 单层降级：只有 1 个非执行层有 price_levels 时，用接近度评分替代
- 动量降级（C1 fix）：所有非执行层都无 price_levels 但有 momentum 时，用动量方向一致性替代

**动量评分** (`momentum_score`)：
- 收集所有层的 momentum 值
- 取均值后用 sigmoid-like 归一化到 [0, 1]

### Stage 3: 决策门控 (`apply_decision_gate`)

用 MTFSynthesis 评分过滤时机信号：

**mtf_mode 控制**：

| mtf_mode | 方向过滤 | 共振过滤 |
|----------|---------|---------|
| None | 关闭 | 关闭 |
| "direction" | 开启 | 关闭 |
| "confluence" | 关闭 | 开启 |
| "direction+confluence" | 开启 | 开启 |

**过滤规则**：

| 信号类型 | 过滤条件 |
|---------|---------|
| entries | timing_signal AND direction_match AND confluence >= threshold |
| exits | 不过滤（风控不应被阻挡） |
| adds | confluence >= threshold * 0.8（放宽 20%） |
| reduces | 不过滤 |

**方向判断**：
- long: direction_score > 0
- short: direction_score < 0
- mixed (M2 fix): direction_score != 0（0 值表示中性，阻止入场）

## 核心算法

### s% 接近度 (`compute_s_pct`)

```
s% = (ATR / close) * proximity_mult
```

ATR 衡量当前波动率，close 是当前价格，proximity_mult 是 DNA 可调参数（默认 1.5）。

### 价格区间 (`build_price_zone`)

```
zone = [P * (1 - s%), P * (1 + s%)]
```

对每个价格位 P（如 EMA 值 60000），以 s% 为半径构建区间。

### 区间并集 (`merge_intervals`)

排序后线性扫描合并重叠区间。用于同一层多个价格位的合并。

### 区间交集 (`intersect_intervals`)

双指针扫描两个已排序区间集的交集。用于跨层价格区间重合度计算。

### 共振评分 (`compute_confluence_score`)

1. 对每层的价格区间做层内并集
2. 对所有层的并集做层间交集
3. 评分 = (交集宽度 / max_zone_width) * 价格在交集内的加权

### 动量方向一致性 (C1 fix)

当 price confluence 为 0 且有 >=2 个非执行层有 momentum 时：

1. 对每根 bar，收集所有层的动量值
2. 计算多数方向的比例（agreement = majority / total）
3. agreement > 0.5 时，评分 = 0.3 + 0.7 * (agreement - 0.5) / 0.5

单层动量降级：只有 1 个非执行层有 momentum 时，用归一化动量强度 * 0.5 作为 confluence 代理。

### 已知架构问题

1. **`_build_exec_signal_set` 扁平 AND**：不区分 state 信号（结构/zone 层）和 pulse 信号（执行层），全部 AND 组合。正确做法应为 gate + trigger 模式。
2. **动量中性点**：动量方向判断用 `> 0`，对 RSI (0-100)、Stochastic (0-100) 等有界指标不正确，应为 `> neutral_point`（如 RSI > 50）。

## 信号组合 (`_build_exec_signal_set`)

内部函数，构建跨层信号组合：

1. 遍历所有层，按角色分类
2. 非执行层信号用 `resample_signals`（ffill）对齐到执行周期
3. 执行层信号直接 `reindex(fill_value=False)`
4. entries 用 AND 组合，exits/adds/reduces 用 OR 组合
5. entry + exit 冲突时 exit 优先

## 主入口 (`run_mtf_engine`)

```
1. 遍历 dna.layers，对每层调用 evaluate_layer_with_context
2. 调用 _build_exec_signal_set 获取原始 SignalSet
3. 调用 synthesize_cross_layer 获取 MTFSynthesis 评分
4. 调用 apply_decision_gate 过滤信号
5. 设置 entry_direction 和 degraded_layers
6. 返回最终 SignalSet
```

## 路由关系

```
executor.dna_to_signal_set()
  ├─ dna.mtf_mode is not None → run_mtf_engine()  [新引擎]
  └─ dna.mtf_mode is None     → 旧 AND/OR 路径     [向后兼容]
```

## 测试覆盖

| 测试文件 | 覆盖范围 |
|---------|---------|
| tests/test_mtf_engine.py | 核心算法（s%, price zone, intervals, confluence）、层评估器、决策门控 |
| tests/test_mtf_integration.py | 端到端集成（单周期/多周期/向后兼容） |
| tests/test_mtf_evolution.py | 进化算子适配 |
| tests/test_c1_momentum_e2e.py | C1 动量 confluence 端到端验证 |

## 涉及文件

| 文件 | 行数 | 核心内容 |
|------|------|---------|
| `core/strategy/mtf_engine.py` | 789 | 全部 MTF 引擎实现 |
