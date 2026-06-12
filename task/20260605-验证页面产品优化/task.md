# 策略验证页面产品优化

## 任务目标
从产品设计层优化策略验证页面，解决 8 个已识别问题（3 个 P0 + 5 个 P1），新增 verify_session 表实现会话级历史管理。

## 用户意图
- 当前页面是从技术视角搭建的骨架，缺少产品视角的用户体验设计
- 需要前后端一起优化：新增 verify_session 表 + 重构验证页面 UI/UX
- 核心诉求：打开页面看到策略库全貌、验证结果持久可回溯、历史按会话分组

## 已知问题清单
### P0
1. 跨品种/周期混验证，UI 只显示一种数据源信息
2. 历史记录扁平逐条，不是验证会话
3. 结果是临时的，刷新即消失

### P1
4. 验证前没有策略预览
5. 长时间验证没有进度反馈
6. 结果表格信息密度不足
7. 日期区间缺少预设和校验
8. 无空状态引导

## 状态
- 阶段：B1 准备（推理链已冻结）
- 冻结确认：用户同意推理链，2026-06-05

---

## 研究第 1 轮

### 任务结构性理解

**前端组件能力**：项目有丰富的 UI 组件库（Tabs、Progress、Badge、StatCard、EmptyState、GlassCard、Skeleton），可直接复用。缺少 Collapsible 但可用 useState + 条件渲染替代。Trading.tsx 展示了完善的多区域布局模式（StatCard 网格 + GlassCard 卡片 + 双栏布局）。

**后端 session 插入点**：verify 端点 (strategies.py:532-790) 有 3 个精确的插入点：① 行 588 后创建 session；② 行 665 的 save_backtest_result 传入 session_id；③ 行 789 后更新 session 汇总。遵循现有 _apply_fitness_columns + _create_paper_trading_tables 的程序化 migration 模式。

**当前页面代码问题**：使用硬编码 slate 色系（非语义 token）、原生 HTML table（非 shadcn Table 组件）、无 isLoading 骨架屏、sourceInfo 只取第一条策略的数据源（误导）。

### 任务认知变化

初始认知："前端页面 UI 优化"。
更新认知：**前后端各占一半工作量**。后端新增 verify_session 表 + 修改 verify 端点流程是前提条件，否则前端的会话级历史无法实现。同时前端需要从组件层面重写（替换硬编码色彩、使用 shadcn Table、增加 StatCard 摘要）。

### 待消解的不确定性

无。所有关键决策点已有明确方案。

### 决策

研究完成，构建推理链。

---

## 推理链（冻结前）

### 1. 任务定义

**优化策略验证页面的产品设计体验：新增后端 verify_session 会话管理（含 migration + CRUD + 端点改造），重构前端验证页面（策略概览、日期预设、结果摘要、会话级历史、空状态引导、shadcn 组件统一）。**

### 2. 现状定位

**产品层面**：当前验证页面是从 VerifyDrawer 直接迁移的"功能骨架"，缺少产品视角的用户体验设计。8 个问题中 3 个是结构性的（数据源信息错误、历史无会话、结果不持久），5 个是体验缺陷。

**代码层面**：
- Verify.tsx (395 行) 使用硬编码 slate 色系而非语义 token，使用原生 HTML table 而非 shadcn Table 组件
- sourceInfo 只取 strategies[0] 的 symbol/timeframe (第 46-50 行)，跨品种时信息错误
- 结果存在 useState 中 (第 34 行)，不持久
- 历史通过 GET /verify/history 查询 backtest_result 散记录，无会话概念
- 无策略预览、无进度反馈、无空状态引导

**后端层面**：
- save_backtest_result 不接受 session_id 参数
- verify 端点无 session 创建/更新逻辑
- backtest_result 表无 session_id 列
- 无 verify_session 表

### 3. 解决策略

**分层改造：数据层 → 后端流程层 → 前端展示层**

选择此策略的原因：verify_session 表和 backtest_result.session_id 是前后端所有功能的基础，必须先建。后端 verify 端点的 3 个插入点是 session 数据的生产者。前端页面的所有改进（会话历史、结果持久、策略概览）都依赖 session 数据。

排除的替代方案：
- 排除"仅前端优化，不做 session"——P0 问题 2（历史无会话）和 3（结果不持久）无法解决
- 排除"用时间窗口聚合模拟 session"——不够精确，无法存储会话级摘要

### 4. 范围边界

**改动文件清单**：

| 文件 | 改动内容 | 原因 |
|------|----------|------|
| api/db_ext.py | 新增 verify_session 建表函数 + backtest_result.session_id 列 + session CRUD 函数 + save_backtest_result 添加 session_id 参数 | 数据层基础 |
| api/schemas.py | 新增 VerifySessionResponse schema | session API 契约 |
| api/routes/strategies.py | verify 端点添加 session 创建/关联/更新；history 端点改为按 session 查询 | 后端流程改造 |
| web/src/pages/Verify.tsx | 完全重写：策略概览 + 配置优化 + 结果摘要 + 会话级历史 + 空状态 | 前端页面重构 |
| web/src/types/api.ts | 新增 VerifySession 类型 | 前端类型 |
| web/src/services/strategies.ts | 修改 getVerifyHistory 为 getVerifySessions | API 调用更新 |
| web/src/hooks/useStrategies.ts | 修改 useVerifyHistory 为 useVerifySessions | Hook 更新 |
| web/src/test/... | 更新/新增测试 | 测试覆盖 |
| tests/test_api_verify.py | 新增 session 测试 | 后端测试 |
| tests/test_db_ext.py | 新增 session CRUD 测试 | 数据层测试 |

**不改的内容**：

| 排除项 | 原因 |
|--------|------|
| BacktestEngine / compute_fitness | 核心计算逻辑无 bug |
| POST /verify 的分组/回测/评分逻辑 | 只插入 session 管理，不改计算流程 |
| VerifyDrawer.tsx | 已在上一迭代删除 |
| Strategies.tsx | 已在上一迭代清理 |

### 5. 行为规格

#### 5.1 verify_session 数据层

**表结构**：verify_session 表包含 session_id PK、status (running/completed/failed)、strategy_ids JSON、data_ranges JSON、init_cash/fee/slippage、summary_json TEXT、total_results/total_strategies 计数、error_message、created_at/completed_at 时间戳。`[测试验证]`

**列关联**：backtest_result 新增 session_id TEXT 列，save_backtest_result 新增可选参数 session_id。`[测试验证]`

**CRUD 函数**：save_verify_session、get_verify_session、update_verify_session、list_verify_sessions（按 created_at DESC 排序，支持 limit）。`[测试验证]`

#### 5.2 verify 端点 session 管理

**创建 session**：verify 端点在循环开始前创建 session（status='running'），每个 save_backtest_result 传入 session_id，循环结束后更新 session（status='completed', summary_json, 统计数据）。异常时更新为 status='failed'。`[测试验证]`

**向后兼容**：不传 session_id 时 save_backtest_result 正常工作（现有调用方不受影响）。`[代码审查]`

#### 5.3 验证历史 API

**输入输出契约**：GET /api/strategies/verify/sessions 返回 verify_session 列表（按 created_at DESC），每个 session 包含完整摘要。GET /api/strategies/verify/sessions/{session_id}/results 返回该 session 关联的 backtest_result 列表。`[测试验证]`

#### 5.4 前端验证页面重写

**页面布局**（使用 Tabs 组件分为两个 tab）：

**Tab 1 — 验证**：
- 空状态：策略库为空时显示 EmptyState（引导前往策略库/实验室）
- 策略概览区：按 symbol/timeframe 分组显示策略数量 + 数据源范围，解决 P0-1（数据源信息错误）
- 配置区：日期区间输入 + 快捷预设按钮（近 3/6/12 月）+ 高级参数折叠区
- 验证按钮：显示总策略数
- 运行状态：Progress 组件 + 文案提示
- 结果摘要：4 个 StatCard（总验证数、达标数、平均评分、最佳策略）
- 结果表格：使用 shadcn Table 组件，增加排名序号、fitness 列、最大回撤列、来源 Badge

**Tab 2 — 历史**：
- 会话列表：每个 session 一行（验证时间、策略数、参数摘要、平均评分），解决 P0-2（历史无会话）
- 点击展开查看该 session 的完整结果排名表格

**视觉统一**：使用语义 token（text-text-primary/text-text-secondary）替代硬编码 slate 色系。`[代码审查]`

#### 5.5 结果持久化

验证结果通过 verify_session + backtest_result 持久化到 DB。页面刷新后切换到「历史」tab 可查看最近验证结果。解决 P0-3（结果临时性）。`[集成测试]`

### 6. 风险披露

| 风险 | 影响 | 缓解 |
|------|------|------|
| save_backtest_result 再次修改签名（已改 2 次） | 影响所有调用方 | session_id 为可选参数，默认 None |
| verify 端点的 except 块需要正确处理 session 状态更新 | session 卡在 running 状态 | 在 except 中更新为 failed |
| 前端页面完全重写，工作量大 | 可能引入回归 | 逐区域实现，每区域完成后测试 |

### 7. 实施顺序

**Task 1: 新增 verify_session 表 + backtest_result.session_id 列**
- 无依赖，数据层基础
- 改动：db_ext.py（建表 + 列 + CRUD）
- 验证：新增 test_db_ext.py 测试

**Task 2: 修改 verify 端点集成 session 管理**
- 依赖 Task 1
- 改动：strategies.py（3 个插入点）+ db_ext.py（save_backtest_result 添加 session_id）
- 验证：新增 test_api_verify.py 测试

**Task 3: 新增 session 相关 schemas + API 端点**
- 依赖 Task 1
- 改动：schemas.py + strategies.py（sessions 端点）
- 验证：新增端点测试

**Task 4: 前端类型 + service + hook 更新**
- 依赖 Task 3
- 改动：types/api.ts + services/strategies.ts + hooks/useStrategies.ts

**Task 5: 重写 Verify.tsx 页面**
- 依赖 Task 4
- 改动：pages/Verify.tsx 完全重写
- 验证：TypeScript 编译 + 前端测试通过

**Task 6: 端到端验证**
- 依赖全部
- 运行全量测试 + 手动验证
