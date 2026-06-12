# 进化中心功能逻辑测试验证

> 日期: 2026-05-27
> 状态: 实施完成，全量测试通过

---

## 一、任务定义

为本次迭代的 3 组改动建立测试覆盖：(1) `_build_requirements()` 从 requirements_json 读取 5 维配置的新方法，(2) 3 处 UPDATE 语句中 best_fitness 写入，(3) 前端 TaskDetailDrawer → StrategyDetail 的 prop 传递修复。

---

## 二、现状定位

### 已有测试覆盖

| 被测功能 | 已有测试 | 覆盖情况 |
|----------|----------|----------|
| `compute_fitness()` | `tests/test_scoring.py:467-587` (TestComputeFitness, 11 用例) | 完整覆盖 |
| `RequirementsConfig` | `tests/test_scoring.py:579-586` (默认值断言) | 完整 |
| `score_strategy()` | `tests/test_scoring.py:198-307` (TestScorer) | 完整 |
| 进化 DB 写入 | `tests/test_evolution_arch.py` (部分) | 未覆盖 best_fitness |
| 进化 Runner 逻辑 | `tests/test_evolution_flow.py` (集成测试) | 未覆盖 requirements 读取 |

### 未覆盖的关键功能

| 被测功能 | 测试缺口 | 风险 |
|----------|----------|------|
| `_build_requirements()` | **完全没有测试** — 新增方法，2 个调用点 | 高：核心数据通路，错误会导致进化使用错误阈值 |
| best_fitness DB 写入 | **没有测试** — 3 处 UPDATE 新增字段 | 中：字段可能为 NULL，前端无法显示 |
| requirements_json 解析边界 | **没有测试** — 畸形 JSON、部分字段、类型混合 | 高：线上旧数据可能出现各种边界 |
| 前端 StrategyDetail prop 渲染 | **没有测试** — 新增 prop 传递 | 低：prop 传递为简单赋值 |

### 代码设计问题

1. `_build_requirements()` 是 `EvolutionRunner` 的实例方法（api/runner.py:698），但测试需要 Runner 实例。Runner 初始化依赖较多（DB 连接、WS 推送等），需要隔离。
2. `compute_fitness()` 是纯函数，已有完善测试。`_build_requirements()` 的输出直接喂给 `compute_fitness()`，两者之间的数据契约已通过 RequirementsConfig 类型保证。
3. 前端测试框架为 Vitest + @testing-library/react，组件测试已有 setup 文件和 mock 基础设施。

---

## 三、解决策略

按后端 → 前端的顺序建立测试：

**策略：对 `_build_requirements()` 做单元测试（隔离 Runner 依赖），对 best_fitness 写入做集成测试（利用现有 tmp_db fixture），前端用 Vitest 组件测试验证 prop 渲染。**

选择原因：
- `_build_requirements()` 是纯逻辑方法（输入 dict，输出 RequirementsConfig），适合直接单元测试
- best_fitness 写入涉及 DB，利用已有的 tmp_db + init_db_ext fixture 可以隔离
- 前端 prop 传递修复可以用 render + screen 查询验证

排除的方案：
- 不做端到端测试（太重，需要完整进化流程）
- 不测试前端术语替换（纯 UI 标签，已在构建中验证，无逻辑风险）

---

## 四、范围边界

### 要测试的

| 测试目标 | 测试文件 | 验证方式 |
|----------|----------|----------|
| `_build_requirements()` 优先路径 | 新建 `tests/test_runner_requirements.py` | 单元测试 |
| `_build_requirements()` 回退路径 | 同上 | 单元测试 |
| `_build_requirements()` 边界条件 | 同上 | 单元测试 |
| best_fitness DB 写入 | 同上 | 集成测试 |
| StrategyDetail prop 渲染 | 新建 `web/src/test/components/StrategyDetail.test.tsx` | 组件测试 |

### 不测试的

| 不测试内容 | 理由 |
|-----------|------|
| 前端术语替换（16 处标签） | 纯 UI 字符串，无逻辑风险，构建验证已覆盖 |
| `compute_fitness()` | 已有 11 个完善测试用例 |
| Evolution.tsx 英文翻译 | 纯标签替换，无逻辑 |
| 完整进化流程 | 端到端测试太重，超出本次范围 |

---

## 五、行为规格

### S1: `_build_requirements()` 优先路径 `[测试验证]`

**前置**: task_row 包含有效的 requirements_json（字符串或 dict）
**行为**: 返回从 requirements_json 解析的 RequirementsConfig，包含全部 5 维字段
**后置**: 返回的 RequirementsConfig 字段与 requirements_json 中的值一致

用例：
- requirements_json 为 JSON 字符串 → 解析为 dict，提取 5 维
- requirements_json 为已解析的 dict → 直接使用
- requirements_json 包含部分字段 → 缺失字段使用默认值（0.15/0.30/0.40/10/1.2）

### S2: `_build_requirements()` 回退路径 `[测试验证]`

**前置**: task_row 中 requirements_json 不存在 / 为 None / 为空字符串 / JSON 畸形
**行为**: 从旧列 min_annual_return / max_drawdown_limit 构建部分 RequirementsConfig
**后置**: min_annual_return 使用旧列值（默认 0.10），max_drawdown 使用旧列值（默认 0.30），其余 3 维使用 dataclass 默认值

用例：
- requirements_json 为 None → 回退到旧列
- requirements_json 为空字符串 → 回退到旧列
- requirements_json 为畸形 JSON → 回退到旧列（不抛异常）
- 旧列 min_annual_return 也不存在 → 使用 0.10
- 旧列 max_drawdown_limit 为 0 → or 运算符回退到 0.30

### S3: best_fitness 写入 DB `[测试验证]`

**前置**: 进化任务存在且 best_fitness 为 NULL
**行为**: UPDATE 语句将 best_fitness 写入 DB
**后置**: 查询该任务的 best_fitness 列不为 NULL，值与预期一致

用例：
- 初始 best_fitness 为 NULL → UPDATE 后不为 NULL
- best_fitness 值与 champion_rec.score 一致

### S4: StrategyDetail prop 渲染 `[测试验证]`

**前置**: StrategyDetail 接收 champion_fitness / champion_qualified / champion_satisfaction prop
**行为**: 渲染对应的达标详情区域
**后置**: 页面显示适应度值、达标/未达标标记、维度满足度详情

用例：
- champion_fitness >= 1.0 → 显示绿色适应度值 + "达标" badge
- champion_fitness < 1.0 → 显示琥珀色适应度值 + "未达标" badge
- champion_satisfaction 有数据 → 显示每个维度的 actual/required/ratio/met

---

## 六、风险披露

| 风险 | 影响 | 缓解 |
|------|------|------|
| `_build_requirements()` 是 Runner 实例方法，测试需要 mock Runner | 测试复杂度增加 | 直接实例化 Runner 并 mock 不需要的依赖，或提取为静态方法 |
| 前端组件测试需要 mock framer-motion 等 UI 库 | 渲染可能失败 | 参考现有 setup.ts 的 mock 模式 |
| tmp_db fixture 的 schema 可能不包含 requirements_json 列 | 测试无法写入测试数据 | 验证 init_db_ext 是否创建该列 |

---

## 七、实施顺序

1. **验证测试基础设施** — 确认 tmp_db fixture 支持 requirements_json 列，确认 Vitest 环境正常
2. **后端单元测试 `_build_requirements()`** — S1 + S2 规格的测试用例
3. **后端集成测试 best_fitness 写入** — S3 规格
4. **前端组件测试 StrategyDetail** — S4 规格
5. **运行全量测试** — 确认新测试通过且未破坏现有测试
