# 任务：策略验证页面交互设计优化

## 状态：推理链 v5 已实现

## 实施结果

所有 6 项任务已完成：
- 后端 521 passed / 1 pre-existing failure
- 前端 234 passed
- TypeScript 编译无错误

### 改动文件
| 文件 | 改动 |
|------|------|
| api/db_ext.py | +30行：_VERIFY_STRATEGY_COLUMNS + _apply_verify_strategy_columns() + version 24 + allowed 扩展 |
| api/schemas.py | +4行：StrategyResponse 增加 verify_count/verify_avg_score/verify_best_score/last_verified_at |
| api/routes/strategies.py | +60行：_strategy_row_to_response 返回新字段 + _update_strategy_verify_fields_sync() + _VerifyProcessor._update_strategy_verify_fields() + finalize/verify 回写 |
| web/src/types/api.ts | +4行：Strategy interface 增加验证字段 |
| web/src/pages/Verify.tsx | 完全重写：toolbar 配置 + SSE 进度 + 策略卡片（操作按钮+展开详情） |
| web/src/pages/Strategies.tsx | +8行：策略行增加验证标识 badge（验证×N 均分X.XX） |

## 实施结果

所有 4 项任务已完成，服务已重启：
- 后端 1888 passed / 2 pre-existing failures
- 前端 234 passed
- TypeScript 编译无错误

### 改动文件
| 文件 | 改动 |
|------|------|
| api/routes/strategies.py | +280行：_VerifyProcessor 类 + POST /verify/stream SSE endpoint |
| web/src/services/strategies.ts | +60行：verifyStrategiesStream SSE 函数 + 类型定义 |
| web/src/hooks/useStrategies.ts | +70行：useVerifyStream hook（SSE消费 + 状态管理） |
| web/src/pages/Verify.tsx | 完全重写：紧凑配置 + 进度面板 + 策略卡片网格 + 历史视图 |

---

## 用户反馈历史

**v1 反馈**：方案停留在"修组件修 bug"层面，页面本质简单但被设计成大而空的布局，功能随意堆叠。

**v2 反馈**：需要展示验证进度——总条数、已验证条数、当前处理状态等可见信息。

---

## 推理链 v5 — 验证反馈闭环 + 页面完整操作流程

### 用户反馈

v4 方案仍停留在"页面展示+操作按钮"层面，没有从产品闭环角度思考。用户核心洞察：
**策略库是第一次产出内容，如果一条策略经过多次验证依然很好，应该在策略上标识出来，便于后续选择策略时知道验证效果。**

### 核心问题

**验证是策略质量信号的来源，不是孤立的一次性操作。** 当前验证结果存在 `verify_session` + `backtest_result` 表中，与 `strategy` 表完全脱节：
- Strategy 表**无任何验证字段**（verify_count / verified_at 等均不存在）
- 验证完成后**不更新 Strategy 表**
- 策略库页面**无法展示验证历史**，用户选择策略时没有验证依据

缺失的产品闭环：`验证 → 质量信号沉淀到策略 → 选择策略时可见 → 决策更可靠`

### 1. 任务定义

1. 在 Strategy 表增加验证汇总字段，验证完成后自动回写
2. 策略库页面展示验证标识，作为策略选择依据
3. 重写验证页面（紧凑配置 + 进度追踪 + 结果卡片 + 操作按钮），形成完整闭环

### 2. 现状定位

**数据模型缺口**（strategy 表 17 个字段，无验证相关）：
- `verify_count` → 不存在
- `verify_avg_score` → 不存在
- `verify_best_score` → 不存在
- `last_verified_at` → 不存在

**代码缺口**：
- `_VerifyProcessor.finalize()`（strategies.py:1018-1062）：计算 summary 后只更新 session，不更新 strategy
- 同步 `verify_strategies`（strategies.py:769-817）：同上
- `update_strategy()`（db_ext.py:1182-1217）：allowed 白名单 12 个字段，不含验证字段
- `StrategyResponse`（schemas.py:171-191）：不含验证字段
- `_strategy_row_to_response`（strategies.py:65-100）：不返回验证字段

**已有的能力**（无需改动）：
- 后端 SSE endpoint + useVerifyStream hook 已实现
- 跨页面导航模式已实现（Strategies → Trading/Lab/Evolution）
- `strategyMap` 已建立 strategy_id → Strategy 映射

### 3. 解决策略

**策略：数据层反馈 + 展示层标识 + 操作层闭环**

三层联动：
1. **数据层**：Strategy 表增加 4 个验证汇总字段，finalize() 完成后回写
2. **展示层**：策略库页面显示验证标识（次数/均分），策略卡片展示验证状态变化
3. **操作层**：验证页面卡片增加操作按钮（交易/回测/进化），连接到对应页面

计算公式：
```
new_count = old_count + 1
new_avg = (old_avg × old_count + new_score) / (old_count + 1)
new_best = max(old_best, new_score)
last_verified_at = now()
```

### 4. 数据模型变更

**新增字段**（strategy 表）：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| verify_count | INTEGER | 0 | 参与验证次数 |
| verify_avg_score | REAL | NULL | 历次验证平均综合评分 |
| verify_best_score | REAL | NULL | 历次验证最佳综合评分 |
| last_verified_at | TEXT | NULL | 最近验证时间 |

**更新时机**：`_VerifyProcessor.finalize()` 和同步 `verify_strategies` 完成后，遍历 summary 更新每条策略的验证字段。

### 5. 完整页面设计

#### 验证页面 — 待验证态（idle）

```
┌─ Header（1行）────────────────────────────────────────────┐
│ 🛡 策略验证   23条策略 · 3品种              [历史记录]    │
├───────────────────────────────────────────────────────────┤
│                                                            │
│  [近3月] [近6月] [近1年]  [+ 自定义区间]                   │
│  2024-01 ~ 2025-01  资金[100000]  费率[0.06%]  滑点[0.02%]│
│                                            [▶ 开始验证]    │
│                                                            │
│  ┌─ 引导区 ──────────────────────────────────────────┐    │
│  │      配置时间区间后开始验证                        │    │
│  │      将验证全部 23 条策略 × 3 个品种              │    │
│  └───────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────┘
```

#### 验证页面 — 结果态（done）

```
┌─ Header ──────────────────────────────────────────────────┐
│ 🛡 策略验证   23条策略 · 3品种              [历史记录]    │
├───────────────────────────────────────────────────────────┤
│  已验证 23条 · 3区间 (2024-01~2025-01)  [重新验证]        │
│                                                            │
│  达标 12/23    │    均分 0.72    │    最佳: MACD趋势策略   │
│                                                            │
│  [全部] [达标] [未达标]        [评分] [达标率] [收益]      │
│                                                            │
│  ┌─ Strategy Card (达标) ──────────────────────────────┐  │
│  │ #1 MACD趋势 [进化] BTC/1h       0.85   2/3 ✓      │  │
│  │ ██████ +15.2%✓ │ ████ +8.3%✓ │ ██ -2.1%✗         │  │
│  │ 年化+12.4% 夏普1.03 回撤-8.5%                      │  │
│  │ ─────────────────────────────────────────────────── │  │
│  │ [▶ 开始交易]   👁 回测   🧬 优化                    │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌─ Strategy Card (未达标) ────────────────────────────┐  │
│  │ #2 RSI反转 [实验室] ETH/4h       0.32   0/3 ✗     │  │
│  │ ██ -3.1%✗ │ █ -5.8%✗ │ █ -8.2%✗                  │  │
│  │ 年化-5.7% 夏普-0.42 回撤-18.3%                     │  │
│  │ ─────────────────────────────────────────────────── │  │
│  │ [🧬 继续优化]   👁 回测   💹 交易                   │  │
│  └─────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────┘
```

**卡片展开态**（点击卡片主体）：
- DNA 策略基因摘要（入场/出场/执行规则）
- 各区间详细指标表格
- 完整操作按钮

**操作按钮**（按达标状态差异化）：
- 达标策略：主操作 [▶ 开始交易]（绿色）+ 辅助 👁 回测 + 🧬 优化
- 未达标策略：主操作 [🧬 继续优化]（蓝色）+ 辅助 👁 回测 + 💹 交易
- 导航模式与策略库页面一致：`navigate("/trading", { state: {...} })`

#### 策略库页面 — 验证标识（展示层）

策略表格行增加验证标识：

```
┌─ 策略行 ──────────────────────────────────────────────────┐
│ MACD趋势策略  BTC/1h  [进化]  验证×3 均分0.72  0.85 ✓    │
│                                            [▶][⚡][✏][🗑] │
└───────────────────────────────────────────────────────────┘
```

- `验证×3 均分0.72`：verify_count 和 verify_avg_score，验证过才显示
- 未验证策略无此标识
- 颜色编码：均分 > 0.6 绿色，> 0.3 蓝色，≤ 0.3 灰色

### 6. 范围边界

**改动**：
| 文件 | 改动 |
|------|------|
| `api/db_ext.py` | +1 函数 `_apply_verify_strategy_columns()` + allowed 扩展 + version 24 注册 |
| `api/schemas.py` | StrategyResponse +4 字段 |
| `api/routes/strategies.py` | `_strategy_row_to_response` +4 字段 + `finalize()` + `verify_strategies` 回写逻辑 |
| `web/src/types/api.ts` | Strategy interface +4 字段 |
| `web/src/pages/Verify.tsx` | 完全重写 |
| `web/src/pages/Strategies.tsx` | 策略行增加验证标识 |

**不改动**：
- SSE endpoint（已实现）
- hooks / services（已实现）
- Lab / Evolution / Trading 页面

### 7. 行为规格

**BS-1~BS-9** 保持 v3 定义不变，新增/修改：

**BS-10: Strategy 表验证字段** `[测试验证]`
- 新增 4 个字段：verify_count / verify_avg_score / verify_best_score / last_verified_at
- 默认值：0 / NULL / NULL / NULL
- `update_strategy()` allowed 白名单包含这 4 个字段

**BS-11: 验证完成后回写策略** `[测试验证]`
- `_VerifyProcessor.finalize()` 和同步 `verify_strategies` 完成后，遍历 summary
- 对每条策略计算并更新验证字段（count+1, avg=(old_avg*old_count+new_score)/new_count, best=max(old_best,new_score), last_verified_at=now）
- StrategyResponse 返回这 4 个字段

**BS-12: 策略库验证标识** `[代码审查]`
- 策略行在 qualified badge 旁显示验证标识
- verify_count > 0 时显示："验证×N 均分X.XX"
- 颜色：均分 > 0.6 绿色，> 0.3 蓝色，≤ 0.3 灰色
- verify_count = 0 时不显示任何验证标识

**BS-13: 紧凑 toolbar 配置** `[代码审查]`
- 配置区 2 行内联，不使用 GlassCard 容器
- 所有参数默认可见，不需要折叠
- 验证完成后折叠为 1 行摘要 + [重新验证]

**BS-14: 卡片操作按钮** `[代码审查]`
- 达标策略：[▶ 开始交易] 绿色 + 👁 回测 + 🧬 优化
- 未达标策略：[🧬 继续优化] 蓝色 + 👁 回测 + 💹 交易
- 导航传参与策略库页面一致

**BS-15: 卡片展开详情** `[代码审查]`
- 点击卡片主体展开/折叠
- 显示 DNA 摘要 + 各区间详细指标
- 展开面板底部有完整操作按钮

### 8. 风险披露

| 风险 | 确定性 | 影响 | 缓解 |
|------|--------|------|------|
| Strategy.dna 可能为 undefined | 低 | 中 | 操作按钮在 dna 不存在时 disabled |
| finalize 中逐策略 update_strategy 是 N 次单独 SQL | 确定 | 低 | verify 一次通常 <50 条策略，单次 UPDATE 很快 |
| 已有历史验证数据不会自动回填到新字段 | 确定 | 低 | 默认 0/NULL，从本次验证开始累积 |

### 9. 实施顺序

1. **T1: 数据模型**（BS-10）— db_ext.py: ALTER 函数 + allowed 扩展 + version 24
2. **T2: 后端回写**（BS-11）— schemas.py + strategies.py: finalize/verify 回写 + response 返回
3. **T3: 前端类型** — types/api.ts: Strategy +4 字段
4. **T4: 验证页面重写**（BS-13~15）— Verify.tsx: toolbar + 进度 + 卡片+操作+展开
5. **T5: 策略库验证标识**（BS-12）— Strategies.tsx: 行内验证 badge
6. **T6: 测试验证** — pytest + vitest + TypeScript

---

## 推理链 v3

### 1. 任务定义

重新设计策略验证页面的空间分配、信息架构和验证进度追踪。页面功能本质是"选日期区间 → 验证全部策略（实时看到进度）→ 看卡片结果"。需要：配置占最少空间、验证中显示真实进度、结果以策略卡片形式展示三个维度（达标/评分/一致性）。

### 2. 现状定位

**设计问题**：空间分配倒置 + 验证过程无反馈
- 配置区占 40% 页面高度但功能只是选日期
- 验证中只显示一个 spinner，无法知道进度
- 结果用不可读的密集表格展示

**代码 bug**：缓存 key 不匹配 + 4 个数据源无 loading/error

**后端验证循环结构**（strategies.py:604-765）：
```
for group (symbol/timeframe分组):
    for date_range (日期区间):
        load_data()
        batch_run(group所有策略)  ← 向量化一次完成
        for strategy in group:
            save_result()
```
总步骤数 = len(groups) × len(data_ranges)。每个步骤完成一个品种+区间的所有策略回测。

### 3. 解决策略

**策略：配置最小化 + SSE 进度追踪 + 策略卡片网格**

页面分三种状态：

**待验证态**：
```
┌─ Header（1行）────────────────────────────────────┐
│ 🛡 策略验证   23条策略 · 3品种     [历史记录]    │
├────────────────────────────────────────────────────┤
│ ┌─ Config（紧凑 2-3行）───────────────────────┐  │
│ │ [近3月] [近6月] [近1年]  [+ 自定义区间]     │  │
│ │ 2024-01 ~ 2025-01                            │  │
│ │ [高级参数 ▼]                    [▶ 开始验证] │  │
│ └─────────────────────────────────────────────┘  │
│ ┌─ 引导区 ────────────────────────────────────┐  │
│ │      配置时间区间后开始验证                  │  │
│ │      将验证全部 23 条策略                    │  │
│ └─────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────┘
```

**验证中态**（新增 SSE 进度追踪）：
```
┌─ Header（1行）────────────────────────────────────┐
│ 🛡 策略验证   23条策略 · 3品种     [历史记录]    │
├────────────────────────────────────────────────────┤
│ ┌─ 进度面板 ──────────────────────────────────┐  │
│ │                                              │  │
│ │  ████████████░░░░░░░░░  4/9 步骤            │  │
│ │                                              │  │
│ │  正在处理 BTC/1h · 2024-04~2024-07           │  │
│ │  已完成 12 条策略 · 2 个区间                 │  │
│ │                                              │  │
│ │  [取消验证]                                  │  │
│ │                                              │  │
│ └──────────────────────────────────────────────┘  │
│                                                    │
│  ┌─ 渐进结果（已完成的步骤结果）──────────────┐  │
│  │ (已完成的策略结果逐步出现)                  │  │
│  └────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────┘
```

**结果态**：
```
┌─ Header（1行）────────────────────────────────────┐
│ 🛡 策略验证   23条策略 · 3品种     [历史记录]    │
├────────────────────────────────────────────────────┤
│ ┌─ Config（折叠为1行）────────────────────────┐  │
│ │ 3个区间 (2024-01~2025-06) · 100,000初始资金  │  │
│ │ [修改配置]                                   │  │
│ └─────────────────────────────────────────────┘  │
│                                                    │
│  达标 12/23    │    均分 0.72    │    最佳: 策略名  │
│                                                    │
│  [筛选: 全部 ▼]              [排序: 综合评分 ▼]    │
│                                                    │
│  ┌─ Strategy Card ─────────────────────────┐      │
│  │ #1 策略名 [进化] BTC/1h      0.85  2/3  │      │
│  │ ██████ +15.2%✓ │ ████ +8.3%✓ │ ██-2.1%✗│      │
│  │ 年化+12.4% 夏普1.03 回撤-8.5% 胜率58%   │      │
│  └─────────────────────────────────────────┘      │
│  ... 更多卡片 ...                                  │
└────────────────────────────────────────────────────┘
```

**SSE 进度追踪设计**：

后端新增 `POST /api/strategies/verify/stream` endpoint：
- 保持原 `/verify` endpoint 不变（向后兼容）
- 将现有双层循环提取为可复用函数 `_process_verify_range()`
- SSE 生成器在每个 group×range 步骤完成后 yield 进度事件

事件格式：
```
event: progress
data: {"current": 4, "total": 9, "group": "BTC_1h", "range_start": "2024-04-01", "range_end": "2024-07-01", "batch_results": [...]}

event: complete
data: {"session_id": "xxx", "summary": [...], "results": [...]}
```

前端消费：
- 使用 `fetch` + `ReadableStream`（非 EventSource，因为需要 POST）
- 每收到 progress 事件更新进度条和已完成结果
- 收到 complete 事件切换到结果态
- 支持通过 `AbortController` 取消验证

### 4. 范围边界

**改动文件**：
- `api/routes/strategies.py` — 新增 SSE endpoint + 提取循环函数（~80 行新增，不改现有 endpoint）
- `web/src/pages/Verify.tsx` — 完全重写
- `web/src/hooks/useStrategies.ts` — 修缓存 key（1行）+ 新增 SSE hook
- `web/src/services/strategies.ts` — 新增 SSE 请求函数

**不改动**：
- 现有 `/verify` endpoint — 保持不变
- db_ext.py — 不改
- schemas.py — 不改（复用现有类型）
- types/api.ts — 不改（复用现有类型）
- 其他页面 — 不影响

### 5. 行为规格

**BS-1: 页面状态切换** `[代码审查]`
- 未验证态 → 验证中态 → 结果态，三种状态对应不同布局
- 历史态通过 header 按钮切换，独立于验证流程

**BS-2: 紧凑配置区** `[代码审查]`
- 3-4 行内完成所有配置（预设 + 日期 + 操作）
- 默认 1 个日期区间
- 高级参数折叠，默认收起
- "开始验证"按钮右对齐
- 验证完成后折叠为 1 行摘要

**BS-3: SSE 进度追踪** `[集成测试]`
- 后端 `/verify/stream` 在每个 group×range 步骤完成后推送 progress 事件
- progress 事件包含：current（当前步骤）、total（总步骤）、group（品种/周期）、range（当前区间）、batch_results（本批次结果）
- complete 事件包含：session_id、summary（综合评分列表）、results（全部原始结果）
- 前端进度面板显示：进度条 + "步骤 X/M" + 当前处理品种/区间 + 已完成策略数
- 支持取消验证（AbortController 断开 SSE 连接）
- 取消时后端将 session 标记为 failed

**BS-4: 策略卡片** `[代码审查]`
- 3 行结构：头部（排名+名称+评分+达标率）/ 周期条（色条+收益率+达标标记）/ 汇总指标
- 综合评分使用 getFitnessColor 颜色编码
- 周期条色条：正收益绿色、负收益红色，宽度按比例缩放
- grid 布局：1列→2列→3列 响应式

**BS-5: 筛选排序** `[代码审查]`
- 筛选：全部/达标/未达标
- 排序：综合评分(默认) / 达标率 / 平均收益

**BS-6: 统计摘要** `[代码审查]`
- 紧凑单行：达标数 / 平均评分(颜色编码) / 最佳策略名

**BS-7: 历史记录** `[代码审查]`
- header 按钮切换到历史视图
- Session 列表 + 展开详情
- loading/error 状态完整

**BS-8: Loading/Error 状态** `[代码审查]`
- 所有数据源有 loading 状态
- 策略为空有 EmptyState
- API 错误有错误提示

**BS-9: 缓存 key 修复** `[测试验证]`
- invalidateQueries queryKey 修正

### 6. 风险披露

| 风险 | 确定性 | 影响 | 缓解 |
|------|--------|------|------|
| SSE endpoint 中 batch_run 是 CPU 密集同步操作，可能阻塞事件循环 | 确定 | 高 | 使用 asyncio.to_thread() 包装，确保不阻塞 |
| 策略数 >50 时卡片过多 | 确定 | 中 | 增加分页（每页 20 张） |
| SSE 连接中断时 session 停留在 running 状态 | 确定 | 中 | 前端取消时调用 update_session(failed)；后端检测断开 |
| 完全重写可能遗漏功能 | 确定 | 中 | 逐条对照行为规格 |

### 7. 实施顺序

1. **T1: 后端 SSE endpoint**（BS-3 后端部分）
   - 提取循环逻辑为 `_process_verify_range()` 可复用函数
   - 新增 `POST /verify/stream` SSE endpoint
   - 保持原 `/verify` endpoint 不变

2. **T2: 前端 SSE hook + 缓存 key 修复**（BS-3 前端 + BS-9）
   - 新增 `useVerifyStream` hook（fetch + ReadableStream 解析 SSE）
   - 修复缓存 key

3. **T3: 重写 Verify.tsx 页面**（BS-1/BS-2/BS-4~BS-8）
   - 紧凑配置区（可折叠）
   - 进度面板（进度条 + 取消按钮）
   - 策略卡片网格（含周期条可视化）
   - 筛选/排序
   - 历史视图
   - Loading/Error/Empty

4. **T4: 端到端测试**
   - TypeScript 编译 + vitest + pytest
   - SSE 进度端到端验证
