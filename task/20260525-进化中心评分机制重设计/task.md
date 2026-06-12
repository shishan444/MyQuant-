# 进化中心评分机制重设计

## 任务定义

替换当前加权求和评分机制（score_strategy 0-100分 + 三套评分模板），改为用户配置"运行要求"驱动的 fitness 评估体系（compute_fitness 满足度乘积 + qualified 资格门控），使进化搜索方向与"让策略去运行获取收益"的目标对齐。

## 现状定位

### 问题 A：评分机制是"相对排名"而非"绝对质量判定"
- `score_strategy()` 输出 0-100 分，用于种群内相对比较，不回答"策略值不值得运行"
- `engine.py:240`：champion_score 初始 -1.0，任何正分数策略都能成为冠军
- 负收益策略可以因 Sharpe 高得分 66.5 成为冠军
- 胜率不参与评分维度

### 问题 B：评分维度与目标不对齐
- 权重硬编码在 templates.py，用户无法调整
- 归一化函数给亏损策略基础分（annual_return=0 时有 10 分，normalizer.py:11-19）
- 只有 optimizer 模板有硬约束

### 问题 C：进化产出无质量门控
- trading.py:73-102：模拟交易启动不检查策略质量
- WS 推送所有 champion，不区分是否达标
- score_template 在 paper_trading_task 中存储但从未使用

## 解决策略

### 核心设计：要求驱动评估

用用户输入的要求（收益率/回撤/胜率等）同时服务两个角色：
1. 计算 fitness（连续梯度信号，满足度乘积 0+，>=1.0 表示全部达标）
2. 判定 qualified（硬性门槛，决定策略能否展示和运行）

### fitness 计算：满足度乘积

对每个要求维度计算 ratio（0 到 1+），fitness = 所有 ratio 的乘积。
乘积惩罚短板，fitness >= 1.0 等价于全部达标。

### 资格门控：qualified 布尔判定

所有维度都达标才 qualified。进化引擎用 fitness 引导搜索，展示和运行用 qualified 做门控。

## 范围边界

### 改动文件

**核心层（重写）：**
- `core/scoring/scorer.py`：score_strategy → compute_fitness
- `core/scoring/templates.py`：删除
- `core/scoring/normalizer.py`：删除
- `core/scoring/metrics.py`：保留不变

**进化引擎（适配）：**
- `core/evolution/engine.py`：score → fitness，TEMPLATE_MUTATION_BIAS → satisfaction 驱动

**API 层（字段替换）：**
- `api/runner.py`：评分调用替换 + qualified 逻辑
- `api/schemas.py`：ScoreTemplate → RequirementsConfig，best_score → best_fitness
- `api/routes/evolution.py`：参数接收替换
- `api/routes/strategies.py`：回测评分替换
- `api/routes/trading.py`：删除 score_template，加 qualified 检查

**DB 迁移：**
- 新增 migration SQL（ALTER ADD 新列，不删旧列）

**前端（UI 变更）：**
- `web/src/components/evolution/AutoConfigForm.tsx`：requirements 替换 score_template
- `web/src/components/evolution/SeedConfigForm.tsx`：同上
- `web/src/components/evolution/ProgressPanel.tsx`：best_score → best_fitness + qualified_count
- `web/src/components/evolution/ScoreTrendChart.tsx`：Y轴适配 + fitness=1.0 达标线
- `web/src/components/evolution/StrategyList.tsx`：qualified 徽章
- `web/src/components/evolution/StrategyDetail.tsx`：dimension_scores → satisfaction
- `web/src/components/evolution/HistoryTable.tsx`：best_score → best_fitness
- `web/src/components/evolution/TaskDetailDrawer.tsx`：score_template → requirements 展示
- `web/src/components/evolution/BacktestDrawer.tsx`：total_score → fitness
- `web/src/components/lab/BacktestMetricsPanel.tsx`：删除 total_score 展示
- `web/src/components/trading/CreateTaskDialog.tsx`：qualified 警告
- `web/src/pages/Strategies.tsx`：qualified 徽章
- 新建 `web/src/components/evolution/RequirementsPanel.tsx`
- 新建 `web/src/components/evolution/SatisfactionBreakdown.tsx`

**测试（更新）：**
- 更新所有使用 score_strategy / ScoreTemplate 的测试
- 新增 compute_fitness 单元测试
- 新增 qualified 门控集成测试

### 不改动的文件
- `core/strategy/` — 不涉及评分
- `core/backtest/engine.py` — 只消费 metrics，不涉及评分
- `core/trading/` — 模拟交易逻辑不变，只在 API 入口加门控
- `core/evolution/operators.py` — 进化算子不依赖评分具体含义
- `core/evolution/population.py` — 种群创建不涉及评分
- `core/evolution/champion.py` — 接口不变（compare score/fitness）

## 行为规格

### BS-1: compute_fitness 输出结构 `[测试验证]`
- 输入：metrics dict + requirements config
- 输出：{"fitness": float, "qualified": bool, "satisfaction": dict}
- 不变量：fitness >= 0，qualified=True 当且仅当所有维度 ratio >= 1.0
- 边界：metrics 为空 → fitness=0, qualified=False
- 边界：requirements 某维度为 0 → 对应 ratio 按 1.0 处理（不参与约束）

### BS-2: fitness 乘积计算正确性 `[测试验证]`
- 前置：annual_return=0.20, required=0.15 → return_ratio=1.333
- 前置：max_drawdown=0.25, required=0.30 → drawdown_ratio=1.2
- 前置：win_rate=0.45, required=0.40 → winrate_ratio=1.125
- 前置：total_trades=15, required=10 → trades_ratio=1.5
- 前置：profit_factor=1.5, required=1.2 → pf_ratio=1.25
- 契约：fitness = 1.333 * 1.2 * 1.125 * 1.5 * 1.25 ≈ 3.375
- 不变量：任一维度 ratio=0 则 fitness=0

### BS-3: qualified 判定正确性 `[测试验证]`
- 前置：所有维度达标 → qualified=True
- 前置：任一维度不达标 → qualified=False
- 边界：某维度恰好等于要求 → qualified=True（>= 关系）

### BS-4: 进化引擎 fitness 兼容性 `[测试验证]`
- 前置：engine.py 使用 fitness 排序、选择、精英保留
- 契约：fitness 越大越优，与当前 score 语义一致
- 不变量：engine.py 的选择、精英、锦标赛、早停逻辑行为不变（只替换数值来源）

### BS-5: strategy 提取使用 qualified 替代 strategy_threshold `[测试验证]`
- 前置：进化过程中自动提取策略
- 契约：只有 qualified=True 的策略才保存到 strategy 表
- 边界：qualified=False 但 fitness 很高的策略不提取

### BS-6: 模拟交易 qualified 门控 `[测试验证]`
- 前置：用户尝试用 qualified=False 的策略启动模拟交易
- 契约：API 返回警告但不阻止（前端展示警告，用户确认后可继续）
- 边界：旧策略 qualified=NULL 视为未评估，不警告

### BS-7: 回测面板不展示 fitness `[代码审查]`
- 前置：策略实验室执行回测（无 requirements 配置）
- 契约：BacktestMetricsPanel 只展示 raw metrics，不展示 fitness/qualified
- 理由：fitness 需要用户配置的 requirements 做基准，回测时无此基准

### BS-8: 前端 RequirementsPanel 配置 `[代码审查]`
- 前置：用户创建进化任务
- 契约：表单展示 5 个 requirements 输入项（收益/回撤/胜率/交易次数/盈亏比），每项有默认值
- 不变量：收益和回撤两项必填，不配置不让运行

### BS-9: ScoreTrendChart 适配 fitness 刻度 `[代码审查]`
- 前置：进化进行中
- 契约：Y 轴范围自适应，fitness=1.0 处有达标参考线，达标区域绿色底色
- 不变量：fitness 无上界时图表自动扩展 Y 轴

### BS-10: DB 迁移向后兼容 `[测试验证]`
- 前置：已有 evolution_task 记录包含 score_template 和 best_score
- 契约：ALTER ADD 新列，不删旧列，旧数据可读
- 不变量：旧任务的 best_score 值保留，前端根据 requirements_json 是否存在判断新旧格式

## 风险披露

### R1：fitness 乘积可能导致梯度消失
- 影响：某维度 ratio 为 0 时 fitness=0，进化无法区分"差一点"和"差很多"
- 缓解：ratio 不为负，最小值为 0；但收益为负时 return_ratio=0，fitness=0
- 消除方式：对 return_ratio 做特殊处理——收益为负时使用线性惩罚而非直接归零

### R2：默认 requirements 门槛过高/过低
- 影响：过高 → 进化 200 代无一达标，用户体验差；过低 → 所有策略都达标，门控形同虚设
- 缓解：先观察几轮进化的达标率再调整默认值

### R3：前端改动量大
- 影响：14 个文件修改（12 组件 + constants + api.ts），不新建独立组件
- 缓解：前端变更集中在字段名替换和展示逻辑，AutoConfigForm 是唯一需要布局重组的大改组件

## 实施顺序

### Step 1: 核心评分重写
- 重写 scorer.py → compute_fitness()
- 删除 templates.py, normalizer.py
- 更新 metrics.py 的导入路径（如需要）
- 对应规格：BS-1, BS-2, BS-3
- 依赖：无

### Step 2: 进化引擎适配
- engine.py: score → fitness, target_score → target_fitness
- _TEMPLATE_MUTATION_BIAS → satisfaction 驱动变异
- 对应规格：BS-4
- 依赖：Step 1

### Step 3: API Schema 更新
- schemas.py: ScoreTemplate → RequirementsConfig, best_score → best_fitness 等
- 对应规格：BS-8（Schema 侧）
- 依赖：Step 1

### Step 4: API Runner 更新
- runner.py: 评分调用替换 + qualified 逻辑 + strategy 提取改用 qualified
- 对应规格：BS-5
- 依赖：Step 1, Step 3

### Step 5: API Routes 更新
- evolution.py: 参数接收替换
- strategies.py: 回测评分处理
- trading.py: 删除 score_template, 加 qualified 检查
- 对应规格：BS-6, BS-7
- 依赖：Step 3, Step 4

### Step 6: DB 迁移
- 新增 migration SQL
- 对应规格：BS-10
- 依赖：Step 3

### Step 7: 前端修改
- AutoConfigForm: 删除 3 字段，新增 5 字段 requirements，布局重组
- SeedConfigForm: 同上
- ProgressPanel: StatCard 值替换 best_score→best_fitness, target_score→qualified_count
- ScoreTrendChart: Y 轴适配, targetScore 线→达标线(1.0), 达标区域填充, 文字更新
- StrategyDetail: MetricItem 满足度标记替代维度分数, 删除 Calmar, 顶部 fitness+qualified
- StrategyList: qualified 圆点, 展开面板 评分→适应度
- TaskDetailDrawer: 概览页字段替换, CurveTab 统计卡替换
- BacktestMetricsPanel: 删除 "评分" 卡片
- BacktestDrawer: 内置 MetricsPanel 同步
- CreateTaskDialog: qualified 警告区(条件显示)
- **Strategies 页面（全面改造）**:
  - 列布局重设计: 删除夏普列, 新增盈亏比/交易数/复选框/状态列
  - 行展开详情面板: 三栏(策略信息/回测指标/DNA结构+操作), 从已有字段提取
  - 批量选择+操作栏: 复选框+批量删除/批量对比/取消选择
  - 批量对比面板: 新建 StrategyComparePanel.tsx, 调用已有 compare API
  - qualified 标记: 行内圆点+名称列Badge+达标行左侧绿线
  - 过滤排序增强: 达标状态过滤, 列排序切换, 默认排序改为 best_fitness DESC
- constants.ts: 删除 OPTIMIZE_TARGETS, 新增 REQUIREMENTS_DEFAULTS
- api.ts: 类型定义更新
- evolutionChart.ts: dataKey 更新
- useEvolution.ts: WS 消息字段映射更新
- 对应规格：BS-7, BS-8, BS-9
- 依赖：Step 5, Step 6

### Step 8: 测试更新
- 更新所有使用旧评分接口的测试
- 新增 compute_fitness / qualified 测试
- 对应规格：所有 BS
- 依赖：Step 1-7
