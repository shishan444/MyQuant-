# 批量回测新页面

## 任务目标
新建批量回测页面（/batch-backtest），支持从策略库选择已验证的优秀策略，跨多个时间范围运行详细回测，
展示权益曲线、交易信号、完整指标，提供 SSE 流式进度展示。

## 初始理解
- 功能定位：验证→**批量回测**→模拟交易 工作流的中间环节
- 复用 Verify 的 UX 模式（策略选择→日期配置→SSE进度→结果展示）
- 复用 Lab 的可视化组件（K线图、权益曲线、信号标记）
- 后端需要新端点：批量回测 + SSE 流式 + 返回完整 BacktestResult（含 equity_curve、signals）

---

## 研究第 1 轮

### 任务结构性理解

**核心发现：Verify 引擎已经生成了完整回测数据，只是没有传递到前端。**

- `BacktestEngine.batch_run()` 返回 `list[BacktestResult]`，每个结果包含 `equity_curve`（pd.Series）和 `trades_df`（DataFrame）——`engine.py:779-786`
- `_VerifyProcessor.process_step()` 调用 `batch_run()` 后只提取了 metrics 用于评分，**丢弃了** equity_curve 和 trades_df——`strategies.py:1011-1097`
- 前端 Lab 页面已有完整可视化组件：`KlineChart`（K线+信号标记）、`EquityCurveChart`（权益曲线）、`BacktestMetricsPanel`（指标面板）——都是纯 props 驱动，可直接 import

**数据流结构**：

```
Verify（现有）：batch_run → 提取 metrics → SSE推送摘要 → 前端卡片展示（无图表）
Lab（现有）：run → 提取完整结果 → 同步返回 → 前端K线+曲线+信号
批量回测（新）：batch_run → 提取完整结果 → SSE推送摘要+存储详情 → 前端卡片+点击展开图表
```

**复用映射**：

| 需要的 | 来源 | 复用方式 |
|--------|------|---------|
| SSE 流式进度 | Verify _VerifyProcessor | 复制模式，创建 _BatchBacktestProcessor |
| K线图+信号 | Lab KlineChart | 直接 import |
| 权益曲线 | Lab EquityCurveChart | 直接 import |
| 指标面板 | Lab BacktestMetricsPanel | 直接 import |
| 日期配置 | Verify 配置面板 | 参考实现 |
| 批量执行 | Verify batch_run | 直接复用 |
| 结果存储 | Verify save_backtest_result | 复用，run_source="batch_backtest" |

### 任务认知变化

研究前认为需要"从零构建批量回测引擎"。研究后发现**引擎已经就绪**，核心工作是：
1. 后端：在 Verify 处理器模式上增加完整结果序列化 + 详情查询端点
2. 前端：组合现有组件构建新页面

工作量比预期小很多。

### 待消解的不确定性

无。所有基础设施已验证可用。

### 决策
研究完成，进入推理链构建。

---

## 推理链

### 1. 任务定义

新建"批量回测"功能模块（独立页面 `/batch-backtest`），支持批量选择已验证策略，跨多个时间范围运行完整回测（含权益曲线和交易信号），通过 SSE 流式展示进度，完成后可按策略-时段查看详细 K 线图、权益曲线和完整指标。

### 2. 现状定位

**问题类型：功能缺失（现有能力割裂）**

系统已有两种回测能力但互不关联：
- Lab 回测（`Lab.tsx`）：单策略、单时段、有完整可视化（K线/曲线/信号），但无批量、无多时段、无进度
- Verify 验证（`Verify.tsx`）：多策略、多时段、SSE进度，但只返回摘要指标，丢弃了 equity_curve 和 trades_df

**关键点**：`BacktestEngine.batch_run()` 实际生成了完整结果（`engine.py:779-786`），Verify 端点在 `process_step()` 中只序列化了 metrics 部分。新端点只需在相同模式上序列化完整结果。

**前端组件完全可复用**：KlineChart（`components/charts/KlineChart.tsx`）、EquityCurveChart（`components/lab/EquityCurveChart.tsx`）、BacktestMetricsPanel（`components/lab/BacktestMetricsPanel.tsx`）均为纯 props 驱动的展示组件。

### 3. 解决策略

**创建新的 SSE 端点和新页面，复用 Verify 处理器模式和 Lab 可视化组件。**

后端策略：
- 创建 `_BatchBacktestProcessor`，基于 `_VerifyProcessor` 模式（分组×时段步进），但 SSE 推送摘要指标，同时将完整 BacktestResult（含 equity_curve/signals）存储到 backtest_result 表
- 提供详情查询端点 `GET /api/strategies/batch-backtest/{result_id}`，按需返回完整回测结果
- SSE 事件保持轻量（只推摘要），详情数据在用户点击时按需加载

前端策略：
- 新建 `BatchBacktest.tsx` 页面，布局仿 Verify（配置→进度→结果卡片）
- 结果卡片可展开，展开后通过详情端点获取 equity_curve/signals，用 Lab 组件渲染 K 线图和权益曲线
- 策略来源：从策略库页面通过 navigate state 传入 strategy_ids，同时页面内支持手动调整

排除的方案：
- 扩展 Verify 页面增加"详细模式"：会使 Verify 职责模糊（验证 vs 回测），页面过度膨胀
- 在 SSE 中推送完整结果（含曲线/信号）：单次 SSE 事件可能达数百 KB，影响流式体验

### 4. 范围边界

**新增文件：**
- `web/src/pages/BatchBacktest.tsx` — 新页面
- 无新增后端文件（在 strategies.py 中新增端点和处理器类）

**改动文件：**
- `api/routes/strategies.py` — 新增 `_BatchBacktestProcessor` 类和 `POST /batch-backtest/stream` 端点 + `GET /batch-backtest/{result_id}` 端点
- `api/schemas.py` — 新增请求/响应类型
- `web/src/App.tsx` — 新增路由
- `web/src/components/layout/Sidebar.tsx` — 新增导航项
- `web/src/services/strategies.ts` — 新增 SSE stream 函数
- `web/src/hooks/useStrategies.ts` — 新增 useBatchBacktestStream hook
- `web/src/types/api.ts` — 新增类型定义

**不改：**
- `core/backtest/engine.py` — 引擎无需改动，batch_run 已返回完整结果
- `core/data/` — 数据加载逻辑无需改动
- `api/db_ext.py` — 复用 backtest_result 表，无需新表
- Lab/Verify/Strategies 等现有页面 — 不做修改（Strategies 页面的跳转按钮将在后续迭代中添加）

### 5. 行为规格

**5.1 后端 SSE 端点**
- 路径：`POST /api/strategies/batch-backtest/stream`
- 请求体：`{ strategy_ids: string[], data_ranges: {start,end}[], init_cash?, fee?, slippage?, leverage? }`
- SSE 事件格式与 Verify 一致：`progress`（摘要指标）/ `complete`（汇总）/ `error`
- 每个 progress 事件的 batch_results 包含每策略的摘要指标 + result_id（用于后续获取详情）
- 处理器按 `{symbol}_{timeframe}` 分组，按 data_range 步进，每组调用 batch_run
- 完整 BacktestResult（含 equity_curve/signals）存储到 backtest_result 表，run_source="batch_backtest"
- 不更新 strategy 表的 verify_* 字段（与验证区分）
- 验证方式：`[集成测试]`

**5.2 后端详情查询端点**
- 路径：`GET /api/strategies/batch-backtest/{result_id}`
- 返回完整 BacktestResult：metrics + equity_curve（序列化为 [{timestamp,value}]）+ signals（序列化为 [{type,timestamp,price,reason}]）
- 验证方式：`[代码审查]`

**5.3 前端页面配置区**
- 策略选择：显示从策略库跳转传入的 strategy_ids（带名称、星级显示），支持手动添加/删除
- 日期区间：预设快捷选项（近3月/6月/1年）+ 自定义区间，最多 3 个
- 高级参数：初始资金、手续费、滑点、杠杆（复用 Verify 的 localStorage 持久化模式）
- 启动按钮：至少选择 1 个策略 + 1 个日期区间时才可用
- 验证方式：`[代码审查]`

**5.4 前端 SSE 进度展示**
- 进度条：current/total 步骤
- 步骤信息：当前处理的交易对/周期 + 时间范围
- 实时统计：已完成策略数、当前平均收益
- 取消按钮：AbortController 中断 SSE
- 验证方式：`[代码审查]`

**5.5 前端结果展示**
- 统计栏：总策略数、平均收益、最佳策略
- 策略卡片列表（非网格，每个卡片一行）：显示策略名称、星级、每时段摘要指标（收益/夏普/回撤/胜率/交易数）
- 卡片展开后：按时段展示详情，点击具体时段加载完整结果
- 详情视图：权益曲线图（EquityCurveChart）+ 完整指标面板（BacktestMetricsPanel）
- K线图+信号标记（KlineChart）：可选展示，需要加载对应时段的 OHLCV 数据
- 验证方式：`[代码审查]`

**5.6 路由和导航**
- 路由：`/batch-backtest`，注册在 App.tsx
- 导航：Sidebar.tsx 新增"批量回测"项，位于"策略验证"和"模拟交易"之间
- 图标：lucide-react 的 `LineChart` 或 `BarChart3`
- 验证方式：`[代码审查]`

**5.7 策略库跳转入口**
- Strategies 页面批量操作区新增"批量回测"按钮
- 点击后 navigate("/batch-backtest", { state: { strategy_ids: [...] } })
- BatchBacktest 页面读取 location.state 初始化策略列表
- 验证方式：`[代码审查]`

### 6. 风险披露

**确定有风险：**
- SSE 详情数据量大：单个策略单时段的 equity_curve 可能达 ~100KB，如果 SSE 推送完整结果会导致网络拥塞 → 缓解：SSE 只推摘要，详情按需 GET 请求
- backtest_result 表存储增长：每次批量回测写入 N策略×M时段 条记录 → 缓解：与 Verify 相同的存储模式，可接受

**不确定的风险：**
- 首次加载时 K 线图需要的 OHLCV 数据是否可从现有 API 获取 → 需要验证后端是否有按 strategy_id 的 symbol/timeframe/date_range 返回 OHLCV 的端点，如果没有可能需要新增
- 页面复杂度可能导致代码量大（800+ 行）→ 可通过拆分子组件缓解

### 7. 实施顺序

1. **后端 Schema 定义** — BatchBacktestRequest、BatchBacktestResultItem、BatchBacktestSummaryItem（无依赖）
2. **后端 _BatchBacktestProcessor** — 基于 _VerifyProcessor 模式，增加完整结果序列化存储（依赖 1）
3. **后端 SSE 端点** — POST /batch-backtest/stream + GET /batch-backtest/{result_id}（依赖 2）
4. **前端类型定义** — api.ts 新增类型（依赖 1）
5. **前端 SSE 服务 + Hook** — batchBacktestStream 函数 + useBatchBacktestStream hook（依赖 4）
6. **前端 BatchBacktest 页面** — 配置区 + 进度区 + 结果区 + 详情视图（依赖 5）
7. **路由 + 导航 + 跳转入口** — App.tsx + Sidebar.tsx + Strategies.tsx（依赖 6）

## 状态
- 推理链已冻结（用户确认于 2026-06-10）
- 阶段 B：实施完成，服务已重启
