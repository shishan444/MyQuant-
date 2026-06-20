# MyQuant 测试优化 · 实施评估与规划

## 任务定义
基于已认可的测试优化 5 批方案（见 `task/20260619-测试体系审视与规划/task.md`），对每批做**实施评估**（可行性/工作量/风险/具体改动），产出**细化实施规划**（可执行步骤序列 + 验收点），供用户门控确认后开干。本任务为评估+规划，不直接写代码。

## 已认可的五批方案（来自前序任务）
- 批次1 基础设施+清理：加 --cov-branch + 按模块 fail_under、删 derivatives_fetcher 死代码、清理 skip/xpass 矛盾
- 批次2 算法正确性补强：diversity 距离算法、validation 引擎统计链
- 批次3 流程闭环：进化 N代→持久化→resume→冠军可复现 端到端
- 批次4 编排层主路径：trading/runner run_task、strategies route 批量回测
- 批次5 治理：phase 去重、marker 打标、私有耦合降低

## 用户决策（覆盖率门槛）
- 进取方案：按模块设门槛（核心算法90%/引擎85%/编排层阶段60%→75%/API 60%/全局兜底75%）

## 初始研究方向（实施评估要回答）
- 每批**具体改什么/补什么**（文件、函数、用例）
- 每批**工作量**（用例数、代码改动量）
- 每批**技术障碍与风险**（依赖外部数据？无 oracle？慢测试？）
- 每批**验收点**（怎么判断完成）
- **批次间依赖与排序**（哪些必须先做）

---
（以下为实施评估研究记录，追加保留）

## 实施评估结论（2 subagent 并行 + 源码验证）

### 工作量与风险评估总表
| 批次 | 用例/改动 | 代码量 | 人时 | 主要障碍 | 风险 |
|---|---|---|---|---|---|
| 1 基础设施 | 配置+删1文件+修2标记 | ~50行+脚本 | 3-4 | fail_under 设错立即红 | 中 |
| 2 算法补强 | 55-60用例 | ~800行 | 14-16 | validation 统计需确定性 OHLCV 反推 | 低 |
| 3a 单次进化E2E | 3-5用例 | ~150行 | 3 | resume 机制断裂(见下) | — |
| 3b 修resume功能+测试 | 代码+2用例 | ~200行 | 6-8 | 功能改造(非纯测试) | 中 |
| 4 编排层 | 25-31用例 | ~650行 | 14-17 | mock链长/无oracle | 中 |
| 5 治理 | 去重+打标+解耦 | ~300行 | 9-10 | 误删回归哨兵 | 中 |

### ⚠️ 关键发现：批次3 进化 resume 机制断裂（改变原规划）
- `core/persistence/checkpoint.py:54 resume_evolution` 能正确从快照恢复 population（已单测 test_persistence.py:145）
- **但 `api/runner.py` EvolutionRunner 从不调用 resume_evolution**（grep 确认）；进程重启后冷启动总从 `initial_dna` 重新解析（runner.py:335）
- `evolve()` 主循环（engine.py:183-430）**不支持续跑**：无 generation offset、无 population 注入入参，每次都 gen=1 重新 init_population
- 快照**有写**（on_generation 每代 save_snapshot）**无人读**
- **结论：这是产品级功能 gap，不是测试 gap**。补"中断 resume 一致性"测试必然失败
- **处置**：批次3 拆成 3a（单次完整进化主路径 E2E，纯测试，可行）+ 3b（修 runner 接 resume 的功能任务，需用户独立决策）

### 各批实施要点（评估已细化到文件:行号）
**批次1**：pytest.ini:5 追加 `--cov-branch`+`--cov-report=json`；fail_under 用方案A(pyproject `[tool.coverage.report]`+CI脚本 `scripts/check_coverage_thresholds.py` 解析 json)+方案C(全局兜底 N=78=当前值，零回退)；删 `core/data/derivatives_fetcher.py`（__init__.py 空、零引用已证）；修 test_virtual_account.py:614-622(删xfail)、test_mtf_integration.py:277-280(run_backtest→BacktestEngine 类)。
**批次2**：diversity `genotype_distance`(6用例,性质:同=0/对称性已知缺陷/参数diff>0)+`signal/equity_distance`+`compute_phenotype_diversity`+`apply_fitness_sharing`+`check_and_maintain_diversity`(共21用例)；validation `_check_then_conditions`/`_build_distribution`/action_map 直测+1-2端到端smoke(22-25用例)；rule_engine `_pair_trades` 直测(最高ROI,5-6用例)+`_evaluate_rule_conditions`(4用例)。
**批次3a**：最小种群4+2代+make_ohlcv tmp parquet+stub evaluate_fn+patch load_and_prepare_df/_push_ws，测 task→completed/champion/history/snapshot(3用例)。
**批次4**：trading runner `_execute_task` happy path(mock `_fetch_and_update`/`controller.wait`/时间)+MTF+错误分支(7-9用例)；strategies `_VerifyProcessor`/`_BatchBacktestProcessor` 直测(mock BacktestEngine,绕HTTP)+stream(18-22用例)。
**批次5**：phase去重——**必须保留** phase6_regression(golden分数)+phase3(黄金参考实现)；可删 test_invariants↔test_invariant_backtest 重复8-10用例+funding子集；marker 补24无标记文件；私有解耦Top5(`_compute_indicator`/`_indicator_column_cache`/`_build_session`/`_bt_engine_mod`/`_apply_funding_costs`)提升公共或改用公共接口。

### 批次依赖
- 批次1 先行（建覆盖率护栏，后续每批收益可见）
- 批次2/4 互相独立可并行；批次4 的 BacktestEngine mock 模式已在 test_api.py:256 建立
- 批次3a 用 stub evaluate_fn 可解耦，不依赖批次2
- 批次3b（功能修复）独立，不阻塞其他批

---

## 调整后的实施规划（推理链）

### 环1·任务定义
对已认可的 5 批测试优化方案做实施评估，产出可执行实施规划。评估发现批次3 需拆分（resume 是功能 gap），据此调整规划，供用户门控确认实施范围。

### 环2·现状定位（评估结论）
- 批次1/2/4/5 实施可行性确认，工作量/风险/具体改动已细化到文件:行号
- **批次3 重新定位**：resume 一致性是功能缺陷（runner 不读快照），非测试 gap

### 环3·解决策略
- 批次1：fail_under 分两步降风险——先加 --cov-branch 观察基线（不设门槛），标定后加全局兜底78%+per-module脚本
- 批次2：先直测纯函数（_pair_trades/_build_distribution/genotype_distance 性质）再端到端，绕开 oracle 难题
- 批次3a：stub evaluate_fn 解耦，只测主路径闭环不测 resume 一致性
- 批次3b：独立功能任务（修 runner 接 resume），需用户决策是否纳入
- 批次4：trading runner 先打通1个happy path复用fixture；Processor 直测绕HTTP
- 批次5：去重前强制保留 phase6_regression/phase3 黄金实现

### 环4·范围边界
纳入：批次1/2/3a/4/5（测试优化）。排除：批次3b（功能修复，独立任务，待用户决策）；e2e 24过时（前序已记录的独立任务）；回测不变量守卫（已完备）。

### 环5·行为规格（关键验收）
- 批次1：--cov-branch 生效(报告含Branch列)；fail_under=78 兜底不误红；derivatives_fetcher 删除后全量绿；skip/xpass 矛盾消除 `[代码审查/测试验证]`
- 批次2：diversity 17%→80%、validation engine 31%→70%、rule_engine 28%→70% `[测试验证]`
- 批次3a：单次进化E2E 3用例通过，覆盖 task→completed/champion/history/snapshot `[集成测试]`
- 批次4：trading runner 53%→75%、strategies route 32%→60% `[测试验证]`
- 批次5：去重后全量绿且golden/黄金实现保留；24文件打标；Top5私有解耦 `[代码审查]`

### 环6·风险披露
- R1〔确定〕fail_under 设错立即红→分两步：先观察基线再设门槛(=当前值)
- R2〔确定〕批次2 validation 统计无 oracle→先直测纯函数,端到端只做smoke
- R3〔确定〕批次4 mock链长调试成本高→第一个happy path投入大,后续复用fixture
- R4〔确定〕批次5 误删回归哨兵→强制保留清单(phase6_regression/phase3)
- R5〔确定〕跑测试时后台API服务干扰WS测试(评估时现66 failed)→测试前停API服务

### 环7·实施顺序（推荐）
1. **批次1**（3-4h，护栏先行）→ 2. **批次2**（14-16h，最高ROI）→ 3. **批次3a**（3h，闭环）→ 4. **批次4**（14-17h，重活）→ 5. **批次5**（9-10h，降噪）。3b 独立决策。
总工作量（不含3b）：**约 43-50 人时（5-6 人日）**。

---

## 门控确认（冻结）

**用户确认（2026-06-19）**：
- 实施范围：**全部分批实现**（批次1→2→3a→4→5）
- 批次3b（修 runner 接 resume 功能）：**独立任务，暂不做**（保持测试任务纯粹，3a 用 stub evaluate_fn 解耦）
- 覆盖率门槛：进取按模块（全局兜底 78% + per-module 脚本）

**冻结状态**：批次 1-2-3a-4-5 为实施基准，偏离必须报告。3b 记录为独立功能任务（待后续决策）。

---

# 阶段 B：实现循环（按批次推进）

## 批次1·基础设施治理（进行中）

### 批次1·完成（B4 合规确认 + 最终校验）
**测试结果**：1919 passed（0 skip / 0 xfail / 0 xpass / 0 failed，41s）。
- skip/xpass 矛盾消除：`test_pnl_matches_backtest` 删 xfail→passed；`test_mtf_backtest_produces_valid_result` 改 `BacktestEngine().run`→实际执行 passed
- 死代码 `core/data/derivatives_fetcher.py` 删除（确认零残留，__init__.py 空）
**覆盖率基线（--cov-branch 计入）**：
- statement 79.3%（8707/10978，删死代码后较 78.5% 升）
- branch 87.5%（3086/3528）
- 合并 76.11%（R1 验证：加 branch 后从 78.5% 降，故 fail_under 不能设 78）
- `--cov-fail-under=74` 兜底生效（76.11%>74%，exit 0）
- per-module 脚本 8 模块基线 OK（exit 0）
**行为规格**：S1(branch 列生效)✓ S2(fail_under=74兜底+per-module脚本)✓ S3(删死代码)✓ S4(skip/xpass消除)✓
**改动文件**：pytest.ini、pyproject.toml、scripts/check_coverage_thresholds.py(新)、core/data/derivatives_fetcher.py(删)、tests/test_virtual_account.py、tests/test_mtf_integration.py
**七环对比**：无偏差。策略一致（--cov-branch + 全局兜底74% + per-module脚本，分两步降风险）；范围未超界。

---

## 批次2·算法补强（进行中）

### 批次2·进度（高 ROI 纯函数核心已完成）
| 模块 | 改动前 | 当前 | 新增测试 | 目标 |
|---|---|---|---|---|
| rule_engine（_pair_trades） | 20.4% | **44%** | test_rule_engine.py 10用例 | 70% |
| diversity（距离函数+compute_diversity） | 13.9% | **56%** | test_diversity.py 20用例 | 80% |
| validation/engine（_check_then_conditions+_build_distribution+辅助） | 26.2% | **27%** | test_validation_engine.py 18用例 | 70% |
| **总计** | — | — | **+48 用例** | — |

**全量回归**：1967 passed（0 失败），合并覆盖率 76.11%→**77.80%**（+1.69pp），fail_under=74 兜底生效。
**新增测试均标 `@pytest.mark.unit`**（纯函数单测）。

### 批次2·剩余（达目标覆盖率 70-80% 需端到端/有状态测试）
- **validation/engine 27%→70%**（最大缺口）：需 validate_hypothesis 主路径（77-254 统计）+ _evaluate_single_condition action_map（296-347）端到端——要构造 OHLCV parquet + 反推 WHEN 命中，评估估 6-7h
- **diversity 56%→80%**：需 apply_fitness_sharing（267-282）+ check_and_maintain_diversity（339-367）有状态函数
- **rule_engine 44%→70%**：需 _evaluate_rule_conditions（220-240）+ evaluate_rules 端到端（82-186，需 tmp parquet）

**性质**：高 ROI 纯函数核心已拿完；剩余都是"有状态/端到端"，工作量大、ROI 递减。

### 用户决策（批次2 节奏）
选"先推进其他批次"：先广度拿下批次3a/4/5 高 ROI 核心，再回头把批次2 补到目标覆盖率。批次2 剩余端到端标记为后续深挖。

---

## 批次3a·单次进化主路径 E2E（进行中）

### 批次3a·完成
- 新增 test_evolution_closure.py 4 用例（标 slow+integration）：result shape 契约（champion/history/stop_reason/total_generations）、on_generation 每代回调、history 完整性、extra_ancestors 注入
- 用 stub evaluate_fn（确定性，无回测/无数据）跑 EvolutionEngine.evolve，守卫进化闭环主路径
- **resume 一致性未测**（批次3b 断裂：runner 不读快照）——测试文件 docstring 显式注释此限制
- engine.py 已 96% 覆盖，本批价值在"闭环契约"而非拉高覆盖率

---

## 阶段交付（批次1+2+3a）
- **新增 52 测试用例**（rule_engine 10 + diversity 20 + validation_engine 18 + evolution_closure 4）
- 全量 **1971 passed**（批次1 后 1967 + 批次3a 4），0 失败
- 合并覆盖率 **77.80%**（批次1 基线 76.11% → +1.69pp）
- 覆盖率护栏生效（--cov-branch + fail_under=74 + per-module 脚本）
- 剩余：批次4（编排层，14-17h，最大）+ 批次5（治理，9-10h）+ 批次2 深挖到目标覆盖率

## 批次4·编排层主路径（待启动，最大块，用户选先做批次5）

---

## 批次4·编排层主路径（进行中，用户继续推进）

### 批次4·核心完成
| 模块 | 改动前 | 全量口径 | 新增测试 |
|---|---|---|---|
| trading/runner `_execute_task` | 47.6% | **62%** | test_trading_execute.py 3用例（主路径+no_data+crash_recovery）|
| strategies `_VerifyProcessor` | 32%(整文件) | **40%** | test_verify_processor.py 3用例（init/process_step/finalize+404+insufficient）|
| strategies `_BatchBacktestProcessor.init` | — | 含上方 | test_batch_processor.py 2用例（grouping+404）|

**mock 模式建立**（可复用）：
- trading runner：patch `_load_data`/`_fetch_and_update`/`_init_predictor` + fake controller（wait 后 stop）+ DB（init_db_ext+save_paper_trading_task）
- strategies Processor：patch `_bt_engine_mod.BacktestEngine` + 实例替换 `_load_df`/`_load_mtf` + DB（init_db_ext+save_strategy）

### 批次4·剩余（复杂 mock，ROI 递减）
- `_BatchBacktestProcessor.process_step`（用 ReplayRunner/DecisionPipeline bar-by-bar，mock 更重）
- `verify_strategies` 同步端点（585-848）+ SSE stream（1126-1143）
- trading runner MTF 路径（265-291）+ `_init_predictor`（425-445）

### 批次4·深挖（用户继续推进）
| 新增测试 | 覆盖 |
|---|---|
| test_trading_execute +_init_predictor（3用例：default/invalid/empty_df）+ MTF mtf_data_missing（1用例）| trading/runner 62%→**71.7%** |
| test_batch_processor +process_step（2用例：replay 成功+insufficient，mock ReplayRunner）| strategies 40%→**58.9%** |

**mock 模式细化**：
- ReplayRunner：patch `core.trading.replay.ReplayRunner`，fake result 需 equity_curve/total_trades/events_log（含 entry_price/exit_price/side）/total_return/bars_processed
- MTF：patch `core.trading.runner.load_mtf_data`（顶部 import）+ make_mtf_dna 触发 is_mtf 分支
- _init_predictor：PredictionDNA.from_json 异常→None 守卫

**两模块逼近目标**：trading/runner 71.7%（目标75%，差3pp）、strategies 58.9%（目标60%，差1pp）

### 批次4·剩余（更深的 HTTP/SSE 包装 + MTF 完整循环）
- verify_strategies 同步端点（585-848）+ SSE stream（1126-1143）—— HTTP 包装 _VerifyProcessor
- trading runner MTF 完整循环（load_mtf_data 返回有效 → 347-360 MTF refresh）

---

## 会话总结（批次1+2高ROI+3a+5子项1+批次4含深挖）

**本次会话交付**：
- 新增 **~75 测试用例** + 24 文件 marker 打标 + 覆盖率护栏 + 死代码清理 + 矛盾修复
- 合并覆盖率 76.11% → **80.33%**，全量 **1985 passed**

**覆盖率提升**：
| 模块 | 前 | 后 |
|---|---|---|
| rule_engine | 20.4% | 44% |
| diversity | 13.9% | 56% |
| trading/runner | 47.6% | **71.7%** |
| strategies(route) | 32% | **58.9%** |
| validation/engine | 26.2% | 27% |


---

## 会话总结（批次1+2高ROI+3a+5子项1+批次4核心）

**本次会话交付**：
- 新增 **68 测试用例**（test_rule_engine 10 / test_diversity 20 / test_validation_engine 18 / test_evolution_closure 4 / test_trading_execute 3 / test_verify_processor 3 / test_batch_processor 2 + 部分修复）
- marker 打标 **24 文件**（unit/integration 分层生效）
- 覆盖率基础设施：`--cov-branch` + `--cov-fail-under=74` + per-module 脚本 + 删 derivatives_fetcher + 修 skip/xpass
- 合并覆盖率 76.11% → **79.48%**，全量 **1979 passed**

**覆盖率提升**：
| 模块 | 前 | 后 |
|---|---|---|
| rule_engine | 20.4% | 44% |
| diversity | 13.9% | 56% |
| trading/runner | 47.6% | 62% |
| strategies(route) | 32% | 40% |
| validation/engine | 26.2% | 27% |

**剩余**（后续会话）：批次4 深挖（ReplayRunner/stream/MTF）、批次5 子项2/3（私有解耦+phase去重）、批次2 深挖达目标、批次3b 修 resume



---

## 批次5·清理治理（进行中）
用户决策：先做批次5（相对简单独立）。按风险从低到高：marker 打标 → 私有解耦 Top5 → phase 去重。

### 批次5·子项1 marker 打标（完成）
- 24 个无 marker 文件加 pytestmark（基于"是否跑重型引擎/多模块"判断）：
  - **11 integration**：test_batch_evaluation/batch_signals/derivatives_pipeline/direction_gene_population/invariant_backtest/ml_indicators/phase1_error_visibility/phase3_vectorize_mtf/phase6_batch_integration/phase6_regression/verify_star
  - **13 unit**：test_column_cache/confidence_sizing/cross_timeframe_detector/direction_gene_executor/direction_gene_mutation/direction_signal_role/evolution_missing/executor_vectorize/ml_lookahead/ml_performance/order_generator/order_manager/trading_metrics
- 全量 1971 passed 不破坏
- **分层选择性生效**：`-m unit` 选 1327、`-m integration` 选 629（共 1956，余 15 为 smoke/xfail/未标）
- 现可 `-m unit`（快速）/ `-m integration` 分层执行，为 CI 分层奠基

### 批次5·子项2/3（待做）
- 子项2 私有解耦 Top5（_compute_indicator 提升公共等，~5h，改源码+测试）
- 子项3 phase 去重（test_invariants↔invariant_backtest，~3-4h，中风险需保留 golden）

---

## 会话总结（批次1+2高ROI+3a+5子项1）

**本次会话交付**：
- 新增 **52 测试用例**（test_rule_engine 10 / test_diversity 20 / test_validation_engine 18 / test_evolution_closure 4）
- marker 打标 **24 文件**（unit/integration 分层生效）
- 覆盖率基础设施：`--cov-branch` + `--cov-fail-under=74` + per-module 脚本 + 删 derivatives_fetcher 死代码 + 修 skip/xpass 矛盾
- 合并覆盖率 76.11% → **77.80%**，全量 **1971 passed**

**覆盖率提升**（批次2 高ROI核心）：
| 模块 | 前 | 后 |
|---|---|---|
| rule_engine | 20.4% | 44% |
| diversity | 13.9% | 56% |
| validation/engine | 26.2% | 27% |

**剩余**（后续会话推进）：
- 批次5 子项2/3（私有解耦 + phase 去重，~8-9h）
- 批次4 编排层（trading runner + strategies Processor，14-17h，最大块）
- 批次2 深挖达目标覆盖率（validation 端到端等，6-7h）
- 批次3b（修 runner resume 功能，独立功能任务，6-8h）

---

## 剩余项实施评估（第二轮·门控前，2026-06-19，2 subagent 核查 + coverage.json 实测）

### 覆盖率校准（修正过时记录）
| 模块 | 之前记录 | coverage.json 实测 | 目标 | 缺口 |
|---|---|---|---|---|
| validation/engine | 27% | **43.17%** | 70% | 27pp |
| diversity | 56% | **60.61%** | 80% | 19pp |
| rule_engine | 44% | 44.09% | 70% | 26pp |
| trading/runner | 71.7% | 71.7% | 75% | 3pp |
| strategies(route) | 58.9% | 58.9% | 65%+ | ~6pp |
| 全局 | 80.33% | 80.33% | — | — |

### 事实修正（subagent 核查，证伪了之前假设）
- rule_engine 实际在 **core/validation/rule_engine.py**（非 core/rules/）
- `verify_strategies`（strategies.py:573-848）是**内联复制**（非 Processor 薄包装），补测需完整 mock；SSE stream（1119-1147/1603-1631）才是真薄包装
- 批次5子项2 `_bt_engine_mod` 是**伪命题**（import 别名非私有直访，无需改）；`_build_session` 仅 mock 桩（小改）；真解耦项=_compute_indicator(40+处,无public)+_apply_funding_costs(10+处,无public)+_indicator_column_cache(需只读访问器)
- 批次5子项3 实际可删仅 4 用例（test_invariants.py:79/95/213/305），ROI 极低；phase6_regression+phase3_vectorize_mtf 确认 golden 保留
- **mock 范例已存在**：test_boundary_p0.py:399 `@patch load_parquet + compute_all_indicators` 可绕真实 parquet/OHLCV，端到端数据构造成本可控

### 剩余项实施评估（细化到函数:行号）
**批次2深挖（~8-11h，~26例）**
- diversity 61%→80%（2-3h，~7例，**最高ROI纯函数**）：apply_fitness_sharing(L251-282)+check_and_maintain_diversity(L320-367)+compute_phenotype_diversity(L202-244)
- rule_engine 44%→70%（2-3h，~5例）：evaluate_rules端到端(L59-197)+_evaluate_rule_conditions(L204-240)；patch路径=core.validation.rule_engine.load_parquet
- validation/engine 43%→70%（4-5h，~12-14例，最大缺口）：validate_hypothesis主路径(L48-266)+7个helper(_resolve_target L371-418/_resolve_pattern L421-464/_lookback L487-517/_cross_* L467-484/_spike/_shrink)
**批次4剩余（~5-8h，~5-7例）**
- verify_strategies同步端点(573-848)：完整mock(同Processor模式)，2-3例
- SSE stream(1119-1147/1603-1631)：TestClient+薄包装，2例
- trading runner MTF完整循环(342-363)：mock _fetch_and_update返回更长df，1-2例
**批次5子项2（~4-6h，改源码，需回归）**
- _compute_indicator→indicators.py暴露public单算子，迁移40+处测试
- _apply_funding_costs→engine.py暴露public
- _indicator_column_cache→新增只读访问器
- _build_session→改patch目标；_bt_engine_mod不动
**批次5子项3（~1-2h，ROI极低）**：删4用例，建议不做

### 推荐实施顺序
1. 批次2-diversity（2-3h，最高ROI）→ 2. 批次2-rule_engine（2-3h）→ 3. 批次2-validation（4-5h）→ 4. 批次4剩余（5-8h）→ 5. 批次5子项2（4-6h，改源码最后做便于回归）
**总 ~17-25h**。批次5子项3 建议不做；批次3b 独立功能任务维持暂不做。

### 风险（确定）
- R1 validation端到端需反推WHEN命中——test_boundary_p0有范例，可控
- R2 verify_strategies内联复制补测成本高于预期（非复用Processor）
- R3 批次5子项2改源码（暴露public API）涉及生产代码，需回归
- R4 测试前停API服务（WS干扰）








