# 进化评定机制重构 — 推理链

> 状态：门控待确认

---

## 1. 任务定义

将策略评定机制从"五维平等乘积"模型重构为"单目标函数 + 约束条件"模型，使进化选择压力忠实对齐用户意图。

---

## 2. 现状定位

**2.1 核心设计缺陷（设计问题，非 bug）**

`compute_fitness`（scorer.py:27-124）采用五维 ratio 乘积：
```python
fitness = return_ratio * drawdown_ratio * winrate_ratio * trades_ratio * pf_ratio
```

用户设置高收益目标（如 min_annual_return=6.0）时，return_ratio 被压缩到 [0, ~1] 区间，而其他维度 ratio 可达 3-5。乘积模型下，不满足收益目标的策略（return_ratio < 1）可以因其他维度超标获得更高 fitness，导致进化选择压力偏离用户意图。

证据：scorer.py:113（乘积计算）、scorer.py:64（return_ratio = actual/required）

**2.2 无法触发策略的处理缺陷（代码问题）**

单条路径（runner.py:853-856）给零交易策略 score=5.0，高于正常 fitness 范围（多数策略 fitness 0-3），导致无法触发的策略排名高于达标策略。

批量路径（runner.py:960-983）无零交易检查，所有策略都走完回测后才由 scorer.py:47 返回 fitness=0。

**2.3 胜率和交易次数不应作为评分维度（设计问题）**

- 胜率：信息已被盈利因子覆盖。30% 胜率 + 5:1 盈亏比是好策略，但被胜率维度惩罚
- 交易次数：是统计显著性的门槛条件，不是策略质量的衡量维度

**2.4 影响范围（调用链追踪结果）**

fitness 值被以下路径消费：
- 进化核心：engine.py:251 按 fitness 排序选精英 → 全部进化行为
- 自动提取：runner.py:552 qualified=True 才保存到策略表
- OOS 验证：runner.py:722 fitness 和 qualified 独立存储
- 回测 API：strategies.py:302,472 通过 score_strategy shim 消费
- WS 推送：4 种消息类型全部携带 fitness/qualified
- 前端：6 个组件消费 fitness、qualified、best_score、dimension_scores
- 多样性：diversity.py:167 用 dimension_scores 计算个体间距离
- 交易警告：trading.py:110 检查 strategy.qualified

预测模块（prediction/evolution.py:19）有独立 _compute_fitness，不受影响。

---

## 3. 解决策略

**采用"单目标函数 + 约束条件"模型：**

- **目标函数**：可配置，默认 Sharpe ratio。用户可选 annual_return、Calmar ratio 等
- **约束条件**：max_drawdown、total_trades、profit_factor 三个维度。不达标 → fitness=0
- **去掉**：win_rate 评分维度（信息已被 profit_factor 覆盖）
- **qualified**：所有约束条件满足 + 目标函数值 > 0

**为什么选这个策略：**

1. Sharpe ratio 天然平衡收益和风险，不需要把收益和回撤拆成两个独立维度再想办法组合
2. 单一目标函数给进化提供清晰的梯度，选择压力直接指向目标
3. 约束条件是"门槛"语义，达标后不再影响排序，不会和目标函数竞争选择压力
4. 可配置目标函数（Sharpe / Calmar / annual_return）满足不同场景：用户设 600% 收益 → objective=annual_return 直接以收益值作为 fitness

**排除的替代方案：**

- 加权求和（旧方案）：需要手动调权重，权重与目标值域相关，不同场景需不同权重
- Pareto 前沿：多目标进化复杂度高，种群 15 个体太小，Pareto 方法需要更大种群
- 保持乘积模型但加权重：没有解决根本问题（高目标值域压缩）

---

## 4. 范围边界

**改动文件：**

| 文件 | 改动内容 |
|------|----------|
| `core/scoring/scorer.py` | 重构 RequirementsConfig（增加 objective 字段）、重写 compute_fitness |
| `api/runner.py` | 修复零交易 score（5.0→0）、批量路径增加零交易早退、_build_requirements 适配新结构 |
| `api/schemas.py` | EvolutionTaskCreate 增加 objective 字段、RequirementsConfigModel 适配 |
| `tests/test_scoring.py` | 新增测试覆盖新 fitness 模型 |

**不改动（排除项）：**

| 文件/模块 | 排除原因 |
|-----------|----------|
| `core/evolution/engine.py` | 不改。engine 消费 fitness float 值，不关心计算方式 |
| `core/evolution/champion.py` | 不改。ChampionRecord.score 就是 fitness，字段语义不变 |
| `core/evolution/diversity.py` | 不改。dimension_scores 仍然从 satisfaction 中计算，新模型保留 satisfaction |
| `core/prediction/` | 不改。独立的 _compute_fitness，与主评分无关 |
| `api/routes/strategies.py` | 不改。通过 score_strategy shim 间接消费，shim 内部适配 |
| `api/routes/evolution.py` | 不改。透传 fitness/qualified 字段，结构不变 |
| `api/routes/trading.py` | 不改。qualified 判定语义不变 |
| `api/db_ext.py` | 不改。DB 字段不变 |
| `core/scoring/normalizer.py` | 不改。已废弃，不动 |
| `core/scoring/templates.py` | 不改。已废弃，不动 |
| `score_strategy` shim | 不改接口。内部适配新 compute_fitness 返回结构 |
| 前端 TSX | 本次不改。fitness/qualified 字段名和语义不变，前端无需感知内部计算模型变化 |

---

## 5. 行为规格

### 5.1 RequirementsConfig 新增 objective 字段

```
RequirementsConfig:
  objective: str = "sharpe"  # "sharpe" | "calmar" | "annual_return"
  max_drawdown: float = 0.30
  min_total_trades: int = 10
  min_profit_factor: float = 1.2
  # 保留但可选（向后兼容）
  min_annual_return: float = 0.15  # 作为约束条件（当 objective != "annual_return" 时）
  min_win_rate: float = 0.0  # 默认关闭，保留接口兼容
```

前置条件：objective 值必须在 {"sharpe", "calmar", "annual_return"} 中
后置条件：RequirementsConfig 实例可被 compute_fitness 消费

[代码审查]

### 5.2 compute_fitness 新计算模型

输入：metrics dict（来自回测），requirements（RequirementsConfig），liquidated bool
输出：dict { fitness: float, qualified: bool, satisfaction: dict, raw_metrics: dict, objective_name: str, objective_value: float }

计算逻辑：
1. 零交易或被强平 → 返回 fitness=0, qualified=False
2. 约束检查：
   - max_drawdown 约束：abs(actual_drawdown) > requirements.max_drawdown → fitness=0
   - total_trades 约束：actual_trades < requirements.min_total_trades → fitness=0
   - profit_factor 约束：actual_pf < requirements.min_profit_factor → fitness=0
   - annual_return 约束（当 min_annual_return > 0）：actual_return < requirements.min_annual_return → fitness=0
3. 目标函数计算：
   - objective="sharpe" → fitness = metrics["sharpe_ratio"]（已由 metrics.py 计算）
   - objective="calmar" → fitness = metrics["calmar_ratio"]（已由 metrics.py 计算）
   - objective="annual_return" → fitness = metrics["annual_return"]
4. fitness < 0 → fitness = 0（Sharpe 可以为负，钳位到 0）
5. qualified = 约束全部通过 AND fitness > 0
6. satisfaction dict 仍然计算各维度的 ratio（用于 dimension_scores 和 diversity），但不参与 fitness 计算

不变量：
- fitness >= 0（非负）
- qualified=True 蕴含 fitness > 0
- 约束不达标时 fitness = 0（不是负数或极小正数）

边界：
- metrics 中缺少目标字段（如 sharpe_ratio 为 0）→ fitness=0
- 全部约束恰好达标 + 目标函数恰好 > 0 → qualified=True, fitness = 目标值

[测试验证]

### 5.3 进化选择压力验证

当用户设 objective="annual_return"，min_annual_return=6.0（600%）：

策略 A：annual_return=3.0, drawdown=0.25, trades=30, pf=1.8
- 约束检查：drawdown 0.25 <= 0.30 ✓, trades 30 >= 10 ✓, pf 1.8 >= 1.2 ✓, return 3.0 < 6.0 ✗
- fitness = 0（return 约束不达标）

策略 B：annual_return=6.0, drawdown=0.25, trades=30, pf=1.8
- 约束检查：全部通过 ✓
- fitness = 6.0（目标函数值）

策略 C：annual_return=8.0, drawdown=0.35, trades=30, pf=1.8
- 约束检查：drawdown 0.35 > 0.30 ✗
- fitness = 0（drawdown 约束不达标）

结果：策略 B 排名最高，策略 A 和 C 都被淘汰。进化选择压力正确指向"满足所有约束且收益最高的策略"。

[测试验证]

### 5.4 零交易策略处理修复

单条路径（_evaluate_dna）：
- entries.sum() == 0 → diagnostics["score"] = 0.0（不是 5.0）

批量路径（_evaluate_population）：
- 在 batch_run 之前检查每个个体的 signal
- 或者在 compute_fitness 的零交易路径处理（已有 scorer.py:47）

不变量：零交易策略 fitness = 0, qualified = False

[测试验证]

### 5.5 score_strategy shim 向后兼容

score_strategy（scorer.py:163）继续被 strategies.py 回测 API 调用。
- 内部使用新 compute_fitness
- legacy_score 映射：fitness 值范围从乘积模型变为 Sharpe/Calmar/annual_return
  - sharpe 场景下 fitness 范围约 0-5，用 `min(100, fitness * 20)` 映射到 0-100
  - annual_return 场景下 fitness 范围约 0-10，用 `min(100, fitness * 10)` 映射
  - calmar 场景下 fitness 范围约 0-5，用 `min(100, fitness * 20)` 映射
- total_score、dimension_scores 字段继续返回，保持 API 契约不变

[代码审查]

### 5.6 satisfaction 和 dimension_scores 保留

新 compute_fitness 仍然计算各维度的 satisfaction dict（ratio 值），用于：
- diversity.py:167 的 equity_distance 计算
- 前端 StrategyDetail.tsx 的维度条形图
- DB 中 champion_dimension_scores 存储

satisfaction 计算方式不变（ratio = actual / required），但不参与 fitness 计算。

[代码审查]

### 5.7 EarlyStopChecker 适配

target_score 默认值从 1.0 调整为对应目标函数的合理值：
- sharpe 模式：target_score 默认 1.5（Sharpe > 1.5 是优秀策略）
- calmar 模式：target_score 默认 2.0
- annual_return 模式：target_score 使用用户设置的 min_annual_return

前端不传 target_score → runner.py 根据 objective 类型设置合理默认值。

[测试验证]

---

## 6. 风险披露

**确定有风险：**

R1. fitness 值域变化导致前端显示异常
- 影响范围：BacktestDrawer.tsx 用 >=1.0 判断颜色、Strategies.tsx 按 best_fitness 排序
- 缓解：前端颜色阈值和排序逻辑基于 fitness 值域。Sharpe 模式下 fitness 范围 0-5，当前阈值 1.0 仍然合理（Sharpe > 1.0 是良好策略）
- 但 annual_return 模式下 fitness 范围 0-10+，颜色阈值需要适配
- 本次不改前端，但需要验证现有阈值在新模型下是否仍然合理

R2. score_strategy shim 的 legacy_score 映射变化
- 影响范围：回测 API 返回的 total_score 值变化
- 缓解：回测 API 的 total_score 是信息展示字段，不驱动任何自动化决策。映射变化可接受

R3. DB 中已有策略的 best_fitness 值与新模型不兼容
- 影响范围：Strategies.tsx 按 best_fitness 排序，新旧策略混排时数值含义不同
- 缓解：已有策略数量少（开发阶段），不影响核心功能。后续可通过 migration 清理

**不确定的风险：**

U1. Sharpe ratio 在进化初期的选择压力
- 进化初期多数策略 Sharpe ≈ 0 或负数，fitness 全部为 0，锦标赛选择退化为随机
- 缓解方案：fitness 钳位到 0 后，锦标赛从 fitness=0 的种群中随机选择 → 相当于初始化阶段
- 需要在测试中验证：种群是否能在几代之后产生 fitness > 0 的个体

---

## 7. 实施顺序

按依赖关系排序：

**Step 1：重构 RequirementsConfig 和 compute_fitness**
- 文件：core/scoring/scorer.py
- 依赖：无
- 产出：新评分模型 + satisfaction 保留
- 验证：test_scoring.py 新增测试用例

**Step 2：修复零交易策略处理**
- 文件：api/runner.py（单条路径 score 5.0→0.0，批量路径增加早退）
- 依赖：Step 1（compute_fitness 已处理零交易，但 runner.py 的 fallback score 需要同步修复）
- 验证：单元测试

**Step 3：适配 _build_requirements 和 API schema**
- 文件：api/runner.py（_build_requirements 适配新 RequirementsConfig）、api/schemas.py（增加 objective 字段）
- 依赖：Step 1
- 验证：代码审查

**Step 4：适配 score_strategy shim**
- 文件：core/scoring/scorer.py（shim 内部适配）
- 依赖：Step 1
- 验证：现有 score_strategy 测试通过

**Step 5：适配 EarlyStopChecker target_score 默认值**
- 文件：api/runner.py（根据 objective 设置合理 target_score 默认值）
- 依赖：Step 3
- 验证：代码审查

**Step 6：运行全部测试验证无回归**
- 依赖：Step 1-5
- 验证：pytest tests/
