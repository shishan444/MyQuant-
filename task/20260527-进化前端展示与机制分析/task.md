# 进化前端展示与策略产出机制分析

> 日期: 2026-05-27
> 状态: A2 推理链构建完成，待用户确认

---

## 一、任务定义

梳理进化中心从"输入达标要求"到"产出达标策略"的完整链路，分析前端展示与设计方案之间的差距，给出分优先级的修复方案。

---

## 二、现状定位

### 用户视角的问题链

用户在进化中心完成一次探索，经历了这样的体验：

```
1. 配置阶段：看到"运行要求"——年化收益15%、最大回撤30%... ✓ 已修复
2. 运行阶段：进度面板显示"当前最优分"——这是什么？跟我的要求什么关系？
3. 结果阶段：图表纵轴"最优分数"、历史表"最优分"、发现策略"综合评分"
4. 用户困惑：我输入的是收益率/回撤要求，为什么看到的都是"分数"？
```

**核心矛盾**：前端配置表单已改为"运行要求"(5维达标)，但进度/结果/历史面板仍使用旧的"评分/分数"术语体系。两套概念并存导致用户无法理解进化产出的策略是否满足自己的要求。

### 问题 1：术语混乱——"评分"vs"适应度"vs"达标"

在 7 个组件中发现 **16 处旧术语**：

| 组件 | 旧术语 | 出现位置 |
|------|--------|----------|
| ProgressPanel | "当前最优分" | 行129 |
| ScoreTrendChart | "最优分数"、"平均分数" | 行57,84,286,300 |
| StrategyList | "综合评分" | 行502,525 |
| HistoryTable | "最优分" | 行29 |
| TaskDetailDrawer | "最优分数"、"评分模板"、"目标分数"、"最高分"、"平均分" | 行165,204,211,320,325 |
| Evolution.tsx | 英文 `score`、`qualified`、`fitness` | 行416-428 |

同时有新术语"适应度"、"达标"穿插其中。同一个面板内新旧术语并存，用户无法理解。

### 问题 2：5维达标详情展示链路断裂

设计方案要求展示每个维度的达标/未达标状态（满足度标记）。当前状态：

- **StrategyDetail.tsx** 已实现完整的 per-dimension satisfaction 展示（行282-318）
- **但 TaskDetailDrawer.tsx** 调用 `<StrategyDetail dna={championDna} />` 时**未传递** `champion_satisfaction`、`champion_fitness`、`champion_qualified` 参数（行245）
- 结果：达标详情组件已就绪但数据传递断裂，用户看不到"哪几个维度达标、哪几个未达标"

### 问题 3：设计方案规定的 11 个面板改动，大部分未实施

| 面板 | 设计方案要求 | 当前状态 |
|------|-------------|----------|
| 8.1 配置表单 | 删除评分模板、新增运行要求5维 | ✓ 已修复 |
| 8.2 进度面板 | StatCard 改为"最优适应度"+"达标策略" | 部分实现（术语混合） |
| 8.3 趋势图 | Y轴改为fitness刻度、达标区域填充 | 未实现（仍用score） |
| 8.4 策略详情 | 维度满足度标记替代分数 | 数据链路断裂 |
| 8.5 策略列表 | qualified圆点+适应度替代评分 | 部分实现 |
| 8.6 任务详情抽屉 | 运行要求替代评分模板 | 部分实现（回退仍显示旧字段） |
| 8.7 回测指标 | 删除评分卡片 | 未确认 |
| 8.8 策略库页面 | 全面改造 | ✓ 已实施 |
| 8.9 模拟交易警告 | qualified警告区 | 未实施 |

### 问题 3 补充：策略产出机制说明

用户不了解的策略产出机制完整链路：

```
用户创建任务 → 前端发送 requirements(5维) → API存入 requirements_json
    → Runner读取 requirements_json 构建 RequirementsConfig
    → 每个DNA个体 → BacktestEngine回测 → 得到metrics
    → compute_fitness(metrics, requirements) → 计算5维满足率乘积
    → fitness = return_ratio × drawdown_ratio × winrate_ratio × trades_ratio × pf_ratio
    → qualified = 5维全部达标(每维 actual >= required)
    → 选择压力：fitness越高越优，fitness>=1.0表示全部达标
    → 自动提取：每代结束后，qualified=True 且基因签名去重的个体 → save_strategy()
    → 前端通过WebSocket收到 strategy_discovered 通知
```

关键理解点：
- **fitness 是乘积**：一维短板会拉低整体值，不允许用强项补偿弱项
- **fitness >= 1.0 = 全部达标**：此时 qualified=True
- **策略提取条件**：仅 qualified=True 的个体会被提取到策略库
- **最新任务 qualified_count=0**：意味着整个进化过程中没有任何个体同时满足5维要求

---

## 三、解决策略

按优先级分三层修复：

### 第一层（用户体验直接改善）：术语统一 + 术语翻译

将所有"评分/分数/score"术语统一为"综合得分"（保留展示但区分于适应度），将所有英文标签（fitness/qualified/score）翻译为中文。

改动量小、风险低、直接消除用户困惑。

### 第二层（达标详情可见）：修复数据传递链路

修复 TaskDetailDrawer → StrategyDetail 的 prop 传递，让 5 维达标详情渲染出来。

同时修复 ProgressPanel 增加达标/未达标维度汇总提示。

### 第三层（设计方案对齐）：趋势图 Y 轴适配 + 达标区域填充

ScoreTrendChart 增加达标线标注、Y轴适配 fitness 刻度。此为中期任务。

---

## 四、范围边界

### 本次实施范围（第一层 + 第二层）

| 文件 | 改动内容 |
|------|----------|
| ProgressPanel.tsx | "当前最优分" → "综合得分"；确认达标术语正确 |
| ScoreTrendChart.tsx | "最优分数" → "综合得分"；"平均分数" → "平均得分"；图例同步 |
| StrategyList.tsx | "综合评分" → "综合得分" |
| HistoryTable.tsx | "最优分" → "综合得分" |
| TaskDetailDrawer.tsx | 修复 prop 传递给 StrategyDetail；"最优分数" → "综合得分"；"评分模板"回退保留但标注legacy |
| Evolution.tsx | 英文 fitness/score/qualified 翻译为中文 |

### 不在本次范围

| 内容 | 理由 |
|------|------|
| 趋势图 Y 轴适配和达标区域填充 | 设计对齐工作，需独立实施周期 |
| 回测指标面板删除评分卡片 | 需确认 Lab 页面是否受影响 |
| 模拟交易 qualified 警告 | 模拟交易模块需独立评估 |
| 组件重命名（如 ScoreTrendChart → FitnessTrendChart） | 破坏性改动，需评估影响面 |

---

## 五、行为规格

### S1: 所有面向用户的"评分/分数"术语统一为"综合得分" `[代码审查]`

- "最优分数" → "综合得分"
- "平均分数" → "平均得分"
- "综合评分" → "综合得分"
- "最优分" → "综合得分"
- "最高分" → "最高得分"
- 前置：代码中 API 字段名 `best_score` 不变（仅改显示标签）

### S2: 英文标签翻译为中文 `[代码审查]`

- Evolution.tsx 折叠摘要中 `fitness` → `适应度`
- Evolution.tsx 折叠摘要中 `score` → `得分`
- Evolution.tsx 折叠摘要中 `qualified` → `达标`

### S3: TaskDetailDrawer 传递 satisfaction/fitness/qualified 给 StrategyDetail `[代码审查]`

- 前置：task 对象已有 `champion_satisfaction`、`best_fitness`、`qualified_count` 字段
- 行为：TaskDetailDrawer 调用 StrategyDetail 时传递这些 prop
- 后置：StrategyDetail 的"达标详情"区域正常渲染

---

## 六、风险披露

| 风险 | 影响 | 缓解 |
|------|------|------|
| best_fitness 可能为 NULL（旧任务） | StrategyDetail 显示空白 | 已有 fallback 逻辑 |
| champion_satisfaction 数据可能不存在 | 达标详情区域不渲染 | StrategyDetail 内部已有条件判断 |

---

## 七、实施顺序

1. **术语统一** — 6 个文件的标签替换（低风险，高可见度）
2. **Prop 传递修复** — TaskDetailDrawer → StrategyDetail（中等风险，需验证数据格式）
3. **构建验证** — 确认前端构建通过
