# B8: 验证与场景

## 定位

`core/validation/` 实现了 WHEN/THEN 假设验证引擎和场景验证系统。假设验证用于策略实验室的"假设验证"模式，场景验证用于"场景验证"模式。API 层直接调用。

## 文件职责

### 核心验证引擎

| 文件 | 行数 | 职责 |
|------|------|------|
| `engine.py` | 689 | WHEN/THEN 假设验证主引擎：16+ 种动作评估、MTF 支持、触发记录、分布统计 |
| `rule_engine.py` | 315 | 入场/出场规则评估：信号生成 + 交易配对 + 胜率统计 |
| `patterns.py` | 270 | 纯模式检测算法（背离/连续/触碰反弹/角色反转） |
| `mtf.py` | 150 | 多时间周期数据加载与合并（merge_asof + 前向填充） |

### 场景验证系统 (scene/)

| 文件 | 行数 | 职责 |
|------|------|------|
| `scene/__init__.py` | 13 | 公共 API 导出 |
| `scene/base.py` | 84 | SceneDetector 抽象基类 + 数据结构 |
| `scene/scene_engine.py` | 234 | 场景验证编排器：加载→检测→前向统计→聚合 |
| `scene/forward_stats.py` | 160 | 前向统计计算（多周期收益/亏损/峰值/谷值） |
| `scene/top_pattern.py` | 106 | 枢轴点图表形态检测（双顶/头肩顶/三重顶） |
| `scene/pattern_match.py` | 551 | 图表形态匹配引擎（极端优先搜索策略） |
| `scene/pivot.py` | 74 | 滚动窗口枢轴点检测 |
| `scene/volume_spike.py` | 63 | 成交量异常检测（成交量 > N 倍均线） |
| `scene/mean_reversion.py` | 86 | 均值回归检测（价格偏离均线 N%） |
| `scene/volume_breakout.py` | 107 | 放量突破检测（成交量激增 + 价格突破关键位） |
| `scene/support_resistance.py` | 110 | 支撑阻力触碰检测（BB/Donchian/Keltner 带触边） |
| `scene/cross_timeframe.py` | 98 | 跨周期信号确认检测（高周期金叉 + 低周期确认） |

## 假设验证引擎 (engine.py)

`validate_hypothesis()` 是主入口。流程：

```
加载 Parquet → compute_all_indicators → MTF 合并
  ↓
评估 WHEN 条件 → 生成触发时间点
  ↓
对每个触发点: 检查 THEN 条件（forward window）
  ↓
构建 ValidationResult:
  match_rate, trigger_records, distribution, percentiles,
  concentration_range, signal_frequency, extremes
```

### 条件动作类型（16+）

| 动作 | 含义 |
|------|------|
| touch / breakout / breakdown | 触碰/突破/跌破固定值或指标线 |
| cross_above / cross_below | 穿越固定值 |
| gt / lt / ge / le | 简单比较 |
| spike / shrink | 成交量激增/萎缩（倍数） |
| divergence_top / divergence_bottom | 背离检测 |
| consecutive_up / consecutive_down | 连续上涨/下跌 N 根 |
| cross_above_series / cross_below_series | 穿越另一指标线 |
| lookback_any | 回望窗口内满足条件 |
| touch_bounce / role_reversal | 触碰反弹/角色反转 |

### 跨时间周期引用

条件中的 target 支持跨周期格式 `"4h:ema_20"`，解析为合并后的 `ema_20_4h` 列。`merge_to_base()` 用 `pd.merge_asof` 做时间对齐，时间戳前移一个基础周期防止未来信息泄露。

### 已知问题

- line 134 引用 `warnings` 在 line 137 定义之前，MTF 加载失败时可能 NameError
- `_evaluate_conditions()` 的 AND/OR 逻辑只读最后一个条件的 `logic` 字段——`rule_engine.py` 修复了这个问题

## 规则评估引擎 (rule_engine.py)

`evaluate_rules()` 评估入场/出场规则，生成买卖信号，配对交易，计算胜率：

```
评估入场条件 → entry 信号 Series
评估出场条件 → exit 信号 Series
  ↓
_pair_trades(): 顺序配对（入场→出场→记录→继续）
  ↓
RuleResult: signals, trades, win_rate, total_return
```

入场和出场同时触发时，出场优先（与回测引擎一致）。

## 场景验证系统

### 6 种场景检测器

| 检测器 | 检测内容 | 关键参数 |
|--------|----------|----------|
| TopPatternDetector | 双顶/头肩顶/三重顶 | ATR 高度约束 (0.5x-8x) |
| VolumeSpikeDetector | 成交量 > N 倍滚动均值 | 倍数=2.5, 窗口=20 |
| MeanReversionDetector | 价格偏离均线 N% | 偏离=3%, 均线=EMA50 |
| VolumeBreakoutDetector | 放量 + 突破关键位 | 关键位=BB 上轨 |
| SupportResistanceDetector | 触碰支撑/阻力位 | 逼近百分比 |
| CrossTimeframeDetector | 高周期信号 + 低周期确认 | 金叉 EMA20/50 |

### 检测流程

```
scene_engine.run_scene_verification()
  ↓ 加载数据 + 计算指标 + (可选)MTF 合并
  ↓ 根据 scene_type 选择检测器
  ↓ detector.detect() → TriggerPoint[]
  ↓ compute_forward_stats() → 多周期前向统计
  ↓ aggregate_by_horizon() → 聚合结果
  ↓
SceneVerificationResult { triggers, horizon_stats, aggregate }
```

### pattern_match.py 的极端优先策略

双顶/头肩顶/三重顶的匹配算法：先把所有峰按价格降序排列，从最高峰开始尝试组合——显著形态优先匹配。几何约束用 ATR 控制（加密货币波动大，允许 0.5x-8x ATR 高度）。形态完成后检查 10 根 K 线内关键价位是否被突破（level intact check）。

## 数据流

```
前端请求
  ├─ POST /api/validate → validate_hypothesis() → ValidationResult
  ├─ POST /api/validate/rules → evaluate_rules() → RuleResult
  └─ POST /api/validate/scene → run_scene_verification() → SceneVerificationResult
```

## 涉及文件

| 文件 | 核心内容 |
|------|---------|
| `core/validation/engine.py` | WHEN/THEN 假设验证主引擎 |
| `core/validation/rule_engine.py` | 规则评估 + 交易配对 |
| `core/validation/patterns.py` | 模式检测算法 |
| `core/validation/mtf.py` | MTF 数据合并 |
| `core/validation/scene/scene_engine.py` | 场景验证编排 |
| `core/validation/scene/forward_stats.py` | 前向统计 |
| `core/validation/scene/top_pattern.py` + `pattern_match.py` + `pivot.py` | 图表形态 |
| `core/validation/scene/volume_*.py` + `mean_reversion.py` + `support_resistance.py` + `cross_timeframe.py` | 4 种检测器 |
