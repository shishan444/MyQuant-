# 前端 Fitness 模型适配

## 状态：实施中

## 任务定义
后端 fitness 模型已从"五维乘积"改为"单目标函数 + 硬约束"，前端需要适配三个维度：配置（新增 objective）、判定（用 qualified 替代 >= 1.0）、展示（动态颜色阈值）。

## 推理链（冻结）

### 1. 任务定义
前端适配后端新 fitness 模型，涉及 14 个文件的类型、配置表单、展示层、测试四个层次的变更。

### 2. 现状定位
- `types/api.ts:173-179` RequirementsConfig 缺少 objective 字段
- `constants.ts:240-246` REQUIREMENTS_DEFAULTS 使用旧默认值（min_annual_return=0.15, min_win_rate=0.40）
- 5 个组件硬编码 `>= 1.0` 作为达标边界：ProgressPanel:46, BacktestDrawer:301, StrategyDetail:78, StrategyList:507, TaskDetailDrawer:361
- 3 个配置表单无 objective 选择器：AutoConfigForm, SeedConfigForm, QuickPresets

### 3. 解决策略
- 达标判定：全面使用后端 qualified 布尔值
- fitness 颜色：新增 getFitnessColor 工具函数，按 objective 分档
- 图表达标线：使用 task.target_score 动态值

### 4. 范围边界
**改**：types/api.ts, constants.ts, lib/utils.ts, AutoConfigForm.tsx, SeedConfigForm.tsx, QuickPresets.tsx, ProgressPanel.tsx, ScoreTrendChart.tsx, TaskDetailDrawer.tsx, StrategyDetail.tsx, StrategyList.tsx, BacktestDrawer.tsx, pages/Strategies.tsx, test/fixtures.ts, test/StrategyDetail.test.tsx
**不改**：hooks/useEvolution.ts, services/evolution.ts, pages/Evolution.tsx（仅展示 best_fitness，逻辑不变）

### 5. 行为规格
- B1: RequirementsConfig 接口包含 objective?: string [代码审查]
- B2: REQUIREMENTS_DEFAULTS 包含 objective: "sharpe", min_annual_return: 0.0, min_win_rate: 0.0 [代码审查]
- B3: getFitnessColor(fitness, objective?, targetScore?) 返回 tailwind 颜色类名 [测试验证]
- B4: AutoConfigForm 和 SeedConfigForm 顶部新增 objective Select [代码审查]
- B5: QuickPresets 三个预设增加 objective 字段 [代码审查]
- B6: ProgressPanel reachedTarget 改为 qualified_count > 0 [代码审查]
- B7: ScoreTrendChart targetFitness 改为接收 targetScore prop [代码审查]
- B8: 5 个展示组件用 getFitnessColor 替代硬编码 >= 1.0 [代码审查]

### 6. 风险
- 旧任务无 objective → getFitnessColor 默认 "sharpe" 向后兼容
- min_win_rate 前端保留但标记为可选 [低风险]

### 7. 实施顺序
1. 类型 + 常量层（types/api.ts, constants.ts）
2. 工具函数（lib/utils.ts）
3. 配置表单（AutoConfigForm, SeedConfigForm, QuickPresets）
4. 展示层达标判定（ProgressPanel, TaskDetailDrawer, ScoreTrendChart）
5. 展示层颜色阈值（StrategyDetail, StrategyList, BacktestDrawer, Strategies.tsx）
6. 测试适配（fixtures.ts, StrategyDetail.test.tsx）
