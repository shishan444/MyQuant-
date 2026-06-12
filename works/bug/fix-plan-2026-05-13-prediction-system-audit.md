# 价格区间预测系统 -- 实施审计修复方案

> 日期: 2026-05-13
> 状态: 已实施完成
> 前置: Phase 1-3 已完成并提交（8 commits, 64 tests passing）
> 说明: 对已实施的价格区间预测系统进行设计 vs 代码的逐层对比审计，产出修复方案

---

## 一、审计范围

设计方案：`works/设计稿/价格区间预测系统设计方案.md`（596 行）
实施代码：`core/prediction/`（6 文件）、`core/trading/`（4 文件）、`api/`（3 文件）

逐层对比维度：架构一致性、算法正确性、时序正确性、状态管理、工程规范。

---

## 二、核心设计原则

### 崩溃是 bug，不是运维事件

正确的响应链：

```
崩溃 → 找到 bug → 修复 bug → 重新测试
```

而非：

```
崩溃 → 自动恢复 → 掩盖问题 → 继续跑
```

"恢复"机制的危害比崩溃本身更大——它让崩溃变成系统的"正常行为"，开发者失去修复根因的压力。
长期下来，系统在"经常崩溃但总能恢复"的脆弱状态中运行，直到恢复机制本身也出 bug。

结论：
- 不存在崩溃恢复，崩溃后标记 error 并记录日志，便于定位 bug
- 不存在 pause，真实交易不允许暂停
- runner 意外终止后，任务标记 stopped + stop_reason=crash_recovery，用户 restart 创建全新任务

### 任务生命周期（简化版）

```
pending → running → stopped（正常完成 / 用户停止 / 出错）
                ↓
         restart → 创建全新任务（无历史仓位、无历史状态、predictor 重新 warmup）
```

不存在的操作：pause、resume、crash recovery replay。

---

## 三、发现的问题

### BUG-1 [P1]: runner.py predict/observe 时序倒置

**是什么**

设计方案 Section 5.4 定义了每根 bar 的精确执行顺序：

```
Step 2: observe bar[i] 的 actual → 更新 GARCH 状态到 S'
Step 3: predict bar[i+1] with S'  ← 用更新后的状态
```

并且明确写了时序约束："observe 必须在 predict 之前调用（先更新 GARCH 状态，再生成新预测）"

**实际代码**（runner.py:384-413）：

```python
prediction = predictor.predict(new_df, i)         # 先 predict（用旧状态 S）
# ... process_bar_v2 ...
predictor.observe(prev_row["high"], prev_row["low"], prev_prediction)  # 后 observe
```

**影响**

GARCH 状态始终落后 1 根 bar。bar[i] 的 predict 使用的是没有被 bar[i-1] actual 更新的 sigma。

平稳市场下影响小（相邻 bar 的 sigma 变化不大）。但在剧烈波动后（如单根 -10% 大阴线），下一根 bar 的预测 sigma 偏低，产出过窄的区间。对于以波动率预测为核心的系统，这是原则性错误。

**修复**

将 observe 移到 predict 之前，并且 observe 使用当前 bar[i] 的 H/L（不是 bar[i-1]）：

```python
# 修正后时序（runner.py 主循环）：

# Step 1: observe bar[i] 的 actual，更新 GARCH
if predictor is not None and prev_prediction is not None:
    predictor.observe(
        float(row["high"]), float(row["low"]),
        prev_prediction,  # prev_prediction 是对 bar[i] 的预测
    )

# Step 2: predict bar[i+1]，用更新后的 GARCH 状态
prediction = predictor.predict(new_df, i) if predictor is not None else None
prev_prediction = prediction
```

**涉及文件**
- `core/trading/runner.py` 主循环（约 line 384-413）

---

### BUG-2 [P1]: pause/resume 能力不应存在

**是什么**

当前系统实现了 pause/resume 端点，允许暂停正在运行的交易任务，后续恢复继续执行。

**为什么是设计失误**

1. **语义上站不住**：市场不会因为系统暂停而停止波动。有仓位暴露但停止止损检查和仓位管理，不是"暂停"，是放弃控制权。

2. **训练错误的操作直觉**：纸面交易系统的职责是训练接近实盘的操作直觉。"先暂停看看"的习惯迁移到实盘就是灾难。

3. **增加不必要的系统复杂度**：pause/resume 需要完整的状态快照和恢复机制（predictor GARCH 状态、PositionPlan、pending_decision），增加了大量边界 case。

**需修改内容**

| 文件 | 修改 |
|------|------|
| `api/routes/trading.py` | 删除 `pause_task` 和 `resume_task` 端点 |
| `core/trading/runner.py` | TaskController 移除 stop_reason="pause" 语义，简化为只有 stop |

---

### BUG-3 [P1]: _min_replay 崩溃恢复机制不应存在

**是什么**

`_min_replay` 的唯一调用场景是：任务有 `last_bar_time`（之前跑过），被 runner 重新拾起。
正常流程中任务是 `pending → running → stopped`，不会回到 pending 带着历史状态重新开始。
唯一触发路径就是 runner 崩溃。

**为什么应该删除**

崩溃是 bug，不是正常操作。正确的做法是标记 error + 记录日志 + 修复 bug。
用 replay 机制掩盖崩溃，反而阻碍发现和修复真正的 bug。

**连带删除**

| 删除项 | 原因 |
|--------|------|
| `_min_replay` 方法 | 为崩溃恢复服务，崩溃应修 bug 而非恢复 |
| predictor 状态持久化 | restart 时重新 warmup，不需要保存/恢复 GARCH 状态 |
| PositionPlan 持久化 | restart 时重新创建，不需要保存/恢复挂单计划 |
| `recover_stale_trading_tasks` 的自动恢复逻辑 | 改为标记 error 并记录日志 |

**保留**

| 保留项 | 原因 |
|--------|------|
| checkpoint 保存（balance, position, last_bar_time） | 记录"跑到哪了"，便于事后分析定位 bug，不用于恢复 |
| 任务 error 标记 + 日志堆栈 | 崩溃后标记 error，日志记录完整堆栈，便于定位 bug |

**需修改内容**

| 文件 | 修改 |
|------|------|
| `core/trading/runner.py` | 删除 `_min_replay` 方法，删除 replay 调用逻辑 |

---

### BUG-4 [P3]: _process_tranches 的 long/short 死分支

**是什么**

account.py:324-328：

```python
if self.position.side == "long":
    touched = bar_low <= tranche.price_level <= bar_high
else:
    touched = bar_low <= tranche.price_level <= bar_high  # 完全一样
```

两个分支的代码完全相同。无论做多做空，逻辑都是"挂单价落在 bar 范围 [bar_low, bar_high] 内就算触及"——这是正确的。

**修复**

删除 if/else 分支，统一为一行：

```python
touched = bar_low <= tranche.price_level <= bar_high
```

**涉及文件**
- `core/trading/account.py`（约 line 324-328）

---

### BUG-5 [文档]: PredictionResult.width 定义矛盾

**是什么**

设计方案 Section 4.3 写 `width = high - low`（全宽），但 Section 5.1 的计算路径写 `width = sigma * K`（半宽）。

实现用的是半宽（`width = sigma * K`），代码注释也写了 `single-side half-width`。这和 Section 5.1 一致，但和 Section 4.3 矛盾。

数学上 `low = close - sigma*K`，`high = close + sigma*K`，所以 `high - low = 2 * sigma * K = 2 * width`。实际实现中 `width` 确实是半宽。

**修复**

更新设计方案 Section 4.3 的注释：

```
width: float    # 单侧半宽 = sigma * K（high - low = 2 * width）
```

---

## 四、遗漏项（非 bug，后续迭代）

### OMIT-1: needs_retrain() 从未被检查

`predictor.needs_retrain()` 存在但 runner.py 从未调用。当命中率持续低于 45% 时，没有任何机制发出警告。

建议：runner 保存状态时检查 needs_retrain，写入 DB 字段，API 层暴露给前端做提示。

### OMIT-2: 进化器缺少交叉操作

设计方案 Section 8 列出 "交叉：混合两个父代的参数和因子权重"，但 evolution.py 只有 _mutate()。纯变异搜索在 8 维因子权重空间中效率较低，容易早熟收敛。

### OMIT-3: prediction_dna_json 无 API 格式验证

api/routes/trading.py 对 dna_json 做了 StrategyDNA.from_json() 验证，但 prediction_dna_json 没有验证。无效 JSON 会被 _init_predictor() 的 try/except 吞掉，静默降级。

### OMIT-4: factors.py 每次调用都重新计算 rolling

每根 bar 调用 compute_factors() 时，rolling().mean() 和 rolling().rank() 都在完整的 df 上重新计算。在高频使用时有性能开销。可预计算因子列。

---

## 五、实施计划

### Phase A: runner.py 修复（预计改动 1 文件）

所有 BUG-1/2/3 的修改集中在 `core/trading/runner.py`：

1. 主循环：observe 移到 predict 之前，用当前 bar 的 H/L（BUG-1）
2. 删除 `_min_replay` 方法及其调用（BUG-3）
3. TaskController 移除 pause 语义（BUG-2 的一部分）

### Phase B: 清理 pause/resume 端点（预计改动 1 文件）

1. 删除 `api/routes/trading.py` 中 `pause_task` 和 `resume_task` 端点（BUG-2）

### Phase C: 清理死代码 + 文档修正（预计改动 2 文件）

1. `core/trading/account.py`：删除 _process_tranches 的死分支（BUG-4）
2. 更新设计方案 Section 4.3 的 width 注释（BUG-5）

### Phase D: 测试更新

1. 更新现有测试以匹配修改后的行为
2. 新增测试：验证 observe 在 predict 之前调用
3. 删除 _min_replay 相关测试（如果存在）

---

## 六、删除清单

| 删除项 | 文件 | 原因 |
|--------|------|------|
| `pause_task` 端点 | api/routes/trading.py | pause 不应存在 |
| `resume_task` 端点 | api/routes/trading.py | resume 不应存在 |
| `TaskController.stop_reason = "pause"` 逻辑 | core/trading/runner.py | pause 不应存在 |
| `_min_replay` 方法 | core/trading/runner.py | 崩溃恢复不应存在 |
| `_find_replay_start` 方法 | core/trading/runner.py | _min_replay 删除后无用 |
| `_restore_pending_decision` 方法 | core/trading/runner.py | 不再恢复历史状态 |
| `recover_stale_trading_tasks` 的自动恢复 | core/trading/runner.py | 改为标记 error |
| long/short 死分支 | core/trading/account.py | 死代码 |

---

## 七、风险评估

| 修改 | 风险 | 缓解 |
|------|------|------|
| BUG-1 时序修复 | 改变 GARCH 状态更新时机 | 改完后跑全量测试对比 |
| BUG-2 删除 pause | 前端 pause 按钮失效 | 需前端配合移除 |
| BUG-3 删除 replay | runner 崩溃后无法自动恢复 | 不应该自动恢复，崩溃是 bug 要修 |
| BUG-4 死分支 | 无风险 | 纯代码清理 |
