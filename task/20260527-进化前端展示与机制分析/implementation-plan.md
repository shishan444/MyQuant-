# 进化前端展示修复 — 精确实施方案

> 基于 A2 推理链，逐文件逐行精确设计

---

## 实施步骤 1：术语统一（6 个文件）

### 1.1 ProgressPanel.tsx

**文件**: `web/src/components/evolution/ProgressPanel.tsx`

| 行号 | 当前值 | 改为 |
|------|--------|------|
| 129 | `label="当前最优分"` | `label="综合得分"` |

仅此一处。其余术语（"当前适应度"、"已达标"、"达标策略"）已正确。

---

### 1.2 ScoreTrendChart.tsx

**文件**: `web/src/components/evolution/ScoreTrendChart.tsx`

| 行号 | 当前值 | 改为 |
|------|--------|------|
| 57 | `最优分数: {dataPoint.bestScore.toFixed(1)}` | `综合得分: {dataPoint.bestScore.toFixed(1)}` |
| 78 | `累计最佳: {dataPoint.cumulativeBest.toFixed(1)}` | （保持不变，"累计最佳"可接受） |
| 84 | `平均分数: {dataPoint.avgScore.toFixed(1)}` | `平均得分: {dataPoint.avgScore.toFixed(1)}` |
| 286 | `最优分数` | `综合得分` |
| 300 | `平均分数` | `平均得分` |

---

### 1.3 StrategyList.tsx

**文件**: `web/src/components/evolution/StrategyList.tsx`

| 行号 | 当前值 | 改为 |
|------|--------|------|
| 502 | `综合评分:` | `综合得分:` |
| 525 | `综合评分:` | `综合得分:` |

---

### 1.4 HistoryTable.tsx

**文件**: `web/src/components/evolution/HistoryTable.tsx`

| 行号 | 当前值 | 改为 |
|------|--------|------|
| 29 | `<th ...>最优分</th>` | `<th ...>综合得分</th>` |

---

### 1.5 TaskDetailDrawer.tsx

**文件**: `web/src/components/evolution/TaskDetailDrawer.tsx`

| 行号 | 当前值 | 改为 |
|------|--------|------|
| 165 | `{ label: "最优分数"` | `{ label: "综合得分"` |
| 204 | `<Section title="评分模板">` | `<Section title="评分模板 (旧)">` |
| 318 | `最高分` | `最高得分` |
| 324 | `平均分` | `平均得分` |

说明：
- 行 204 的"评分模板"改为"评分模板 (旧)"，因为这是旧任务的回退显示，新任务不会走到这个分支（有 requirements 就显示"达标要求"）
- "目标分数"（行 211）也属于旧回退，但作为旧任务的历史信息保留原样

---

### 1.6 Evolution.tsx

**文件**: `web/src/pages/Evolution.tsx`

| 行号 | 当前值 | 改为 |
|------|--------|------|
| 418 | `fitness {currentTask.best_fitness.toFixed(3)}` | `适应度 {currentTask.best_fitness.toFixed(3)}` |
| 423 | `score {currentTask.best_score.toFixed(1)}` | `得分 {currentTask.best_score.toFixed(1)}` |
| 428 | `{currentTask.qualified_count} qualified` | `{currentTask.qualified_count} 达标` |

---

## 实施步骤 2：修复 TaskDetailDrawer → StrategyDetail prop 传递

**文件**: `web/src/components/evolution/TaskDetailDrawer.tsx`

### 当前代码（行 245）：
```tsx
<StrategyDetail dna={championDna} />
```

### 改为：
```tsx
<StrategyDetail
  dna={championDna}
  champion_metrics={task.champion_metrics}
  champion_dimension_scores={task.champion_dimension_scores}
  champion_satisfaction={task.champion_satisfaction}
  champion_fitness={task.best_fitness}
  champion_qualified={task.qualified_count != null && task.qualified_count > 0 ? true : undefined}
/>
```

说明：
- `task.champion_metrics` — EvolutionTask 类型已定义（types/api.ts:144-151）
- `task.champion_dimension_scores` — 已定义（types/api.ts:152）
- `task.champion_satisfaction` — 已定义（types/api.ts:153）
- `task.best_fitness` — 映射为 `champion_fitness` prop
- `qualified` — 根据 `qualified_count > 0` 推断（task 上没有直接的 qualified 字段，用 qualified_count > 0 作为代理）

---

## 实施步骤 3：构建验证

```bash
cd web && npx vite build
cd /mnt/d/git/aicode/everycode/MyQuant && bash scripts/restart.sh
```

---

## 总改动量统计

| 文件 | 改动数 | 改动类型 |
|------|--------|----------|
| ProgressPanel.tsx | 1 处 | 标签替换 |
| ScoreTrendChart.tsx | 4 处 | 标签替换 |
| StrategyList.tsx | 2 处 | 标签替换 |
| HistoryTable.tsx | 1 处 | 标签替换 |
| TaskDetailDrawer.tsx | 4 处 + 1 处 prop 扩展 | 标签替换 + prop 传递 |
| Evolution.tsx | 3 处 | 英文→中文翻译 |
| **合计** | **16 处** | |
