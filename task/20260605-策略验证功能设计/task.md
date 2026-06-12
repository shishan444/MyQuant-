# 策略验证功能设计

## 状态：推理链已冻结，阶段 B 实施中

用户确认：同意方案（3 手动区间 + 综合评分降序排序 + VerifyDrawer 替换 CompareDialog）

## 任务定义
在 Strategies 策略库页面内扩展策略验证功能，支持批量选择策略、自定义数据区间、多期交叉验证，帮助用户筛选出可靠的策略。

## 初始理解
- 用户工作流：进化产出 → 策略入库 → **验证筛选**（当前缺失）→ 模拟交易
- 当前 Strategies 页面已有轻量对比功能（compare，最多 5 条），但无法选择数据区间、无法多期验证
- 需要扩展为完整的验证功能：批量选策略 + 自选数据区间 + 多期交叉验证 + 稳定性评分
- 前后端均需改动

## 研究第 1 轮

### 任务结构性理解

**前端 Strategies 页面**：以 `Strategies.tsx` 单文件组件为主体（~700行），包含 CompareDialog 弹窗、ExpandPanel 展开面板、StrategyCardRow 行组件等内部子组件。状态管理全部使用 useState（无 useReducer），关键状态包括 `selectedIds: Set<string>`（批量选择）、`compareTargets: Strategy[]`（对比目标）、`sortState`（排序）。批量操作栏在选中策略后显示，提供"批量对比"和"批量删除"两个按钮。点击"运行回测"是跳转到 Lab 页面（`navigate("/lab", {state})`），不是直接调用 API。

**后端 API 能力**：
- `POST /api/strategies/backtest`：单策略回测，支持 `strategy_id` 或内联 `dna` 两种模式，支持 `data_start/data_end` 参数
- `POST /api/strategies/compare`：多策略对比，串行逐个回测，支持 `data_start/data_end` 但前端未传
- `BacktestEngine.batch_run()`：支持批量并行回测（一次 vbt 调用），但仅进化 Runner 使用，未暴露为 API
- `GET /api/data/available-sources`：查询数据日期范围，前端已有 `useAvailableSources()` hook
- `backtest_result` 表存储了 `data_start/data_end` 字段，支持按区间分组查询

**数据流关键路径**：
1. 前端发起请求 → API 路由 → `load_and_prepare_df(data_start, data_end)` 加载切片数据 → `BacktestEngine.run()` → 结果存入 `backtest_result` 表 → 返回前端
2. 数据区间完全由 API 参数控制，Engine 层不感知日期范围
3. 多策略 × 多区间的实现模式：外层循环 N 个区间（每次加载不同切片的 `enhanced_df`），内层调用 `batch_run()` 并行回测 M 条策略

### 任务认知变化

1. **Compare 功能已损坏**：前端 `compareStrategies()` 未传 `dataset_id`（必填字段），后端会在第 406 行抛出 404。这不是"轻量对比可用"，而是"根本不能用"。这改变了任务性质——不是"扩展现有功能"，而是"修复并升级"。

2. **batch_run 可以利用**：进化 Runner 中已有成熟的 `batch_run` 机制，性能优势明显（N 条策略只需 1 次 vbt 调用）。策略验证可以复用这个能力，新增 API 端点暴露它。

3. **Strategies 页面跳转到 Lab 做回测是绕路**：用户在 Strategies 选中策略后，跳转到 Lab 页面做回测，然后需要手动返回。验证功能应该内嵌在 Strategies 页面，不需要跳转。

### 待消解的不确定性

1. **compare 弹窗的 dataset_id 修复方案**：是直接从策略的 symbol/timeframe 构造 dataset_id，还是让用户选择？这影响验证功能的 UI 设计。
   → 研究任务：确认策略的 symbol/timeframe 是否与 parquet 文件名一致

2. **多期交叉验证的"期"如何定义**：是用户手动指定 N 个日期区间，还是系统自动按月/季度分割？这决定了 UI 复杂度和 API 设计。
   → 研究任务：了解 Lab 页面 BacktestModePanel 的日期选择实现作为参考

3. **验证结果的展示形态**：是表格（每个策略 × 每个区间的指标矩阵）还是图表（权益曲线叠加）？这影响前端组件设计。
   → 暂不研究，可在设计阶段与用户讨论

### 决策
继续研究——消解不确定性 1 和 2。

---

## 研究第 2 轮

### 不确定性消解

**不确定性 1 已消解**：dataset_id 可以从策略的 symbol + timeframe 直接构造，规则为 `f"{symbol}_{timeframe}"`（如 `"BTCUSDT_4h"`）。后端 compare 端点（strategies.py:406）用此拼接 parquet 路径，前端 Lab 的 BacktestModePanel（BacktestModePanel.tsx:56）也用相同规则。因此，修复 compare 功能只需在 Strategies 页面的 CompareDialog 中，从第一条策略的 symbol/timeframe 构造 dataset_id 即可。

**不确定性 2 已消解**：Lab 页面使用原生 `<input type="date">` 日期选择，配合快捷按钮（近3月/近6月/近1年/今年/全部）。日期范围来自 `available-sources` API 的 `time_start/time_end`。前端传后端的日期格式为 `"YYYY-MM-DD"`。多期验证可以复用这套日期选择模式——系统提供快捷分割（如"按季度分割"、"按半年分割"），同时允许用户手动指定日期区间。

### 任务结构性理解（更新）

**Compare 修复方案明确**：CompareDialog 中补传 `dataset_id: f"{strategies[0].symbol}_${strategies[0].timeframe}"` 即可修复。但更进一步——验证功能是 compare 的超集，可以完全替换 compare 弹窗。

**验证功能的设计空间**：
1. **数据层**：可复用 `load_and_prepare_df()` + `BacktestEngine.batch_run()`，无需新的核心逻辑
2. **API 层**：需新增一个验证端点，接受 `strategy_ids + data_ranges`，内部循环区间 + batch_run
3. **前端 UI 层**：复用 Strategies 页面已有的批量选择机制（selectedIds），新增验证配置面板（策略列表 + 日期区间选择 + 验证模式）和结果展示面板
4. **日期选择**：复用 `useAvailableSources()` 获取范围，原生 `<input type="date">` + 快捷按钮

**策略的同质性约束**：batch_run 要求所有策略使用相同的数据集（同一个 `enhanced_df`），因此批量验证时所有策略必须是同一 symbol + timeframe 组合。如果用户选中了不同 symbol 的策略，需要分组验证。当前策略库的策略大部分来自同一次进化任务（同一 symbol/timeframe），所以这个约束在实际使用中影响不大。

### 待消解的不确定性

无——所有影响处理方式的不确定性已消解。验证结果展示形态（表格 vs 图表）属于设计决策，可在推理链中直接规定。

### 决策
研究完成，进入推理链构建。

---

## 推理链（v2 — 基于用户反馈修订）

### 1. 任务定义

在 Strategies 策略库页面新增策略验证功能：用户批量选择策略后，手动设置 3 个独立的数据时间区间进行回测，系统计算每个策略在各区间的表现，综合评估策略的收益水平和跨期稳定性，按综合评分降序排序，帮助用户筛选出收益最高、最稳定的策略。同时替换已损坏的 CompareDialog。

### 2. 现状定位

**代码设计问题：CompareDialog 功能损坏。** 前端 `compareStrategies()`（services/strategies.ts:71-78）未传必填参数 `dataset_id`，后端 compare 端点（strategies.py:406）因缺失 parquet 路径而抛出 404。"批量对比"按钮必然失败。

**架构设计问题：验证环节缺失。** 用户工作流中"进化产出 → 策略入库 → **验证筛选** → 模拟交易"的验证筛选环节无对应功能。用户需跳转 Lab 做回测再返回策略库，操作断裂。

**评分系统现状。** `compute_fitness()`（core/scoring/scorer.py:35-111）采用"约束门控 + 目标函数"模式：
- 约束门控：max_drawdown、total_trades、profit_factor、annual_return 四个硬约束，任一失败 fitness=0
- 目标函数：根据 objective（sharpe/calmar/annual_return）取对应的原始指标值
- 最终：`fitness = 约束全过 ? max(0, objective_value) : 0.0`
- `qualified = fitness > 0 且无约束失败`

这个评分机制**可以直接复用于每个区间的独立评分**，但缺少跨区间聚合能力——不存在"多区间综合评分"的概念。

**batch_run 已可复用。** `BacktestEngine.batch_run()`（engine.py:643）支持 N 条策略一次 vbt 调用并行回测，但仅进化 Runner 使用。

### 3. 解决策略

**3a. 用户手动设定 3 个验证区间。** 不使用系统自动分割（按季度/半年等），改为用户手动设置 3 组 data_start/data_end。理由：用户了解自己的策略在什么行情下运行，手动选区间的验证结果比自动分割更有针对性——比如用户可以故意选"牛市/熊市/震荡"三种行情来验证策略的适应性。

**3b. 综合评分设计。** 核心问题：如何从 3 个区间的回测结果得出一个"综合评分"，使降序排序能反映"收益最高、最稳定"。

评分公式设计：
```
per_period_fitness[i] = compute_fitness(metrics_i) 的 fitness 值
qualified[i] = 对应区间的 qualified 布尔值

comprehensive_score = avg_fitness × qualified_ratio × consistency_bonus

其中:
  avg_fitness = mean(fitness_1, fitness_2, fitness_3)
  qualified_ratio = count(qualified) / 3        (0.0, 0.33, 0.67, 1.0)
  consistency_bonus = 1 + 0.2 × (3个区间全部qualified ? 1 : 0)
```

**设计理由**：
- `avg_fitness` 衡量**收益水平**——3 个区间的平均适应度
- `qualified_ratio` 衡量**通过率**——全部达标的策略得满分，部分达标按比例打折。例如 fitness 值很高但只有 1/3 达标的策略，得分 = avg_fitness × 0.33，自动排名靠后
- `consistency_bonus` 是 20% 的奖励加成——3/3 全部达标才获得，鼓励稳定性而非单期爆发

**为什么不用变异系数（CV）**：CV 衡量波动程度，但在只有 3 个数据点时不可靠（1 个异常值就能让 CV 剧变）。`qualified_ratio` 是更稳健的二值判定——约束通过就是通过，不通过就是不通过。

**为什么不用最差区间（min）**：min 太保守，惩罚了整体表现好但某期因数据量不足而表现稍差的策略。qualified_ratio 已经起到了"惩罚不达标期"的作用，但不会因为达标期的微小差异而过度惩罚。

**3c. 结果展示**：矩阵表格 + 综合评分降序排列。行=策略（按综合评分降序），列=区间1指标 | 区间2指标 | 区间3指标 | 综合评分。每行最后一列显示综合评分和达标率（如"3/3"）。

**3d. 前端交互**：复用 Strategies 页面已有的 `selectedIds` 批量选择机制。批量操作栏的"批量对比"按钮替换为"策略验证"。点击后打开 VerifyDrawer 抽屉，内含：3 组日期选择器 + 验证按钮 + 结果表格。

### 4. 范围边界

**改动文件**：

后端：
- `api/routes/strategies.py`：新增 `POST /verify` 端点
- `api/schemas.py`：新增 `VerifyRequest`、`VerifyResponse`、`VerifyResultItem` 模型

前端：
- `web/src/pages/Strategies.tsx`：替换 CompareDialog 为 VerifyDrawer，更新批量操作栏
- `web/src/components/strategies/VerifyDrawer.tsx`：**新建**，验证配置 + 结果矩阵表格
- `web/src/services/strategies.ts`：新增 `verifyStrategies()` 服务函数
- `web/src/hooks/useStrategies.ts`：新增 `useVerifyStrategies()` mutation hook
- `web/src/types/api.ts`：新增验证相关类型定义

**不改**：
- `core/backtest/engine.py`、`core/scoring/scorer.py`、`core/data/mtf_loader.py`：已可复用
- `web/src/pages/Lab.tsx`、`web/src/components/lab/`：独立，不受影响

### 5. 行为规格

**B1: 验证触发** [代码审查]
- 前置：用户选中 >= 1 条策略
- 行为：批量操作栏显示"策略验证"按钮。点击打开 VerifyDrawer 抽屉，选中策略列表传入

**B2: 验证配置——3 个日期区间** [代码审查]
- 行为：抽屉展示 3 组日期选择器（data_start/data_end），使用 `<input type="date">`
- 日期范围默认从 `useAvailableSources()` 返回的 time_start/time_end 获取
- 每个区间可独立修改。3 个区间不要求连续或互斥
- 前置：至少 1 个区间填写了有效日期才能提交
- 约束：若选中策略包含不同 symbol/timeframe 组合，显示提示"将分组验证"

**B3: 验证 API 调用** [测试验证]
- 输入契约：
  ```
  {
    strategy_ids: string[],        // 策略 ID 列表
    data_ranges: Array<{           // 1~3 个日期区间
      start: string,               // "YYYY-MM-DD"
      end: string                  // "YYYY-MM-DD"
    }>,
    init_cash?: number,            // 默认 100000
    fee?: number,                  // 默认 0.001
    slippage?: number              // 默认 0.0005
  }
  ```
- 后端行为：
  1. 按 symbol/timeframe 分组策略
  2. 对每组：循环 data_ranges → 每个区间 load_and_prepare_df(start, end) → batch_run 策略组
  3. 对每个回测结果：compute_metrics → compute_fitness → 构建 VerifyResultItem
  4. 存入 backtest_result 表（run_source="verify"）
  5. 计算每条策略的综合评分（avg_fitness × qualified_ratio × consistency_bonus）
- 输出契约：
  ```
  {
    results: Array<{               // 每个 策略×区间 一个条目
      strategy_id, data_start, data_end,
      total_return, sharpe_ratio, max_drawdown,
      win_rate, total_trades, profit_factor,
      fitness, qualified, error?
    }>,
    summary: Array<{               // 每条策略一个汇总
      strategy_id, strategy_name,
      comprehensive_score,         // 综合评分
      avg_fitness,                 // 平均适应度
      qualified_count,             // 达标期数 (0-3)
      total_periods,               // 总期数
      per_period_metrics: Array<{  // 各期指标摘要
        data_start, data_end,
        total_return, sharpe_ratio, max_drawdown,
        fitness, qualified
      }>
    }>
  }
  ```
- 不变量：(strategy_id, data_start, data_end) 组合恰好产生一个 result
- 边界：data_ranges 为空返回 400 错误；单条策略可验证

**B4: 综合评分计算** [测试验证]
- 公式：`comprehensive_score = avg_fitness × qualified_ratio × consistency_bonus`
- `avg_fitness` = mean(fitness_1, fitness_2, fitness_3)，未填写的区间不参与计算
- `qualified_ratio` = count(qualified periods) / count(filled periods)
- `consistency_bonus` = 1.2 if 全部达标 else 1.0
- 边界：所有区间 fitness=0 时 comprehensive_score=0；单区间时退化 fitness × qualified
- 不变量：comprehensive_score >= 0

**B5: 结果展示——综合排名表** [代码审查]
- 行为：summary 按综合评分降序排列，展示表格：
  - 行：策略名 | 区间1年化/夏普/回撤 | 区间2年化/夏普/回撤 | 区间3年化/夏普/回撤 | 综合评分 | 达标率
- 单元格颜色：年化收益正值绿色、负值红色；达标显示绿色勾、未达标显示红色叉
- 综合评分列加粗显示，作为主要排序依据
- 支持点击展开查看某策略的完整区间指标详情

**B6: 结果持久化** [测试验证]
- 每个回测结果存入 backtest_result 表，run_source="verify"
- result_id 全局唯一，strategy_id 外键关联

**B7: 移除 CompareDialog** [代码审查]
- 删除 CompareDialog 代码，"批量对比"按钮替换为"策略验证"
- compare API 端点保留

### 6. 风险披露

**确定有风险**：
1. **batch_run 内存**：串行处理区间缓解。3 个区间 × 10 策略，预计 15-30 秒。
2. **前端超时**：设置 120s timeout + 加载动画。

**不确定的风险**：
1. **3 个区间日期重叠**：用户可能设置重叠区间，导致重复计算。影响不大（结果仍有效），但显示提示即可。

### 7. 实施顺序

1. **后端：verify 端点**（无依赖）→ 新增 schemas + 路由 + 综合评分计算
2. **前端：类型 + 服务 + hook**（依赖 1 的 API 契约）
3. **前端：VerifyDrawer 组件**（依赖 2）→ 3 组日期选择器 + 结果排名表
4. **前端：集成到 Strategies**（依赖 3）→ 替换 CompareDialog + 更新批量操作栏
5. **测试**（依赖 1-4）→ 后端 API 测试 + 前端组件测试
