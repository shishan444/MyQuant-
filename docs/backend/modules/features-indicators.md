# B3: 技术指标与信号

## 定位

`core/features/` 提供 DNA 信号基因到实际交易信号的转换基础——把 "RSI(14) < 30" 这样的基因描述变成 DataFrame 上的布尔列。同时为进化引擎提供指标注册表（约束变异空间）和使用画像（引导变异方向）。

## 文件职责

| 文件 | 行数 | 职责 |
|------|------|------|
| `indicators.py` | 365 | 指标计算引擎：`_compute_indicator()` 单指标计算 + `compute_all_indicators()` 批量预计算 |
| `registry.py` | 358 | 指标注册表：39 个指标定义、参数约束、支持的 condition 类型、分类 |
| `signal_builder.py` | 195 | DNA→信号的另一种实现（与 executor.py 功能重叠） |
| `indicator_profile.py` | 329 | 指标使用画像：推荐角色、推荐参数、推荐条件、跟随概率 |
| `patterns/candlestick.py` | ~180 | 10 种蜡烛图形态检测（看跌吞没/黄昏之星/三只乌鸦等） |
| `patterns/divergence.py` | ~80 | 牛背离/熊背离检测（价格 vs RSI 方向不一致） |

## 指标注册表 (registry.py)

`INDICATOR_REGISTRY` 是一个 `Dict[str, IndicatorDef]`，定义了 39 个指标，分 7 个类别:

| 类别 | 指标 | 数量 |
|------|------|------|
| trend | EMA, SMA, WMA, DEMA, TEMA, VWAP | 6 |
| momentum | RSI, MACD, Stochastic, CCI, ROC, Williams %R, Aroon, CMO, TRIX | 9 |
| volatility | BB, ATR, Keltner, Donchian | 4 |
| volume | OBV, CMF, MFI, RVOL, VROC, AD, CVD, VWMA | 8 |
| trend_strength | ADX, PSAR | 2 |
| pattern | 10 种蜡烛图形态 | 10 |
| structure | VolumeProfile | 1 |

每个 `IndicatorDef` 包含:
- **category**: 分类（用于进化时的同类替换）
- **params**: `Dict[str, ParamDef]`，每个参数有 min/max/default/step/candidates
- **output_fields**: 输出字段名列表（如 BB 的 upper/middle/lower）
- **supported_conditions**: 该指标支持的 condition 类型列表
- **guard_only**: 标记为 True 的指标（ATR, ADX, PSAR, VolumeProfile）不应作为 entry_trigger 使用

`ParamDef.clamp()` 把变异后的参数值约束到合法范围并对齐到 step 边界。

## 指标计算引擎 (indicators.py)

### 列名契约

`_compute_indicator()` 和 `executor._get_indicator_column()` 之间有一套隐含的列名契约。两者各自用 if-elif 链维护相同的命名规则:

```
EMA(20)       → ema_20
RSI(14)       → rsi_14
MACD(12,26,9) → macd_12_26_9 / macd_signal_12_26_9 / macd_histogram_12_26_9
BB(20,2.0)    → bb_upper_20_2 / bb_middle_20_2 / bb_lower_20_2
BearishEngulfing → pattern_bearish_engulfing
```

**两处代码是各自独立实现的**（`indicators.py:79-263` 和 `executor.py:273-399`），不是共享逻辑。如果新增指标，必须同时更新两处的列名映射，否则计算出的列找不到。

### compute_all_indicators() 的全量计算

`compute_all_indicators()` (line 340-364) 遍历 `_DEFAULT_PARAMS` 的 56 组参数，逐个调用 `_compute_indicator()`。这意味着:

- 回测请求**不知道 DNA 需要哪些指标**，一股脑全算
- MTF DNA 对每个时间周期都做一次全量计算（`mtf_loader.py:110` 调用 `compute_all_indicators(tf_df)`）
- 计算失败的指标被 `except` 静默跳过（line 360-362）
- **VolumeProfile 被排除在 `_DEFAULT_PARAMS` 之外**（注释 "guard_only and expensive"），只有 DNA 明确包含 VolumeProfile 基因时才按需计算

### 自定义指标（非 pandas-ta）

不是所有指标都用 pandas-ta。以下是自己实现的:
- **CVD**: `(close - open) / (high - low) * volume` 的累积和，有除零保护
- **RVOL**: `volume / SMA(volume, period)`
- **VolumeProfile**: 滚动窗口内按价格分桶计算成交量直方图，提取 POC/VAH/VAL。纯 Python 循环实现，是全系统最慢的指标（`_rolling_volume_profile` line 266-337）

## 使用画像 (indicator_profile.py)

`PROFILES` 为 40 个指标各定义了进化引导参数:

- **recommended_roles**: 推荐的基因角色（如 RSI → entry_trigger/exit_trigger，EMA → entry_guard/exit_guard）
- **recommended_params**: 推荐参数值（如 RSI period 推荐用 7/14/21）
- **recommended_conditions**: 推荐的条件+阈值（如 RSI 推荐 lt [25,30,35] 和 gt [65,70,75]）
- **follow_probability**: 进化时跟随推荐的概率（0.50-0.80）。剩余概率留给随机探索

这个画像被进化引擎的变异算子使用（`core/evolution/operators.py`），70% 概率按推荐生成，30% 随机——平衡领域知识和探索能力。

## signal_builder.py vs executor.py

这两个文件功能高度重叠——都做 "DNA + DataFrame → entries/exits 信号":

| | executor.py | signal_builder.py |
|---|---|---|
| 列名解析 | `_get_indicator_column()` | `_resolve_column()` |
| 条件评估 | `evaluate_condition()` | 复用 executor 的 `evaluate_condition()` |
| 信号组合 | 自行实现 | 复用 executor 的 `combine_signals()` |
| MTF 支持 | 有（layer 逐评估 + resample） | 无（只处理 signal_genes，忽略 layers） |
| 使用场景 | 回测引擎调用 | 进化引擎评估个体时调用（推断） |

**关键差异**: signal_builder 不支持 MTF。如果进化产生的 DNA 有 layers，用 signal_builder 评估会丢失跨周期信号。但回测引擎（backtest/engine.py）调用的是 executor 的 `dna_to_signal_set()`，所以最终回测结果是正确的。signal_builder 可能在进化中间评估（快速筛选）时使用以减少开销（推断，未从代码确认调用关系）。

## 蜡烛图形态 (patterns/)

`candlestick.py` 的 8 种形态检测都是纯 pandas 向量化操作——shift + 布尔组合，无依赖外部库。输出是 0/1 整数列，用 `eq` condition 匹配。

`divergence.py` 的背离检测基于"价格创新低但 RSI 不创新低"的逻辑，依赖 DataFrame 中已存在 `rsi_*` 列。检测到背离的条件是: `price_lower & rsi_higher & rsi_oversold`。

## 数据流

```
OHLCV DataFrame (Parquet)
    ↓
compute_all_indicators(df)
    ↓ 遍历 56 组参数
    ↓ _compute_indicator() → pandas-ta / 自定义函数
    ↓
Enhanced DataFrame (带 100+ 指标列)
    ↓
executor._get_indicator_column(df, gene)
    ↓ 按列名契约找到对应的 Series
    ↓
executor.evaluate_condition(series, close, condition)
    ↓ 16 种条件评估
    ↓
布尔 Series → 交易信号
```

## 涉及文件

| 文件 | 核心内容 |
|------|---------|
| `core/features/indicators.py` | 56 组参数的批量计算引擎 |
| `core/features/registry.py` | 39 个指标的注册表定义 |
| `core/features/signal_builder.py` | DNA→信号的简化版实现（无 MTF） |
| `core/features/indicator_profile.py` | 40 个指标的进化引导画像 |
| `core/features/patterns/candlestick.py` | 8 种蜡烛图形态检测 |
| `core/features/patterns/divergence.py` | 牛/熊背离检测 |
