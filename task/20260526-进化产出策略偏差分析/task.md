# 进化中心产出策略偏差根因分析

> 日期: 2026-05-26
> 状态: B 实施完成，待最终校验

---

## 一、任务定义

修复进化引擎的 requirements 传递断裂问题——用户在前端表单设置的 5 维达标标准未传递到 fitness 评估函数，导致进化产出与用户预期不符。

---

## 二、现状定位

### 核心问题：requirements_json 写入但从未读取，用户配置完全无效

**断裂点 1（关键）：Runner 从旧列构建 RequirementsConfig，忽略 requirements_json**

`api/runner.py:773-776`（`_evaluate_dna`）和 `api/runner.py:866-869`（`_evaluate_population`）：
```python
req = RequirementsConfig(
    min_annual_return=task_row.get("min_annual_return", 0.10),
    max_drawdown=task_row.get("max_drawdown_limit") or 0.30,
)
```
这行代码仅从 `min_annual_return` 和 `max_drawdown_limit` 两个旧列取值。`requirements_json` 列（包含完整的 5 维配置）从未被解析和使用。

**断裂点 2：前端只传 requirements 嵌套对象，不传旧的顶层字段**

`api/routes/evolution.py:332`：`payload.min_annual_return` 使用 Pydantic 默认值 `0.10`（schema 定义 `api/schemas.py:315`）。因为前端只发送 `requirements` 对象，不发送 `min_annual_return` 顶层字段，所以旧列总是 0.10。

**断裂点 3：Runner 只使用 2 维而非 5 维**

即使旧列有值，Runner 也只取 `min_annual_return` 和 `max_drawdown`，其余 3 个维度（`min_win_rate`、`min_total_trades`、`min_profit_factor`）始终使用 RequirementsConfig 类默认值（0.40/10/1.2），不受用户配置影响。

### 附加问题

**best_fitness 列从未被写入**
- `api/runner.py:484,502,667` 的 UPDATE 语句只写 `best_score`，从不写 `best_fitness`
- `best_score` 实际存储的是 fitness 值（达标比率乘积，可 >1.0），而非旧 0-100 分
- 所有历史任务的 `best_fitness` 列均为 NULL

**qualified_count 和 champion_satisfaction 同样未写入 DB**

**min_annual_return=6.0 的解释**
- 最近任务创建于 2026-05-26T14:49:58（旧前端代码）
- 旧前端表单以小数显示（0.15），用户可能输入 "6" 以为表示 6%
- 但 6.0 = 600% 年化收益，几乎不可能达标
- 不过此值在 requirements_json 中，Runner 根本不读取，所以实际使用的是旧列的 0.10

### 因果链总结

```
用户设置 "年化收益 15%"
  → 前端 requirements.min_annual_return = 0.15
  → API 存入 requirements_json = {"min_annual_return": 0.15, ...}
  → API 存入 min_annual_return 列 = 0.10 (Pydantic 默认值)
  → Runner 从 min_annual_return 列读取 0.10
  → compute_fitness() 使用 0.10 (10%) 作为达标线
  → 进化产出策略满足 10% 即被视为"达标"
  → 用户期望 15%，实际用了 10%，产出偏差
```

**这是代码设计问题**——API 层同时维护两套字段（requirements 嵌套 + min_annual_return 顶层），但 Runner 只使用旧的顶层字段。

---

## 三、解决策略

**策略：修改 Runner 从 requirements_json 读取完整 5 维配置，废弃旧列路径**

选择此策略的原因：
1. requirements_json 已经被正确写入（`api/routes/evolution.py:304-306`）
2. 前端已经正确传递 requirements 对象
3. 只需修改 Runner 的读取端，数据流完整打通

排除的替代方案：
- 方案 B（从 requirements 提取值填充旧列）——不彻底，仍然只支持 2 维，且维护两套同步逻辑
- 方案 C（删除旧列）——破坏性太大，需要 DB 迁移且影响旧数据

修复 best_fitness 写入的同时解决此问题。

---

## 四、范围边界

### 改动文件

| 文件 | 改动内容 | 理由 |
|------|----------|------|
| `api/runner.py` | `_evaluate_dna` 和 `_evaluate_population` 中从 requirements_json 读取配置 | 修复断裂点 1 和 3 |
| `api/runner.py` | UPDATE 语句增加 best_fitness、qualified_count、champion_satisfaction 字段 | 修复附加问题 |
| `core/scoring/scorer.py` | 无改动（compute_fitness 已正确实现） | 已验证正确 |

### 不改动

| 文件/组件 | 理由 |
|-----------|------|
| 前端（AutoConfigForm/SeedConfigForm） | 已在上一轮修复，requirements 正确传递 |
| `api/routes/evolution.py` 创建端点 | requirements_json 已正确写入 |
| `api/schemas.py` | RequirementsConfigModel 已正确定义 |
| `core/evolution/engine.py` | 引擎本身无问题，选择压力基于 fitness 值 |

---

## 五、行为规格

### S1: Runner 从 requirements_json 读取完整 5 维配置 `[代码审查]`

**前置条件**：task_row 中有 `requirements_json` 列（非 NULL）
**行为**：
- 如果 `requirements_json` 存在且可解析，使用解析后的 RequirementsConfig（包含全部 5 个维度）
- 如果 `requirements_json` 不存在或解析失败，回退到从旧列 `min_annual_return`/`max_drawdown_limit` 构建 2 维 RequirementsConfig
- 回退路径的默认值保持不变：min_annual_return=0.10, max_drawdown=0.30, min_win_rate=0.40, min_total_trades=10, min_profit_factor=1.2
**后置条件**：compute_fitness() 接收到用户实际设置的 5 维阈值

### S2: best_fitness 写入 DB `[代码审查]`

**前置条件**：champion_tracker 更新了 champion 信息
**行为**：
- `evolution_task.best_fitness` 列被更新为 champion 的 fitness 值
- 与 `best_score` 同步更新（两者在同一 UPDATE 语句中）
**后置条件**：API 返回的 task 对象中 `best_fitness` 不再为 NULL

### S3: qualified_count 写入 DB `[代码审查]`

**行为**：`evolution_task.qualified_count` 列在每代评估后被更新为当前合格个体数
**后置条件**：API 返回的 task 对象中 `qualified_count` 反映实际值

### S4: 前端展示的 requirements 与进化实际使用的一致 `[集成测试]`

**行为**：用户设置"年化收益 15%"，进化中使用 0.15 作为 min_annual_return 阈值

---

## 六、风险披露

### 确定有风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| 旧任务没有 requirements_json | 回退到旧列路径，行为不变 | 回退逻辑保证兼容 |
| best_fitness 与 best_score 语义不同 | best_score 存的是 fitness 值（>1.0），best_fitness 也存 fitness 值 | 两者同源，值相同 |

### 不确定是否有风险

| 不确定项 | 影响 | 消除方式 |
|----------|------|----------|
| evolution_history 表是否有 fitness 列 | 如果没有，历史趋势图可能不显示 fitness 数据 | 检查 DB schema |

---

## 七、实施顺序

1. **修改 `_evaluate_dna` 和 `_evaluate_population` 的 requirements 读取逻辑**（runner.py）— 最高优先级，直接解决用户问题
2. **修改 UPDATE 语句添加 best_fitness/qualified_count 写入**（runner.py）— 修复数据完整性
3. **验证测试** — 确认构建通过，进化行为符合预期
