# B8: 验证与场景

## 定位

`core/validation/` 实现两个子系统: (1) WHEN/THEN 假设验证引擎 (2) 场景验证系统（10 种图表形态检测 + 前向统计）。

## 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `engine.py` | 689 | WHEN/THEN 假设验证引擎 |
| `rule_engine.py` | 315 | 规则条件评估（含 AND/OR/IF 逻辑） |
| `mtf.py` | 150 | 多时间框架数据合并（防前瞻） |
| `patterns.py` | 270 | 内置形态检测 |
| `scene/base.py` | 84 | SceneDetector ABC |
| `scene/scene_engine.py` | 234 | 场景验证调度器 |
| `scene/pattern_match.py` | 551 | 图表形态匹配（极值优先搜索） |
| `scene/forward_stats.py` | 160 | 前向统计计算 |
| 其他 scene/*.py | ~600 | 8 种检测器实现 |

## 关键链路

### WHEN/THEN 验证 (engine.py:48)

```
validate_hypothesis(pair, timeframe, start, end, when_conditions, then_conditions)
  L82  解析数据目录
  L94  load_parquet()
  L108 compute_all_indicators()
  L111-132 MTF 合并:
    扫描条件获取引用的时间框架
    -> load_mtf_data() (mtf.py:45)
    -> merge_to_base() (mtf.py:88) -- 防前瞻合并
  L140 _evaluate_conditions():
    L294-347 _evaluate_single_condition():
      解析 subject -> Series, target -> value/Series
      从 action_map 分发 16 种动作类型
  L156-196 每个触发点:
    获取 trigger_price, 构建前向窗口
    -> _check_then_conditions() (L549)
  L201-266 聚合: match_rate, distribution, percentiles, concentration
```

### 规则引擎 (rule_engine.py:59)

```
evaluate_rules(symbol, timeframe, start, end, entry_conditions, exit_conditions)
  L97  load_parquet() + compute_all_indicators()
  L147-148 _evaluate_rule_conditions():
    每个条件用自己的 logic (AND/OR/IF) -- 修复了 engine.py 的 logic bug
  L156-168 生成 buy_signals, sell_signals
  L173 _pair_trades(): 顺序配对 entry->exit
  L178-197 统计: win_rate, total_return_pct
```

### 场景验证 (scene_engine.py:73)

```
run_scene_verification(symbol, timeframe, scene_type, params, horizons)
  L101 解析 sub-pattern -> 父检测器
  L153-175 MTF: load_mtf_data() + merge
  L178-180 detector.detect(enhanced_df, params) -> List[TriggerPoint]
  L196-222 每个触发点: compute_forward_stats(horizons)
  L225 aggregate_by_horizon()
```

## 关键机制

### MTF 无前瞻合并 (mtf.py:88-149)

`merge_to_base()` 三步防前瞻: (1) 高时间框架列前移一个基础时间单位 (2) ffill (3) `pd.merge_asof(direction="backward")` 关联到之前最近的高时间框架数据。

### 目标解析 5 层策略 (engine.py:371-418)

(1) 直接数值 (2) 字符串转浮点 (3) 跨时间框架格式 "4h:ema_20" -> "ema_20_4h" (4) 精确列名 (5) 模糊匹配 (strip underscores + lowercase substring)。

### 极值优先搜索 (pattern_match.py:132-495)

从 BennyThadikaran/stock-pattern 移植。峰值按价格降序排序 -> 对每个峰值 A 找后续最高 C -> 找 A/C 间最低谷底 B -> 几何约束 (价格接近度 <= 0.5*avgBarLength, ATR 高度 0.5x-8x)。保证先尝试"最佳"峰值。

### Pivot 检测 (pivot.py:21-73)

滚动窗口 [i-bars_left .. i+bars_right]，中心高点=窗口最大值(唯一) -> 峰值；中心低点=窗口最小值(唯一) -> 谷底。默认 bars_left=6, bars_right=6 (13根K线窗口)。

### 前向统计 (forward_stats.py:12-72)

每个触发点和 horizon h: 查看 h 根 K 线，计算 close_pct, max_gain_pct, max_loss_pct, bars_to_peak, bars_to_trough。不足 h 标记 is_partial。

## 接口定义

| 函数 | 说明 |
|------|------|
| `validate_hypothesis(pair, tf, start, end, when, then) -> ValidationResult` | 假设验证 |
| `evaluate_rules(symbol, tf, start, end, entry, exit) -> RuleResult` | 规则评估 |
| `run_scene_verification(symbol, tf, scene_type, ...) -> SceneVerificationResult` | 场景验证 |
| `merge_to_base(base_df, info_dfs, ...) -> DataFrame` | MTF 防前瞻合并 |
| `SceneDetector.detect(df, params) -> List[TriggerPoint]` | 检测器 ABC |

## 关键参数

| 参数 | 默认值 | 设计意图 |
|------|--------|---------|
| then_window | 8 | 前向检查 THEN 的 K 线数 |
| bars_left/bars_right | 6/6 | Pivot 检测窗口 |
| _MAX_PATTERN_SPAN | 200 | 形态点间最大距离 |
| horizons | [6,12,24,48] | 前向统计周期 (4h K线中 1/2/1/2天) |

## 约定与规则

- **条件格式**: `{subject, action, target, logic, window, timeframe}`
- **Action 命名**: 短动词 (gt/lt/ge/le) + 语义动词 (touch/cross_above/breakout/spike/...)
- **MTF 列命名**: 高时间框架指标列附加 `_TF` 后缀 (ema_20_4h)
- **SceneDetector 注册**: 新检测器加入 scene_engine.py:30-37 DETECTORS + 42-61 SCENE_META
- **错误容忍**: 整个模块用提前返回空结果，不抛异常
- **入场/出场配对**: 顺序配对，优先出场；无匹配出场的交易保持未平仓
