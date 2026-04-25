# B6: 进化引擎

## 定位

`core/evolution/` 实现了完整的遗传算法框架，负责策略的自动发现和优化。尽管技术栈里列了 deap，但实际代码**完全手写**——没有 deap 的 import。所有选择、交叉、变异算子都是独立实现。

## 文件职责

| 文件 | 行数 | 职责 |
|------|------|------|
| `engine.py` | 399 | 主进化循环：评估→选择→交叉→变异→早停→自适应控制 |
| `operators.py` | 671 | 6 种变异算子 + 交叉算子 + 条件生成器 + MTF 层变异 |
| `population.py` | 527 | 种群初始化、7 种经典策略模板、随机 DNA 生成 |
| `diversity.py` | 374 | 多样性度量（基因型/表型/评分距离）、适应度共享、新鲜血液注入 |
| `champion.py` | 74 | 线程安全的冠军追踪器（Hall-of-Fame 模式） |
| `lineage.py` | 40 | 变异历史记录与格式化 |
| `__init__.py` | 空 | 无导出 |

## 主循环: EvolutionEngine.evolve()

```
初始化种群 (init_population, 40/40/20 比例)
  ↓
逐代循环:
  ├─ 强制任务约束 (leverage, direction)
  ├─ 全量评估 [(ind, score), ...]
  ├─ 排序 + 记录 history
  ├─ 追踪 champion + stagnation_count
  ├─ 自适应变异记录 (1/5 rule)
  ├─ 早停检查 (4 个条件)
  │
  ├─ 精英保留: top elite_ratio (min 2)
  ├─ 锦标赛选择: tournsize=3, 选 n_children*2 个父代
  ├─ 交叉 + 变异:
  │   ├─ crossover(p1, p2) → child
  │   ├─ n_mutations 次 random.choices(mutation_pool)
  │   └─ 失败时回退到 create_random_dna
  ├─ 新鲜血液: 3-5 个随机个体
  ├─ 多样性维护: 替换重复个体
  └─ 截断到 population_size
```

### 每代种群构成

假设 population_size=15，elite_ratio=0.15：

| 组成 | 数量 | 来源 |
|------|------|------|
| 精英 | max(2, int(15*0.15)) = 2 | 上代最优，原样保留 |
| 子代 | 15 - 2 - 3 = 10 | 锦标赛选择 → 交叉 → 变异 |
| 新鲜血液 | 3 (固定预留) + 补齐 | 完全随机 DNA |

**子代产生是成对的**：从 2*n_children 个父代中，每两个做一次 crossover → mutation → 产出 1 个子代。所以 20 个父代最多产出 10 个子代。

### 任务级约束

每代评估前强制覆盖所有个体的 leverage 和 direction（"mixed" 模式除外）。这意味着即使变异算子修改了这些字段，下一轮评估时也会被覆盖回来。这是**任务级约束**——进化不能突破用户设定的杠杆/方向边界。

## 早停: EarlyStopChecker

4 个停止条件，任一满足即停：

| 条件 | 参数 | 触发时机 |
|------|------|----------|
| target_reached | target_score=80 | best_score >= target 且 gen >= min_generations |
| stagnation | patience=15 | 连续 15 代改进 < min_improvement(0.5) |
| decline | decline_limit=10 | 连续 10 代 best_score 下降 |
| max_generations | max_generations=200 | 达到最大代数 |

`target_reached` 有 `min_generations=20` 的保护——即使第一代就达到目标分，也至少跑 20 代才允许停止。

## 自适应变异: _AdaptiveMutationController

实现了 Rechenberg 的 **1/5 成功规则**：

- 滑动窗口(10 代)追踪 best_score 是否有改进
- 成功率 > 30%: mutation_boost = 0.85（减少变异强度，精细化）
- 成功率 < 15%: mutation_boost = 1.3（增加变异强度，跳出局部最优）
- 其余: boost = 1.0

boost 的实际作用是**调整变异次数的权重分布**：stuck 时偏向更多次变异，improving 时偏向更少次变异。不是直接放大变异幅度。

## 停滞自适应的变异权重

除了 1/5 rule，还有基于 `stagnation_count` 的权重表：

| 停滞程度 | mut_weights [params, indicator, logic, risk, add_signal, remove_signal] | 变异次数偏好 |
|----------|-------|------------|
| 正常 (0-4) | [35, 10, 10, 25, 10, 10] — 偏参数+风控微调 | [1:50, 2:35, 3:15] |
| 中等 (5-8) | [25, 20, 15, 20, 10, 10] — 均衡 | [1:25, 2:45, 3:30] |
| 严重 (>8) | [15, 30, 10, 15, 20, 10] — 偏指标替换 | [2:30, 3:45, 4:25] |

严重停滞时重点放在**替换指标**(30%)和**增删信号**(30%)——大刀阔斧地改变策略结构，而不是微调参数。

### 模板叠加

`_TEMPLATE_MUTATION_BIAS` 在停滞权重之上再叠加评分模板偏好：

| 模板 | params | indicator | risk |
|------|--------|-----------|------|
| profit_first / aggressive | 1.5x | 1.2x | 0.5x |
| steady / balanced | 1.0x | 1.0x | 1.0x |
| risk_first / conservative | 0.7x | 0.8x | 1.8x |

收益优先模式多调参数少动风控，风控优先反过来。

## 变异算子 (operators.py)

### 6 种基础变异

| 算子 | 作用 | 关键细节 |
|------|------|----------|
| `mutate_params` | 随机选一个信号基因的参数做微调 | 三级优先：profile 推荐 → registry candidates → 多项式有界变异 |
| `mutate_indicator` | 替换为同类指标 | `get_interchangeable()` 取同 category 的指标；guard_only 指标不能做 trigger |
| `mutate_logic` | 翻转 AND/OR | 随机选 entry_logic / exit_logic / both；支持 MTF 层 |
| `mutate_risk` | 调整风控参数 | stop_loss ±0.005*N, position_size ±0.05*N, take_profit 联动, direction 15% 概率翻转 |
| `mutate_add_signal` | 添加一个 guard 信号 | 优先补缺失的 entry_guard / exit_guard |
| `mutate_remove_signal` | 移除一个 guard 信号 | **只删 guard，不删 trigger**——保证至少有入场/出场触发 |

### MTF 专用变异

| 算子 | 作用 |
|------|------|
| `mutate_cross_logic` | 翻转层间 AND/OR |
| `mutate_add_layer` | 新增时间周期层（从候选列表中选不在已有层中的） |
| `mutate_remove_layer` | 删除非执行周期层（至少保留 1 层） |
| `mutate_layer_timeframe` | 改变非执行层的时间周期 |

MTF 变异只在 `timeframe_pool > 1` 时被加入 mutation_pool。

### _pick_signal_pool(): 变异目标选择

所有作用于信号基因的变异都通过 `_pick_signal_pool()` 选择目标：50% 概率选基础 signal_genes，50% 按层平分选某个 MTF layer 的 signal_genes。这保证 MTF 策略的各层都有机会被变异。

### 多项式有界变异 (_polynomial_mutation)

`mutate_params` 的第三级后备，实现了 Deb & Goyal (1996) 的多项式变异：

- `eta=20` 控制分布形状——高 eta 偏向小扰动（精细化），低 eta 允许大跳
- 产生靠近当前值的小变异概率高，远离当前值的大变异概率低
- 结果经过 `pdef.clamp()` 约束到合法参数范围并对齐到 step 边界

### 条件生成: generate_random_condition()

分两路：

1. **Profile 引导**（`use_profile=True`）: 查 indicator_profile 的 `recommended_conditions`，按 `follow_probability` 概率跟随推荐
2. **自由探索**: 从 registry 的 `supported_conditions` 中随机选，按条件类型生成配套字段

对每种条件类型有特定的生成逻辑——RSI 的阈值从 [25,30,35,40,60,65,70,75] 中选，lookback 的窗口从 [3,5,8,10] 中选，touch_bounce 的 proximity 从 [0.005,0.01,0.02] 中选。这些硬编码的候选值体现了领域知识。

## 交叉: crossover()

不是均匀交叉，而是**功能分区交叉**：

```
child = 入场信号(父A) + 出场信号(父B)
        logic_genes = random.choice([A, B])
        risk_genes = random.choice([A, B])
        execution_genes = A 的（子代继承父A的交易对和周期）
```

MTF 层的交叉：如果双亲都有 layers，按位置配对交叉（zip），每个对应层做同样的 entry-from-A + exit-from-B。单亲有 layers 时直接继承。

## 种群初始化 (population.py)

### 7 种经典策略模板

| 模板名 | 策略类型 | 入场触发 | 入场守卫 | 出场触发 | 出场守卫 |
|--------|----------|----------|----------|----------|----------|
| trend_ema | EMA 趋势跟随 | MACD histogram cross_above 0 | EMA(50) price_above | MACD histogram cross_below 0 | ATR(14) |
| momentum | RSI 动量 | RSI(14) < 30 | MACD histogram cross_above | RSI(14) > 70 | BB percent > 0.8 |
| mean_reversion | BB 均值回归 | BB percent < 0.0 | RSI(14) < 35 | BB percent > 0.8 | — |
| trend_breakout | BB 挤压突破 | MACD histogram cross_above | BB bandwidth < 0.02 | MACD histogram cross_below | ATR(14) |
| dual_ma_cross | 双均线交叉 | EMA(9) cross_above | EMA(21) price_above | EMA(9) cross_below | EMA(21) price_below |
| multi_tf_trend | 多周期趋势 | EMA(50) cross_above | ADX(14) > 25 | EMA(50) cross_below | ATR(14) |
| volatility | 波动率突破 | MACD histogram cross_above | BB bandwidth < 0.02 | MACD histogram cross_below | ATR(14) |

### init_population() 的 40/40/20 比例

| 比例 | 来源 | 细节 |
|------|------|------|
| 40% | 模板突变 | 从 STRATEGY_TEMPLATES 选一个模板生成种子，对种群前 3 名之一做一次随机变异 |
| 40% | Profile 引导随机 | `create_random_dna(profiled=True)`，按 indicator_profile 推荐参数和条件 |
| 20% | 自由探索 | `create_random_dna(profiled=False)`，完全随机参数和条件 |

**去重**: `exclude_signatures` 参数允许排除已有的基因签名，用于连续进化时避免重复探索。去重后不足的部分用随机个体补充（最多尝试 size*3 次）。

**验证失败回退**: 如果 `validate_dna()` 失败，回退到固定的 RSI(14) < 30 / RSI(14) > 70 简单策略。

## 多样性系统 (diversity.py)

### 三层距离度量

| 层级 | 函数 | 度量方式 |
|------|------|----------|
| 基因型 | `genotype_distance()` | 按角色分组对比 signal_genes 的指标名、参数差、条件类型 |
| 表型 | `signal_distance()` | 对比 total_trades、win_rate、annual_return、max_drawdown 的差异 |
| 评分 | `equity_distance()` | 对比 scoring 的 dimension_scores 差异 |

表型和评分距离依赖 `_eval_diagnostics` 属性（由评估阶段设置），缺失时降级到基因型距离。

### 适应度共享

`apply_fitness_sharing()` 对距离 < share_radius(0.3) 的个体做惩罚：shared_score = raw_score / sharing_sum。距离越近的个体群，有效适应度越低。

**注意**: `apply_fitness_sharing()` 在主循环 `evolve()` 中**没有被调用**。它是一个可用但未启用的机制（推断）。

### 新鲜血液与多样性维护

- `inject_fresh_blood()`: 每代注入 3-5 个完全随机的个体
- `check_and_maintain_diversity()`: 当 diversity < 0.30 或某签名占 >30% 种群时，重复个体被随机新个体替换

## 冠军追踪 (champion.py)

`ChampionTracker` 用 `threading.Lock` 保证原子更新。score、metrics、dimension_scores 作为**不可变快照** (`ChampionRecord`) 一起更新——注释说这是为了修复"best_score 和 champion_metrics 来自不同个体"的同步 bug。

分数 <= 0 的候选不会更新冠军。

## 血统追踪 (lineage.py)

轻量工具：`record_mutation()` 向 `dna.mutation_ops` 追加操作描述，`format_lineage()` 输出可读的血统链（ID + 代数 + 父代 + 变异序列）。

**注意**: 实际变异算子（operators.py）已经自行维护 `mutation_ops`，`record_mutation()` 似乎是一个未被主流程使用的辅助函数（推断）。

## 数据流

```
EvolutionEngine.evolve(ancestor, evaluate_fn)
  ↓
init_population(ancestor, extra_ancestors, ...)
  ├─ 40% 模板突变个体
  ├─ 40% Profile 引导随机个体
  └─ 20% 自由探索个体
  ↓
逐代:
  evaluate_fn(dna) → score    (由 api/runner.py 注入：回测+评分)
  ↓
_tournament_select → parents
  ↓
crossover(p1, p2) → child
random.choices(mutation_pool) → n_mutations 次变异
  ↓
inject_fresh_blood(3-5 个随机个体)
check_and_maintain_diversity(替换重复)
  ↓
next generation
  ↓
EarlyStopChecker → stop or continue
  ↓
返回 { champion, champion_score, history, stop_reason, total_generations }
```

## 涉及文件

| 文件 | 核心内容 |
|------|---------|
| `core/evolution/engine.py` | 主进化循环、早停、自适应变异、模板偏好 |
| `core/evolution/operators.py` | 6 种变异算子、交叉、条件生成、MTF 变异 |
| `core/evolution/population.py` | 种群初始化、7 种策略模板、随机 DNA 生成 |
| `core/evolution/diversity.py` | 多层距离度量、适应度共享、新鲜血液、多样性维护 |
| `core/evolution/champion.py` | 线程安全冠军追踪 |
| `core/evolution/lineage.py` | 变异历史记录 |
