# B6: 进化引擎

## 定位

`core/evolution/` 实现完整的手写遗传算法框架，自动搜索最优交易策略。核心循环: 初始化种群 -> [评价 -> 选择 -> 交叉 -> 变异 -> 多样性维护] x N 代 -> 返回 Champion。

## 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `engine.py` | 440 | 主循环 + 早停 + 自适应变异 + 模板偏置 + 种群排序暴露 |
| `operators.py` | 752 | 6 种变异 + 7 种 MTF 变异 + 交叉 + 条件生成 |
| `population.py` | 556 | 种群初始化 + 7 个经典模板 + 随机 DNA 生成 |
| `diversity.py` | 382 | 多层次多样性度量 + 适应度共享 + 新鲜血液 |
| `champion.py` | 74 | 线程安全的 Hall-of-Fame 追踪器 |
| `lineage.py` | 40 | 变异历史记录 |

## 关键链路

### 进化主循环 (EvolutionEngine.evolve, engine.py:196)

```
evolve(ancestor, evaluate_fn, on_generation, extra_ancestors, exclude_signatures,
       stop_check, evaluate_population)
  L223-229  init_population(population_size, ancestor, ...)
    ancestor 作为第一个个体
    40% 模板变异 + 40% 随机DNA + 20% 自由探索
    exclude_signatures 去重
  L231  self._population = population  (初始种群引用)
  L244  for gen in 1..max_generations:
    L246-248  强制约束 leverage/direction（每代覆盖，防止变异漂移）
    L252-257  评估: evaluate_population(batch) 或 evaluate_fn(逐个)
              scored = [(ind, score)] sorted descending
    L266-267  best_score, avg_score
    L276-281  追踪 champion 和 stagnation_count
    L284  adaptive_mut.record(best_score)

    L286-288  [关键] self._population = [ind for ind, _ in scored]
              将排序后的种群暴露给回调，确保 _population[0] 是最优个体
              修复了此前 _population 未排序导致 champion 数据错乱的 Bug

    L291  on_generation(gen, best_score, avg_score) -- 回调
    L294  EarlyStopChecker.check(best_score, gen)
      -> target_reached / stagnation(15代) / decline / max_generations

    L308-310  Elite 保留 (top elite_ratio, min 2)
    L314  Tournament selection (tournsize=3)
    L317-328  变异权重根据停滞代数调整 (3档)
    L330-344  1/5 rule 自适应变异 boost
    L347-353  模板感知偏置叠加
    L380-398  Crossover + Mutation
    L407-415  新鲜血液注入 (3-5 随机个体)
    L418-422  check_and_maintain_diversity()
    L424  self._population = population (新种群，下一代用)
    L427  population[:population_size] 截断
```

### 种群排序与 Champion 追踪（关键修复）

**问题背景**: `evolve()` 中 `scored` 列表按分数降序排序，但 `population` 变量（原始列表）从未排序。`on_generation` 回调通过 `engine._population[0]` 读取"最优个体"，但实际上拿到的是未排序列表的第一个——一个随机位置的个体。

**修复** (engine.py:286-288): 在调用 `on_generation` 之前，将排序后的 scored 列表写回 `self._population`:
```python
self._population = [ind for ind, _ in scored]
```

这保证了:
- `engine._population[0]` 就是当前代的最优个体
- runner.py 的 `on_generation` 回调能正确读取最优个体的 `_eval_diagnostics`
- ChampionTracker 原子更新的 score/metrics/dimension_scores 三者一致性
- 自动策略提取（score >= threshold）不会提取错误个体

### 交叉 (crossover, operators.py:664)

```
L676-680  entry 从 parent_a, exit 从 parent_b
L686-688  logic/risk 随机选一个 parent
L697-745  MTF layers: 对应层逐一交叉
  L723-733  每层: entry 从 la, exit 从 lb
  L734-736  logic/role 随机选
L763-765  mtf_mode/confluence/proximity 随机选
```

### 变异 (以 mutate_params 为例, operators.py:372)

```
L374  dna.to_dict() 深拷贝
L381  _pick_signal_pool: 50% base, 50% 随机层
L387-392  随机选一个有参数的 signal gene
L403-410  优先: Profile 推荐参数
L413-420  其次: Registry candidates (50%)
L423-429  最后: 多项式有界变异 (DE-style)
L432  StrategyDNA.from_dict(data) 重建
```

## 关键机制

### 多项式有界变异 (_polynomial_mutation, operators.py:341-369)

Deb & Goyal 1996 经典算子。eta=20 控制分布形状 -- 高 eta 小扰动(开发)，低 eta 大跳跃(探索)。

### 1/5 成功规则 (_AdaptiveMutationController, engine.py:92-122)

Rechenberg 自适应策略。滑动窗口(10代): success_rate > 0.3 -> boost=0.85(减变异)；< 0.15 -> boost=1.3(增变异)。

### 锦标赛选择 (engine.py:125-142)

tournsize=3，比截断选择更好保持多样性同时保持选择压力。

### 适应度共享 (diversity.py:265-296)

shared_score = raw_score / sharing_sum，邻居越多适应度打折越重。share_radius=0.3。

### 变异权重动态调整

| 停滞代数 | params | indicator | logic | risk | add | remove | 特点 |
|----------|--------|-----------|-------|------|-----|--------|------|
| <=4 | 35 | 10 | 10 | 25 | 10 | 10 | 参数微调+风控 |
| 5-8 | 25 | 20 | 15 | 20 | 10 | 10 | 均衡 |
| >8 | 15 | 30 | 10 | 15 | 20 | 10 | 指标替换+加信号 |

### 模板感知变异偏置 (engine.py:146-159)

在停滞权重之上叠加模板偏置。不同模板对 params/indicator/risk 三类变异有不同倾向:

| 模板 | params | indicator | risk | 设计意图 |
|------|--------|-----------|------|---------|
| explorer | 1.5x | 1.2x | 0.5x | 收益优先 -> 多调参数/指标，少调风控 |
| optimizer | 1.0x | 1.0x | 1.0x | 均衡 -> 无偏 |
| max_return | 1.8x | 1.5x | 0.3x | 极致收益 -> 大量探索指标和参数 |

叠加方式 (engine.py:347-353): 乘法叠加后重新归一化，不影响总变异概率。

### MTF 变异算子 (7 种)

| 算子 | 权重 | 说明 |
|------|------|------|
| add_layer | 5 | 添加 MTF 层 |
| remove_layer | 3 | 移除非执行层 |
| layer_timeframe | 3 | 修改层时间框架 |
| cross_logic | 10 | 翻转跨层逻辑 |
| mtf_mode | 3 | 切换 MTF 模式 |
| confluence_threshold | 3 | 共振阈值变异 |
| proximity_mult | 3 | 邻近倍数变异 |

## 接口定义

| 函数 | 说明 |
|------|------|
| `EvolutionEngine.evolve(ancestor, evaluate_fn, ..., evaluate_population=None) -> Dict` | **主入口**，支持逐个或批量评估 |
| `EarlyStopChecker.check(best, gen) -> (action, reason)` | 早停检查 |
| `mutate_params(dna) -> StrategyDNA` | 参数变异 |
| `mutate_indicator(dna) -> StrategyDNA` | 同类指标替换 |
| `mutate_logic(dna) -> StrategyDNA` | AND/OR 翻转 |
| `mutate_risk(dna) -> StrategyDNA` | 风控微调（含方向变异，但会被引擎强制覆盖）|
| `mutate_add_signal(dna) -> StrategyDNA` | 添加 guard |
| `mutate_remove_signal(dna) -> StrategyDNA` | 移除 guard |
| `crossover(parent_a, parent_b) -> StrategyDNA` | 功能分区交叉 |
| `init_population(size, ancestor, ...) -> List[StrategyDNA]` | 种群初始化 |
| `create_random_dna(timeframe, ...) -> StrategyDNA` | 随机 DNA |
| `compute_diversity(population) -> float` | 基因型多样性 |
| `check_and_maintain_diversity(pop, ...) -> List[StrategyDNA]` | 多样性维护 |
| `ChampionTracker.update(score, metrics, dimension_scores) -> bool` | 原子更新冠军 |

## 关键参数

| 参数 | 默认值 | 设计意图 |
|------|--------|---------|
| population_size | 15 | 平衡探索广度与计算成本 |
| max_generations | 200 | 硬上限 |
| patience | 15 | 连续15代无改善早停 |
| elite_ratio | 0.15 | 精英保留（至少2个）|
| target_score | 80.0 | 达标后早停 |
| min_generations | 20 | 最少运行代数 |

## 约定与规则

- **变异返回新实例**: to_dict() -> 修改 -> from_dict()，永不修改原对象
- **metadata 更新**: strategy_id(新UUID), parent_ids([原id]), mutation_ops(追加), generation(+1)
- **只移除 guard**: mutate_remove_signal 不移除 trigger，保护 entry/exit 能力
- **50/50 层分配**: _pick_signal_pool 在 base 和 MTF 层间均匀分配
- **ChampionTracker 线程安全**: threading.Lock + copy.deepcopy，score/metrics/dimension_scores 原子更新
- **种群去重**: exclude_signatures 支持跨批次多样性
- **direction 强制覆盖**: engine.py:248 每代覆盖 ind.direction = self.direction，即使 mutate_risk 变异了方向也会被还原。这不是 Bug，而是设计意图——任务级方向约束不应被个体变异打破
- **batch 评估优先**: 当 `evaluate_population` 不为 None 时，整个种群一次性评估（通过 BacktestEngine.batch_run），比逐个评估快数倍
