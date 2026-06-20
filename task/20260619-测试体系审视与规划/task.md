# MyQuant 测试体系审视与优化规划

## 任务定义
审视 MyQuant 测试框架与用例分布，进行批判性质疑，分析覆盖面/覆盖流程/能力的优化方向，给出测试优化规划方案。本任务为**分析任务**，产出是测试现状审视 + 质疑清单 + 优化规划推理链，供用户门控后决定是否实现。

## 已知背景（来自前序任务）
- 后端：core/ 17591 行（strategy/backtest/evolution/trading/validation/scoring/features/data/discovery/prediction/persistence），api/ 7205 行
- 测试规模：后端 pytest 1917 passed（排除 e2e）；前端 vitest 228 用例（227 passed/1 failed）；e2e 64 用例（40 passed/24 failed-过时）
- 测试配置：pytest.ini（--cov=core --cov=api, markers: smoke/unit/integration/slow/e2e）、pytest_e2e.ini（playwright chromium, base_url :8000）、vite.config test 段（jsdom）
- 已知测试问题：e2e 24 过时（英文断言 vs 中文 UI、旧路由 /library vs /strategies）、vitest 1 过时（达标 badge）、conftest.py 有 autouse indicator cache 清理 fixture
- 工程关键不变量（必须有测试守卫）：回测避免未来函数、信号 shift(1)、止损止盈基于 HIGH/LOW、手续费/滑点/资金费率/杠杆/清算不可绕过、prediction 自包含、协作式取消

## 初始研究方向
1. 测试框架组织：pytest/vitest/e2e 三层配置、conftest/fixture/marker 使用、测试分层（unit/integration/e2e）是否清晰
2. 用例分布：按模块（哪些模块测试密集/稀疏/缺失）、按类型、按文件规模
3. 覆盖率：各模块实际覆盖率（跑 --cov）、低覆盖/无覆盖区域
4. 测试与能力映射：核心能力（回测/进化/交易/验证/数据/MTF）是否有测试守卫、哪些不变量有专门测试
5. 质疑点：低价值测试、缺失覆盖、flaky、未来函数风险测试、流程缺口、测试与实现耦合

---
（以下为研究循环各轮记录，追加保留）

## 研究第 1 轮（2 subagent 并行 + 死代码验证）

### 任务结构性理解
MyQuant 测试体系规模可观（后端 1983 + 前端 220 + e2e 64 ≈ 2267 用例），三层骨架 pytest/vitest/playwright。**强项**：回测不变量守卫几近完备（shift/HIGH-LOW/fee/funding/leverage/liquidation，是量化系统命脉），MTF/prediction/discovery/features/scoring 覆盖率优秀（>90%）。**结构性问题**：
1. **覆盖错位**：算法核心层饱和，业务编排层空洞——diversity 17%、validation/engine 31%、rule_engine 28%、api/routes/strategies 32%、trading/runner 53%。
2. **流程闭环缺失**：碎片化单测守卫零件，无人守卫"组装后的机器"——进化 resume 闭环、trading runner 编排、validation 规则链均无连贯端到端测试。
3. **分层 marker 失效**：99.7% 裸测试，unit/slow/e2e 三 marker 用量 0，无法选择性执行/CI 分层。
4. **覆盖率门槛缺失**：无 --cov-branch、无 fail_under → 覆盖率无声下降（validation/engine 31% 能长期存在）。
5. **测试-实现强耦合**：34 处私有符号直访，集中在 core.strategy.executor 的 indicator 缓存。
6. **死代码**：derivatives_fetcher 0% 且无生产引用（已验证）。

### 任务认知变化
从"均匀补覆盖"→"聚焦编排层空洞 + 流程闭环 + 基础设施治理"。总体 79% 不算低，问题是**错位**而非不足。新增认知：覆盖率基础设施本身是高杠杆风险源（无门槛让空洞长期存在）；测试资产强项明确（回测不变量），优化应攻坚弱项而非均匀投入。

### 待消解的不确定性
- derivatives_fetcher 死活 → **已验证：死代码**（无生产引用），处置=删除/废弃而非补测。
- 编排层"难测 vs 没测" → 不改变"建议补"核心，只影响方式（已够）。
- marker 失效意图 → 不改变"加 fail_under + marker"建议（行业最佳实践，已够）。

### 决策
研究完成，构建规划推理链。

---

## 推理链 = 测试优化规划方案

### 环1 · 任务定义
产出 MyQuant 测试体系优化规划方案：基于现状诊断与质疑，给出"基础设施治理 + 编排层覆盖补强 + 流程闭环测试 + 清理治理"四方向的分批实施计划，供用户门控后选择实现批次。

### 环2 · 现状定位（诊断 + 质疑）
**覆盖率画像**（真实 --cov 数据，总体 79%）：
- 强（>90%）：prediction/discovery/features/scoring/strategy(dna,executor,mtf)/evolution(engine,operators)/persistence/db/data(merger,csv_importer)
- 弱（<60%）：**diversity 17%**（genotype_distance 算法未测）、**validation/engine 31% + rule_engine 28%**（规则回测+假设统计主路径）、**api/routes/strategies 32%**（批量/回测业务主路径~1100行）、**trading/runner 53%**（run_task 主体）、scene_engine 47%、derivatives_fetcher 0%（死代码）

**质疑清单（分类）**：
- A 缺失覆盖：A1 derivatives_fetcher（死代码→删）、A2 diversity 距离算法、A3 validation 引擎统计链、A4 strategies route 业务主路径、A5 trading runner run_task、A6 scene_engine
- B 低价值：B1 test_compute_diversity trivial（只断言 float，未测算法）、B2 test_api skip/xpass 矛盾、B3 phase 系列与 invariants 重叠
- C 风险：C1 无 branch coverage + 无 fail_under（覆盖率无声下降）、C2/C3 flaky/未来函数风险已控制（强项）
- D 流程缺口：D1 进化 resume 端到端闭环、D2 trading runner 编排、D3 validation 规则链
- E 分层混乱：E1 test_evolution_flow 实为 REST/WS 集成、E2 marker 未打标、E3 unit 测多模块协作

### 环3 · 解决策略（四方向）
1. **基础设施治理（最高杠杆，先做）**：加 `--cov-branch`（真实覆盖）+ `--cov-fail-under`（防无声下降）+ 激活 marker 分层。理由：一次配置改动惠及全部后续，堵住"覆盖率空洞长期存在"的根因。排除替代"手动定期检查覆盖率"——不可持续。
2. **编排层覆盖补强**：针对 diversity/validation/strategies-route/trading-runner 四处低覆盖，补**算法正确性 + 业务主路径**测试。理由：这些是"算法组合成业务"的编排层，单测守卫了零件但没人守卫组装。策略：优先补"算法正确性"（diversity 距离、validation 统计），再补"业务主路径"（route/runner，可能需 mock 外部数据）。
3. **流程闭环测试**：补"进化 N 代→持久化→重启 resume→继续→冠军可复现"端到端测试。理由：这是产品核心价值链（D1），碎片单测无法守卫 resume 后状态一致性。
4. **清理治理**：删 derivatives_fetcher 死代码、清理 skip/xpass 矛盾、phase 去重核查、逐步降低私有符号直访。理由：减少噪音和重构风险。

### 环4 · 范围边界
**纳入（规划覆盖）**：pytest.ini 覆盖率配置、4 处低覆盖模块补测、1 条端到端闭环、死代码/矛盾/耦合清理。
**排除（不纳入）**：回测不变量守卫（已完备，不重复投入）、前端 vitest（组织规整，仅 e2e 过时需另任务）、e2e 24 过时（独立的"测试同步"任务，已在前序任务记录）、prediction/discovery/features/scoring 高覆盖模块（不动）。

### 环5 · 行为规格（各优化项验收标准）

**方向1·基础设施**
- S1 `pytest.ini` 加 `--cov-branch`，覆盖率报告含分支覆盖列 `[代码审查]`
- S2 加 `--cov-fail-under=N`，N 取当前语句覆盖率减 2pp 作为下限门槛（防下降），后续随补测上调 `[代码审查]`

**方向2·编排层补强**
- S3 diversity：新增 genotype_distance 正确性测试（参数diff/conditiondiff/riskgene对比/相同=0/不同>0），替换 B1 trivial 测试；diversity.py 覆盖率 17%→≥80% `[测试验证]`
- S4 validation：新增 validate_hypothesis 的 THEN 窗口/分布/百分位/信号频率统计测试 + rule_engine 规则→信号→trade→统计链测试；engine.py 31%→≥70%、rule_engine 28%→≥70% `[测试验证]`
- S5 trading/runner：新增 run_task 主路径测试（MTF加载→judgment构建→决策循环→order提交→状态更新），可用 mock 数据；runner.py 53%→≥75% `[测试验证]`
- S6 strategies route：新增批量评估/回测业务主路径测试（按symbol/timeframe分组、data_ranges处理）；strategies.py 32%→≥60% `[测试验证]`

**方向3·流程闭环**
- S7 新增进化 resume 端到端测试：跑 N 代→每代持久化快照→模拟重启→resume→继续进化→冠军与连续跑一致/可复现 `[集成测试]`

**方向4·清理治理**
- S8 删除 derivatives_fetcher（确认无引用后） `[代码审查]`
- S9 清理 test_api skip/xpass 矛盾标记 `[代码审查]`
- S10 phase 系列 vs invariants 重叠核查报告（去重建议） `[代码审查]`

### 环6 · 风险披露
- R1〔确定〕补编排层测试可能因依赖外部数据（币安API/大K线）而难写 → 缓解：用 data_factory + mock/fixture 构造小数据，不触网络。
- R2〔确定〕fail_under 设过低无意义、过高立即红 → 缓解：初设当前值-2pp，随补测逐步上调。
- R3〔不确定〕diversity/validation 算法的"正确期望值"无参考实现（无 oracle）→ 消除：用构造的已知输入手算期望值，或用性质测试（相同输入=0距离、对称性）。
- R4〔确定〕端到端 resume 测试可能慢（跑多代进化）→ 缓解：用最小种群(4)+2代+小数据，标 slow marker。

### 环7 · 实施顺序（5 批次，按杠杆/风险/依赖排序）
- **批次1·基础设施+清理（高杠杆低风险）**：S1+S2（coverage 配置）+ S8（删死代码）+ S9（清理矛盾）。一次配置 + 机械清理，立即见效。
- **批次2·算法正确性补强（高价值）**：S3（diversity）+ S4（validation 引擎）。补核心算法测试，覆盖率提升最显著。
- **批次3·流程闭环（高价值，产品命脉）**：S7（进化 resume 端到端）。
- **批次4·编排层主路径（中价值，较重）**：S5（trading runner）+ S6（strategies route）。需构造业务数据，工作量较大。
- **批次5·治理（低优先）**：S10（phase 去重核查）+ marker 打标推进 + 私有耦合逐步降低。

每批独立可验证（跑对应测试 + 覆盖率提升 + 全量回归不破坏）。

---

## 门控结果与交付状态

**用户决策（2026-06-19）**：
- 推进方式：**只要分析规划**——不进入阶段 B 实现。审视报告 + 规划方案作为本次交付，存于本 task 文件。
- 覆盖率门槛偏好：**进取（按模块设门槛）**——未来实现时采用。

### 覆盖率门槛推荐配置（未来实现批次1时落地）
pytest-cov 的 `--cov-fail-under` 仅支持全局单值；按模块设门槛的实现路径（任选其一，实现时定）：
- **方案A（推荐）**：`pyproject.toml` 配 `[tool.coverage.report]` + 全局 `--cov-fail-under=75` 兜底，CI 脚本解析 `coverage json` 对各模块单独判定门槛。
- **方案B**：用 `coverage-threshold` 第三方插件声明 per-package 门槛。

**建议的按模块门槛（基于当前覆盖率 + 模块重要性）**：
| 模块类别 | 模块 | 当前 | 目标门槛 |
|---|---|---|---|
| 核心-算法（已高） | prediction/discovery/features/scoring | >95% | **90%** |
| 核心-引擎 | strategy/backtest/evolution(engine,operators) | 68-97% | **85%** |
| 核心-编排（当前空洞） | trading/runner、validation/engine、diversity | 17-53% | 阶段性：先 **60%**，补测后升 75% |
| API 层 | api/routes/strategies 等 | 32-56% | **60%** |
| 数据层 | data（除 derivatives_fetcher 死代码） | 84-100% | **80%** |
| 全局兜底 | — | 79% | **75%**（fail-under） |

### 交付成果
- ✅ 测试体系全景审视（规模/分布/覆盖率/分层/耦合，全部带证据）
- ✅ 批判性质疑清单（A 缺失/B 低价值/C 风险/D 流程缺口/E 分层混乱）
- ✅ 四方向优化规划 + 5 批次实施顺序（含验收标准、风险、依赖）
- ✅ 覆盖率门槛按模块推荐配置
- 📄 完整内容存于本 task 文件，供后续按需选择批次实现


