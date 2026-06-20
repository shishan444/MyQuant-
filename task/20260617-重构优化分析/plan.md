# MyQuant 全栈重构 · 实施 Plan

> 配套推理链：`task/20260617-重构优化分析/task.md`（已冻结）
> 范围：P0 + P1 出文件级+规格级详细 plan；P2/P3 出方向与要点
> 创建：2026-06-18
> 状态：阶段 B 产出（本轮交付物 = 本文档，不落代码）

---

## 0. 执行原则与基线

**原则**：收敛式重构，每步行为不变 + 回归通过。风险升序推进（P0→P1→P2→P3）。

**禁区（任何步骤不得触碰逻辑）**：
- `core/backtest/` 数学：清算阈值 `maintenance = init_cash*(1-0.9/leverage²)`、资金费率 `RATE_PER_8H=0.001`、`shift(1)`、杠杆
- `core/trading/` 交易执行数学：订单/持仓/权益一致性
- 评分阈值语义、`prediction/` 自包含边界
- 视觉布局与交互模式（专项后续）

**回归基线（每个 P1 项完成后必跑）**：
```bash
# 后端
cd MyQuant && python -m pytest                            # 全量（含 cov core/api）
cd MyQuant && python -m pytest tests -m "unit or smoke"   # 缩小范围时
# 前端
cd MyQuant/web && npm run lint && npm run test && npm run build
```

**不变量保护约定**：涉及交易/回测/评分的项，只允许「提取/搬运/重命名」，禁止改公式数值。所有此类项在规格中标注 `[不变量·禁改数学]`。

---

# 🔴 P0 · 立即可做（S 工作量 · 零/低风险）

> 全部无行为变化（删死代码）或纯结构提取（行为等价）。可独立提交，互不依赖。

## P0-1 ｜ 前端死代码清理（11 项 + 导出 + 测试）

**目标**：清除 0 生产消费者的死代码，收敛 `components/lab/index.ts` 导出面。

**改动文件**：
- 删除：`web/src/components/lab/ConditionPill.tsx`、`ConditionPillGroup.tsx`、`TimeframeLabel.tsx`、`TimeframeSelector.tsx`、`ReferencePanel.tsx`、`ValidationConclusion.tsx`、`TriggerTable.tsx`、`TriggerDetailDrawer.tsx`、`DistributionChart.tsx`
- 删除：`web/src/components/charts/ChartLegend.tsx`
- 删除：`web/src/stores/lab.ts` + `web/src/test/stores/lab.test.ts`（79 行，测 useLabStore）
- 改：`web/src/components/lab/index.ts` —— 移除第 1、2、6、7、8、9、10、11、12 行导出（ConditionPill/ConditionPillGroup/ValidationConclusion/DistributionChart/ReferencePanel/TriggerTable/TriggerDetailDrawer/TimeframeLabel/TimeframeSelector）；**保留** SubjectDropdown/ActionDropdown/TargetInput（被 RuleConditionRow 活路径引用）、SceneModePanel/SceneResult/SceneSelector（Lab.tsx:851 活路径）、BacktestModePanel/BacktestMetricsPanel/EquityCurveChart/SaveStrategyDialog/RuleConditionRow/RuleConditionGroup

**规格**：纯删除 + 导出收敛，无新逻辑。

**验证** `[代码审查]` `[测试验证]`：
- `cd web && npm run build`（tsc -b 必须通过——证明无残余引用）
- `cd web && npm run lint && npm run test`
- grep 确认 `web/src`（排除 test）再无 ConditionPill 等符号引用

**风险与回退**：极低。回退 = git revert 单提交。

---

## P0-2 ｜ 后端 signal_builder.py 删除

**目标**：消除自声明死代码，去除 features→strategy 伪依赖环。

**改动文件**：
- 删除：`core/features/signal_builder.py`
- 删除：`tests/test_signal_builder.py`（116 行）
- 改：`core/features/registry.py:463` 注释（去掉对 signal_builder.py 的提及，保留 executor.py/indicators.py）

**规格**：纯删除。生产零 import（已验证：`registry.py:463` 仅注释提及）。

**验证** `[测试验证]`：`cd MyQuant && python -m pytest`（全绿）；`grep -rn signal_builder --include=*.py`（仅余注释或空）。

**风险**：极低。

---

## P0-3 ｜ 流式 Hook 去重（createStreamHook 工厂）

**目标**：消除 `useVerifyStream`/`useBatchBacktestStream` ~100 行逐行重复（`hooks/useStrategies.ts:104-302`）。

**改动文件**：
- 新建：`web/src/hooks/createStreamHook.ts`
- 改：`web/src/hooks/useStrategies.ts` —— 两个 hook 改为薄封装调用工厂

**实现级规格**：
```typescript
// createStreamHook.ts
interface StreamHookConfig<TPayload, TProgress, TComplete, TState> {
  streamFn: (payload: TPayload, callbacks: StreamCallbacks<TProgress, TComplete>, signal: AbortSignal) => void;
  errorLabel: string;                 // "验证失败" | "批量回测失败"
  // verify 独有：onComplete 时 invalidate verify-sessions + state 带 sessionId
  onCompleteExtra?: (data: TComplete, qc: QueryClient) => void;
  withSessionId?: boolean;            // true→state 含 sessionId 字段
}
export function createStreamHook<TP, TPr, TC>(config: StreamHookConfig<TP, TPr, TC>) {
  // 内含：abortRef/cancelledRef/state(start/cancel/reset) + callbacks 模板
  // toast.error(`${config.errorLabel}: ${message}`, {duration: Infinity})
  // withSessionId 时 state 加 sessionId，onComplete 设 data.session_id
  // onCompleteExtra?.(data, qc) 在 onComplete 内调用
  return () => { /* 返回 {...state, start, cancel, reset} */ };
}
// useStrategies.ts
export const useVerifyStream = createStreamHook({
  streamFn: (p, cb, s) => api.verifyStrategiesStream(p, cb, s),
  errorLabel: "验证失败", withSessionId: true,
  onCompleteExtra: (_d, qc) => qc.invalidateQueries({ queryKey: [...strategiesKeys.all, "verify-sessions"] }),
});
export const useBatchBacktestStream = createStreamHook({
  streamFn: (p, cb, s) => api.batchBacktestStream(p, cb, s),
  errorLabel: "批量回测失败",
});
```
**4 处差异已参数化**：sessionId / onComplete invalidate / toast 文案 / streamFn。两 hook 导出名保留（消费方零改动）。

**验证** `[测试验证]`：`npm run test`（`test/hooks/useStrategies` 若有则保留；现有 useTradingWebSocket 等测试不变）；`npm run build`。

**风险**：低。回退 = 保留旧实现直到新工厂测试通过再切换。**注意**：verify 的 `qc` 依赖通过 `useQueryClient()` 在工厂内获取。

---

## P0-4 ｜ toTime helper 抽取

**目标**：消除 `KlineChart.tsx:88-95` 与 `EquityCurveChart.tsx:9-16` 一字不差的时间转换重复。

**改动文件**：
- 新建或在 `web/src/components/charts/core/` 加 `time.ts`（与现有 `chartThemes.ts`/`useChartSync.ts` 同层）
- 改：`KlineChart.tsx`、`EquityCurveChart.tsx` 删除本地 toTime，改 import

**规格**：`export function toTime(ts: number | string): Time` —— 实施前读两处确认入参类型与 lightweight-charts `Time` 类型一致后统一。

**验证** `[测试验证]` `[代码审查]`：`npm run build`；人工核对两处调用入参未变。

**风险**：极低。

---

## P0-5 ｜ EquityCurve 格式化复用 lib/utils

**目标**：`components/trading/EquityCurve.tsx:22,26` 私有 `formatTime`/`formatMoney` 改用 `lib/utils.ts` 的 `formatDateTime`/`formatCurrency`。

**改动文件**：`web/src/components/trading/EquityCurve.tsx`

**规格**：删除私有函数，替换调用点。**附带**：评估 `lib/utils.ts:27 formatPercent`（入参小数）与 `:40 formatPercentValue`（入参已百分数）命名混淆——若同文件改动成本低则加注释区分，否则记入后续。

**验证** `[代码审查]`：`npm run build`；核对 recharts tick formatter 输出格式不变。

**风险**：低（注意金额/时间显示格式与原私有函数一致）。

---

## P0-6 ｜ OptionDropdown 合并（SubjectDropdown / ActionDropdown）

**目标**：`SubjectDropdown.tsx:105` 与 `ActionDropdown.tsx:133` 同构的「trigger button + DropdownPortal + 分组 options」合并为通用组件。

**改动文件**：
- 新建：`web/src/components/lab/OptionDropdown.tsx`
- 改：`SubjectDropdown.tsx`（带搜索+分类）、`ActionDropdown.tsx`（带分类）改为基于 OptionDropdown 的薄封装

**规格**：
```typescript
interface OptionDropdownProps<T> {
  value: T; options: OptGroup[];        // 分组 options
  onSelect: (v: T) => void;
  searchable?: boolean;                 // SubjectDropdown true, ActionDropdown false
  triggerLabel?: (v: T) => string;
  // 复用现有 DropdownPortal
}
```
**保留** `getSubjectLabel`/`getActionLabel` 导出（RuleConditionRow 活路径用）。

**验证** `[代码审查]` `[测试验证]`：`npm run build && npm run test`；Lab 页面条件下拉视觉与交互不变（专项视觉后续，本步只保等价）。

**风险**：低。注意 `ConditionPillGroup.tsx:41` 的 AndOrConnector 引用——但 ConditionPillGroup 已在 P0-1 删除，此处引用随之消失。

---

## P0-7 ｜ discovery.ts 接入 Axios 实例

**目标**：`services/discovery.ts:65,88,111` 原生 `fetch` 绕过 `api.ts:22-42` 的 422 拦截器，错误格式全局不一致。

**改动文件**：`web/src/services/discovery.ts`

**规格**：将 `fetch(url)` 替换为 `api.get/post`（与 `services/strategies.ts` 同模式）。**注意**：若 discovery 用 SSE/流式响应，axios 流式处理与 fetch 不同——实施前读 `:65,88,111` 确认是否流式；流式则保留 fetch 但统一错误抛出格式为 `ApiError`（对齐 `api.ts` 拦截器输出）。

**验证** `[代码审查]`：`npm run build`；核对 discovery 接口 422 错误经统一格式化（sonner toast 文案与其他 service 一致）。

**风险**：低-中（流式兼容性是唯一风险点，实施前必须确认）。

---

# 🟠 P1 · 应做（M 工作量 · 低-中风险）

> 涉及跨模块搬运或契约变更，每项需完整回归。建议逐项独立提交。

## P1-1 ｜ runner 评估逻辑归位 core/evolution

**目标**：把 `api/runner.py:773-1010` 的进化评估核心（`_evaluate_dna`/`_evaluate_population`/`_build_requirements`）移入 `core/evolution`，提供 default 实现。runner.py 从 1021 行降至 ~400 行（只剩线程/心跳/恢复/WS 推送）。

**依据**：`engine.py:186,191` 的 `evolve()` 已设计为接受 `evaluate_fn`/`evaluate_population` 回调注入——评估逻辑本应在 core 提供 default。

**改动文件**：
- 新建：`core/evolution/evaluation.py`（或并入现有合适模块）
  ```python
  def build_default_evaluate_fn(requirements: EvalRequirements) -> Callable[[StrategyDNA], float]: ...
  def build_default_evaluate_population_fn(requirements: EvalRequirements) -> Callable[[List[StrategyDNA]], List[float]]: ...
  ```
- 改：`api/runner.py` —— 删除 `_evaluate_dna`/`_evaluate_population`/`_build_requirements`，改为从 core 导入并注入 `engine.evolve(evaluate_fn=..., evaluate_population=...)`
- `EvalRequirements` 数据类承载原 `_build_requirements` 的产物（杠杆覆盖、回测参数、评分模板等）

**验证** `[测试验证]` `[集成测试]`：
- `python -m pytest tests -m "unit or integration"`（evolution/runner 相关）
- **关键**：跑一次完整进化任务，对比 champion DNA 与 score 与重构前 baseline 一致（行为不变验证）
- 评估函数是进化核心，回归不通过不得合入

**风险**：中。`_execute_task`(`runner.py:316-700`) 含连续进化循环/冠军提取/模板注入，搬运时需保持调用顺序与 WS 推送时机不变。**回退**：保留旧函数到独立 PR 验证后再删。

---

## P1-2 ｜ compute_trading_metrics 归位 core/scoring

**目标**：`api/db_ext.py:915-1001`（`_compute_equity`、`compute_trading_metrics`）是 trading 域数学错位到 persistence，移入 `core/scoring` 或 `core/trading`。

**改动文件**：
- 新建/并入：`core/scoring/trading_metrics.py`（或 `core/trading/metrics.py`）
  ```python
  def compute_equity(balance, margin, unrealized_pnl) -> float: ...   # 原 _compute_equity
  def compute_trading_metrics(equity_snapshots) -> TradingMetrics: ... # win_rate/profit_factor/max_drawdown
  ```
- 改：`api/db_ext.py` —— 删除数学函数，保留 SQL 读写；CRUD 处改为调用 core 函数

**规格** `[不变量·禁改数学]`：`equity = balance + margin + unrealized_pnl`（`db_ext.py:915-921`）与 `core/trading/account._equity` 同源——归位后两处共享，杜绝数值漂移。drawdown/profit_factor 算法逐字搬迁，不改。

**验证** `[测试验证]`：`python -m pytest`；对比 trading metrics 输出与重构前一致。

**风险**：低-中（纯搬迁，但跨 persistence/scoring 边界，注意 import 方向：scoring 不应反向依赖 db_ext）。

---

## P1-3 ｜ persistence 统一（公开 connect + 消除裸 SQL + _connect）

**目标**：消除三套 DB 访问，trading 不再抓私有 `_connect`。

**改动文件**：
- 改：`core/persistence/db.py` —— `_connect`(db.py:23) 公开为 `connect(db_path)`（保留 WAL/synchronous/busy_timeout/row_factory）；新增 `transaction(db_path)` 上下文管理器（commit/rollback）
- 改：`core/trading/runner.py:81,147,157` —— `from core.persistence.db import _connect` → `connect`；ad-hoc SQL 收敛为 persistence 层方法（如 `save_trade`/`save_equity_snapshot`）
- 改：`api/runner.py:279,469,530,549,715,744`、`api/routes/evolution.py:579` —— 7 处裸 `sqlite3.connect`+`UPDATE` 收敛为 persistence 方法调用
- `api/db_ext.py` 的 paper-trading/strategy CRUD 评估是否也走统一 `connect`（可分阶段）

**规格**：所有 DB 写入单点经 persistence。trading 不再感知 SQL（符合 `模拟交易.md:14-19` 声明）。

**验证** `[测试验证]` `[集成测试]`：`python -m pytest`；跑模拟交易任务验证 trade/equity 快照持久化正常；进化任务 progress 更新正常。

**风险**：中。裸 SQL 散落 8+ 处，收敛需保证每处事务语义（commit 时机）不变。**建议**：分两步——先公开 `connect` 替换 `_connect` 引用（低风险），再逐步收敛裸 SQL（逐处验证）。

---

## P1-4 ｜ 类型契约对齐（types/api.ts ↔ schemas.py）

**目标**：消除前后端契约漂移，减少运行时 422，evolution 产出 DNA 字段不丢。

**改动文件**：
- 改：`web/src/types/api.ts:26-32 RiskGenes` —— 补 `sl_mode: "pct" | "atr"`、`atr_period: number`（对齐 `schemas.py:111-112`）
- 改：`web/src/types/api.ts:14-19 LogicGenes` —— `add_logic`/`reduce_logic` 由可选改必填（对齐 `schemas.py:92-93` 默认 "AND"），或确认前端可选的合理性后保留并在 docs 标注
- 改：`web/src/types/api.ts:4 SignalGene.role` —— 联合补 `"direction"`（对齐后端 `SignalRole` 含 DIRECTION，实施前读 `schemas.py:50` 确认完整枚举）
- 改：消费 RiskGenes/LogicGenes 的组件（`components/lab/SeedConfigForm`、`lib/dna-generator.ts`、`pages/Lab.tsx:413-434` 手搓 DNA 路径）—— 补 sl_mode/atr_period 默认值处理

**规格**：契约字段一一对应；前端类型不得比后端窄（漏字段=数据丢失风险）。

**验证** `[测试验证]` `[代码审查]`：
- `cd web && npm run build`（tsc 通过）
- `npm run test`（dna-generator/strategy-utils/type-contracts 测试）
- 后端 `python -m pytest tests/test_schemas*`（若有）
- **关键路径**：Lab 构建策略 → 提交后端 → 回读，确认 sl_mode/atr_period 往返不丢

**风险**：中。补字段联动 Lab.tsx 手搓 DNA 与表单，需保视觉不变。`SignalGene.condition` 前端强类型 vs 后端 dict 的差异**保留**（前端更严格是优势），仅确保联合覆盖后端所有 condition type。

**回退**：分字段提交（先 sl_mode/atr_period，再 LogicGenes，再 role）。

---

## P1-5 ｜ query error 状态补全（Trading / Strategies）

**目标**：两个高频页面网络失败时静默停留 loading，补 query error 分支（docs 错误处理要求）。

**改动文件**：`pages/Trading.tsx`、`pages/Strategies.tsx`

**规格**：
- 使用 React Query 的 `isError`/`error` 状态，渲染复用现有 `components/ErrorBoundary` 或新增轻量 `<ErrorState>`（与 EmptyState 对称）
- error 文案经 `api.ts` 422 格式化（已有拦截器），展示 + 「重试」按钮（`refetch`）
- 不改数据流，只加 UI 分支

**验证** `[代码审查]` `[测试验证]`：`npm run test`（Trading/Strategies 测试补 error 用例）；人工 mock 网络失败确认有可见反馈。

**风险**：低（加分支不改数据流）。注意与现有 mutation toast（sonner）不重复打扰。

---

# 🟡 P2 · 架构债（方向与要点 · M-L 工作量 · 中风险）

> 本轮给出方向，细化 plan 留待确认后展开。每项需独立 PR + baseline 对比。

## P2-1 ｜ 回测流水线合并
- **现状**：`api/routes/strategies.py` 回测流水线复制 5 次（`:237,431,611,900,1304`）
- **方向**：抽 `core/services/backtest_service.run_and_score(dna, params) -> BacktestResult`，含 metrics 兜底组装（R4）、方向标签映射（R7）、`_bars_per_year`（R6）；路由改为调用 service
- **要点**：5 副本含流式（_VerifyProcessor/_BatchBacktestProcessor）与同步差异，合并前**逐副本 diff**，流式路径保留为 service 的流式变体；**baseline 指标逐字节对比**
- **预期收益**：strategies.py 1779→<800 行

## P2-2 ｜ 迁移单轨化
- **现状**：`migrations/*.sql`(7) + `db_ext.py:69-330`(~30 函数) + `db.py:32-81` 三轨
- **方向**：选定 migrations/*.sql 为单一真相，db_ext 的 `_apply_*` 改为执行迁移或删除；保证 `init_db_ext` 幂等
- **要点**：需迁移存量库；缺 007 的原因需查清

## P2-3 ｜ data→features 反向依赖修复
- **现状**：`core/data/mtf_loader.py:55,93` 调 `core.features.compute_all_indicators`（违反 `数据层.md:17`）
- **方向**：mtf_loader 只返回 raw OHLCV（含 MTF 拼装），指标计算上移到调用方（trading/strategy/evolution）在拿到 df 后自行 compute_all_indicators
- **要点**：影响面广（所有消费 mtf_loader 的模块），需逐调用方调整；data 层可独立测试是收益

## P2-4 ｜ chart-settings 单数据源
- **现状**：`stores/chart-settings.ts:145`(localStorage) 与 `pages/Settings.tsx:399`(写后端) 双写，刷新不回填→漂移
- **方向**：二选一——推荐后端为单一源（Settings 写后端，前端启动时从后端拉取回填 store），或纯前端 localStorage（删除后端 chart_indicators 接口）
- **要点**：需定刷新时回填策略；与 KlineChart 的 store+props 双通道驱动（`KlineChart.tsx:155` + `useChartIndicators.ts:81`）协同考虑

---

# 🟢 P3 · 锦上添花（方向 · L 工作量 · 中高风险）

## P3-1 ｜ Lab.tsx backtest 配置态下沉
- `pages/Lab.tsx`(1155 行) 的 10 个 backtest useState（`:122-140`）+ 整块 JSX（`:528-846`）+ ref 命令式调用（`:804`）下沉到 `BacktestModePanel`；消除 props+ref 混合
- 保视觉不变；与视觉专项协同

## P3-2 ｜ KlineChart 拆分
- `components/charts/KlineChart.tsx`(959 行, 11 useRef) 拆为图例/MTF/annotation 子模块
- lightweight-charts 命令式 API，拆分需谨慎保渲染时序

## P3-3 ｜ operators.py 表驱动化
- `core/evolution/operators.py`(780 行) 15 个结构相似的 `mutate_*` 收敛为表驱动
- **[不变量·禁改数学]** 变异算子是进化核心，需回归对比 champion 分布

## P3-4 ｜ 杠杆风险数学抽公共常量
- `account.py:313,322-323`、`position.py:231`、`backtest/engine.py:100-101` 的清算阈值/资金费率公式抽公共常量/纯函数
- **[不变量·禁改数学]** 纯提取（`RATE_PER_8H=0.001`、`0.9` 维持保证金系数、`hours_per_bar` 表单点定义），单元测试锁定输出

---

# 执行顺序与里程碑

| 里程碑 | 内容 | 风险 | 退出标准 |
|--------|------|------|----------|
| **M0** | P0-1～P0-7（7 项，全部 S） | 零/低 | pytest 全绿 + web lint/test/build 全绿；死代码清零 |
| **M1** | P1-5（query error）+ P1-4（类型契约，分字段） | 低-中 | 契约往返不丢字段；error 有可见反馈 |
| **M2** | P1-2（metrics 归位）+ P1-1（runner 归位） | 中 | 进化 champion baseline 对比一致；trading metrics 一致 |
| **M3** | P1-3（persistence 统一，分两步） | 中 | DB 写入单点；trading 不感知 SQL |
| **M4** | P2（架构债，逐项独立 PR） | 中 | 各项 baseline 对比 |
| **M5** | P3（与视觉专项协同） | 中高 | 视觉不变 + 复杂度下降 |

**建议**：M0 可一次性合入（低风险高收益）；M1-M3 逐项独立提交、每项完整回归；M4/M5 待专项确认。

---

# 风险登记册

| ID | 风险 | 影响 | 缓解 | 状态 |
|----|------|------|------|------|
| R1 | 回测流水线 5 副本合并致结果漂移 | 高（核心业务） | 逐副本 diff + baseline 逐字节对比；流式保留为变体 | P2 阶段处理 |
| R2 | 类型契约补字段联动 Lab 手搓 DNA | 中 | 分字段提交；往返测试 sl_mode/atr_period | P1-4 |
| R3 | data→features 修复影响面广 | 中 | 逐调用方调整；data 层独立测试 | P2-3 |
| R4 | runner 评估搬运破坏进化行为 | 高 | 保留旧函数独立验证后再删；champion 对比 | P1-1 |
| R5 | persistence 裸 SQL 收敛改事务语义 | 中 | 分两步（先 connect 后 SQL）；逐处验证 commit 时机 | P1-3 |
| R6 | discovery 流式与 axios 不兼容 | 低-中 | 实施前确认是否 SSE；流式则统一错误格式而非换 axios | P0-7 |
| R7 | operators 表驱动影响 champion 分布 | 中 | 回归对比 champion 分布；[不变量·禁改数学] | P3-3 |

---

_本 plan 为阶段 B 实施基准。落地时每项偏离推理链须报告。交易/回测/评分不变量为硬约束。_
