# B4: 策略 DNA

## 定位

`core/strategy/` 是整个工程的核心数据结构。其他所有模块——指标计算、回测引擎、进化算子、评分系统、API 序列化——都围绕 `StrategyDNA` 这个类型运转。

## 核心类型: `StrategyDNA`

`dna.py` 用 dataclass 定义了一个四层基因结构:

| 基因层 | 类型 | 字段 | 作用 |
|--------|------|------|------|
| signal_genes | `List[SignalGene]` | indicator / params / role / field_name / condition | 单个信号条件，如 "RSI(14) < 30" |
| logic_genes | `LogicGenes` | entry_logic / exit_logic / add_logic / reduce_logic | 用 AND/OR 组合同角色的信号 |
| execution_genes | `ExecutionGenes` | timeframe / symbol | 执行参数——在哪个交易对、哪个周期跑 |
| risk_genes | `RiskGenes` | stop_loss / take_profit / position_size / leverage / direction | 风控参数 |

### SignalGene 的角色系统

`SignalRole` 枚举定义了 8 种角色，分四组:

- **入场**: `entry_trigger`（直接触发买）、`entry_guard`（过滤入场条件）
- **出场**: `exit_trigger`（直接触发卖）、`exit_guard`（过滤出场条件）
- **加仓**: `add_trigger` / `add_guard`
- **减仓**: `reduce_trigger` / `reduce_guard`

同角色的信号用 `logic_genes` 的 AND/OR 组合。触发和守卫在执行时没有区别——`executor.py:441` 直接把 triggers + guards 放进同一个列表再 combine。区分 trigger 和 guard 的意义在于进化时可以独立变异。

### Condition 的 16 种类型

`ConditionType` 枚举覆盖了从简单比较到复杂形态检测的全部条件:

1. **简单比较** (lt/gt/le/ge) — 指标 vs 固定阈值
2. **穿越** (cross_above/cross_below) — 指标穿越固定阈值
3. **价格关系** (price_above/price_below) — 价格 vs 指标线
4. **动态穿越** (cross_above_series/cross_below_series) — 指标 A 穿越指标 B
5. **回望窗口** (lookback_any/lookback_all) — N 根 K 线内满足条件
6. **支撑阻力** (touch_bounce/role_reversal/wick_touch) — 价格触碰/反转/影线触碰

Condition 是一个 `Dict[str, Any]`，不是强类型。`type` 字段决定分支，其余字段按类型需要提供（如 `threshold`、`target_indicator`、`window`、`direction` 等）。

### 多时间周期 (MTF) 支持

DNA 支持多时间周期通过 `layers: Optional[List[TimeframeLayer]]` 字段:

- 每个 `TimeframeLayer` 有自己的 `timeframe`、`signal_genes`、`logic_genes`
- `cross_layer_logic`（AND/OR）控制层间信号组合
- `is_mtf` 属性通过 `_layers_explicit` 标志区分"用户显式传入了 layers"和"自动包装的单层"

**自动包装机制** (`dna.py:284-294`): 如果 `from_dict` 时没有 layers 但有 signal_genes，会自动创建一个单层 TimeframeLayer。这个自动包装的层不会让 `is_mtf` 返回 True，因为 `_layers_explicit=False`。

### 序列化约定

- JSON 序列化用 `to_dict()` → `json.dumps`
- 反序列化用 `json.loads` → `from_dict()`
- `SignalGene` 的 `field_name` 在 JSON 里映射为 `field`（`to_dict` 写 "field"，`from_dict` 把 "field" 转回 "field_name"）
- `strategy_id` 如果为空/缺失，`from_dict` 自动生成 UUID

## 信号转换: `executor.py`

`executor.py` 是 DNA → 交易信号的桥梁:

1. `_get_indicator_column()` — 根据 SignalGene 的 indicator + params 构建列名，从 DataFrame 中查找。**这里维护了所有 30+ 种指标的列名映射规则**，是指标系统和信号系统之间的契约。
2. `evaluate_condition()` — 把 condition dict 转为布尔 Series。16 种条件类型对应 16 个分支。
3. `evaluate_layer()` — 对单个 TimeframeLayer 评估所有信号基因，按角色分组，用 logic_genes 组合。
4. `dna_to_signal_set()` — 顶层入口。MTF 模式下逐层评估 + `resample_signals()` 对齐到执行周期 + `cross_layer_logic` 组合。

**关键细节**: entry 和 exit 同时为 True 时，exit 优先（`executor.py:458-459, 620-621`）。trend_direction 取第一个 `ema_*` 列作为参考，不是参数化的。

## DNA 校验: `validator.py`

`validate_dna()` 在回测前检查合法性:
- 至少 1 个入场信号 + 1 个出场信号
- stop_loss ∈ [0.005, 0.20], position_size ∈ [0.10, 1.0], leverage ∈ [1, 10]
- take_profit > stop_loss（如果设置）
- direction ∈ {long, short}
- 复杂条件类型的必填字段检查（如 cross_above_series 需要 target_indicator）

**注意**: `validator.py:33-36` 只检查 `dna.signal_genes`，不检查 layers。MTF 策略的 layer 信号在 line 48-61 有单独检查，但如果信号只在 layer 里不在顶层 signal_genes 里，入场/出场检查会漏过（推断）。

## 策略命名: `generate_strategy_name()`

格式: `{indicator}{type} {direction} {timeframe}-{hash4}`
例: `EMA趋势 做多 4H-A3F2`

hash4 来自所有 signal_genes + logic + risk 参数的 MD5 前 4 位，用于区分相同指标不同参数的策略。

## 数据流

```
StrategyDNA (dataclass)
    ↓ from_json / from_dict
    ↓ (API 接收前端 payload)
    ↓
executor.dna_to_signal_set(dna, enhanced_df, dfs_by_timeframe)
    ↓ _get_indicator_column → 找到指标列
    ↓ evaluate_condition → 布尔 Series
    ↓ combine_signals → AND/OR 组合
    ↓ resample_signals → 高周期对齐到执行周期
    ↓
SignalSet { entries, exits, adds, reduces, trend_direction }
    ↓
backtest/engine.py 使用 SignalSet 驱动 vectorbt 回测
```

## 涉及文件

| 文件 | 行数 | 核心内容 |
|------|------|---------|
| `core/strategy/dna.py` | 346 | StrategyDNA 及四层基因 dataclass、序列化、MTF 支持、命名 |
| `core/strategy/executor.py` | 639 | DNA→信号转换、16 种条件评估、MTF 层间组合 |
| `core/strategy/validator.py` | 112 | DNA 合法性校验 |
