# 预测性订单管理系统 - 实施规划

> 状态: 待决策
> 日期: 2026-05-20

---

## 一、任务定义

为模拟交易构建独立的预测性订单管理决策管线，并实现回放模式用于快速验证。

核心改造：
- 决策管线与运行模式解耦（回放/实时共享同一管线）
- 信号 + 预测 → 限价订单（不再是市价即时执行）
- 订单生命周期管理（预测驱动，不是时间驱动）
- 回放模式：用历史数据逐根喂入决策管线，秒级完成验证

---

## 二、现状定位

### 2.1 代码证据

**回测引擎**（vectorbt，不改）：
- 入口：`core/backtest/engine.py:602` `BacktestEngine.run()`
- 信号→交易：`engine.py:206` `order_func_nb()`（Numba JIT，批量处理）
- 不使用 VirtualAccount，完全独立的执行路径
- 结果：`BacktestResult`（total_return, sharpe, trades_df等）

**模拟交易**（需要改造）：
- 主循环：`core/trading/runner.py:335-443`
- 决策管线逻辑（应提取）：`runner.py:369-433`（observe → predict → process_bar → evaluate）
- 运行模式逻辑（实时专属）：数据获取(`_fetch_and_update`)、状态持久化、WS推送、controller/wait
- 账户：`core/trading/account.py` VirtualAccount（SL/TP执行价有问题）
- 预测：`core/prediction/predictor.py` PriceRangePredictor（observe/predict管线完整）
- 判断：`core/trading/judgment.py` evaluate()（即时决策，无订单管理）

**决策管线 vs 运行模式的分界**：

| 决策管线（提取为DecisionPipeline） | 运行模式（回放/实时差异） |
|---|---|
| L378-384: predictor.observe() | L215-219: 任务状态管理 |
| L386-390: predictor.predict() | L241-259: 数据初始化+forming_bar |
| L393-402: account.process_bar_v2() | L306-318: 崩溃恢复检查 |
| L409-419: PositionPlan生命周期 | L320-322: 状态持久化+WS推送 |
| L427-431: 信号评估+决策 | L335-336: controller/stop循环 |
| L369-433整体: 逐bar处理循环 | L338-361: 数据获取刷新 |
| | L437-442: 持久化+心跳+wait |

### 2.2 根本问题

1. **架构问题**：回测和模拟交易共享信号引擎，但决策管线没有分离。模拟交易的决策逻辑和回测一样是"信号→即时执行"，缺少预测驱动的订单管理
2. **代码设计问题**：决策管线逻辑耦合在 runner.py 的实时循环中，无法被回放模式复用
3. **执行问题**：SL/TP执行价使用 bar_open 而非触发价

---

## 三、解决策略

**策略：提取 → 新建 → 集成**

1. 从 runner.py 提取决策管线为独立的 DecisionPipeline 类
2. 新建 OrderGenerator（价格计算）和 OrderManager（生命周期管理）
3. 新建 ReplayRunner 复用 DecisionPipeline，用历史数据驱动
4. 改造 runner.py 调用同一个 DecisionPipeline
5. 修复 SL/TP 执行价

排除的方案：
- 不改造回测引擎（vectorbt批量处理，架构完全不同）
- 不引入外部量化框架（现有代码已有完整基础，引入成本>收益）
- 不做市商模型（方向性交易，不需要双边报价）

---

## 四、范围边界

### 新建文件

| 文件 | 职责 |
|------|------|
| `core/trading/order_generator.py` | 信号+预测→Order的价格计算和生成 |
| `core/trading/order_manager.py` | 订单生命周期管理（成交检查/有效性/超时） |
| `core/trading/pipeline.py` | 模式无关的决策管线（从runner.py提取） |
| `core/trading/replay.py` | 回放运行器（历史数据→DecisionPipeline） |
| `tests/test_order_generator.py` | OrderGenerator单元测试 |
| `tests/test_order_manager.py` | OrderManager单元测试 |
| `tests/test_pipeline.py` | DecisionPipeline集成测试 |
| `tests/test_replay.py` | ReplayRunner集成测试 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `core/trading/types.py` | 新增 Order、PipelineResult 数据结构 |
| `core/trading/account.py` | 修复 check_sl_tp 执行价；新增订单成交接口 |
| `core/trading/runner.py` | 主循环改造为调用 DecisionPipeline |
| `core/trading/judgment.py` | 出场判断保持不变，入场改为由 OrderGenerator 处理 |

### 不修改文件

| 文件 | 原因 |
|------|------|
| `core/strategy/executor.py` | 信号引擎保持不变 |
| `core/strategy/mtf_engine.py` | MTF框架保持不变 |
| `core/prediction/predictor.py` | 预测器保持不变 |
| `core/backtest/engine.py` | 回测引擎保持不变（vectorbt架构） |
| `core/strategy/dna.py` | DNA结构保持不变（P2阶段增加pricing基因） |

---

## 五、行为规格

### 5.1 Order 数据结构

```
输入: side(long/short), price(float), size_pct(float), source(entry/add)
输出: Order实例
不变量: price > 0, size_pct in (0, 1], side in ("long", "short")
边界: price=0表示市价单（回退模式）
验证: [测试验证]
```

### 5.2 OrderGenerator 订单生成

```
输入: BarSignals, PredictionResult|None, AccountState, JudgmentConfig
输出: Order 或 None
契约:
  - signals.entry=True + prediction可用 → 生成限价Order（price由预测计算）
  - signals.entry=True + prediction不可用 → 生成市价Order（price=0）
  - signals.entry=False → 返回None
  - direction由signals.direction决定
  - size_pct由config.initial_entry_pct × target_pct计算
  - confidence_sizing生效时按confidence缩放size
不变量: 生成的Order.price在prediction区间内（有限价时）
边界: prediction=None → 回退市价；confidence=0.1 → 最小仓位
验证: [测试验证]
```

### 5.3 OrderGenerator 价格计算

```
输入: prediction(PredictionResult), direction(+1/-1), confidence(0.1~1.0), config
输出: order_price(float), fill_probability(float)
公式:
  mu = (prediction.low + prediction.high) / 2
  sigma = prediction.width
  alpha_factor = config.pricing_alpha_base + config.pricing_alpha_range * confidence
  做多: price = mu - alpha_factor * sigma, clamp(prediction.low, mu)
  做空: price = mu + alpha_factor * sigma, clamp(mu, prediction.high)
  P_fill = norm.cdf((price - mu) / sigma) [做多]
契约:
  - price始终在prediction区间内
  - P_fill >= config.pricing_min_fill_prob，否则回退市价
不变量: prediction.low <= price <= prediction.high [做多]
边界: sigma=0 → price=mu；confidence极低 → price接近mu
验证: [测试验证]
```

### 5.4 OrderManager 订单管理

```
输入: active_orders(List[Order]), bar_high, bar_low, prediction, signals
输出: OrderEvents(filled/cancelled/expired orders)
行为:
  成交检查: bar_low <= order.price <= bar_high → status="filled"
  有效性检查: prediction.low <= order.price <= prediction.high AND 无反向信号 → keep
  超时检查: bars_waiting >= max_wait_bars → status="expired"
  每根bar: 所有pending订单的bars_waiting += 1
契约:
  - filled的订单从active_orders移除
  - cancelled/expired的订单也从active_orders移除
  - 同一时间同方向最多1个entry订单
不变量: active_orders中所有订单status="pending"
边界: 无订单时→空操作；bar_high<bar_low→不检查成交
验证: [测试验证]
```

### 5.5 DecisionPipeline 管线

```
输入: bar_data(BarData), sig_set(SignalSet), bar_idx(int)
输出: PipelineResult(events, prediction, state_changed)
流程（每根bar）:
  1. predictor.observe(bar_high, bar_low, prev_prediction) [更新GARCH]
  2. predictor.predict(df, idx) [预测下一根]
  3. order_manager.manage(bar_high, bar_low, prediction, signals) [管理订单]
  4. 对filled订单: account._open_position / _add_position
  5. account.check_sl_tp(bar_high, bar_low) [SL/TP，修复执行价]
  6. PositionPlan生命周期管理（保持兼容）
  7. 信号评估 → OrderGenerator.generate() 或 evaluate() [出场]
契约:
  - observe总是在predict之前调用
  - 成交事件在SL/TP之前处理
  - 出场信号（exit/reduce）仍然立即执行
  - 入场信号（entry）生成限价Order
不变量: 每根bar处理后account状态一致
验证: [集成测试]
```

### 5.6 ReplayRunner 回放运行器

```
输入: dna, historical_df, config
输出: ReplayResult(events_list, final_account, orders_log, metrics)
行为:
  - 加载历史数据到DataFrame
  - 初始化DNA/指标/MTF/Predictor/VirtualAccount
  - 逐根bar调用DecisionPipeline.process_bar()
  - 收集所有events，计算最终metrics
契约:
  - 不访问网络/数据库（纯本地计算）
  - 不依赖TaskController/WS推送
  - 输入数据全部来自参数（DataFrame）
  - 返回与BacktestResult可对比的结果
不变量: 给定相同输入，输出确定
边界: 数据不足（<预热bars）→报错
验证: [集成测试]
```

### 5.7 SL/TP 执行价修复

```
输入: bar_high, bar_low, position(entry_price, side, stop_loss, take_profit)
输出: close events
契约:
  - Long SL: bar_low <= entry*(1-SL) → 执行价 = entry*(1-SL)
  - Long TP: bar_high >= entry*(1+TP) → 执行价 = entry*(1+TP)
  - Short SL: bar_high >= entry*(1+SL) → 执行价 = entry*(1+SL)
  - Short TP: bar_low <= entry*(1-TP) → 执行价 = entry*(1-TP)
不变量: 执行价 = 触发价（不再用bar_open）
边界: SL和TP同时触发 → SL优先（止损优先于止盈）
验证: [测试验证]
```

---

## 六、风险披露

### 确定风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| 订单在不利时机成交（逆向选择） | 入场后价格继续反向移动 | min_fill_prob阈值 + 不挂太远离中间价 |
| 回放模式结果与实时不一致 | 验证结论不可靠 | 回放和实时共用同一DecisionPipeline，逻辑保证一致 |
| 改造影响现有模拟交易功能 | 正在运行的任务异常 | 通过use_limit_orders配置开关保持兼容，默认关闭 |

### 不确定性

| 不确定性 | 影响 | 如何消除 |
|---------|------|---------|
| alpha_factor最优值范围 | 挂单价格质量 | P0先用固定值0.5，通过回放对比调优 |
| 15m bar内用high/low判断成交的准确性 | 成交模拟精度 | 与真实订单簿无关（纸交易），high/low足够 |

---

## 七、实施顺序

### Phase 1: 基础组件（Order + OrderGenerator + OrderManager）

**目标**：构建订单管理的核心数据结构和逻辑，不涉及运行模式。

```
Step 1.1: types.py 新增 Order、PipelineResult、ReplayResult 数据结构
  依赖: 无
  产出: Order dataclass, PipelineResult dataclass, ReplayResult dataclass
  验证: [代码审查]

Step 1.2: order_generator.py 实现订单生成和价格计算
  依赖: Step 1.1 (Order类型)
  产出: OrderGenerator类，generate()方法，compute_order_price()函数
  验证: [测试验证] 价格计算、边界条件、回退市价逻辑

Step 1.3: order_manager.py 实现订单生命周期管理
  依赖: Step 1.1 (Order类型)
  产出: OrderManager类，manage()/add_order()方法
  验证: [测试验证] 成交检查、有效性判断、超时处理

Step 1.4: account.py 修复SL/TP执行价 + 新增订单成交接口
  依赖: Step 1.1 (Order类型)
  产出: check_sl_tp()修复，fill_order()方法
  验证: [测试验证] SL用触发价、TP用目标价、SL优先于TP
```

### Phase 2: 决策管线

**目标**：从 runner.py 提取模式无关的决策逻辑。

```
Step 2.1: pipeline.py 实现DecisionPipeline
  依赖: Step 1.2 (OrderGenerator) + Step 1.3 (OrderManager) + Step 1.4 (account修复)
  产出: DecisionPipeline类，process_bar()方法
  验证: [集成测试] 完整管线：observe→predict→manage→execute→evaluate

Step 2.2: judgment.py 适配改造
  依赖: Step 2.1
  产出: evaluate()保持不变（出场用），入场逻辑由OrderGenerator处理
  验证: [代码审查] 确认出场路径不受影响
```

### Phase 3: 回放模式

**目标**：构建回放运行器，实现快速验证。

```
Step 3.1: replay.py 实现ReplayRunner
  依赖: Step 2.1 (DecisionPipeline)
  产出: ReplayRunner类，run()方法，返回ReplayResult
  验证: [集成测试] 用历史数据跑完整回放，验证输出完整性

Step 3.2: 回放结果对比工具
  依赖: Step 3.1
  产出: compare_replay_vs_backtest()函数，输出对比报告
  验证: [集成测试] 同一策略同一数据，对比入场价格、P&L
```

### Phase 4: 实时模式集成

**目标**：改造 runner.py 使用 DecisionPipeline。

```
Step 4.1: runner.py 重构
  依赖: Step 2.1 (DecisionPipeline)
  产出: _execute_task()改为调用DecisionPipeline，保留实时模式逻辑
  验证: [集成测试] 实时模式功能正常（通过现有流程验证）

Step 4.2: 配置开关
  依赖: Step 4.1
  产出: JudgmentConfig新增use_limit_orders配置，False时保持现有行为
  验证: [代码审查]
```

### 依赖关系图

```
Step 1.1 (types)
    ├── Step 1.2 (order_generator)
    ├── Step 1.3 (order_manager)
    └── Step 1.4 (account fix)
            │
            ▼
    Step 2.1 (pipeline) ←── Step 2.2 (judgment适配)
            │
            ▼
    Step 3.1 (replay) ──→ Step 3.2 (对比工具)
            │
            ▼
    Step 4.1 (runner重构) ──→ Step 4.2 (配置开关)
```

---

## 八、成功标准

### Phase 1 完成标准
- [ ] OrderGenerator 对各种 confidence 和 prediction 组合生成合理的价格
- [ ] OrderManager 正确识别成交、取消、超时
- [ ] SL/TP 用触发价执行（不再用 bar_open）
- [ ] 所有新代码测试覆盖率 >= 80%

### Phase 2 完成标准
- [ ] DecisionPipeline 能正确处理一根bar的完整流程
- [ ] 出场信号仍然即时执行
- [ ] 入场信号生成限价Order
- [ ] Pipeline单元测试通过

### Phase 3 完成标准（关键验证点）
- [ ] ReplayRunner 能用历史数据完成完整回放
- [ ] 回放产生的交易记录可审查（入场价、订单生命周期日志）
- [ ] 同一策略同一时间段：回放入场价格系统性优于回测（或明确得出"无优势"的结论）
- [ ] 回放可在 < 10秒 内跑完一个月的数据

### Phase 4 完成标准
- [ ] runner.py 正确调用 DecisionPipeline
- [ ] use_limit_orders=False 时行为与现有完全一致
- [ ] use_limit_orders=True 时使用新的预测性订单管理
- [ ] 正在运行的模拟交易任务不受影响
