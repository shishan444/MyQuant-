# 策略库页面全面改造

> 日期: 2026-05-26
> 状态: 推理链构建中，待用户确认

## 一、任务定义

按设计方案（`进化中心评分机制重设计方案.md` 8.8 节）实施策略库页面（Strategies.tsx）的全面改造：列布局重设计、行展开详情、批量管理、过滤排序增强。后端补齐缺失的 qualified 过滤、offset 分页、sort_by 白名单校验。

## 二、现状定位

### 前端（Strategies.tsx，600 行）

当前是基础列表页：8 列表格（名称/年化/夏普/回撤/胜率/数据/日期/操作）+ 搜索 + 来源过滤 + 星标 + 单条编辑/删除。设计方案要求的 18 项规格中 17 项未实现。

**代码证据**：
- 列定义：`Strategies.tsx:524-533`，固定 8 列
- 状态：`Strategies.tsx:400-411`，仅有 searchQuery/sourceFilter/starredIds，无 selectedIds/expandedId
- 排序：`Strategies.tsx:409`，硬编码 `sort_by: "created_at"`
- 工具栏：`Strategies.tsx:486-518`，仅搜索+来源过滤

**可复用资源**：
- `StrategyDetail.tsx`（351 行）：已有 fitness/qualified/MTF/指标 grid/达标详情渲染
- `StrategyList.tsx`（567 行）：已有 qualified 圆点(行139)、展开面板(行250)、fitness 展示(行502)
- `compareStrategies` API service（`strategies.ts:71-78`）已定义但页面未调用
- `framer-motion` 已安装（`package.json`），Strategies.tsx 已在使用

### 后端（strategies.py + db_ext.py）

4 项已支持（删除/对比/qualified+fitness返回/metrics），3 项缺失，1 项安全隐患。

**缺失项**：
- qualified 过滤：路由(`strategies.py:113-139`)和 DB(`db_ext.py:1016-1062`)均无 `qualified` 参数
- offset 分页：DB 函数签名只有 `limit`，无 `offset`；SQL 无 `OFFSET` 子句
- sort_by 白名单：`db_ext.py:1055` 直接 f-string 拼接，无校验

**satisfaction 缺口**：strategy 表无 `satisfaction_json` 列（仅 backtest_result 有）。设计方案 8.8.2 中栏的 satisfaction 详情在此条件下不可实现——需要 DB 迁移或在展开时实时计算。**决策：暂不实现 satisfaction 列级详情，达标状态仅展示 fitness 数值和 qualified Badge**。

## 三、解决策略

**前端策略**：在 Strategies.tsx 中增量改造，从内到外：先修后端 → 列布局 → 行展开 → 批量管理 → 过滤排序。复用 StrategyDetail 组件的渲染逻辑，不引入新文件。

**后端策略**：在现有 `list_strategies` 函数上扩展参数（qualified/offset），加 sort_by 白名单校验。改动最小化。

**satisfaction 决策**：设计方案中 satisfaction 详情（各维度 actual/required/ratio）暂不实现，因为 strategy 表无此列、实时计算需重跑回测代价过大。达标状态仅展示 fitness 数值 + qualified Badge + metrics。

**排除的替代方案**：
- 拆分 Strategies.tsx 为多个子组件 → 过度拆分，当前 600 行改完后约 900-1000 行，单文件可管理
- 为 satisfaction 新增 DB 列 → 需要在策略保存时额外计算和持久化，改动面过大，与本次迭代无关

## 四、范围边界

### 改动文件

| 文件 | 改动内容 | 原因 |
|------|----------|------|
| `api/routes/strategies.py` | 路由端点增加 qualified/offset 参数 | 支持 qualified 过滤和分页 |
| `api/db_ext.py` | `list_strategies` 增加 qualified/offset 参数 + sort_by 白名单 | DB 层支持新过滤和分页 |
| `web/src/pages/Strategies.tsx` | 全面改造：列布局/行展开/批量管理/过滤排序 | 任务核心 |

### 不改动

| 文件/模块 | 原因 |
|-----------|------|
| `api/schemas.py` | StrategyResponse 已有 qualified/best_fitness 字段 |
| `web/src/types/api.ts` | Strategy 已有 qualified/best_fitness/metrics 字段 |
| `web/src/services/strategies.ts` | compareStrategies/deleteStrategy 已定义，前端 service 层不需改 |
| `web/src/hooks/useStrategies.ts` | queryOptions 模式，传参即可，不需改接口 |
| `web/src/components/evolution/StrategyDetail.tsx` | 只读取复用其渲染模式，不修改 |
| strategy 表 satisfaction 列 | 改动面过大，与本次迭代无关 |

## 五、行为规格

### BS-1: 后端 API 增强

- **BS-1.1** `GET /api/strategies` 接受 `qualified` 查询参数（`true`/`false`/`null`），过滤达标/未达标策略。`[测试验证]`
- **BS-1.2** `GET /api/strategies` 接受 `offset` 查询参数，配合 `limit` 实现分页。返回的 `total` 为符合过滤条件的真实总数。`[测试验证]`
- **BS-1.3** `sort_by` 参数限制为白名单列名集合（`created_at`, `best_fitness`, `best_score`, `name`），非法值返回 400 错误。`[测试验证]`
- **BS-1.4** `sort_order` 参数限制为 `asc`/`desc`，非法值返回 400 错误。`[代码审查]`

### BS-2: 列布局重设计（8.8.1）

- **BS-2.1** 表格列顺序：复选框 | 状态(qualified圆点) | 名称(含来源Badge+qualified Badge) | 年化 | 回撤 | 胜率 | 盈亏比 | 交易数 | 数据 | 日期 | 操作。`[代码审查]`
- **BS-2.2** 删除"夏普"列，新增"盈亏比"和"交易数"列。`[代码审查]`
- **BS-2.3** qualified=True 的行左侧显示 2px 绿色边线。`[代码审查]`
- **BS-2.4** qualified=True 时名称后显示"达标" Badge（emerald 色）。`[代码审查]`

### BS-3: 行展开详情（8.8.2）

- **BS-3.1** 点击行主体区域（非按钮/复选框）切换展开/收起，同一时刻仅展开一行。`[代码审查]`
- **BS-3.2** 展开面板使用 framer-motion AnimatePresence 动画。`[代码审查]`
- **BS-3.3** 展开面板三栏布局：左栏（策略信息：方向/杠杆/来源/代数/时间/tags/notes）| 中栏（回测指标 6 项 + fitness + qualified Badge）| 右栏（DNA 条件文本 + 4 操作按钮）。`[代码审查]`
- **BS-3.4** 操作按钮：运行回测、模拟交易、继续进化（导航到进化页）、复制 DNA（复制 JSON 到剪贴板）。`[代码审查]`
- **BS-3.5** DNA 条件文本从 `strategy.dna.signal_genes` 提取，格式："角色: 指标(参数) 条件"。`[代码审查]`

### BS-4: 批量管理（8.8.3）

- **BS-4.1** 行首复选框（Checkbox）和表头全选复选框，状态管理用 `useState<Set<string>>`。`[测试验证]`
- **BS-4.2** 选中 ≥1 项时显示批量操作工具栏："已选 N 项" + 批量对比按钮 + 批量删除按钮 + 取消选择按钮。`[代码审查]`
- **BS-4.3** 批量对比：调用 `compareStrategies` API，弹出 Dialog 展示对比表格（指标列 × 策略列）。`[代码审查]`
- **BS-4.4** 批量删除：逐个调用 `deleteStrategy` API，完成后刷新列表。`[代码审查]`
- **BS-4.5** 取消选择：清空 selectedIds，隐藏工具栏。`[代码审查]`

### BS-5: 过滤和排序增强（8.8.4）

- **BS-5.1** 新增达标状态过滤 Select：全部/达标/未达标，前端内存过滤 `strategy.qualified`。`[代码审查]`
- **BS-5.2** 列头排序：年化/回撤/胜率/盈亏比/交易数/日期列可点击切换升序/降序/默认排序。`[代码审查]`
- **BS-5.3** 默认排序改为 `best_fitness DESC`（达标策略排在前面）。`[代码审查]`

### 不变量

- INV-1: 批量操作不影响未选中策略
- INV-2: 删除操作需确认（confirm 对话框）
- INV-3: 行展开和复选框选择互不干扰
- INV-4: 批量对比最多选择 5 个策略（compare API 实际限制）

## 六、风险披露

### 确定有风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| Strategies.tsx 改动量大（600→~1000 行） | 单文件过长，后续维护困难 | 代码结构清晰分区，用注释标记各功能区块 |
| sort_by 白名单可能遗漏合法列名 | 前端排序功能 400 错误 | 白名单覆盖所有 strategy 表可排序列 |
| compareStrategies 是重操作（逐个回测） | 批量对比 5 个策略可能慢 | 限制最多 5 个，加 loading 状态 |

### 不确定

| 不确定 | 如何消除 |
|---------|----------|
| 展开 DNA 条件文本的格式化逻辑复杂度 | 实现时参考 StrategyDetail.tsx 的 flat genes 渲染 |

### 设计偏差

| 偏差 | 原因 |
|------|------|
| satisfaction 详情不实现 | strategy 表无此列，设计方案声称"不需要新增后端 API"但实际需要 |

## 七、实施顺序

按依赖关系排序，高风险优先：

1. **后端 API 增强**（BS-1）— 无依赖，基础能力，前端所有功能的前置条件
2. **列布局重设计**（BS-2）— 依赖后端 qualified/metrics 数据已返回（已满足）
3. **行展开详情**（BS-3）— 依赖列布局（行结构需适配展开面板）
4. **批量管理**（BS-4）— 依赖列布局（复选框列在行首），依赖 compareStrategies API（已就绪）
5. **过滤排序增强**（BS-5）— 依赖列布局（列头排序交互），后端 qualified 过滤（步骤 1）
6. **前端测试更新** — 依赖所有功能完成
