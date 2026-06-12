# MTF 分层价格共振架构重设计方案

> 日期: 2026-04-25
> 状态: 设计讨论中（部分决策已确认，待澄清项见末尾）
> 前置: Phase E-K bug 修复已完成（V1~V9 全部修复，669 tests passing）

---

## 一、问题背景

### 1.1 原始问题

Phase E-K 完成了 MTF 管线中 V1~V9 共 9 个 bug 的修复。修复后代码审计发现更深层的设计缺陷：

**当前 MTF 信号组合是"多信号布尔投票"，不是"分层决策系统"。**

每个周期独立产生 True/False 信号，然后用 AND/OR 逻辑组合。这种方式缺少**跨周期传递价格区间信息并判断价格重合**的核心能力。

### 1.2 用户需求（交易视角）

用户描述的交易逻辑：
- 3d 层给出**方向**和**关键价格位**
- 4h 层给出**价格区间**参考
- 15m 层在价格到达**共同关注区域**时寻找精确入场时机
- 三个周期的价格区间**重合**时信号可信度最高

### 1.3 核心差距

旧架构缺少的能力：
1. 无法传递价格值（只能传 True/False）
2. 无法判断"价格是否同时接近多个周期的关注区域"
3. 无法衡量"重合程度"（只有 0 或 1）

---

## 二、设计讨论过程

### 2.1 讨论 1：专业支撑/阻力识别方法

**起因**：需要验证使用 BB 上中下轨作为支撑/阻力的方案是否专业。

**调研过程**：
- 检索 Investopedia、TradingView 专业社区
- 研究 TradingView 内置的 S/R 识别工具
- 调研专业交易者常用的算法化 S/R 方法

**调研结论**：

| 方法 | S/R 来源 | 我们是否支持 | 适用角色 |
|------|---------|------------|---------|
| 布林带 | 上轨=阻力，下轨=支撑，中轨=SMA20 | 已支持（`bb_*` 列） | zone/structure |
| 移动均线 | EMA200 等作为动态趋势线 | 已支持（`ema_*` 列） | structure |
| 唐奇安通道 | N 周期最高/最低价=天然 S/R | 已支持（`dc_*` 列） | zone |
| Keltner 通道 | ATR 通道上下轨 | 已支持（`kc_*` 列） | zone |
| PSAR | 抛物线止损=动态 S/R | 已支持（`psar` 列） | structure |
| Volume Profile | POC/VAH/VAL=成交量聚集区 | 已支持（`vp_*` 列） | zone |
| Pivot Points | 前日 HLC 计算 S1-S3/R1-R3 | 未实现 | structure |
| 斐波那契回撤 | 23.6%~78.6% 回撤位 | 未实现 | structure |
| Ichimoku Cloud | 云带作为未来 S/R | 未实现 | zone |

**用户确认**："认可，先用已有指标"

### 2.2 讨论 2：接近度阈值计算方法

**起因**：需要一个算法来判断"当前价格是否接近某个参考价格位"。

#### 方案演变过程

**方案 A（最初提案）：简单 ATR 阈值**
```
如果 |当前价格 - 参考价格位| <= proximity_atr_mult * ATR_14
则该价格位"接近"
```
- 阈值是固定价格距离
- 问题：BTC 6万和 ETH 3千需要不同参数

**方案 B（第二轮提案）：交叉周期价差 ATR**
```
delta = |15m 指标值 - 4h 对应价格位|
spread_atr = delta.rolling(14).mean()
如果 delta <= proximity_mult * spread_atr → "接近"
```
- 阈值基于跨周期指标值差异的历史均值
- **用户反馈**："不对，应该是价格的幅度占比，而非固定值"

**方案 C（最终确认）：百分比幅度法 s%**
```
s% = (ATR_14 / close) * proximity_mult
接近阈值 = close * s%
```

**用户确认**："理解正确"

**最终方案详细说明**：

```
对每根执行层 bar：
  s% = (ATR_14 / close) * proximity_mult    # ATR_14 已在 DataFrame 中预计算
  接近阈值 = close * s%                      # 转为价格距离

如果 |当前价格 - 参考价格位| <= 接近阈值 → 该价格位"接近"

示例：close=60300, ATR_14=800, proximity_mult=1.5
  s% = (800 / 60300) * 1.5 = 1.99%
  接近阈值 = 60300 * 0.0199 = 1200
```

**自适应特性**：
- 高波动市场 → ATR 大 → s% 大 → 阈值自动放宽
- 低波动市场 → ATR 小 → s% 小 → 阈值自动收紧
- 高价资产（BTC 6万）和低价资产（ETH 3千）用同样的百分比逻辑，无需手动调参
- `proximity_mult` 默认 1.5，可通过进化调整（范围 0.5~3.0）

### 2.3 讨论 3：共振分数的计算方式

**起因**：如何量化"多个周期关注同一价格区域"的程度。

#### 方案演变过程

**方案 A（最初提案）：按价格位计数**
```
共振分数 = 接近的参考价格位数量 / 总参考价格位数量

示例：5个价格位中3个接近 → 共振分数 = 3/5 = 0.6
```

**方案 B（第二提案）：按层级计数**
```
共振分数 = 有至少1个价格位接近的层数 / 总层数

示例：2个层级都有至少1个接近 → 共振分数 = 2/2 = 1.0
```

**用户反馈**："我认为都不合适，与我理解的还是有差距。我认为共振的计算方式应该先理解共振的作用和使用场景，你必须要进行深度思考。"

**方案 C（最终确认）：区间重合法**

调研了 Investopedia 对 confluence 的专业定义：
> "Confluence occurs when multiple separate strategies or ideas are used together to form one comprehensive strategy. In technical analysis, several indicators are combined to identify entry/exit points."

核心思想：每个层级的价格位形成一个"关注区间"，共振 = 多个层的关注区间是否重合，且当前价格是否落在重合区域内。

**用户确认**："区间重合方案合理"

**最终方案详细说明**：

```
Step 1：构建每层的关注区间
  对每个层的每个价格位 P：
    区间上界 = P * (1 + s%)
    区间下界 = P * (1 - s%)
  层关注区间 = 该层所有价格位区间的并集

Step 2：计算区间重合度
  所有层的关注区间取交集 → 重合区域
  如果交集为空 → 共振分数 = 0.0（各层关注的价位完全不同）
  如果交集存在 → 计算重合区域宽度占所有层关注区间总宽度的比例

Step 3：检查当前价格是否在重合区域内
  如果当前价格在重合区域内 → 共振分数 = 重合度
  如果当前价格不在重合区域内 → 共振分数 = 0.0

Step 4：最终共振分数
  confluence_score = 重合度 * (价格在重合区内 ? 1.0 : 0.0)
```

**直觉解释**：每个层级通过指标值告诉我们"我在关注什么价格区域"。当多个层级关注的价格区域有交集，且价格刚好在那个交集中 → 共振。这比简单的"价格位计数"更准确，因为它衡量的是"区间重叠程度"而非"有多少个点恰好被触及"。

### 2.4 讨论 4：三种组合类型

**用户需求**：不同策略可能使用不同数量的周期层，需要明确每种情况下的行为。

| 类型 | 层配置 | 角色覆盖 | 共振行为 |
|------|-------|---------|---------|
| A（完整） | 3d + 4h + 15m | structure + zone + execution | 方向+价格位+时机完整共振 |
| B（部分） | 4h + 15m | zone + execution | 无独立方向源，使用 DNA.direction 或 zone 层推导方向 |
| C（单周期） | 15m | execution | 无共振，走原始单周期逻辑 |

**自动推导规则**：
```
if layers 中有 >= 1d 周期 → 分配 structure 角色
if layers 中有 >= 1h 周期 → 分配 zone 角色
执行周期层（由 execution_genes.timeframe 决定）→ execution 角色

Type A: 有 structure + zone + execution → 完整共振
Type B: 有 zone + execution（无 structure）→ zone 价格位共振，方向从 DNA 继承
Type C: 只有 execution → 跳过共振，走原始单周期路径
```

---

## 三、确认的架构设计

### 3.1 旧架构（替换）

```
3d 层 → entries: True/False → forward-fill 到 15m
4h 层 → entries: True/False → forward-fill 到 15m
15m 层 → entries: True/False
→ AND/OR 组合所有 True/False → 最终信号
```

### 3.2 新架构

```
3d 层（结构层）→ 趋势方向(+1/-1) + 关键价格位(支撑/阻力值) → 重采样到 15m
4h 层（判断层）→ 价格区间(布林带上/中/下轨值) → 重采样到 15m
15m 层（执行层）→ 入场/出场时机信号

共振引擎：对每根 15m bar，用 s% 为每个价格位构建关注区间，
检查多层的关注区间是否重合，且当前价格是否在重合区域内
→ 共振分数 = 区间重合度 * (价格在重合区 ? 1.0 : 0.0)

最终入场 = 15m 时机信号 AND 共振分数 >= confluence_threshold AND 方向与结构层一致
```

### 3.3 三个角色的职责

| 角色 | 周期范围 | 职责 | 产出 |
|------|---------|------|------|
| structure（结构层） | 1d, 3d | 趋势方向 + 关键价格位 | 方向(+1/-1) + 支撑/阻力价格序列 |
| zone（判断层） | 1h, 4h | 价格区间参考 | 布林带/KC/DC 上下轨价格序列 |
| execution（执行层） | 15m, 30m | 入场/出场时机 | 布尔信号 + K线形态触发 |

层级规则：最少 1 层（单周期），最多 3 层。角色可从周期自动推导（>=1d → structure, >=1h → zone, <1h → execution）。

### 3.4 价格位提取逻辑

每个层的 signal_genes 中，使用以下条件类型的基因会产生价格级输出：

| 条件类型 | 价格位来源 | 示例 |
|---------|-----------|------|
| `price_above` | 指标值本身（如 EMA_200 值） | EMA 作为趋势线 |
| `price_below` | 指标值本身 | EMA 作为压力线 |
| `touch_bounce` | 指标值（BB 下轨=支撑，上轨=阻力） | BB 带接触反弹 |
| `role_reversal` | 指标值 | 支撑/阻力互换 |
| `wick_touch` | 指标值 | 影线触及 |

非价格级条件（`lt`, `gt`, `cross_above`, `eq` 等，对应 RSI/MACD 等振荡器）不提取价格位，只产生布尔信号。

### 3.5 入场/出场门槛

```
最终入场 = 执行层时机信号(15m)
          AND 共振分数 >= confluence_threshold
          AND 方向与结构层一致（Type A 必须，Type B 从 DNA 继承）

最终出场 = 执行层出场信号（不受共振限制，确保止损及时）
加仓/减仓 = 执行层信号 AND 共振分数 >= confluence_threshold * 0.8
```

`confluence_threshold` 默认 0.3，可通过进化调整（范围 0.1~0.9）。

---

## 四、共振计算完整示例

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
  3d 层 EMA200 区间：[60000*(1-0.0199), 60000*(1+0.0199)] = [58806, 61194]
  4h 层 BB下轨区间：[60500*(0.9801), 60500*(1.0199)] = [59296, 61704]
  4h 层 BB中轨区间：[60778, 63222]
  4h 层 BB上轨区间：[62234, 64766]

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
  → 若 15m 有入场信号 → 执行做多入场

价格解读：
  60300 位于 3d 支撑位区间和 4h BB 下轨区间的重叠区域
  → 3d 和 4h 两个周期的关注区间在此价格附近重合
  → 多周期共识，信号可信度较高
```

---

## 五、代码级可行性验证

**结论：可行。** 现有代码库已具备所有基础设施：

1. **价格位数据已就绪**：每个周期的 DataFrame 都已预计算 BB(`bb_upper_20_2`/`bb_middle_20_2`/`bb_lower_20_2`)、KC、DC、EMA、SMA、PSAR、ATR(`atr_14`) 等所有价格级指标
2. **提取函数已存在**：`executor.py:_get_indicator_column()` 可将任何 indicator gene 解析为 DataFrame 中的数值列
3. **跨周期对齐已有**：`resample_signals()` 可将高周期数据 forward-fill 到执行周期
4. **MTF 数据加载完整**：`load_mtf_data()` 为每个周期返回完整增强的 DataFrame
5. **缺口**：没有函数从指标中提取价格位并进行跨周期比较——这是新增的共振引擎要提供的核心能力

**关键插入点**：`executor.py:dna_to_signal_set()` 的 MTF 分支（L536-687），当前做布尔 AND/OR，需替换为价格位提取+共振评分。

---

## 六、文件修改清单

### 新文件

| 文件 | 内容 | 约行数 |
|------|------|-------|
| `core/strategy/confluence.py` | 共振引擎：PriceLevel/PriceZone/LayerOutput 数据结构 + s% 计算、区间构建、区间交集、共振评分函数 | ~180 |

### 修改文件

| 文件 | 修改内容 | 影响程度 |
|------|---------|---------|
| `core/strategy/dna.py` | 添加 LayerRole 枚举，RiskGenes 添加 proximity_atr_mult，StrategyDNA 添加 confluence_threshold；"trend" → "structure" 兼容映射 | 中 |
| `core/strategy/executor.py` | SignalSet 扩展 confluence 字段；新增 evaluate_layer_with_levels()；替换 dna_to_signal_set() MTF 分支为共振逻辑 | 大 |
| `core/backtest/engine.py` | BacktestResult 添加 confluence 诊断字段；传播共振上下文 | 小 |
| `core/strategy/validator.py` | 接受新角色；校验 confluence_threshold 和 proximity_atr_mult；非执行层放宽信号要求 | 小 |
| `core/evolution/operators.py` | mutate_add_layer 角色感知；新增 mutate_confluence_threshold()、mutate_proximity_mult()；更新 crossover() | 中 |

### 不修改文件

| 文件 | 原因 |
|------|------|
| `core/backtest/engine.py` order_func_nb | Numba 函数接口不变，共振过滤在 Python 端预计算后传入布尔数组 |
| `core/data/mtf_loader.py` | 数据加载不变，价格位是 DataFrame 中已有的指标列 |
| `core/features/indicators.py` | 指标计算不变，已有足够的价格级指标（EMA/BB/KC/DC/PSAR） |

---

## 七、向后兼容

1. **单周期策略**：`dna_to_signal_set()` 单周期分支完全不变
2. **现有 MTF 数据库记录**：`from_dict()` 将 `"trend"` 映射为 `"structure"`；缺少 `confluence_threshold` 默认 0.3；缺少 `proximity_atr_mult` 默认 1.5
3. **Numba 接口**：`order_func_nb` 签名和语义完全不变
4. **JSON 序列化**：新字段都是基础类型（float/string），不破坏 JSON
5. **旧 MTF DNA 过渡**：有 `cross_layer_logic` 但无 `confluence_threshold` 的 DNA 走旧的 AND/OR 路径，直到迁移完成

---

## 八、实施阶段

### Phase L: 数据结构与共振引擎（核心基础设施）

1. `dna.py`：添加 LayerRole 枚举 + 新字段
2. 新建 `confluence.py`：PriceLevel / LayerOutput 数据结构 + s% 计算、区间构建、共振评分函数
3. `executor.py`：SignalSet 扩展 + evaluate_layer_with_levels()
4. 单元测试 `tests/test_confluence.py`

### Phase M: 信号管线集成

5. `executor.py`：替换 dna_to_signal_set() MTF 分支为共振逻辑
6. `validator.py`：新角色 + 新参数校验
7. 集成测试 `tests/test_mtf_confluence.py`

### Phase N: 回测引擎与进化集成

8. `engine.py`：传播共振诊断信息
9. `operators.py`：角色感知的层添加 + 新变异算子 + crossover 更新
10. 进化引擎注册新算子
11. 进化测试 `tests/test_mtf_evolution.py`

### Phase O: 修复审计发现的 P0 Bug

12. BUG-1（trend exit 持续触发）：新架构中结构层不再产生 exit 信号，自然消除
13. BUG-2（mixed 无 trend 退化为做多）：新架构中结构层强制提供方向，自然消除
14. BUG-3（单 layer MTF 路径异常）：新架构中角色从周期自动推导，自然消除
15. BUG-4（load_mtf_data 降级问题）：旧 MTF DNA 走旧路径，新 MTF DNA 走共振路径

---

## 九、验证策略

### 单元测试
- s% 计算：ATR_14=800, close=60000, mult=1.5 → s%=0.02
- 价格位区间构建：P=60000, s%=0.02 → [58800, 61200]
- 层区间并集：多个价格位区间合并为连续区间
- 区间交集：两层的关注区间取重合部分
- 共振分数：完全重合→高分，部分重合→中间值，无重合→0.0
- 价格在重合区内：价格在交集内→保留分数，在交集外→分数归零
- 方向提取：structure 层 price_above→+1, price_below→-1

### 集成测试
- 单周期策略结果不变
- 2 层（zone+execution）区间重合共振门控正确
- 3 层（structure+zone+execution）完整流水线
- 不同 confluence_threshold 产生不同交易数量
- 不同 proximity_mult 改变 s% 阈值影响交易频率

### 回归测试
- 全量现有测试通过
- 旧 MTF DNA（有 cross_layer_logic）走兼容路径

---

## 十、待澄清设计项

> 以下内容用户认为尚未充分讨论或澄清，需要在实施前继续讨论确认。

（待补充 — 用户提出后在此记录讨论过程和最终决策）
