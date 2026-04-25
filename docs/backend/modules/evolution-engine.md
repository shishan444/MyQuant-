# B6: 进化引擎

## 定位

`core/evolution/` 实现完整的手写遗传算法框架，自动搜索最优交易策略。核心循环: 初始化种群 -> [评价 -> 选择 -> 交叉 -> 变异 -> 多样性维护] x N 代 -> 返回 Champion。

## 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `engine.py` | 415 | 主循环 + 早停 + 自适应变异 + 模板偏置 |
| `operators.py` | 752 | 6 种变异 + 7 种 MTF 变异 + 交叉 + 条件生成 |
| `population.py` | 556 | 种群初始化 + 7 个经典模板 + 随机 DNA 生成 |
| `diversity.py` | 382 | 多层次多样性度量 + 适应度共享 + 新鲜血液 |
| `champion.py` | 74 | 线程安全的 Hall-of-Fame 追踪器 |
| `lineage.py` | 40 | 变异历史记录 |

## 关键链路

### 进化主循环 (EvolutionEngine.evolve, engine.py:191)

```
evolve(ancestor, evaluate_fn, on_generation, extra_ancestors, exclude_signatures)
  L211-217  init_population(population_size, ancestor, ...)
    L465-466  ancestor 作为第一个个体
    L485-527  40% 模板变异 + 40% 随机DNA + 20% 自由探索
    L530-553  exclude_signatures 去重
  L232  for gen in 1..max_generations:
    L234-238  强制约束 leverage/direction
    L241-242  scored = [(ind, evaluate_fn(ind))] sorted by score
    L269  EarlyStopChecker.check(best_score, gen)
      -> target_reached / stagnation(15代) / decline / max_generations
    L283-284  Elite 保留 (top elite_ratio, min 2)
    L288  Tournament selection (tournsize=3)
    L291-302  变异权重根据停滞代数调整
    L305-322  1/5 rule 自适应变异 boost
    L325-331  模板感知偏置叠加
    L358-376  Crossover + Mutation
    L387-393  新鲜血液注入 (3-5 随机个体)
    L396-400  check_and_maintain_diversity()
    L405  population[:population_size] 截断
```

### 交叉 (crossover, operators.py:648)

```
L660-664  entry 从 parent_a, exit 从 parent_b
L670-672  logic/risk 随机选一个 parent
L681-729  MTF layers: 对应层逐一交叉
  L707-717  每层: entry 从 la, exit 从 lb
  L718-720  logic/role 随机选
L747-749  mtf_mode/confluence/proximity 随机选
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
| `EvolutionEngine.evolve(ancestor, evaluate_fn, ...) -> Dict` | **主入口**，返回 champion/history/stop_reason |
| `EarlyStopChecker.check(best, gen) -> (action, reason)` | 早停检查 |
| `mutate_params(dna) -> StrategyDNA` | 参数变异 |
| `mutate_indicator(dna) -> StrategyDNA` | 同类指标替换 |
| `mutate_logic(dna) -> StrategyDNA` | AND/OR 翻转 |
| `mutate_risk(dna) -> StrategyDNA` | 风控微调 |
| `mutate_add_signal(dna) -> StrategyDNA` | 添加 guard |
| `mutate_remove_signal(dna) -> StrategyDNA` | 移除 guard |
| `crossover(parent_a, parent_b) -> StrategyDNA` | 功能分区交叉 |
| `init_population(size, ancestor, ...) -> List[StrategyDNA]` | 种群初始化 |
| `create_random_dna(timeframe, ...) -> StrategyDNA` | 随机 DNA |
| `compute_diversity(population) -> float` | 基因型多样性 |
| `check_and_maintain_diversity(pop, ...) -> List[StrategyDNA]` | 多样性维护 |
| `ChampionTracker.update(score, ...) -> bool` | 原子更新冠军 |

## 关键参数

| 参数 | 默认值 | 设计意图 |
|------|--------|---------|
| population_size | 15 | 平衡探索广度与计算成本 |
| max_generations | 200 | 硬上限 |
| patience | 15 | 连续15代无改善早停 |
| elite_ratio | 0.15 | 精英保留（至少2个） |
| target_score | 80.0 | 达标后早停 |
| min_generations | 20 | 最少运行代数 |

## 约定与规则

- **变异返回新实例**: to_dict() -> 修改 -> from_dict()，永不修改原对象
- **metadata 更新**: strategy_id(新UUID), parent_ids([原id]), mutation_ops(追加), generation(+1)
- **只移除 guard**: mutate_remove_signal 不移除 trigger，保护 entry/exit 能力
- **50/50 层分配**: _pick_signal_pool 在 base 和 MTF 层间均匀分配
- **ChampionTracker 线程安全**: threading.Lock + copy.deepcopy
- **种群去重**: exclude_signatures 支持跨批次多样性
