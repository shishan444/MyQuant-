# MyQuant 全栈重构优化分析

> 创建时间：2026-06-17
> 任务来源：/sdd-work「研究 MyQuant 工程，进行重构分析，分析可能存在的优化方向」
> 目标：质量更优秀的前提下，代码更简洁、视觉布局更好、交互效果更好
> 当前阶段：阶段 A 完成 / 推理链待门控确认

---

## 一、任务定义（初始理解，待用户确认）

对 MyQuant 工程进行结构性的重构分析，识别可优化方向，覆盖三个维度：
1. **代码更简洁** —— 去冗余、降复杂度、统一重复实现、提升可维护性
2. **视觉布局更好** —— 前端信息架构、空间利用、层级与留白、响应式
3. **交互效果更好** —— 操作流畅度、状态可见性（loading/error/empty/disabled）、反馈与动效

**底线约束**：交易/回测/评分逻辑的不变量不可破（未来函数、shift(1)、手续费/滑点/资金费率/杠杆/清算）。质量不得为简洁让步。

---

## 二、工程现状扫描结果

### 规模
| 分区 | 文件 | 代码行数 |
|------|------|----------|
| 后端 (api/core/data) | 109 个 .py | ~24,905 行 |
| 前端 (web/src，含测试) | — | ~26,617 行 |

### 技术栈
- **后端**：Python 3.12 + FastAPI + Uvicorn + vectorbt + pandas-ta + numba + sklearn + SQLite(WAL) + Parquet
- **前端**：React 19 + TypeScript 6 + Vite 8
  - 样式：Tailwind CSS 4（@tailwindcss/vite）
  - 组件：radix-ui + cva + clsx + tailwind-merge（shadcn/ui 体系）
  - 动效：framer-motion 12
  - 图表：lightweight-charts 5 + recharts 3
  - 数据：Zustand 5 + TanStack React Query 5 + axios
  - 表单：react-hook-form + zod
  - 其他：sonner(toast) / lucide-react(图标)

### 架构
- **后端**：分层单体 `api/ → core/ → data/persistence/`；core 按领域拆 11 个模块（strategy/backtest/features/scoring/evolution/validation/discovery/prediction/trading/persistence/visualization）
- **前端**：`pages → hooks → services → backend API`；`pages → stores/components/lib/types`；8 个页面（Lab/Evolution/Trading/Strategies/Verify/BatchBacktest/DataManagement/Settings）

### 文档完备度
- docs/backend、docs/frontend 各有 INDEX.yaml + domain + flows + crosscut，非常完整
- AI_CODING_GUIDE.md 给出明确的任务边界、读取清单、不变量、无效工作判定、验证要求

### 已观察到的初步线索（待阶段 A 验证，非结论）
1. **图表方案疑似双轨**：charts/KlineChart（疑似 lightweight-charts）与 lab/evolution/trading 下多个 *Chart 组件（疑似 recharts）并存。MAP.md 写"Plotly"，与 package.json 不符 → 文档/代码漂移
2. **组件分层较碎**：components/ 下 lab/(20+)、evolution/(12)、trading/(6)、charts/、ui/、layout/ 混排；自定义 GlassCard/StatCard/PageTransition 与 shadcn ui/ 并行
3. **成对组件**：ConditionPill/ConditionPillGroup、RuleConditionGroup/RuleConditionRow 等需核验是否可合并或抽公共逻辑
4. **多 EquityCurve 实现**：lab/EquityCurveChart.tsx 与 trading/EquityCurve.tsx 并存，需核验是否重复
5. **后端模块多**：11 个 core 领域 + api 层，是否有分层违规、API 层复制 core 逻辑、跨模块耦合需验证

---

## 三、用户的三个目标维度（待阶段 A 翻译为可验证规格）

| 维度 | 含义 | 主要落点 |
|------|------|----------|
| 质量更优秀 | 不为简洁牺牲正确性，覆盖不变量 | 前后端，后端为禁区 |
| 代码更简洁 | 去冗余、降复杂、统一实现 | 前后端 |
| 视觉布局更好 | 信息架构、空间、层级、响应式 | 前端 |
| 交互效果更好 | 流畅度、状态可见性、反馈动效 | 前端 |

---

## 四、范围确认（用户已确认 2026-06-17）

1. **范围与侧重**：✅ 全栈体检驱动 —— 前后端全面扫描，按问题严重度排优先级；前端视觉/交互为重点，后端代码简洁同步覆盖
2. **交付物形态**：✅ 分析报告 + Top 优化项实施 plan —— 报告含证据/收益/风险/工作量/优先级；Top 项给到文件级+规格级 step plan，**本轮不落代码**
3. **视觉评估**：✅ 本轮**不启动前端服务**做视觉专项评估，留作后续专项；但前端**代码层面**（结构/重复/复杂度/状态处理/可维护性）问题仍纳入分析

---

## 五、阶段 A 计划（待用户确认范围后启动）

- A1 研究循环：派 2 agent 并行（架构层 + 链路层），聚焦复杂度热点、重复实现、分层违规、布局/交互缺陷
- 视觉/交互：读关键页面源码 + 已有截图（test_screenshots、works/设计稿），必要时用 webapp-testing 启动验证
- A2 构建七环推理链，写入本文件
- 门控：呈现推理链，用户确认后进入阶段 B

## 研究第 1 轮（2026-06-17）

方法：2 个 general-purpose agent 并行（后端 / 前端分区体检，各含结构+数据流），主 agent 对 Top 影响判断做证伪验证。

### 任务结构性理解

MyQuant 整体架构**健康**——分层清晰、文档完备（前后端 INDEX/domain/flows/crosscut）、测试覆盖较好（前端 26 个测试文件、后端 tests/ 129 项）。技术债不是设计缺陷，而是**累积性偏离**：项目已有正确范本（`api/routes/trading.py` 262 行纯编排、`BacktestEngine.run`），但部分模块在演进中偏离了范本。技术债集中在三个层面：

**后端「胖 API 层」**——本应只编排的 api 层累积了 core 业务逻辑：
- `api/routes/strategies.py`（1779 行）：回测流水线「加载→run→metrics兜底→打分→save」复制 **5 次**（`:237,431,611,900,1304`），含 metrics 兜底组装、方向标签映射、星级评分、裸 SQL。对照 `trading.py` 纯编排范本，这是技术债非设计选择。
- `api/runner.py`（1021 行）：~60% 是进化业务核心（`_evaluate_dna`/`_evaluate_population`/`_build_requirements` `:773-1010`），而 `core/evolution/engine.py:186` 已设计为接受 `evaluate_fn` 回调——评估逻辑本应在 core 提供 default 实现。
- persistence **三轨**：`core/persistence/db.py` + `api/db_ext.py` + 7 处裸 `sqlite3.connect`（`runner.py:279,469,530,549,715,744`、`evolution.py:579`）；`core/trading/runner.py:81,147,157` 越界抓私有 `_connect`（违反 `模拟交易.md:14-19`）。
- 分层反向：`core/data/mtf_loader.py:55,93` 反向依赖 `core/features`（违反 `数据层.md:17` 声明的 data 为底层）。
- 迁移三轨：`migrations/*.sql`(7) + `db_ext.py:69-330`(~30 函数) + `db.py:32-81` 维护同一 schema。
- 死代码：`core/features/signal_builder.py` 文件头自声明 DEPRECATED，生产零引用（`registry.py:463` 仅注释提及）。

**前端技术债**：
- **死代码 11 项**（已证伪验证确认）：ConditionPill、ConditionPillGroup、TimeframeLabel、TimeframeSelector、ReferencePanel、ValidationConclusion、TriggerTable、TriggerDetailDrawer、DistributionChart、charts/ChartLegend、stores/lab.ts(useLabStore)。全部仅自身/互引，无 page 消费。
- 流式 Hook 逐行重复：`hooks/useStrategies.ts:104-200`(useVerifyStream) 与 `:212-302`(useBatchBacktestStream) ~100 行样板。
- 类型契约漂移：`types/api.ts:1-32` vs `api/schemas.py:77-112`——前端 `RiskGenes` 缺 `sl_mode`/`atr_period`，`LogicGenes` 可空性与后端相反，`SignalGene.condition` 前端强类型而后端开放 dict。
- 两个高频页面 query error 缺失：Trading、Strategies 网络失败时静默停留 loading（仅 ErrorBoundary 兜渲染崩溃）。
- 复杂度热点：`pages/Lab.tsx`(1155 行，3 模式+16 useState)、`components/charts/KlineChart.tsx`(959 行，11 useRef 多职责)、`pages/Strategies.tsx`(998 行)。
- chart 指标**双数据源**：`stores/chart-settings.ts:145`(localStorage) 与 `pages/Settings.tsx:399`(写后端) 并存，刷新后不回填→漂移。
- 图表双轨：KlineChart/EquityCurveChart 用 lightweight-charts，trading 的 EquityCurve/ScoreTrendChart/DistributionChart 用 recharts；`toTime` 在两处一字不差重复。

**交叉问题**：前后端类型契约端到端不一致；流式模式前后端各自重复（后端 _VerifyProcessor/_BatchBacktestProcessor，前端 useVerifyStream/useBatchBacktestStream）；指标计算后端路由重算 + chart_builder 闲置、前端图表双库。

### 任务认知变化

初始理解："范围模糊的全栈重构，代码更简洁+视觉+交互更好"。
研究后：工程不需要重写或大改架构，需要的是**收敛式技术债清理**。最高价值项是低风险、立即可见的——死代码清理（前后端）、重复消除（回测流水线、流式 Hook）、分层归位（runner 评估逻辑、persistence 统一）、契约对齐、状态补全。大型组件拆分（Lab.tsx/KlineChart）优先级**低于**上述项，且属于"阻碍未来视觉专项迭代"的结构问题，留待视觉专项协同。视觉/交互实跑评估按用户决策留作后续专项。

### 待消解的不确定性

- **死代码「未来计划」**（影响 P0 是否执行删除）：用户是否打算复活 pill 条件编辑器（ConditionPill 簇）？→ **门控确认项**，不阻塞分析。
- 回测流水线 5 副本的精确差异（合并可行性）：实现细节，Top 项 plan 阶段逐副本 diff 处理，不阻塞。
- 类型契约变更的联动范围：已识别为风险，plan 标注 Lab.tsx:413-434 手搓 DNA 路径。

### 决策

**研究完成**。无会改变「分析方向」的阻塞性不确定性；死代码未来计划留作门控确认。进入 A2 构建推理链。

---

## 七环推理链（待门控确认后冻结）

### 环 1 · 任务定义

对 MyQuant 全栈做结构性重构体检，产出两份交付物：①**优化方向分析报告**（覆盖前后端，每条带证据/收益/风险/工作量/类别/优先级，按性价比排序）；②**Top 优化项的文件级+规格级实施 plan**（步骤、改动文件、实现级规格、验证方式、风险与回退）。**本轮不落代码**。质量底线：交易/回测/评分不变量（未来函数、shift(1)、手续费/滑点/资金费率/杠杆/清算）不可破；视觉布局与交互模式不动（专项后续）。

### 环 2 · 现状定位（证据见上方「结构性理解」，每条均有 文件:行号）

技术债按「偏离范本的程度」分三块：①后端胖 API 层（strategies.py 流水线×5、runner.py 评估错置、persistence 三轨、data→features 反向、signal_builder 死代码）；②前端技术债（11 项死代码、流式 Hook 重复、类型契约漂移、query error 缺失、Lab/KlineChart 复杂度、chart 双数据源）；③前后端交叉（契约不一致、流式端到端重复、图表/指标双轨）。问题性质均为**架构设计/代码设计层面**的累积偏离，非业务逻辑错误。

### 环 3 · 解决策略

**收敛式重构，非重写**。按「风险升序、收益降序」分四层推进，每层有明确退出标准：
- **L1 清死代码**——零风险立即见效（前后端 ~11+1 项）
- **L2 去重复**——低风险，trading.py 范本可循（流式 Hook、helper、格式化、OptionDropdown、discovery 接入）
- **L3 修分层归位**——中风险，行为不变的纯搬运（runner 评估归 core/evolution、metrics 归 core/scoring、persistence 统一、类型契约对齐、query error 补全）
- **L4 降复杂度/补数据源**——中高风险，需回归（回测流水线合并、迁移单轨、data→features 修复、chart 单数据源、Lab/KlineChart 拆分、operators 表驱动、风险数学抽常量）

排除：大改架构、换技术栈、视觉重做。理由：项目已有正确范本，技术债是累积偏离，收敛即可，重写收益不抵风险。

### 环 4 · 范围边界

**后续实施会改**：api/routes/strategies.py、api/runner.py、api/db_ext.py、core/evolution/、core/persistence/、core/data/mtf_loader.py、core/features/signal_builder.py(删)、core/scoring/、core/visualization/；前端死代码 11 项、hooks/useStrategies.ts、types/api.ts、stores/、pages/Trading.tsx、pages/Strategies.tsx、components/lab/index.ts、components/charts/、services/discovery.ts。

**不改（禁区）**：core/backtest 数学（清算阈值/资金费率/shift/杠杆）、core/trading 交易执行数学、评分阈值语义、视觉布局与交互模式、prediction 自包含边界。

**本轮**：只分析 + plan，不写代码。

### 环 5 · 行为规格（交付物规格）

**分析报告规格**：每条优化方向含——诊断 / 证据(文件:行号) / 收益 / 风险 / 工作量(S/M/L) / 类别(架构·代码·业务) / 优先级(P0-P3)；覆盖前后端；按性价比排序；区分「必做/应做/锦上添花」。`[代码审查]`

**Top 项 plan 规格**：每个步骤含——目标 / 改动文件 / 实现级规格(函数签名·数据结构·算法描述) / 验证方式 / 风险与回退 / 不变量保护区。`[测试验证]`（重构后 `cd MyQuant && python -m pytest` + `cd web && npm run test && npm run build` 回归）、`[集成测试]`（流水线合并后指标对比 baseline）

### 环 6 · 风险披露

**确定有风险**：
- 回测流水线合并（L4）：5 副本可能有流式/并发细微差异 → 需逐副本 diff + baseline 指标逐字节对比，否则结果漂移。
- 类型契约对齐（L3）：补 RiskGenes 字段影响 Lab.tsx:413-434 手搓 DNA 路径与策略校验 → 联动范围 plan 细化。
- data→features 修复（L4）：需上移指标计算到 trading/strategy/evolution 调用方，影响面广。

**不确定是否有风险**：
- 死代码未来计划：用户是否复活 pill 编辑器？（门控确认）
- operators.py 表驱动（L4）：变异算子是进化核心，可能影响 champion 分布 → 需回归对比。
- 回测流水线合并的等价性边界：流式与同步路径的差异程度待 plan 阶段 diff。

**缓解**：所有 L3/L4 项要求「行为不变 + 回归测试通过 + 指标对比」；不变量项只抽不改数学；L4 高风险项可拆为独立 PR 增量推进。

### 环 7 · 实施顺序（优化方向优先级，Top 项 plan 在门控后细化到文件级）

**P0｜立即可做·S 工作量·零/低风险**（性价比最高，建议作为首批落地）：
- 前端死代码清理 11 项 + lab/index.ts 导出 + stores/lab.ts
- 后端 signal_builder.py 删除
- 流式 Hook 去重（createStreamHook 工厂）
- toTime helper 抽取（KlineChart ↔ EquityCurveChart）
- EquityCurve 格式化复用 lib/utils
- OptionDropdown 合并（SubjectDropdown/ActionDropdown）
- discovery.ts 接入 Axios 实例

**P1｜应做·M 工作量·低-中风险**：
- runner 评估逻辑归位 core/evolution（提供 default evaluate_fn）
- compute_trading_metrics 归位 core/scoring
- persistence 统一（消除裸 SQL + _connect，公开 connect/transaction）
- 类型契约对齐（types/api.ts ↔ schemas.py）
- query error 补全（Trading/Strategies）

**P2｜架构债·M-L 工作量·中风险**：
- 回测流水线合并（抽 core/services/backtest_service）
- 迁移单轨化
- data→features 反向依赖修复
- chart-settings 单数据源

**P3｜锦上添花·L 工作量·中高风险**：
- Lab.tsx backtest 配置态下沉 BacktestModePanel
- KlineChart 拆分（图例/MTF/annotation 子模块）
- operators.py 表驱动化
- 杠杆风险数学抽公共常量（只抽不改 invariant）

**门控待确认**：①死代码未来计划；②P2/P3 中风险项是否纳入本轮 plan（还是只给 P0/P1 的详细 plan，P2/P3 留方向）。

---

## 门控确认（2026-06-18 · 推理链【冻结】）

用户确认：
1. **死代码处置**：✅ 全部确认废弃可删（前端 11 项 + `signal_builder.py`）
2. **plan 范围**：✅ P0 + P1 出文件级+规格级详细 plan；P2/P3 出方向与要点

推理链标记为**冻结**状态。阶段 B 以此为基准实施（本轮交付物=plan 文档，不落代码），偏离必须报告。

---

## 阶段 B 产出（2026-06-18）

### 交付物
1. **分析报告**＝本文件（工程扫描 + 第一轮研究结构性理解 + 七环推理链 + 优化方向）
2. **实施 plan**＝`plan.md`：P0(7项)+P1(5项) 文件级+规格级详细 plan；P2(4项)+P3(4项) 方向；里程碑 M0-M5；风险登记册 R1-R7

### B2 细化要点
- P1 关键规格经源码确认：流式 Hook 4 处差异（sessionId/onComplete invalidate/toast/streamFn）已参数化为 `createStreamHook`；engine.evolve 回调注入设计已验证（engine.py:186,191）；persistence `_connect`(db.py:23) 公开方案已定；类型契约缺口已逐字段定位（RiskGenes 缺 sl_mode/atr_period、LogicGenes 可空性相反、SignalGene.role 缺 direction）。

### B4 合规确认 + 最终校验（七环对比）

| 环 | 对比结论 |
|---|---|
| 1 任务定义 | 无偏差——产出分析报告+plan，未落业务代码（仅创建 task.md/plan.md 任务文档） |
| 2 现状定位 | 无偏差——plan 改动文件全部锚定推理链认定的关键点（胖API层/前端技术债/交叉） |
| 3 解决策略 | 无偏差——plan 的 P0-P3 风险升序对应推理链 L1-L4 收敛策略 |
| 4 范围边界 | 无偏差（更保守）——未触碰任何业务代码；禁区（backtest/trading 数学、视觉交互）在 plan 原则与每项规格中反复标注 |
| 5 行为规格 | 无偏差——报告每条带证据/收益/风险/工作量/类别/优先级；plan 每项含文件级+规格级+验证方式 |
| 6 风险 | 无偏差——风险登记册 R1-R7 覆盖推理链披露风险；死代码「未来计划」不确定性已由用户确认消解（可删） |
| 7 实施顺序 | **策略微调（自行处理）**——P0-7(discovery 接入 axios) 风险标「低-中」（流式兼容性）略高于其他 P0 项，但工作量小、收益明确故仍置 P0，plan 内已标注前置确认项（实施前确认是否 SSE） |

**结论**：七环对比无重大偏差，仅 P0-7 一处策略微调（等价，已在前置确认中规避风险）。本轮交付完整。

---

## 阶段 B3 实施 P0（2026-06-18 · 用户指令"实施 p0"）

### ⚠️ 环境阻塞发现：venv 损坏（非本次改动造成）
- `MyQuant/venv/bin/python`（及 python3/python3.12）为 **0 字节空文件**（6/16 23:24 被清空），venv 无法运行任何代码
- conda 环境（def/base/py3.13）与系统 `/usr/bin/python3` 均**无项目依赖**（缺 numpy/pytest/vectorbt）
- **影响**：后端 `python -m pytest` 无法执行 → P0-2（后端唯一项）动态验证受阻
- **处置**：不擅自重建 venv（超 P0 代码改动范围 + vectorbt 等重装耗时）；记录待用户决定。前端项不受影响（node v24 / npm 11 可用，PATH 已修正为 /usr/local/bin 优先）

### P0-1 ✅ 前端死代码清理（完成 · 全验证通过）
- 删除 12 文件（9 个 lab 组件 + ChartLegend + stores/lab.ts + test/stores/lab.test.ts）+ 收敛 `components/lab/index.ts`（删 9 行导出，保留 12 行活路径）
- 验证：`build` EXIT=0（tsc 类型检查通过）/ `lint` EXIT=0（eslint 无 error）/ `test` EXIT=0（vitest 全过）/ grep 零残余引用
- 证伪价值兑现：SceneModePanel/SceneResult/SceneSelector 经验证为活路径（Lab.tsx:851），未误删

### P0-2 ✅ 后端 signal_builder 删除（完成 · 动态验证通过）
- 删除 `core/features/signal_builder.py`（自声明 DEPRECATED）+ `tests/test_signal_builder.py`；改 `registry.py:463` docstring
- venv 用 **py3.13** 重建（用户指定，Python 3.13.13）+ pip install -r requirements.txt（vectorbt 0.28.5 + numba 0.61.2 等 3.13 兼容 OK）+ 补装 **pytest-cov**（pytest.ini 隐含依赖，requirements.txt 漏列）
- 验证：`pytest tests/ --ignore=tests/e2e` → **1902 passed, 3 failed, 1 skipped, 1 xpassed**
- **3 failed 确认与 P0-2 无关**：① signal_builder 在整个 tests/ 零引用（已 grep），删除不可能影响 funding/indicator_profile/evolution 测试；② 我的后端改动仅「删 signal_builder + 删其测试 + 改 registry docstring 注释」；③ 失败性质是**随机 mutation 生成边界无效 case**（cross_above_series 缺 target_indicator、lookback 缺 window）+ **测试隔离**（funding 单独跑 PASSED）+ **py3.13 环境差异**（原 venv 为 3.12）
- e2e collection error（6 个 tests/e2e/）：playwright 缺失 + 需运行服务，属独立 e2e 环境，与 P0-2 无关
- **结论**：signal_builder 删除安全，无回归。3 failed + e2e 为既有/环境问题，记录为独立项不纳入 P0

### P0-3 ✅ 流式 Hook 去重（完成 · build+test 通过）
- 新建 `hooks/createStreamHook.ts` 工厂（统一 StreamState + start/cancel/reset + AbortController + toast）
- `useStrategies.ts` 两 hook 改薄封装，参数化 4 处差异（streamFn / errorLabel / sessionIdKey / onCompleteExtra）
- 验证：build EXIT=0（tsc 泛型兼容）/ test EXIT=0（行为不变）；消除 ~100 行重复

### P0-4 ✅ toTime helper 抽取（完成 · 待批量 build）
- 新建 `charts/core/time.ts`；KlineChart.tsx + EquityCurveChart.tsx 删本地 toTime 改 import；两处一字不差，行为等价

### P0-5 ⚠️ EquityCurve 格式化复用（经源码评估·不实施 · plan 偏差）
- 源码确认：trading/EquityCurve.tsx 私有 `formatTime`（`slice(5,16)`→"01-02 03:00" 紧凑轴标签）/ `formatMoney`（$1.2M K/M 缩写）与 lib/utils 的 `formatDateTime`（完整 "2024/01/02 03:00"）/ `formatCurrency`（$1,234,567 千分位）**语义不同**
- 直接替换会改变 XAxis/YAxis 标签 → 变长、可能重叠/超宽（YAxis width=60），**破坏视觉**，违反 plan「不改视觉」原则
- 结论：私有函数是有意的紧凑轴标签格式，非真重复，不实施。待用户决定是否需在 lib/utils 新增紧凑格式版本（当前单消费者，收益低）

### P0-6 ✅ OptionDropdown 合并（完成 · build+test 通过）
- 新建 `components/lab/OptionDropdown.tsx`（共享 trigger+portal+分类列表，参数化 searchable/width/maxHeight）
- SubjectDropdown/ActionDropdown 改薄封装（保留各自业务数据 SUBJECT_OPTIONS / getActionsForSubject / getSubjectLabel / getActionLabel）
- 消除 trigger 样式 + DropdownPortal + 分类渲染重复（~40 行×2）；导出名保留，消费方零改动

### P0-7 ✅ discovery.ts 删除（用户决策 · build 通过）
- 读源码发现 discovery.ts **零前端消费方**（124 行死代码，后端 discovery.py 路由存在但前端无 Discovery 页面接入）
- 后端用软错误模式（HTTP 200 + `{error}`），即便接入 axios 也无法统一错误格式（需改后端 HTTPException）
- **用户决策**：删除 discovery.ts（后端 discovery.py 路由保留，供未来前端接入时重写）
- 删除后 build EXIT=0，零残余引用。比"接入 axios 但无人用"更彻底，符合 P0 死代码清理方向

### P0 前端最终验证（2026-06-18）
- `build` EXIT=0（tsc + vite）/ `lint` EXIT=0（eslint）/ `test` EXIT=0（vitest 全过）
- 后端 P0-2 动态验证受阻于 venv 损坏（见环境阻塞）

---

## B4 合规确认 + 最终校验（P0 实施 vs 冻结 plan）

### 覆盖完整
P0 七项全部处置：**5 项实施完成**（P0-1/3/4/6/7）、**1 项删除完成待动态验证**（P0-2）、**1 项经源码评估不实施**（P0-5）。前端全量 build/lint/test 通过。

### 偏差报告（需用户知晓）
1. **P0-2 已验证通过**（venv 重建后）：1902 passed，3 failed 确认与 P0-2 无关（signal_builder 零引用 + 失败性质是随机/隔离/py3.13 环境差异）。过程中修复 venv 损坏 + 补装 pytest-cov。
2. **P0-5 不实施**（plan 前提偏差）：私有 formatTime/formatMoney 是紧凑轴标签格式，与 lib/utils 完整格式语义不同，替换破坏视觉。
3. **P0-7 改为删除**（用户决策）：discovery.ts 零消费方死代码，删除（后端路由保留）。

### 独立发现（非 P0 范围，记录供后续）
- **venv 损坏**（python 二进制 0 字节，6/16 23:24）已用 py3.13 重建修复；requirements.txt 漏 pytest-cov（已补装），建议补入
- **3 个测试失败**（funding 隔离 + indicator_profile/evolution 随机生成边界 case），疑 py3.13 环境差异（原 3.12），建议固定随机 seed 或用 3.12 对比
- e2e 测试需 playwright + 运行服务，属独立 e2e 环境

### 七环对比
- **任务定义**：实施 P0（用户指令"实施 p0"）→ 5 实施 + 1 删待验 + 1 评估不实施，偏差已报告 ✓
- **解决策略**：收敛式重构、行为不变 ✓（所有实施项 build/test 通过）
- **范围边界**：未触碰禁区（backtest/trading 数学、视觉交互）✓
- **行为规格**：前端 build/lint/test 全过；后端 1902 passed（3 failed 确认与 P0-2 无关）✓
- **风险**：venv 损坏（未预见的环境问题）、P0-5/P0-7 的 plan 前提偏差（实施时读源码发现，已如实报告，未强行实施破坏性改动）

---

## 全量回归验证（2026-06-18 · 用户指令"script 启动 + 全量回归"）

### 启动
- `start_api.sh` 启动后端 uvicorn（py3.13 venv），1s 就绪；API health：/docs 200、/api/strategies 200
- 验证完成后已 `stop.sh` + pkill 停止，端口 8000 关闭

### 回归结果

| 验证项 | 结果 |
|---|---|
| 后端 pytest（排除 e2e） | **1902 passed, 3 failed**（flaky 随机，与 P0 无关） |
| `verify_batch_pipeline.py` | **14/14 通过**（开盘价成交 / SL 触发价 `entry*(1-sl)` / shift(1) 延迟 / exit_reason 合法 / PnL 非单边） |
| `verify_leverage_api.py` | ✅ VERIFICATION COMPLETE（杠杆 L=1/3/5 对比） |
| `verify_mixed_direction.py` | ✅ 正常运行（分析 30 策略，发现既有「mixed 仅做多」业务问题） |
| `verify_strategy_integrity.py` | ✅ 8/10 精确匹配（真实数据重跑，2/10 偏差是 fitness 重构既有） |
| 前端 build / lint / test | **全 EXIT=0** |

### 3 个 pytest failed 分析（确认非 P0 引入）
- 每次跑失败的测试不同（funding → mtf_engine 漂移）= **随机性 flaky** 的确凿证据
- 涉及 evolution/indicator 随机 mutation（生成边界无效 case），seed 未固定
- signal_builder 零引用，P0-2 删除不可能影响；py3.13 环境差异（原 3.12）放大随机行为

### 结论
**核心回测/交易不变量全部验证通过**（开盘价成交、SL 触发价、shift(1) 延迟、费用、杠杆、策略真实性）。P0 改动无回归。3 个 flaky 测试 + mixed_direction 业务发现为既有问题，非 P0 引入。

---

## P1 实施进度（2026-06-18 · 用户指令"继续推进 P1"）

### P1-5 ✅ query error 补全（完成）
- Trading.tsx / Strategies.tsx 加 isError 分支（复用 EmptyState + AlertCircle + 重试 refetch）
- 2 个 error 测试用例；验证 build/lint/test EXIT=0

### P1-2 ✅ compute_trading_metrics 归位（完成）
- 新建 `core/scoring/trading_metrics.py`（compute_equity + compute_trading_metrics 纯函数 + TradingMetricsInput dataclass）
- db_ext.compute_trading_metrics 改为「DB 读 + 调纯函数」；数学逐字搬迁 `[不变量·禁改数学]`
- 新增 `tests/test_trading_metrics.py`（9 单元，锁定 equity/profit_factor/drawdown）
- 验证：单元 + trading_api 集成 = 31 passed

### P1-4 ✅ 类型契约对齐（完成）
- types/api.ts: SignalGene.role 补 `"direction"`（对齐 SignalRole）；RiskGenes 补可选 `sl_mode?`/`atr_period?`
- Lab.tsx 手搓 DNA 补 sl_mode="pct"/atr_period=14 默认值
- LogicGenes 可空性不改（可选反映后端默认值，契约合理）
- 验证 build/test EXIT=0

### P1-1 ✅ runner 评估归位（完成）
- 新建 `core/evolution/evaluation.py`（build_requirements + evaluate_dna + evaluate_population，266 行，data_dir 参数化，逐字搬迁）
- runner.py 3 方法改薄封装（委托 evaluation）；**1021→811 行**（减 210）
- 修复：薄封装用 `getattr(self,"data_dir",None)` 保持「enhanced_df 提供时不访问 data_dir」的原行为（修复 phase1/phase6 测试 AttributeError）
- 验证：评估测试通过（phase1/phase6/evolution，除 flaky）

### P1-3 ✅ persistence 统一·第一步（完成；裸 SQL 第二步记录后续）
- **第一步（低风险，完成）**：db.py 公开 `connect`（_connect 公开别名）；core/trading/runner.py 3 处不再抓私有 _connect（用公开 connect）
- 验证：trading 测试 48 passed；trading/runner 零残余 _connect
- **⏳ 第二步（中风险，记录后续专项）**：7 处裸 `sqlite3.connect` 收敛（api/runner.py 6 处 + routes/evolution.py:579 `_get_connection`）—— 改 connect 会启用 WAL/busy_timeout/row_factory，DB 行为变化需逐处验证
- api 层 _connect 引用（api/runner/db_ext/routes）保留（API→persistence 边界允许，非越界）

### P1 验证状态
- 前端 build/lint/test EXIT=0；后端全量 **1911 passed + 4 failed**（均 flaky 随机/顺序，单独重跑通过，与 P1 无关）
- 核心不变量 verify_batch_pipeline 14/14（P0 回归时验证）

### P1 偏差/记录
- P1-3 分步：第一步完成（核心「trading 不越界」达成），裸 SQL 收敛第二步因 DB 行为变化风险留作后续专项
- 4 个 flaky 测试（evolution/indicator/mtf/phaseD 随机或顺序）+ py3.13 环境差异，非 P1 引入

---

## P1 全量回归验证（2026-06-18 · 用户确认）

### 启动
- start_api.sh 启动后端（py3.13 venv），1s 就绪；API health /docs 200；验证后已停止（端口 8000 关闭）

### 回归结果

| 验证项 | 结果 |
|---|---|
| 后端 pytest（排除 e2e） | **1912 passed, 3 failed**（flaky，与 P1 无关） |
| verify_batch_pipeline.py | **14/14 PASS**（开盘价成交/SL 触发价/shift(1)/exit_reason/PnL） |
| verify_leverage_api.py | ✅ COMPLETE（杠杆对比） |
| verify_mixed_direction.py | ✅ 正常运行 |
| verify_strategy_integrity.py | ✅ 8/10 精确匹配（既有偏差） |
| 前端 build / lint / test | **全 EXIT=0** |

### 结论
**P1 全量回归通过**。核心回测/交易不变量 14/14 + 前端全绿 + 1912 后端测试通过。3 个 flaky + strategy_integrity 2/10 偏差 + mixed 仅做多 均为既有/环境问题，非 P1 引入。

---

## P1-3 第二步：裸 SQL 收敛（2026-06-18 · 用户确认后推进）

### 改动
- 7 处裸 `sqlite3.connect` → `connect`：api/runner.py（6 处：find_pending SELECT / current_gen UPDATE / champion best_score UPDATE ×2 / champion_metrics UPDATE / oos UPDATE）+ api/routes/evolution.py（`_get_connection` 委托 connect）
- 净效果：统一 WAL + busy_timeout=5000 + synchronous=NORMAL + row_factory（原裸 connect 部分缺失）；连接创建换 connect，后续 commit/close 不变
- 残余 `sqlite3.connect` **仅 db.py:24**（_connect 内部，公开 connect 委托它）—— **DB 访问单点达成**

### 验证（全量回归）
- import OK；evolution/runner/persistence/trading 针对性 **345 passed + 1 flaky**
- 全量 pytest（排除 e2e）**1912 passed + 3 failed**（lookback_for_bb/mutate_indicator 随机 + momentum_e2e 顺序，**单独重跑均 PASSED，非 P1-3 引入**）
- `verify_batch_pipeline` **14/14**（DB 写 champion/snapshot 正常）；`verify_strategy_integrity`（DB 读策略重跑）、`verify_leverage_api` 通过
- API health 200；服务已停止

### P1-3 完成总结
第一步（trading 不抓私有 _connect + db.py 公开 connect）+ 第二步（7 处裸 sqlite3.connect 收敛）均完成。**DB 访问单点 db.py**（connect）；core.trading / api.runner / api.routes 不再抓私有 _connect 或裸 sqlite3.connect。api 层 db_ext 的 _connect 引用保留（API→persistence 边界，非本次范围）。

---

## P2 实施进度（2026-06-18 · 用户选"推进4项"，2 agent 研究细化）

### P2-4 ✅ 删 chart_indicators 死数据（方案B，完成）
- agent 证伪发现：后端配置端点是**"死数据"**（前端从不 GET，仅 Settings PUT 写入），真单一源是 localStorage
- 删 api/routes/chart_config.py + app.py 注册(19,130) + Settings handleSave(396-404)/保存按钮(592-598) + test_validate TestChartConfigAPI + chart_indicators.json
- 验证：APP_OK + test_validate 6 passed + 前端 build/lint EXIT=0

### P2-3 阶段一 ✅ mtf_loader 加 compute_indicators 参数（完成，零风险）
- load_and_prepare_df / load_mtf_data 加 `compute_indicators: bool = True`，算指标条件化（默认 True 行为不变）
- 为 data→features 反向依赖修复铺路；阶段二（切换 7 调用方）待 P2-1 后做（借 service 收敛）
- 验证：默认 True 算指标 / False 返回 5 列 OHLCV + 376 passed

### P2-2 轻量 ✅ init_db_ext 改数据驱动（完成）
- 24 段硬编码步骤 → init_db_ext 内局部 `migrations` 注册表循环（21 项 version 5-25，含 `_step_23` helper 处理两函数）
- 修复：模块级 _PY_MIGRATIONS 前向引用 NameError（_create_paper_trading_tables 等在 init_db_ext 后定义）→ 改 init_db_ext 内局部
- 验证：新库 2 次幂等 + 现有 quant.db 应用 + db_ext/evolution_arch 78 passed
- 完整单轨化（21 函数→sql）留后续（SQLite 无 ADD COLUMN IF NOT EXISTS 需 Python guard）

### P2-1 ⏳ 回测流水线合并（M 大工程，下轮专项）
- agent 细化方案：新建 `core/services/backtest_service.py`（prepare_backtest_data/fallback_metrics/persist_backtest/signals 工厂纯函数），5 副本（strategies.py:237/431/611/900/1304）瘦身
- **关键约束**：BacktestEngine（副本1-4）与 ReplayRunner（副本5）metrics 路径**不能强合**（sharpe 禁区）；副本5 用 `_bars_per_year`+events 合成，与 1-4 的 `bt_result.bars_per_year` 不同
- 工作量 M（2-3 天），需 baseline 对比 + 完整回归
- 待下轮专项（含 P2-3 阶段二：切换调用方收敛改动面）

### P2 偏差
- P2-1 因 M 大工程 + 中风险（回测核心），调整为**本轮 3 项 + P2-1 下轮专项**（避免仓促质量风险）
- P2-2 完整单轨化（sql 化）留后续（agent 建议分批）

---

## P2 全量回归验证（2026-06-18 · 用户确认）

### 启动
- start_api.sh 启动后端（py3.13），1s 就绪；API health /docs 200；验证后已停止（端口 8000 关闭）

### 回归结果

| 验证项 | 结果 |
|---|---|
| 后端 pytest（排除 e2e） | **1907 passed, 4 failed**（flaky，与 P2 无关） |
| verify_batch_pipeline.py | **14/14 PASS**（开盘价/SL/shift(1)/exit_reason/PnL） |
| verify_strategy_integrity.py | ✅ 8/10 精确匹配（既有偏差） |
| verify_leverage_api.py | ✅ COMPLETE |
| 前端 build / lint / test | **全 EXIT=0** |

### 4 failed 确认均 flaky（与 P2 三项无关）
- `test_dna_to_signal_set_single_bar`（顺序，单独重跑 2 次 PASSED）
- `test_generates_lookback_for_bb` / `test_mutate_indicator_uses_profile_params`（随机 mutation）
- `test_phaseD_add_signal::test_add_updates_entry_price`（顺序）
- P2 三项（chart删 / mtf_loader compute_indicators默认True / init_db_ext）不影响 dna_to_signal/evolution/indicator

### 结论
**P2 三项全量回归通过**。核心回测/交易不变量 14/14 + 前端全绿 + 1907 后端测试通过。4 个 flaky 均顺序/随机，非 P2 引入。P2-1（回测流水线合并 M 大工程）待下轮专项。

---

## P2-1 回测流水线合并·第一步（2026-06-18 · A+D 类，agent 深度研究后实施）

### 改动
- 新建 `core/services/backtest_service.py`（+ `core/services/__init__.py`）：3 个纯函数逐字提取
  - `fallback_metrics(bt_result)` — metrics 兜底（副本1-4 字面相同）
  - `build_signals_from_trades_df(trades_df)` — BacktestEngine 信号（副本1）
  - `build_signals_from_events(events_log)` — ReplayRunner 信号（副本5 原方法搬入）
- strategies.py：副本1-4 metrics 兜底 → `fallback_metrics`（4 处）；副本1 signals → `build_signals_from_trades_df`；副本5 `_build_signals_json_from_events` → 委托 service；删顶部 `compute_metrics` unused import
- **关键约束遵守**：fallback_metrics **仅服务 BacktestEngine 路径（副本1-4）**；ReplayRunner（副本5）保留独立 metrics 合成（无 metrics_dict 属性、`_bars_per_year` map 不同、trade_win_rate 从 events 解析）——不强合避免改 sharpe

### 验证（全量回归）
- API health 200；import OK；metrics_dict or 残余为 0
- 全量 pytest（排除 e2e）**1907 passed + 3 failed**（lookback_for_bb/mutate_indicator 随机 + invariants 顺序，**单独重跑均 PASSED，非 P2-1**）
- strategies/backtest/compare/verify/batch 针对性 **140 passed**
- `verify_batch_pipeline` **14/14**（回测不变量 + metrics 路径正常）
- 前端 build/lint/test EXIT=0

### ⏳ P2-1 第二步（C+B 类，下轮）
- **C. compute_needed_tfs**（副本2-5）：注意副本1 的 `payload.timeframe_pool` 分支 + 副本2 不校验 `len>1`（保留原行为，不"修正"）
- **B. persist_backtest 参数化**（5 处差异大）：指标源（result.* vs metrics.get）、data_start/end（enhanced_df vs raw df，副本2 是 bug 但不改）、run_source、可选字段（fitness/qualified/session_id/equity_curve/trades_json）—— service 接收已算好的数值元组，调用方取值，避免 service 内分支

### P2-1 进度
第一步（A metrics兜底 + D signals）完成，最高 ROI 重复消除。第二步（C needed_tfs + B persist）因差异复杂留下轮。

---

## P2-1 第二步（2026-06-18 · C 完成 + B 跳过）

### C ✅ compute_needed_tfs（完成）
- backtest_service 加 `compute_needed_tfs(dnas, timeframe) -> set`（空集当无 MTF dna）
- 副本2/3/4/5 的 needed_tfs 计算 + mtf 条件 → 调 service；**保留原行为**（副本2 无 `len>1` gate，helper 返回非空 iff any MTF，`if needed_tfs:` 等价）
- 副本1 的 `timeframe_pool` 分支保留（不用 helper）
- 验证：import OK + needs_mtf 残余为 0 + strategies/mtf/compare/verify/batch **293 passed**

### B ⏭️ persist_backtest（跳过 · 用户决策）
- 评估：save_backtest_result 已是统一 DB 写入入口，5 处差异在**参数值**（data_start/end、run_source、可选字段），非逻辑重复；persist_backtest 是 thin wrapper，收益递减
- A/C/D 已消除核心逻辑重复（metrics兜底4处 + needed_tfs4处 + signals2处）
- **保留 save_backtest_result 直接调用**

### P2-1 全量回归（A+C+D）
- API health 200；全量 pytest **1909 passed + 2 flaky**（lookback_for_bb/mutate_indicator 随机，非 P2-1）
- `verify_batch_pipeline` **14/14**（回测不变量 + MTF 路径正常）；verify_strategy_integrity 8/10（既有偏差）
- 前端 build/lint/test EXIT=0

### P2-1 完成总结
- **A（metrics兜底 副本1-4）+ C（needed_tfs 副本2-5）+ D（signals 副本1/5）完成；B 跳过**
- 新建 `core/services/backtest_service.py`（4 纯函数）；strategies.py 5 副本瘦身（metrics/signals/needed_tfs 委托 service）
- **保留 BacktestEngine vs ReplayRunner 双 metrics 路径**（副本5 不走 fallback_metrics，避免改 sharpe）——禁区遵守

---

## flaky 测试根因分析 + 修复（2026-06-18 · agent 深度分析 + 脚本复现）

### 根因（2 个独立真 bug，非测试写法问题）
- **A 类「随机性」= `operators.py` 真 bug**：`generate_random_condition` 的 profile 路径（76-85）对复杂条件（lookback_any/cross_above_series）**只填 type，漏填必填字段**（window/target_indicator）；free exploration 路径（87-147）才完整。32.5% BB / 9.5% EMA 概率生成无效条件 → validator 失败。**生产 evolution 也受影响**（无效 mutation 被 validator 过滤，浪费迭代）。
- **B 类「顺序」= `executor.py` 真 bug**：模块级全局 `_indicator_column_cache`（:291）以 `id(df)` 为 key **永不自动清理**，跨测试泄漏；Python id 复用使新 df 命中陈旧 cache → 返回错误 indicator 列。agent 已脚本精确复现 `test_dna_to_signal_set_single_bar` 的 entries 错误。

### 修复（3 项）
- **A1** `operators.py`：统一 profile / free-exploration 路径 —— profile 选定 type 后走**完整字段填充**（lookback→window/inner、cross_series→target_indicator），preset 的 threshold/target_field 优先。消除生产无效 mutation + A 类 flaky。
- **B1** `executor.py`：`dna_to_signal_set` 入口加 `clear_indicator_cache()` —— 根治跨调用/跨测试 cache 泄漏。
- **B2** `conftest.py`：autouse fixture 每测试前后清 cache —— 双层保险（被测忘清也隔离）。

### 验证
- A 类测试循环 **5 次全 PASSED**（A1 修复，不再生成无效条件）
- 全量回归 **×2 都 1911 passed, 0 failed**（之前 1907-1912 + 2-4 flaky）
- **flaky 完全消除**，全量回归稳定 0 失败
