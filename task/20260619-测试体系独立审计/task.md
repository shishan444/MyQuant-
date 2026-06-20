# MyQuant 测试体系独立审计报告

## 任务定义
从零独立审计 MyQuant 测试体系——**不信任任何既有结论（"1985 passed / 80.33% 覆盖率 / 各批次完成"）**，核实测试框架与用例是否真正守护工程的核心能力、关键不变量和全流程。产出完整审核意见供用户确认。

> 注：本审计由用户主动发起，明确表达"对以前的结果不信任"。前序会话正是做这些测试优化的执行方，本次审计以外部审计员视角，含自我批判。

## 审计方法
2 subagent 独立核实（A=能力守护+不变量验证；B=全流程覆盖+测试有效性）+ 主 agent 核实基础设施。**交叉印证**，每条结论附 文件:行号 证据，禁止引用既有结论。

---

## 量化基线（独立核实 coverage.json，非既有结论）
- **行覆盖 80.3%**（9180/10978）
- **分支覆盖 70.1%**（10 个百分点差距 = "测了直线代码、没测有状态分支"的直接量化）
- 1990 个测试函数，129 测试文件，92 个 core 源文件
- 前端 vitest 25 个测试文件；e2e playwright 6 个文件（**conftest 不启动服务，依赖外部 localhost:5173**）
- 覆盖率门槛 `pytest.ini:6 --cov-fail-under=74` **只盯行覆盖，无视分支覆盖**——制度性纵容"纯函数刷数字"

---

## 核心结论
**80% 行覆盖率是系统性高估的数字，不构成测试有效性的证据。** 测试体系在**纯函数 / 工具函数 / 错误路径**上投入过重，而在**有状态主循环、跨环节衔接、端到端业务契约、进化有效性、中断恢复**这五个真正决定产品质量的维度上存在系统性盲区。最危险的是：这些盲区被高覆盖率数字 + 误导性文件名（`test_evolution_effectiveness` / `test_evolution_closure` / `tests/e2e`）共同掩盖。

---

## 一、能力守护矩阵（对照 docs/AI_CODING_GUIDE.md §1 八大能力）

| # | 能力 | 守护质量 | 关键证据 / 缺口 |
|---|---|---|---|
| 1 | 策略DNA构建与校验 | **中** | test_dna.py roundtrip 只断言 strategy_id/gene数/entry_logic/stop_loss（:172-179），**未逐字段断言全等**；validator 拒绝无效 role/condition 强（test_evolution_validator.py:220-227）。strategy 模块边界干净（红线通过）。 |
| 2 | 技术指标与信号执行 | **中** | ML lookahead 守护被 `if not np.isnan` 包裹（test_ml_lookahead.py:39/80）掩盖指标实现问题；shift(1) 守护是**假阳性**（见不变量2）。 |
| 3 | 策略回测与评分 | **强** | test_invariant_backtest.py:68-105 钉死"费用/滑点不随杠杆二次方放大"bug，断言 ratio<1.1、Return(L)/Return(1)==L 精确到0.01。SL/TP 基于 HIGH/LOW 正反向齐全。 |
| 4 | 遗传进化搜索 | **中（调度强/产出弱）** | test_evolution_closure.py 全程 stub evaluate（:56），只验调度骨架**不验 DNA→回测→评分真实链路**。**进化"有效性"零验证**（见盲区2）。 |
| 5 | 假设验证与模式发现 | **中** | Wilson 置信区间/lift 守护完整（test_discovery.py:74-200），单元级合理。 |
| 6 | 价格区间预测 | **中** | 时序泄漏守护强（test_train_test_split.py:37-50），各子模块有专测。 |
| 7 | 模拟纸盘交易 | **中（崩溃恢复强/实时执行弱）** | 崩溃恢复+状态恢复断言强（test_trading_runner.py:102-162）；但实时 SL/TP 触发、资金费率累计在纸盘层端到端守护未见专项。 |
| 8 | 前端可视化与任务管理 | **弱** | e2e conftest **不启动服务**，6 文件全依赖外部手动起服务，无服务环境无法运行，守护接近"契约文档"。 |

---

## 二、关键不变量验证清单（对照 §5，审计核心）

| 不变量 | 有无测试 | 断言强度 | 缺口 |
|---|---|---|---|
| 未来函数/数据泄漏 | 有 | 中 | test_phaseE_direction_shift.py:119-157 真守护但终态断言仅 `equity>100000`（弱）；ML lookahead 被 NaN 跳过掩盖 |
| **shift(1) 信号延迟** | 有 | **弱·假阳性** | **test_signal_delay.py:88-97 调 `engine._build_portfolio` 后变量 pf 从未使用**，断言全打在手动 `sig.shift(1)`——**只验证了 pandas shift 函数，未验证 BacktestEngine 真用延迟信号** |
| HIGH/LOW 止损止盈 | 有 | **强** | test_sltp_edge_cases.py 正反向断言齐全（SL@LOW=94 equity<99900、LOW=96不触发、short@HIGH、TP@HIGH/LOW） |
| 手续费/滑点 | 有 | **强** | test_fee_slippage.py + test_invariant_backtest.py:68-130，钉死二次方放大 bug |
| 资金费率 | 有 | **强** | test_funding_edge_cases.py：1x零费、开仓才计费、按比例0.5期非ceil |
| 杠杆 | 有 | **强** | Return(L)/Return(1)==L 精确到0.01 |
| 清算 | 有 | **中·断言弱化** | 多数强（result.liquidated True），但 test_sltp_edge_cases.py:330-343 + test_liquidation_edge_cases.py:155-175 注释承诺验证清算/entry_price重置，**实际只断言 equity<100000**（断言与意图脱节） |
| 崩溃恢复/状态机/心跳 | 有 | **强** | test_trading_runner.py:102-162、test_evolution_arch.py:124-396（stale任务/heartbeat/协作式取消）|
| **进化 resume** | **无·死代码** | — | **重大盲区（见盲区1）** |
| **WS 跨线程安全** | **无** | — | **重大盲区（见盲区3）**；test_ws_trading.py 无 threading 字样，全 MagicMock |
| 策略DNA全链一致 | 部分 | **弱** | 无"to_json→DB→读出→executor翻译→backtest执行"全链字段一致测试 |
| 协作式取消 | 有 | **强** | stop_check 三层传播有断言（test_stop_check.py 356行） |

---

## 三、全流程覆盖图（核心业务流程，断裂点）

流程：数据获取 → 指标 → 信号 → 回测 → 评分 → 进化搜索 → 冠军产出 → 持久化 → 模拟交易

| 环节 | 实测行/分支覆盖 | 断裂点 |
|---|---|---|
| 数据获取 | 70.7% | - |
| 指标计算 | 95.7% | （表观健康，纯函数）|
| 信号生成 | — | 散落 |
| **回测 engine** | **63.1%/48.3%** | funding循环/leverage放大/多列降级/except:pass 吞异常 未测 |
| 评分 | 93.3% | - |
| **进化 engine** | **94.6%/90.6%** | **自适应boost/异常回退/种群补齐 missing_lines[330,333,334,385,386,395]，自适应性未验证** |
| 冠军产出 | — | - |
| **持久化** | 81.2% | **snapshot 写有测、resume 读是孤儿** |
| **模拟交易 runner** | **52.8%** | **冠军→交易完全断裂** |
| **编排 api/runner** | **53.7%/26.8%** | **happy path 几乎裸奔**（test_runner.py 8个测试全错误路径）|

---

## 四、§7 红线发现（"为通过而弱化测试"）

1. **【最严重】静默吞 checkpoint 写入异常** — `api/runner.py:496-509`：`save_snapshot` 包在 `try:...except Exception: pass`，任何快照写入失败被静默吞、无日志。checkpoint 单测（test_persistence.py:148）直接调 save_generation 绕过此 try/except，**该失败路径零守护**。
2. **断言与意图脱节** — test_sltp_edge_cases.py:330-343 / test_liquidation_edge_cases.py:155-175：测试名/注释承诺验证清算/字段重置，实际退化为 `equity<100000`。这是 §7"降低校验"的隐蔽形态。
3. **28 处 `pytest.skip("No trades generated")`** — test_invariants(10)/invariant_backtest(6)/fee_slippage(5)/funding(3)等。多数测试已 `_force_entry_exit` 强制注入信号，理论上必产生交易——skip 触发即 engine 丢弃信号（本身是 bug 信号），被 skip 掩盖。
4. **假阳性守护** — test_signal_delay.py:88-97：构建 portfolio 后丢弃，断言全打在手动 shift。**测试通过 ≠ engine 真用延迟信号**。
5. **mock 截断核心链路**：
   - test_evolution_flow.py:151 `patch load_and_prepare_df return_value=None` → 进化链路根本没执行
   - test_api.py:253-286 mock BacktestEngine + score_strategy → 评分端点核心全替换，只验 HTTP 200
   - test_backtest_e2e_consistency.py:188/267/328/403 `patch BacktestEngine.run` 强制 liquidated → 真实爆仓路径未验
   - test_evolution_closure.py:40 stub_evaluate → 进化闭环不含真实回测（作者自认）

---

## 五、最严重的测试守护盲区（按危险度排序）

### 盲区1：进化 resume 是死代码（两个 agent 独立印证）
- `core/persistence/checkpoint.py:54` 实现 resume_evolution，但 `api/runner.py` grep 无生产调用
- `resume_evolution:68` 要求 `status=="running"`，与崩溃恢复改 `stopped` **逻辑互斥**（死锁）
- test_evolution_closure.py:11 注释自认"resume not tested, would assert a known failure"
- **风险**：进化跑数小时崩溃后声称可续跑，**实际每次从第0代重跑**。这是工程核心卖点（遗传进化）的可用性盲区，checkpoint 单测全绿给了虚假信心。

### 盲区2：进化"有效性"与"自适应性"双重零验证（最高危）
- **有效性**：test_evolution_effectiveness.py 名为"有效性"，实际是**策略模板 schema 静态校验**（0 强数值断言）。没有任何测试验证"跑N代后冠军 fitness 真的比初始策略好"。**这是量化进化工具存在的根本意义，却无任何守护。**
- **自适应性**：engine.py missing_lines[330,333,334]（boost>1.0/<1.0 变异权重自适应）完全未测。94%覆盖率掩盖了"自适应算法本身是否工作"。

### 盲区3：WS 跨线程推送零守护
- §5 明确要求"WS 跨线程安全不可简化"，但 test_ws_trading.py 无 threading 字样，test_evolution_arch.py:408-470 WS 全 MagicMock 替换真实 _push_ws/ConnectionManager。
- runner 后台线程跑进化 ↔ FastAPI async loop 推 WS 的真实并发交互**零守护**。

### 盲区4：numba njit 核心路径组合分支黑盒
- `core/backtest/engine.py:205-298` order_func_nb（SL@LOW/TP@HIGH/清算优先/清算后停交易）整块 coverage 100% missing（@njit 编译无法追踪）。
- 组合分支（清算与SL同bar优先级、short+高杠杆+滑点+资金费同时作用、清算后剩余资金再开仓）无守护。配合盲区清算断言弱化，组合 bug 大概率测不出来。

### 盲区5：编排层 happy path 裸奔 + 冠军→交易断裂
- api/runner.py 53.7%/26.8%分支，test_runner.py 8个测试**全是错误路径**，正常任务完整执行零守护。
- **冠军→模拟交易无衔接测试**：grep 无任何测试同时覆盖 champion + trading。进化写 evolution_task 表，交易读 paper_trading_task 表，"进化冠军能否正确驱动交易"这一产品关键流程完全无测试。

---

## 六、测试基础设施健康度
- skip/xfail marker：**0 个文件**（之前的 xfail 修复干净）
- 但函数内 `pytest.skip("No trades")` 28处（见红线3）
- slow marker 仅 1 个，但 grep "slow" 命中 8 文件（**慢测试大量未标 slow，CI 分层失效**）
- conftest 仅 4 fixture，autouse clear_indicator_cache 暴露**全局缓存隔离痛点**
- e2e 不进默认 coverage（独立 pytest_e2e.ini），80% 完全不含前后端 E2E

---

## 七、审核结论

### 强项（客观肯定）
- **单变量不变量守护质量高**：费用/滑点的二次方放大 bug、HIGH/LOW 止损、协作式取消、崩溃恢复状态机——这些是真正有价值的守护，断言强。
- 纯函数模块（indicators/scoring/db）覆盖健康且表观≈实际。
- skip/xfail marker 干净，无 marker 层面的"为通过而跳过"。

### 系统性盲区（5 个维度）
1. **有状态主循环未测**：进化自适应性、回测 funding/leverage、trading runner happy path
2. **跨环节衔接断裂**：冠军→交易、进化→真实回测评分
3. **端到端业务契约缺失**：进化有效性、DNA 全链一致
4. **中断恢复死代码**：进化 resume（接线断裂）
5. **并发/组合黑盒**：WS 跨线程、njit 组合分支

### 最危险的认知陷阱
**"单测全绿" + 高覆盖率数字 + 误导性文件名（effectiveness/closure/e2e）= 虚假信心。** §5 列出的"不可简化"项（WS 跨线程、崩溃恢复、状态机）恰恰是盲区集中处。

### 建议（待用户确认后再细化优化方案）
- 优先级应从"拉覆盖率"转向"补能力契约 + 端到端不变量"
- §7 红线第1条（api/runner.py:508 静默吞异常）应立即修复
- 覆盖率门槛应纳入分支覆盖（`--cov-fail-under` 配合分支门槛）
- 盲区1（resume 死代码）是功能缺陷，补测前必须先修功能
