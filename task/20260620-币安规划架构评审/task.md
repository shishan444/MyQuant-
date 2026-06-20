# 币安 testnet 接入规划 · 架构评审

> **任务性质**：对已冻结规划（`task/20260620-币安合约testnet接入规划/task.md`）做架构评审，给观点意见。非实施任务。
> **研究方法**：2 个 Explore subagent 并行（架构层 + 链路层），每个判断带文件:行号。评审判断由主 agent 综合下，subagent 只返回客观事实。

---

## 一、总体判断（结论先行）

规划的**方向是对的、纪律是好的**——"独立模块"做风险物理隔离、"模拟交易零改动"做回归保护，这两条在涉及真金白银（哪怕 testnet）的场景里是正确的工程纪律。

但规划存在 **三个架构性认知偏差**，按现状实现会在中途踩坑：

1. **共享边界划得过宽**：规划说共享"信号+决策+风控规则"，但工程事实是**风控不是纯计算**（是 VirtualAccount 的有副作用方法，无法 import），且**shift(1) 的时序安全保证不在纯计算层**（在 pipeline 的跨 bar 暂存机制里，被划成了"独立"）。
2. **时序语义鸿沟被低估**：模拟交易整套链路依赖"逐 bar 严格时序、bar 闭合才推进"。规划没明确实盘是 bar 模型还是 tick 模型——这决定了能否安全复用 judgment 语义。
3. **HEDGE 双仓的不可对照性**：规划说"双向持仓匹配 DNA direction=mixed"，但 **direction="mixed" 不是对冲，是逐 bar 信号二选一**；模拟交易是单仓互斥模型，物理上不支持双仓。实盘双仓是模拟从未验证过的形态。

偏差 1、2 是**实现前必须修正**的；偏差 3 是**必须由你决策**的（关系到"零改动模拟交易"与"实盘双仓"能否同时成立）。

---

## 二、研究事实摘要（subagent 证据）

### F1. 模拟交易 Runner 是"硬绑定"的，非通用编排
- `TradingRunner` 直接 `new VirtualAccount`（`runner.py:230-235`）、`new DecisionPipeline`（`runner.py:311`），表名硬编码 `paper_trading_task`（`runner.py:83`）。
- **无执行后端接口抽象**（无 AbstractExecutor/IOrderGateway Protocol）。`TradingRunner` 与 `EvolutionRunner`（`api/runner.py:455`）各自独立实现 `TaskController`，无共享基类。
- 推论：实盘 `LiveTradingRunner` 会是**第三个独立编排实现**，任务循环/状态机/心跳/崩溃恢复/进度持久化/WS 推送与模拟交易大量重复。

### F2. 持仓记账模型是"单仓互斥"，无对冲
- `VirtualAccount.position` 是 `Optional[Position]` 单字段（`account.py:64`），同一时刻只有一个 Position 或 None。
- 反向信号"先平后开"（`judgment.py:72-80`，Rule 4），物理上**不可能同时持多+空**。
- 全文无 "hedge"/对冲保证金逻辑（account.py / position.py 未找到）。强平保证金是单仓维度公式 `account.py:313`。

### F3. direction="mixed" 是"信号二选一"，不是"对冲"
- `judgment.py:84`：`direction = "long" if signals.direction>0 else "short"`——每 bar 信号只有一个方向（+1/-1/0）。
- `judgment.py:88`：只有 `allowed_direction=="mixed"` 时才让信号方向自由选；但 `Decision` 仍只产单一方向（`judgment.py:96-102`）。
- 结论：mixed = "允许做多也允许做空"（择时），≠ "允许同时持多空"（对冲）。规划把这两个语义混为一谈了。

### F4. 决策依赖本地即时内存状态，无外部状态感知
- `account.get_state()`（`account.py:466-482`）读 `self.position` 内存；`judgment.evaluate` 是纯函数（`judgment.py:13-17`），状态全靠入参。
- "外部改变持仓时的感知机制"——**未找到**。模拟交易假设持仓变更只来自本进程。

### F5. shift(1) 的时序安全靠 pipeline 跨 bar 暂存，不在纯计算层
- 模拟交易路径代码里**没有 `.shift(1)`**（shift 只在回测 `engine.py:418` 和指标跨 bar 条件层）。
- 时序等价物是 `pending_decision` 跨 bar 暂存（`pipeline.py:32,197,243`）：bar N 信号 → bar N+1 `bar_open` 执行（`pipeline.py:189-196`）。
- 依赖前提：`process_bar` 严格按 bar 边界、`bar_idx` 单调（`runner.py:376`）。

### F6. 风控是"逐 bar 后回测式扫描"，有副作用，非纯计算
- `check_sl_tp`（`account.py:266-307`）：每 bar 用 `bar_high/bar_low` 扫描，命中直接 `_close_position`（改 balance/清 position）——**有副作用**。
- `check_liquidation`（`account.py:309-314`）：返回 bool，平仓动作由调用方 `pipeline.py:179` 执行。
- 唯一的纯计算风控是 `max_hold_bars`（`judgment.py:42-51`，返回 Decision），但它依赖 `position_bars_held`（account 计数器）。

### F7. 崩溃恢复哲学："crash is a bug, mark error and stop"
- `runner.py:317-318` 注释 + `runner.py:319-324`：pending+有历史 → 标 error 停止，**不续跑**。
- 与进化任务的 `restart_crashed_tasks`（`api/runner.py:147`）哲学相反。

### F8. 时序前提清单（实盘改 tick 模型全部失效）
1. `pending_decision` 跨 bar 暂存（`pipeline.py:32`）
2. SL/TP 用 `bar_high/bar_low` 判定（`account.py:288,300`）——依赖 bar 闭合
3. 限价单 fill 判定 `bar_low<=price<=bar_high`（`order_manager.py:58`）
4. GARCH 按 bar observe（`predictor.py:57-104`）
5. `_bars_held_count` 每 bar +1（`account.py:450`）
6. funding 按 bar 周期（`account.py:316-326`）

---

## 三、评审意见：三个架构性认知偏差

### 偏差1：共享边界划得过宽 → 修正为"只共享纯计算"
| 规划说法 | 工程事实 | 影响 |
|---|---|---|
| 共享"风控规则（SL/TP/max_hold 逻辑）" | `check_sl_tp`/`check_liquidation` 是 VirtualAccount 方法，深度耦合 `self.position`/`self.balance`，**有副作用**，无法 import（F6） | 规划环3"风控规则 import 复用"不成立。实盘风控必须重写为"下单前拦截"语义（RiskGuard），与模拟"逐 bar 扫描"语义不同 |
| 共享"决策规则 judgment.py" | ✅ `evaluate` 确实纯函数（F4），可共享 | 无影响 |
| 隐含：shift(1) 时序安全随纯计算层共享 | shift 的等价保证在 **pipeline 的 pending_decision 暂存**（F5），pipeline 被划为"独立" | **实盘没继承时序安全保证**。实盘 pipeline 要自建等价机制，且依赖 bar 模型（见偏差2） |

**修正建议**：把规划"共享边界"表精确改为——
- ✅ 可共享：`executor.py`（信号生成）、`judgment.py evaluate`（决策纯函数）、`types.py`（数据类）、`order_generator.py` 的定价计算部分、DNA/GARCH
- ❌ 不可直接 import，需重写实盘语义：风控（SL/TP 触发 → 下单前拦截 + 交易所托管单）、状态管理（内存即时 → 交易所为准 + 本地缓存）
- ⚠️ 时序安全：实盘必须自建"bar 闭合才决策"的等价机制（不是复用，是重实现，见偏差2）

### 偏差2：时序语义鸿沟被低估 → 必须明确"按 bar 轮询"
- 模拟交易整套链路（F8 六项）依赖"逐 bar 严格时序、bar 闭合才推进"。
- 规划环6 R4/R6 提了"状态漂移""testnet 行情偏差"，但没回答**根本问题：实盘是 bar 模型还是 tick 模型？**
  - 若 **tick/实时**：F8 全部失效（bar 未闭合 high/low 不可知，SL/TP fill 判定错，GARCH 被未成型 bar 污染）。
  - 若 **按 bar 轮询**（bar 闭合才决策+下单）：可安全复用 judgment 决策语义 + SL/TP 触发语义，但代价是"信号延迟一个 bar"（bar 闭合→下个 bar_open 下单），testnet 可接受。
- **修正建议**：规划行为规格必须显式写死**"实盘按 bar 轮询模型"**（与模拟交易同模型），这是安全复用纯计算层的前提。tick 实时作为未来选项排除在本轮。

### 偏差3：HEDGE 双仓不可对照 → 需要你决策（最关键）
- 规划环3："双向持仓 HEDGE 支持同时持多+空，匹配 DNA direction=mixed"。
- 工程事实（F2/F3）：**direction="mixed" 是择时（二选一），不是对冲；模拟交易单仓互斥，不支持双仓**。
- 后果链条：
  - 实盘 HEDGE 双仓 = 模拟交易**从未验证过的持仓形态**
  - 这直接打破 MyQuant 价值链"回测→模拟→实盘"的验证传递性
  - 规划现在两头都要（① 零改动模拟交易 ② 实盘双仓匹配 mixed DNA），**逻辑不自洽**
- **三个可决策方向**（需你选）：
  - **A. 单仓模式**（推荐起步）：实盘也用单仓（单向/双向择时，二选一不并存），完全复用模拟交易已验证的持仓语义。HEDGE 作为后续演进。
  - **B. 双仓模式，接受验证缺口**：实盘支持对冲，明确标注"模拟交易无法验证双仓，实盘是首次"，靠 testnet 兜底。需新增 DNA 对冲语义（mixed≠hedge）。
  - **C. 先让模拟交易支持双仓**：违反"零改动"，但补齐价值链。最重。

---

## 四、其他需注意的点（非致命，但影响实现质量）

- **N1."零回归"边界要精确**：共享层（executor/judgment）被实盘场景测出 bug 修复时，会连带影响模拟交易——这不是"改模拟交易"，是"共享代码演化"。规划应声明：共享层修改走最小回归（全量测试），不违反零改动承诺。
- **N2. 编排层重复可接受但别漂移**：三份 Runner（trading/evolution/live）会重复编排逻辑。可接受（独立模块代价），但建议提取轻量编排骨架（至少 TaskController 已部分共享），别让三份各自演化。**注意**：实盘崩溃恢复**不能照抄**模拟交易的"crash→error→stop"（F7）——实盘崩溃时交易所端止损止盈单可能还在，重启要处理孤儿挂单。
- **N3. 真实止损止盈单生命周期**：模拟 SL/TP 是开仓时算的**固定绝对价**（`pipeline.py:75-92`），不变。实盘交易所托管单（STOP_MARKET/TAKE_PROFIT_MARKET）若 v1 固定止损→生命周期简单（开仓挂/平仓撤）；移动止损/保本止损→每次改价撤旧挂新。建议规划明确"v1 固定止损止盈，移动止损后续"。
- **N4. python_binance 1.0.37 不确定性应在实现前消除**：规划 R7 标"不确定"。应插入"第 0 步 spike"（装环境+连 testnet+发 1 单测试单，30 分钟消除），放在 10 步实施顺序的 BinanceClient 封装之前。
- **N5. §1 红线隔离强度**：core/live_trading/ 是同进程同 DB 同依赖。层3 testnet 可接受；但若未来层4真实资金，这层隔离不够。建议（不强制）：core/live_trading/ 独立依赖声明 + 独立配置命名空间 + 独立日志，让实盘子系统边界在代码结构上肉眼可见，为未来独立仓库预留。

---

## 五、实施顺序评审

规划 10 步依赖排序大体合理，**微调建议**：
- 插入**第 0 步**：版本 spike 验证（N4）——消除 1.0.37 不确定性，前置依赖。
- **第 1 步前**：明确"按 bar 轮询模型"决策（偏差2）——它是 Runner 设计的前提，不解决第 6 步 LiveTradingRunner 写出来对不上。
- **第 3 步"模块骨架"**：数据类设计要反映偏差1的共享边界（LiveAccount 独立状态模型，不复用 VirtualAccount；RiskGuard 独立拦截语义，不复用 check_sl_tp）。
- **HEDGE 决策（偏差3）影响第 4 步 BinanceTestnetGateway 的下单矩阵**——A 方向是单仓（4 种动作），B 方向是双仓（4 种动作 + positionSide 双参），实现量级不同。决策要在第 4 步前定。

---

## 六、评审结论

- **可保留**：独立模块方向、零回归纪律、10 步依赖排序骨架。
- **必须修正（实现前）**：偏差1（共享边界精确化）、偏差2（写死 bar 轮询模型）。
- **必须你决策**：偏差3（单仓 A / 双仓 B / 改模拟 C）——这是最关键的，决定整个模块的复杂度和验证可信度。
- **建议前置**：第 0 步 spike；HEDGE 决策。

**下一步**：等你针对偏差3给出方向（以及偏差1/2是否认可修正），我据此更新冻结规划，再谈是否进入实现。

---

# Part 2：实盘模块全景 + 计算引擎能力评估（用户追问，2026-06-20）

> 用户认可"实盘只能复用策略计算"，追问两个第一性原理问题：①实盘量化软件该有哪些模块②计算引擎是否满足实盘要求。本节为结论，证据含源码验证。

## 七、实盘量化软件的 11 个模块（第一性原理分解）

根本问题：**在不确定市场里，基于规则自动把订单送到交易所、管理其生命周期、且不失控。** 从数据流必然环节分解：

1. 行情接入（实时/脏数据/断线重连）
2. 策略计算（信号，纯计算）
3. 决策生成（信号+持仓→动作意图，纯函数）
4. OMS 订单管理（真实生命周期状态机/幂等/孤儿单）
5. 执行网关（交易所API封装/限频/错误码）
6. 持仓账户（**交易所为准**，本地缓存）
7. 下单前风控（名义额/频率/熔断——实盘生命线）
8. 任务编排（bar 轮询/状态机/崩溃恢复孤儿挂单）
9. 凭证配置（加密/权限最小化/testnet 隔离）
10. 持久化（DB 缓存+审计）
11. 监控告警（亏损/连接异常）

### 对照 MyQuant 现状（用户判断正确：只模块2、3可复用）
| 模块 | MyQuant | 实盘 |
|---|---|---|
| 1 行情接入 | executor 读本地 df | 新建（增量拉取+脏校验） |
| 2 策略计算 | executor | **复用** |
| 3 决策生成 | judgment | **复用** |
| 4 OMS | OrderManager 本地撮合 | 新建（真实状态机） |
| 5 执行网关 | 无 | 新建（币安 API） |
| 6 持仓账户 | VirtualAccount 本地记账 | 新建（交易所为准） |
| 7 下单前风控 | 无（只逐bar后扫描） | 新建（下单前拦截） |
| 8 任务编排 | TradingRunner 硬绑定 | 新建（bar 轮询+孤儿单） |
| 9 凭证 | 无 | 新建（加密+隔离） |
| 10 持久化 | paper_trading_task | 新建（live_trading_task） |
| 11 监控 | 无 | 可选起步 |

**实盘 = 9 个新建模块工程，复用 2 个纯计算内核。** OMS/下单前风控/执行网关/状态同步是事故高发区=核心难点。

## 八、计算引擎能力评估（实盘硬要求做标尺，源码证据）

| 实盘硬要求 | 表现 | 评价 |
|---|---|---|
| 确定性 | random 仅 `evolution.py`（离线进化，不在实盘路径） | ✅ 可复现审计 |
| 无未来函数 | shift(1)+pending 暂存 | ✅ 保证在 pipeline 层，实盘重建 |
| 脏数据鲁棒 | executor 9 处 `fillna(False)`、factors `pd.notna` | ✅ NaN→不发信号（安全侧） |
| 成本考量 | `judgment.py:60-67` exit 估算往返手续费，微利拒平 | ✅ exit 有；⚠️ entry 无成本/频率过滤 |
| 反手控制 | `min_hold_bars`（judgment.py:55） | ✅ 平仓侧 |
| 可解释 | DNA 规则 | ✅ |
| bar 内路径 | `account.py:290` SL 优先 | ⚠️ 固有局限（实盘路径未知） |
| 流式增量 | 向量化批算 | ⚠️ 效率非正确性 |
| 实盘约束感知 | judgment 不知保证金/强平距/挂单 | ❌ 下单前风控补 |

**结论**：计算引擎对 bar 级低频规则策略实盘**够格且有诚意**（确定性+未来函数+脏数据安全侧+成本过滤+反手控制齐全）。3 个边界：①天花板=bar 级规则（非高频，是定位非缺陷）②成本过滤不对称（entry 无，可改进）③够不够取决于模型选择（bar 轮询够，tick 不够且不该用）。

## 九、对原评审的强化

Part 2 结论**强化偏差1、偏差2**：复用边界精确到纯计算（模块2、3）；时序模型必须 bar 轮询。偏差3（HEDGE 单/双仓）仍待用户决策，不受 Part 2 影响。
