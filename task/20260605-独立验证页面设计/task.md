# 独立策略验证页面设计与清理

## 任务目标
1. 清理策略库页面（Strategies）中不合理的内容：VerifyDrawer、批量验证按钮、勾选验证流程
2. 规划设计独立的策略验证页面：全量策略自动验证、参数配置、运行状态展示、结果排名、历史记录

## 用户意图
- 策略验证是独立功能，不应嵌入策略库页面
- 验证对象是策略库中所有策略，无需手动选择
- 需要完整的产品视角：参数配置、运行时状态、结果报告、历史记录

## 初始理解
- 现有 VerifyDrawer 是嵌入 Strategies 页面的抽屉式组件，需移除
- 现有后端 /api/strategies/verify 端点可复用/扩展
- 新页面需要路由、导航入口、完整页面布局
- 验证历史需要持久化存储方案

## 状态
- 阶段：B1 准备（推理链已冻结）
- 冻结确认：用户同意推理链，2026-06-05

---

## 研究第 1 轮

### 任务结构性理解

**前端架构**：6 页 SPA，路由定义在 App.tsx:22-35，导航由 Sidebar.tsx 的静态 NAV_ITEMS 数组驱动。页面组件位于 pages/ 目录，每个页面组合 hooks/services/components 三层。当前验证功能完全嵌入 Strategies 页面：
- VerifyDrawer (components/strategies/VerifyDrawer.tsx) 仅被 Strategies.tsx 引用
- 通过 verifyTargets 状态 + 批量勾选 + "策略验证"按钮触发

**后端架构**：POST /api/strategies/verify (strategies.py:529-787) 是完整可用的端点。按 symbol/timeframe 分组策略，双层循环（group × data_range），调用 BacktestEngine.batch_run + compute_fitness，计算综合评分（avg_fitness × qualified_ratio × consistency_bonus），降序排序返回。

**已发现的关键 Bug**：save_backtest_result (db_ext.py:1183-1206) 的函数签名和 INSERT 语句不含 fitness/qualified/satisfaction_json 列，但 verify 路由 (strategies.py:684-688) 传递了这些参数 → TypeError → 被 except (line 713) 捕获 → 验证结果不持久化，且该策略该区间在 results 中显示为 error。

**数据存储层**：backtest_result 表有 fitness/qualified/satisfaction_json 列（通过 _apply_fitness_columns 程序化添加，db_ext.py:137-141），但 save_backtest_result 函数未更新 INSERT 语句，导致这些列始终为默认值。

### 任务认知变化

初始理解："这是一个前端页面重构任务"。
更新认知：**不仅仅是前端重构**。发现的 save_backtest_result bug 意味着验证结果从未被正确持久化，这直接影响了"历史记录"功能的基础。如果不修复此 bug，独立验证页面的历史功能将建立在空中楼阁上。

因此任务范围应扩展为：
1. 前端清理（Strategies 页面移除验证 UI）
2. 后端修复（save_backtest_result 函数）
3. 前端新建（独立验证页面）
4. 可能需要新增 verify_session 概念用于历史记录

### 待消解的不确定性

1. **verify_session 的必要性**：用户提到"运行记录报告"——是否需要新增 verify_session 表来分组管理验证历史？还是复用 backtest_result 中 run_source="verify" 的记录即可？→ 需要研究用户对"历史"的期望深度
2. **全量验证的性能**：全量策略 × 多时间区间的 batch_run 耗时如何？是否需要异步/后台任务模式？→ 当前 120s 超时是否足够？→ 需要了解策略库规模
3. **验证页面的导航位置**：策略库和模拟交易之间？还是有更好的位置？

### 决策

继续研究 — 需消解不确定性 1（verify_session 设计）和 2（性能/异步模式）。不确定性 3 可在推理链中直接决策。

---

## 研究第 2 轮

### 任务结构性理解（更新）

**历史存储方案确认**：不需要新增 verify_session 表。
- `list_backtest_results(db_ext.py:1238-1270)` 已支持 `run_source="verify"` 过滤
- backtest_result 表有 fitness/qualified/satisfaction_json 列（通过 _apply_fitness_columns 添加）
- 只缺少：① 修复 save_backtest_result 函数让其写入这些列；② 新增 GET 历史查询端点

**异步执行模式**：工程有两套成熟的异步 Runner 模式（EvolutionRunner + TradingRunner），都基于守护线程 + DB 轮询 + WS 推送。WebSocket 推送基础设施完整可用。但首版验证页面采用同步模式——全量策略验证的耗时取决于策略数量，先以同步 + 延长超时实现，后续可按需升级为异步。

**前端导航扩展**：Sidebar.tsx 的 NAV_ITEMS 是静态数组，新增导航项只需追加一行。App.tsx 的路由数组同理。

### 任务认知变化（更新）

第 1 轮认知："不仅仅是前端重构，还需要修复后端 bug"。
第 2 轮认知更新：**任务范围比预期更明确**——不需要新增数据库表，不需要新建异步 Runner。核心工作是：
1. 修复 save_backtest_result（3 行改动）
2. 清理 Strategies 页面（移除 4 处验证代码）
3. 新增独立验证页面（路由 + 导航 + 页面组件 + 历史查询端点）

### 待消解的不确定性

无。所有关键不确定性已消解：
- verify_session → 不需要，复用 backtest_result
- 异步模式 → 首版同步，后续按需
- 导航位置 → 推理链中决策

### 决策

研究完成，进入 A2 构建推理链。

---

## 推理链（冻结前）

### 1. 任务定义

**将策略验证从 Strategies 页面的嵌入式抽屉升级为独立页面，同时修复验证结果持久化 bug，实现全量策略多周期验证、结果排名和历史查询功能。**

具体包含：
- 修复 save_backtest_result 函数不写入 fitness/qualified/satisfaction_json 的 bug
- 清理 Strategies 页面中的验证相关代码（VerifyDrawer 引用、verifyTargets 状态、批量验证按钮、组件挂载）
- 新增独立验证页面（路由 /verify），支持全量策略自动验证、参数配置、结果排名、历史记录
- 新增验证历史查询 API 端点

### 2. 现状定位

**结构层面**：验证功能当前嵌入 Strategies 页面（pages/Strategies.tsx），通过 VerifyDrawer 组件实现。VerifyDrawer 仅被 Strategies.tsx 引用（第 21 行），是一个紧耦合的页面内嵌组件。

**代码证据**：
- VerifyDrawer import：Strategies.tsx:21
- verifyTargets 状态：Strategies.tsx:637
- 批量验证按钮：Strategies.tsx:778-789
- VerifyDrawer 组件挂载：Strategies.tsx:957-962
- VerifyDrawer 自身：components/strategies/VerifyDrawer.tsx（~275 行）

**Bug 定位**：`save_backtest_result` (db_ext.py:1183-1206) 的函数签名和 INSERT 语句不含 fitness/qualified/satisfaction_json 列。verify 路由 (strategies.py:684-688) 传递这些参数 → TypeError → except (line 713) 捕获 → 验证结果不持久化且该策略显示为 error。这是一个**代码设计遗漏**——migration 021 添加了列但未更新写入函数。

**数据流现状**：
- 前端：VerifyDrawer → useVerifyStrategies → verifyStrategies service → POST /api/strategies/verify
- 后端：verify_strategies → 按 group × data_range 循环 → batch_run → compute_fitness → (bug) save_backtest_result → 汇总评分
- 历史查询：db_ext.py 有 list_backtest_results(run_source="verify") 函数，但**没有 API 端点暴露**

**架构层面**：
- 路由定义在 App.tsx:22-35，静态数组
- 导航在 Sidebar.tsx:21-28 的 NAV_ITEMS 静态数组
- 页面标题映射在 Sidebar.tsx:30-37 的 PAGE_TITLES
- 新增页面只需在这三处追加条目

### 3. 解决策略

**策略：分层解耦——修复基础设施 → 清理遗留 → 新建独立功能**

选择此策略的原因：
1. save_backtest_result bug 必须先修，否则新页面的历史功能建立在空中楼阁上
2. Strategies 页面清理可以独立进行，不会影响新页面
3. 新页面建立在修复后的基础设施上，确保数据流完整

排除的替代方案：
- 排除"仅做前端清理，不修 bug"——验证历史功能无法实现
- 排除"新建 verify_session 表"——backtest_result + run_source 已足够，list_backtest_results 已支持过滤
- 排除"首版实现异步 VerifyRunner"——同步模式足够满足需求，异步可后续迭代。理由：进化中心 EvolutionRunner 的异步模式是为长时间运行（数小时）设计的，验证任务通常在分钟级

### 4. 范围边界

**改动文件清单**：

| 文件 | 改动内容 | 原因 |
|------|----------|------|
| api/db_ext.py | save_backtest_result 添加 fitness/qualified/satisfaction_json 参数和 INSERT 列 | 修复持久化 bug |
| api/routes/strategies.py | 新增 GET /api/strategies/verify/history 端点 | 支持历史查询 |
| web/src/pages/Strategies.tsx | 移除 VerifyDrawer import、verifyTargets 状态、验证按钮、VerifyDrawer 组件挂载 | 清理遗留代码 |
| web/src/components/strategies/VerifyDrawer.tsx | **删除此文件** | 功能迁移到独立页面 |
| web/src/pages/Verify.tsx | **新建**独立验证页面 | 新功能 |
| web/src/App.tsx | 添加 /verify 路由 | 路由注册 |
| web/src/components/layout/Sidebar.tsx | 添加导航项和页面标题 | 导航入口 |
| web/src/hooks/useStrategies.ts | 新增 useVerifyHistory hook | 历史查询数据获取 |
| web/src/services/strategies.ts | 新增 getVerifyHistory 函数 | 历史查询 API 调用 |
| web/src/test/components/strategies/Strategies.test.tsx | 移除验证相关 mock 和断言 | 测试更新 |
| tests/test_api_verify.py | 新增历史端点测试 | 测试覆盖 |

**明确不改的内容**：

| 排除项 | 原因 |
|--------|------|
| POST /api/strategies/verify 端点逻辑 | 计算逻辑正确，只需修复 save 调用 |
| useVerifyStrategies hook | 可完全复用 |
| verifyStrategies service | 可完全复用 |
| Verify 相关类型定义 (types/api.ts) | 可完全复用 |
| BacktestEngine / compute_fitness | 核心计算无 bug |
| useAvailableSources hook | 可完全复用 |
| EvolutionRunner / TradingRunner | 不影响，不引入新的 Runner |

### 5. 行为规格

#### 5.1 save_backtest_result 修复

**输入输出契约**：save_backtest_result 新增 3 个可选参数 `fitness: float = 0.0`、`qualified: int = 0`、`satisfaction_json: Optional[str] = None`，INSERT 语句增加对应 3 列。调用方传入这些值时正确写入 DB。`[代码审查]`

**向后兼容**：不传这些参数时使用默认值，现有调用方不受影响。`[代码审查]`

#### 5.2 验证历史查询 API

**输入输出契约**：GET /api/strategies/verify/history?strategy_id=xxx&run_source=verify，返回 backtest_result 列表。`[测试验证]`

#### 5.3 Strategies 页面清理

**不变量**：清理后 Strategies 页面仍正常工作——策略列表、搜索过滤、删除、展开面板功能不变。`[测试验证]`

**行为变化**：批量操作栏不再显示"策略验证"按钮。VerifyDrawer 不再挂载。`[测试验证]`

#### 5.4 独立验证页面

**页面布局**（四个区域从上到下）：

**区域 A — 参数配置区**：
- 验证时间区间：动态可添加的日期区间输入（最少 1 个，默认 3 个），每个区间有开始/结束日期
- 交易参数：初始资金、手续费率、滑点（有默认值 100000 / 0.001 / 0.0005）
- 数据源信息：显示可用 symbol/timeframe 的数据时间范围（从 useAvailableSources 获取）
- 策略统计：显示策略库中 N 条策略将被验证
- 「开始验证」按钮（全部填写至少 1 个时间区间后可点击）

**区域 B — 运行状态区**（验证进行时显示）：
- 加载动画 + "验证中..."文案
- 验证完成后自动切换到结果展示

**区域 C — 结果排名区**（验证完成后显示）：
- 排名表格按综合评分降序，列：策略名 | 来源 | symbol/timeframe | 各区间指标（年化、夏普、达标标记）| 综合评分 | 达标率
- 表格头显示区间日期
- 达标指标用绿色 ✓，未达标用红色 ✗
- 正收益绿色、负收益红色
- 摘要统计：总验证数、达标数、平均综合评分

**区域 D — 历史记录区**（页面下方，始终可见）：
- 历史验证记录列表：每次验证按时间倒序
- 每条记录显示：验证时间、策略数、参数摘要
- 点击可展开查看历史结果排名

**前置条件**：策略库中至少有 1 条策略。无策略时显示空状态提示。`[代码审查]`

**后置条件**：验证结果通过 save_backtest_result 持久化到 DB，可被历史查询 API 检索。`[集成测试]`

#### 5.5 导航与路由

**路由**：/verify 映射到 Verify 页面组件。`[代码审查]`

**导航位置**：策略库 (/strategies) 和模拟交易 (/trading) 之间。`[代码审查]`

**导航图标**：使用 lucide-react 的 ShieldCheck 图标，标签"策略验证"。`[代码审查]`

### 6. 风险披露

**确定有风险**：

| 风险 | 影响 | 缓解 |
|------|------|------|
| save_backtest_result 修改可能影响现有调用方 | 18 处调用 save_backtest_result 的地方需要确认兼容 | 新参数设为可选且有默认值，不传时行为不变 |
| 全量策略验证耗时长，可能超过 HTTP 超时 | 前端收到超时错误，结果丢失 | 延长前端 service 的 timeout 到 300s；后续版本可升级为异步 |
| VerifyDrawer 删除后，Strategies 测试需要更新 | 测试可能失败 | 更新测试，移除验证相关 mock 和断言 |

**不确定是否有风险**：

| 不确定性 | 影响 | 消除方式 |
|----------|------|----------|
| 策略库中策略数量不确定，可能超过 200 条 | 验证耗时可能超过 300s | 运行时检查策略数量，超过阈值时提示用户；后续版本可引入异步模式 |

### 7. 实施顺序

**Task 1: 修复 save_backtest_result 持久化 bug**
- 无依赖，高风险优先
- 改动：db_ext.py 的函数签名 + INSERT 语句
- 验证：运行 test_api_verify.py 确认修复

**Task 2: 新增验证历史查询 API 端点**
- 依赖 Task 1（需要正确的持久化数据）
- 改动：api/routes/strategies.py 新增 GET /verify/history，db_ext.py 新增 list_verify_history 函数（如需）
- 验证：新增后端测试

**Task 3: 清理 Strategies 页面验证代码**
- 无依赖，独立进行
- 改动：Strategies.tsx 移除 4 处验证代码，删除 VerifyDrawer.tsx，更新 Strategies.test.tsx
- 验证：运行前端测试

**Task 4: 添加验证页面路由和导航**
- 无依赖，独立进行
- 改动：App.tsx 添加路由，Sidebar.tsx 添加导航项和页面标题
- 验证：代码审查

**Task 5: 构建独立验证页面**
- 依赖 Task 4（需要路由）和 Task 2（需要历史 API）
- 改动：新建 pages/Verify.tsx，新增 useVerifyHistory hook，新增 getVerifyHistory service
- 验证：前端测试 + 手动测试

**Task 6: 端到端验证与测试更新**
- 依赖 Task 1-5 全部完成
- 改动：新增测试用例，运行全量测试
- 验证：后端 86+ tests passed，前端 234+ tests passed
