# B3: 技术指标与信号

## 定位

`core/features/` 是"翻译器"——把指标数值翻译成布尔交易信号。定义、计算、注册 40 种技术指标，提供从 DNA 策略到交易信号的完整构建链路。

## 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `indicators.py` | 365 | 40 种指标批量预计算引擎 |
| `registry.py` | 358 | 指标注册表（结构化元数据） |
| `indicator_profile.py` | 329 | 进化先验知识（推荐配置） |
| `signal_builder.py` | 185 | DNA -> 交易信号构建器 |
| `patterns/candlestick.py` | 129 | 8 种 K 线形态检测 |
| `patterns/divergence.py` | 95 | 多空背离检测 |

## 关键链路

### 批量预计算所有指标

```
indicators.py:340 compute_all_indicators(df)
  L350  复制 DataFrame
  L352-362  遍历 _DEFAULT_PARAMS (30 种指标, 72 组参数):
    L355  _compute_indicator(result, name, params)
    L357-359  仅添加新列，跳过已有
    L360-362  计算失败静默跳过（容错设计）
```

### DNA -> 交易信号

```
signal_builder.py:116 build_signal_set(dna, enhanced_df)
  L121-127  初始化 8 个信号列表 (entry/exit/add/reduce x trigger/guard)
  L128-151  遍历 dna.signal_genes:
    L129  _resolve_column 查找指标列
    L133  evaluate_condition 计算布尔信号 + fillna(False)
    L136-151  按 gene.role 分类
  L154-173  combine_signals 按 AND/OR 组合
  L176-177  防止同时 entry+exit（优先 exit）
```

## 关键机制

### VolumeProfile 滚动计算 (indicators.py:266-337)

每个时间点取 [i-lookback+1, i] 窗口，构建 bins 个等宽分桶按成交量统计直方图。POC = 最大分桶中点价格。Value Area = 累计 70% 成交量的分桶集合 -> VAH/VAL。时间复杂度 O(n * lookback * bins)。

### 指标注册表 (registry.py:48-346)

`INDICATOR_REGISTRY`: Dict[str, IndicatorDef]，40 种指标结构化元数据。每个定义: category, params（带范围约束）, output_fields, supported_conditions, guard_only。`get_interchangeable(name)` 返回同类别指标列表。

### Profile 系统 (indicator_profile.py:49-328)

`PROFILES`: Dict[str, IndicatorProfile]，为进化引擎提供先验知识。每个 Profile: recommended_roles, recommended_params, recommended_conditions, follow_probability (0.5-0.8)。

### K 线形态检测 (patterns/candlestick.py)

8 种: bearish_engulfing, evening_star, three_black_crows, shooting_star, three_white_soldiers, morning_star, bullish_reversal, bearish_reversal。输出 int(0/1)，列名 `pattern_{name}`。

### 背离检测 (patterns/divergence.py)

- bullish_divergence (L23): 价格创新低 AND RSI 更高 AND RSI < 40
- bearish_divergence (L53): 价格创新高 AND RSI 更低 AND RSI > 60

## 接口定义

| 函数 | 签名 | 位置 |
|------|------|------|
| `compute_all_indicators` | `(df) -> DataFrame` | indicators.py:340 |
| `build_signal_set` | `(dna, enhanced_df) -> SignalSet` | signal_builder.py:116 |
| `build_signals` | `(dna, enhanced_df) -> (Series, Series)` | signal_builder.py:102 |
| `extract_indicator_requirements` | `(dna) -> List[Tuple]` | signal_builder.py:17 |
| `get_interchangeable` | `(name) -> List[str]` | registry.py:349 |

## 关键参数

| 参数 | 位置 | 默认值 | 设计意图 |
|------|------|--------|---------|
| `_DEFAULT_PARAMS` | indicators.py:30 | 72 组 | 批量预计算参数预设 |
| `bins` (VP) | indicators.py:207 | 50 | VolumeProfile 分桶数 |
| `lookback` (VP) | indicators.py:207 | 60 | VolumeProfile 滚动窗口 |
| `lookback` (div) | divergence.py:23 | 20 | 背离检测回溯窗口 |
| `follow_probability` | indicator_profile.py:27 | 0.50-0.80 | 进化遵循推荐的概率 |
| `guard_only` | registry.py:41 | ATR/ADX/PSAR/VP | 只适合做 guard 的指标 |

## 约定与规则

- **列名**: `{indicator}_{param1}_{param2}` (ema_20, rsi_14, bb_upper_20_2.0)
- **形态输出**: int(0/1)，列名 `pattern_{name}`
- **分类**: trend(6) + momentum(9) + volatility(4) + volume(8) + trend_strength(2) + pattern(10) + structure(1) = 40
- **容错**: 失败静默跳过
- **信号防冲突**: entry+exit 同时 True 时优先 exit
- **向后兼容 re-export**: indicators.py:18-23 重新导出 registry.py 的类型
