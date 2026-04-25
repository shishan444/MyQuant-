# B4.1: MTF 共振引擎

## 定位

`core/strategy/mtf_engine.py` (790 行) 是系统中最复杂的模块。用多维度评分门控取代旧版的布尔 AND/OR 跨层逻辑，实现"双轨道 + 三阶段管线"。

## 三阶段管线

```
Stage 1: 层评估 + 上下文提取
  每层独立评估 -> LayerResult (signal_set + direction + price_levels + momentum)
     |
Stage 2: 跨层综合 (synthesize_cross_layer)
  direction_score:   +1/-1/0 方向评分
  confluence_score:  0.0~1.0 共振评分
  momentum_score:    0.0~1.0 动量评分
  strength_multiplier: 0.0~1.0+ 强度乘数
     |
Stage 3: 决策门控 (apply_decision_gate)
  entry 受方向+共振双门控
  exit/reduce 不过滤（风控优先）
  add 受宽松门控 (0.8 * threshold)
```

## 关键链路

### 主入口 (run_mtf_engine, L649)

```
run_mtf_engine(dna, dfs_by_timeframe, enhanced_df)
  L661  获取执行层 DataFrame
  L667  for layer in dna.layers:
    L679  evaluate_layer_with_context(layer, layer_df, exec_df.index)
      -> evaluate_layer() (executor.py L408)
      -> extract_context(df, gene, category) (L239)
      -> resample_values(...) (非执行层, L348-363)
      -> 返回 LayerResult
  L683  _build_exec_signal_set(layer_results, dna, exec_df)
    L731-741  每层 resample_signals / reindex
    L757-760  entries AND, exits/adds/reduces OR
    L763-764  防止同K线同时 entry+exit
  L691  synthesize_cross_layer(...)
  L697  apply_decision_gate(exec_signal_set, synthesis, dna)
  L698-701  设置 entry_direction, degraded_layers
```

### 跨层综合 (synthesize_cross_layer)

```
L431-440  direction: resolve_direction_conflict (最高周期优先)
L442-480  confluence: compute_confluence_score (区间交集)
L497-507  momentum: sigmoid 归一化
L512-551  momentum fallback (价格 confluence=0 时启用)
```

### 决策门控 (apply_decision_gate, L587)

```
mtf_mode=None:       不过滤 (向后兼容)
mtf_mode="direction": 仅方向过滤
mtf_mode="confluence": 仅共振过滤
mtf_mode="direction+confluence":
  entry: timing_signal AND direction_match AND confluence >= threshold
  exit:  timing_signal (不过滤)
  add:   timing_signal AND confluence >= threshold * 0.8
  reduce: timing_signal (不过滤)
```

## 关键机制

### s% 接近度计算 (compute_s_pct, L17)

`s% = (ATR / close) * proximity_mult`。ATR 越大、proximity_mult 越大 -> 共振区间越宽。

### 价格区间交集 (intersect_intervals, L63-79)

标准双指针区间交集算法，O(n+m)。对每根 K 线：(1) 各层构建价格区间 [P*(1-s%), P*(1+s%)] (2) 层内区间并集 (3) 层间区间取交集 (4) score = 交集宽度 / max_zone_width。

### 方向冲突解决 (resolve_direction_conflict, L184-186)

多 structure 层方向不同时，选最大时间框架方向为准。

### 上下文提取 (extract_context, L239-296)

从单个信号基因提取三类上下文：
- **direction**: 趋势指标 + price_above/price_below -> +1/-1
- **price_levels**: 趋势/波动指标输出作为价格水平线
- **momentum**: 动量指标原始输出

### 动量共振回退 (L509-551)

价格区间共振为 0 时（structure/zone 缺乏价格水平输出），统计各层动量方向多数派占比，超 50% 时计算 agreement 评分 (0.3~1.0)。

### ATR 获取三级回退 (_get_exec_atr, L774-789)

先找 `atr_` 前缀列 -> 手动计算 True Range 14周期均值 -> close * 0.02。

## 接口定义

| 函数 | 说明 |
|------|------|
| `compute_s_pct(atr, close, mult) -> float` | 邻近百分比 |
| `build_price_zone(price, s_pct) -> Tuple` | 价格区间 |
| `compute_confluence_score(layer_zones, price, max_width) -> float` | 共振评分 |
| `compute_proximity_score(levels, price, s_pct) -> Series` | 单层邻近度 |
| `resolve_direction_conflict(layers_with_dir) -> Series` | 方向冲突解决 |
| `LayerResult` (dataclass) | signal_set, direction, price_levels, momentum, strength, volatility |
| `MTFSynthesis` (dataclass) | direction_score, confluence_score, momentum_score, strength_multiplier |
| `extract_context(df, gene, category) -> dict` | 上下文提取 |
| `evaluate_layer_with_context(layer, df, exec_idx) -> LayerResult` | 带上下文的层评估 |
| `synthesize_cross_layer(...) -> MTFSynthesis` | 跨层综合 |
| `apply_decision_gate(signals, synthesis, dna) -> SignalSet` | 决策门控 |
| `run_mtf_engine(dna, dfs, enhanced_df) -> SignalSet` | **主入口** |

## 关键参数

| 参数 | 默认值 | 设计意图 |
|------|--------|---------|
| proximity_mult | 1.5 | ATR 放大系数，越大共振区间越宽 |
| confluence_threshold | 0.3 | 共振评分门槛 |
| mtf_mode | None | 控制门控维度激活 |
| add 宽松系数 | 0.8 | add 信号使用 80% threshold，比 entry 更容易触发 |

## 已知架构问题

1. **`_build_exec_signal_set` 扁平 AND**: state 和 pulse 信号不区分，应改为 gate+trigger 模式
2. **动量 confluence 用 `> 0` 判断方向**: 对 RSI 等有界指标不正确，应用 `> 50`

## 约定与规则

- 非执行层数据必须 ffill 到执行层时间框架
- exit/reduce 永不过滤（风控优先）
- mtf_mode=None 时仍计算诊断分数但不门控
- `_SimpleGene` 适配器 (L229-236) 复用 executor.py 的 `_get_indicator_column`
- degrade 计数: 缺失 timeframe 数据时该层跳过
