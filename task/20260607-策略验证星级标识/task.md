# 策略验证星级标识方案

## 任务目标
为验证后的策略设计 1-5 星评级标识，在策略库中一眼辨别策略价值。需考虑多次验证产生不同评分的聚合方案。

---

## 阶段 A 研究循环

### A1. 结构性理解

#### 当前评分体系（代码证据）

**fitness 计算** (`core/scoring/scorer.py:35-111`)
- objective = sharpe (默认)，fitness = max(0, sharpe_ratio)
- 硬约束门控：max_drawdown <= 30%, trades >= 10, profit_factor >= 1.2
- 任何约束失败 → fitness=0, qualified=False

**comprehensive_score 计算** (`api/routes/strategies.py:834-840`)
```
comprehensive_score = avg_fitness × qualified_ratio × consistency_bonus
```
- avg_fitness: 各周期 fitness 算术平均 (0~5，典型 sharpe 范围)
- qualified_ratio: 达标周期占比 (0~1)
- consistency_bonus: 全部达标 1.2，否则 1.0
- 实际值域：[0, 6]（sharpe 模式下）

**数据库存储** (`api/db_ext.py:149-154`)
- verify_count: INTEGER DEFAULT 0 — 验证次数
- verify_avg_score: REAL — 历次 comprehensive_score 的加权平均
- verify_best_score: REAL — 历次最高 comprehensive_score
- last_verified_at: TEXT

**更新逻辑** (`api/routes/strategies.py:549-577`)
- 原子 SQL：increment count + running average + max(best)
- 每次验证写入一次

**前端展示** (`web/src/pages/Strategies.tsx:429-437`)
- 验证 badge：`验证x{count} {avg_score}`
- 颜色三档：avg_score > 0.6 绿色，> 0.3 蓝色，其余灰色
- 无星级概念

#### 关键数据流
```
验证请求 → 按 group×range 回测 → compute_fitness(per period)
  → comprehensive_score(avg_fitness × qualified_ratio × consistency_bonus)
  → _update_strategy_verify_fields(SQL 原子更新 count/avg/best)
  → 前端 Strategies badge 展示
```

### A2. 推理链（v2 — 经产品设计审视后修正）

#### 1. 任务定义
在策略验证系统中引入 1-5 星绝对评级机制，将验证结果映射为直观的星级标识，写入数据库并在策略库页面以星级图标展示。星级采用绝对评价（不按百分位），只存最新星级。

#### 2. 现状定位

**现状**：验证评分只有数值型 comprehensive_score，用户在策略库看到 `验证x3 0.45` 这样的文字，需要理解数值含义才能判断策略质量。没有直观的"好/中/差"视觉信号。

**关键点**（代码设计问题）：
- Strategies.tsx:429-437 的 badge 只有文字和三档颜色，区分度不足
- comprehensive_score 的值域 [0, 6] 对用户不直观（sharpe=0.8 是好还是差？）
- 多次验证的 verify_avg_score 是加权平均，但展示时无法看出一致性

#### 3. 解决策略

**星级前提：全区间达标**。用户定义"1星=所有区间有正向收益"，所以星级的前提是 `qualified_count == total_periods`。非全达标策略不展示星级，保留原有文字 badge。

**星级映射**（全达标前提下，按 avg_fitness 绝对阈值分档）：

| 星级 | 含义 | 条件 | 阈值依据 |
|------|------|------|----------|
| 5★ | 全周期卓越 | 全达标 + avg_fitness ≥ 2.0 | Sharpe≥2.0 量化交易公认"优秀" |
| 4★ | 全周期优秀 | 全达标 + avg_fitness ≥ 1.2 | Sharpe≥1.2 "良好偏上" |
| 3★ | 全周期良好 | 全达标 + avg_fitness ≥ 0.8 | Sharpe≥0.8 "还行" |
| 2★ | 全周期合格 | 全达标 + avg_fitness ≥ 0.5 | Sharpe≥0.5 勉强可用 |
| 1★ | 全周期达标 | 全达标 + avg_fitness > 0 | 通过全部硬约束，最低正 fitness |
| 无星 | 未验证 / 非全达标 | — | 不展示星级，保留文字 badge |

**多次验证聚合**：只存最新星级（verify_star），不存最低/最高。
- 星级反映策略当前市场适应性
- 验证次数表达可靠程度
- 展示格式：`★★★★☆ ×3`
- 排除取最低：不同验证条件不可比，取最低惩罚探索行为
- 排除取平均：星级是离散分档，平均无意义

**排除方案**：
- ❌ 基于纯收益率的星级：不考虑风险
- ❌ 百分位排序：策略数量少，百分位不稳定
- ❌ 不存储直接计算：策略库需要持久化标识

#### 4. 范围边界

**改动文件**：
- `api/routes/strategies.py` — 星级计算函数 + 写入逻辑
- `api/db_ext.py` — 新增 verify_star 列 + migration
- `api/schemas.py` — StrategyResponse 新增字段
- `web/src/types/api.ts` — Strategy 接口新增字段
- `web/src/pages/Strategies.tsx` — 星级展示
- `web/src/pages/Verify.tsx` — 验证结果中展示星级

**排除**：
- 不修改评分核心 (`core/scoring/scorer.py`)
- 不修改 verify session 表
- 不修改前端验证详情页的 comprehensive_score 数值展示

#### 5. 行为规格

**BS-1**: 星级计算函数 `compute_verify_star(avg_fitness, qualified_count, total_periods) -> int`
- 输入：avg_fitness (float), qualified_count (int), total_periods (int)
- 输出：0-5 整数（0=无星级）
- 规则：全达标前提 + avg_fitness 阈值映射；非全达标返回 0
- 验证：`[测试验证]`

**BS-2**: 数据库 migration 新增一列
- verify_star INTEGER DEFAULT NULL
- 幂等 ALTER TABLE
- 验证：`[代码审查]`

**BS-3**: 验证完成后写入星级
- 在 _update_strategy_verify_fields 中，同步更新 verify_star
- verify_star = 本次计算的星级
- 验证：`[测试验证]`

**BS-4**: StrategyResponse 返回星级字段
- verify_star: Optional[int] = None
- 验证：`[代码审查]`

**BS-5**: 前端策略库星级展示
- 全达标策略：显示星级图标 + 验证次数 `★★★★☆ ×3`
- 非全达标但有验证：保留现有 `验证x{count} {score}` badge
- 颜色：5★ 金色 amber，3-4★ 蓝色，1-2★ 灰色
- verify_count=0 时不展示任何验证标识
- 验证：`[代码审查]`

**BS-6**: 验证结果页面星级展示
- 每个 StrategyCard 的评分区域显示星级
- 全达标策略显示星星，非全达标不显示
- 验证：`[代码审查]`

**不变量**：
- verify_star 只在验证完成时写入
- 非全达标策略 verify_star = 0（不展示星级）
- comprehensive_score=0 时 verify_star=0

#### 6. 风险披露

**确定风险**：
- R1: 阈值标定偏差 — 实际分布未知，可能集中在某几档。缓解：上线后观察分布再微调。

**不确定风险**：
- U1: 全达标前提是否过严 — 验证默认用严格约束（回撤<30%/盈亏比>1.2/交易≥10），全达标可能筛选率过高导致大部分策略无星级。缓解：先上线观察比例，如果<10%策略能获星级则考虑放宽前提条件。

#### 7. 实施顺序

1. **T1**: 星级计算函数 `compute_verify_star` + 单元测试（BS-1）
2. **T2**: 数据库 migration（BS-2）+ schema 更新（BS-4）
3. **T3**: 后端写入逻辑（BS-3）
4. **T4**: 前端类型定义 + 策略库星级展示（BS-5）
5. **T5**: 验证页面星级展示（BS-6）

---

## 门控状态
**已冻结** — 用户于 2026-06-07 确认，同意绝对评价策略和修正后的阈值方案。

---

## 阶段 B：实施（下方由实现循环填充）
