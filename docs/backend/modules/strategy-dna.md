# B4: 策略 DNA

## 定位

`core/strategy/` 是整个工程的核心数据结构。其他所有模块——指标计算、回测引擎、进化算子、评分系统、API 序列化——都围绕 `StrategyDNA` 这个类型运转。

## 核心类型: `StrategyDNA`

`dna.py` (388 行) 用 dataclass 定义了一个四层基因结构:

| 基因层 | 类型 | 字段 | 作用 |
|--------|------|------|------|
| signal_genes | `List[SignalGene]` | indicator / params / role / field_name / condition | 单个信号条件，如 "RSI(14) < 30" |
| logic_genes | `LogicGenes` | entry_logic / exit_logic / add_logic / reduce_logic | 用 AND/OR 组合同角色的信号 |
| execution_genes | `ExecutionGenes` | timeframe / symbol | 执行参数——在哪个交易对、哪个周期跑 |
| risk_genes | `RiskGenes` | stop_loss / take_profit / position_size / leverage / direction | 风控参数 |

### MTF 控制参数 (新增)

`StrategyDNA` 新增三个字段控制 MTF 引擎行为：

| 字段 | 类型 | 默认值 | 作用 |
|------|------|--------|------|
| mtf_mode | `Optional[str]` | None | 激活 MTF 共振引擎。None=旧引擎, "direction"/"confluence"/"direction+confluence" |
| confluence_threshold | `float` | 0.3 | 共振评分门槛 [0.1, 0.9]，低于此值的 entry 被 gate 拦截 |
| proximity_mult | `float` | 1.5 | s% 接近度乘数 [0.5, 3.0]，控制价格区间半径 |

### SignalGene 的角色系统

`SignalRole` 枚举定义了 8 种角色，分四组:

- **入场**: `entry_trigger`（直接触发买）、`entry_guard`（过滤入场条件）
- **出场**: `exit_trigger`（直接触发卖）、`exit_guard`（过滤出场条件）
- **加仓**: `add_trigger` / `add_guard`
- **减仓**: `reduce_trigger` / `reduce_guard`

同角色的信号用 `logic_genes` 的 AND/OR 组合。触发和守卫在执行时没有区别——`executor.py` 直接把 triggers + guards 放进同一个列表再 combine。区分 trigger 和 guard 的意义在于进化时可以独立变异。

### Condition 的 16 种类型

`ConditionType` 枚举覆盖了从简单比较到复杂形态检测的全部条件:

1. **简单比较** (lt/gt/le/ge) — 指标 vs 固定阈值，产出**状态信号**（持续 True）
2. **穿越** (cross_above/cross_below) — 指标穿越固定阈值，产出**脉冲信号**（1 bar True）
3. **价格关系** (price_above/price_below) — 价格 vs 指标线，产出**状态信号**
4. **动态穿越** (cross_above_series/cross_below_series) — 指标 A 穿越指标 B，产出**脉冲信号**
5. **回望窗口** (lookback_any/lookback_all) — N 根 K 线内满足条件，产出**状态信号**
6. **支撑阻力** (touch_bounce/role_reversal/wick_touch) — 价格触碰/反转/影线触碰，产出**脉冲信号**

信号类型对 MTF 组合的影响：state 信号作为守卫/门限，pulse 信号作为触发器。entry 应由 pulse 信号触发（1 bar），而非 state 信号持续触发（每 bar）。

### 方向支持: direction 字段

`RiskGenes.direction` 接受三个值：

| 值 | 含义 | order_func_nb 映射 |
|----|------|-------------------|
| "long" | 只做多 | 0 |
| "short" | 只做空 | 1 |
| "mixed" | 双向交易 | 2 |

mixed 模式下，每根 bar 的交易方向由 `SignalSet.entry_direction` 决定（+1 做多, -1 做空）。`entry_direction` 延迟 1 bar 防止前瞻偏差。

### 三角色系统: derive_role()

`derive_role(timeframe: str) -> str` 根据时间周期自动推导层角色：

| 时间周期 | 角色 | 职责 |
|---------|------|------|
| >= 1d | "structure" | 提供趋势方向和关键价格位 |
| >= 1h 且 < 1d | "zone" | 提供价格区间参考 |
| < 1h | "execution" | 提供入场/出场时机 |

反序列化兼容：旧 DNA 中的 role="trend" 会自动映射为 "structure"。

### 多时间周期 (MTF) 支持

DNA 支持多时间周期通过 `layers: Optional[List[TimeframeLayer]]` 字段:

- 每个 `TimeframeLayer` 有自己的 `timeframe`、`signal_genes`、`logic_genes`、`role`
- `cross_layer_logic`（AND/OR）控制旧引擎的层间信号组合
- `is_mtf` 属性通过 `_layers_explicit` 标志区分"用户显式传入了 layers"和"自动包装的单层"
- `timeframes` 属性返回所有层（包括顶层）的时间周期列表

**自动包装机制**: 如果 `from_dict` 时没有 layers 但有 signal_genes，会自动创建一个单层 TimeframeLayer。这个自动包装的层不会让 `is_mtf` 返回 True，因为 `_layers_explicit=False`。

### 序列化约定

- JSON 序列化用 `to_dict()` -> `json.dumps`
- 反序列化用 `json.loads` -> `from_dict()`
- `SignalGene` 的 `field_name` 在 JSON 里映射为 `field`（`to_dict` 写 "field"，`from_dict` 把 "field" 转回 "field_name"）
- `strategy_id` 如果为空/缺失，`from_dict` 自动生成 UUID
- `mtf_mode`、`confluence_threshold`、`proximity_mult` 在 `to_dict`/`from_dict` 中序列化，缺失时用默认值

## 信号转换: `executor.py`

`executor.py` (750 行) 是 DNA -> 交易信号的桥梁:

1. `_get_indicator_column()` — 根据 SignalGene 的 indicator + params 构建列名，从 DataFrame 中查找。**这里维护了所有 30+ 种指标的列名映射规则**，是指标系统和信号系统之间的契约。
2. `evaluate_condition()` — 把 condition dict 转为布尔 Series。16 种条件类型对应 16 个分支。
3. `evaluate_layer()` — 对单个 TimeframeLayer 评估所有信号基因，按角色分组，用 logic_genes 组合。
4. `dna_to_signal_set()` — 顶层入口。路由到新 MTF 引擎或旧 AND/OR 路径。
5. `_resample_pulse()` — 对跨周期脉冲信号做时间窗口聚合（非 ffill），保留单 bar 触发特性。

**路由逻辑** (`dna_to_signal_set`)：
- `dna.mtf_mode is not None` -> 调用 `run_mtf_engine()` (新 MTF 引擎)
- `dna.is_mtf` 且有角色定义 -> 角色感知的 gate+trigger 组合
- 其他 -> 旧 AND/OR 路径

**关键细节**: entry 和 exit 同时为 True 时，exit 优先。trend_direction 取第一个 `ema_*` 列作为参考，不是参数化的。

## SignalSet 数据结构

`SignalSet` 是信号管线的最终产出，传递给回测引擎：

| 字段 | 类型 | 作用 |
|------|------|------|
| entries | pd.Series (bool) | 入场信号 |
| exits | pd.Series (bool) | 出场信号 |
| adds | pd.Series (bool) | 加仓信号 |
| reduces | pd.Series (bool) | 减仓信号 |
| degraded_layers | int | 因数据缺失跳过的 MTF 层数 |
| entry_direction | pd.Series (float) | 每 bar 交易方向 (+1/-1)，用于 mixed 模式 |
| mtf_diagnostics | dict | MTF 引擎诊断信息（direction_score, confluence_score 等） |

## DNA 校验: `validator.py`

`validator.py` (165 行) `validate_dna()` 在回测前检查合法性:

**基础校验**：
- 至少 1 个入场信号 + 1 个出场信号
- stop_loss in [0.005, 0.20], position_size in [0.10, 1.0], leverage in [1, 10]
- take_profit > stop_loss（如果设置）
- direction in {long, short, mixed}
- 复杂条件类型的必填字段检查（如 cross_above_series 需要 target_indicator）

**MTF 校验** (新增)：
- mtf_mode 必须是 None / "direction" / "confluence" / "direction+confluence"
- confluence_threshold in [0.1, 0.9]
- proximity_mult in [0.5, 3.0]
- 层角色接受 None / "trend" (旧) / "execution" / "structure" / "zone"
- 最多 3 层
- 至少需要一个执行层
- cross_layer_logic 必须是 AND 或 OR
- mixed 方向 + 无 trend 层时发出警告

## 策略命名: `generate_strategy_name()`

格式: `{indicator}{type} {direction} {timeframe}-{hash4}`
例: `EMA趋势 做多 4H-A3F2`

direction 为 "mixed" 时显示为 "mixed"。hash4 来自所有 signal_genes + logic + risk 参数的 MD5 前 4 位。

## 数据流

```
StrategyDNA (dataclass)
    | from_json / from_dict
    | (API 接收前端 payload)
    |
    v
executor.dna_to_signal_set(dna, enhanced_df, dfs_by_timeframe)
    |
    +-- mtf_mode is not None --> mtf_engine.run_mtf_engine()
    |     | evaluate_layer_with_context (时机 + 上下文)
    |     | synthesize_cross_layer (评分合成)
    |     | apply_decision_gate (门控过滤)
    |     v
    |   SignalSet { entries, exits, adds, reduces, entry_direction, mtf_diagnostics }
    |
    +-- mtf_mode is None --> 旧引擎
    |     | evaluate_layer (时机 only)
    |     | resample_signals (ffill)
    |     | combine_signals (AND/OR)
    |     v
    |   SignalSet { entries, exits, adds, reduces }
    |
    v
backtest/engine.py 使用 SignalSet 驱动回测
```

## 涉及文件

| 文件 | 行数 | 核心内容 |
|------|------|---------|
| `core/strategy/dna.py` | 388 | StrategyDNA 四层基因、derive_role、MTF 控制参数、序列化、命名 |
| `core/strategy/executor.py` | 750 | DNA->信号转换、16 种条件评估、MTF 路由、_resample_pulse |
| `core/strategy/validator.py` | 165 | DNA 合法性校验、MTF 参数范围检查、层角色校验 |
| `core/strategy/mtf_engine.py` | 789 | MTF 共振引擎（见 B4.1 模块文档） |
