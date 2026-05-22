# 测试框架用例更新

## 任务定义
根据 docs 文档中描述的接口契约和行为规格，补充缺失的测试用例，使测试覆盖与文档对齐。

## 现状定位

### 测试覆盖现状
- 现有测试总数：~120 个（trading 模块 83 + prediction 模块 37）
- 文档描述的行为规格：54 条（模拟交易 35 + 价格预测 19）
- 端到端场景：10 个

### 关键覆盖缺口（按模块）

**DecisionPipeline（缺口最大）**：
- `process_bar` 从未与 predictor+df 组合调用 → Steps 1-2 (observe/predict) 在管线上下文中未测试
- `_evaluate_with_orders` 的 add 路径（有持仓+同向入场→生成 add order）未覆盖
- `_evaluate_with_orders` 的 reversal 路径（有持仓+反向入场→平仓）未覆盖
- `profit_add_only` 守卫在管线上下文中未测试
- Liquidation 路径（Step 5）未触发
- PositionPlan 生命周期（Step 6/6b）在管线上下文中未测试

**VirtualAccount.fill_order**：
- 是订单管理系统与账户的桥梁，但从未被直接测试
- entry/add 两种 source 的行为均未验证
- 所有现有测试使用 fee=0.0, slippage=0.0，费用和滑点扣除逻辑完全未验证

**PriceRangePredictor**：
- `needs_retrain` true 条件未测试（只测了 false）
- `predict` with 非空 factor_weights 未端到端验证
- `miss_streak >= 3` 中间分支未测试（只测了 >= 5）

**ReplayRunner**：
- `predictor_factory` 参数从未被传入测试
- `avg_wait_bars` 计算未验证
- 有持仓时的 equity fallback 路径未测试

### 根因分析
这是架构演进的必然结果：(1) 预测性订单管理系统新增了 pipeline/order_generator/order_manager/replay 四个模块，初期测试覆盖了各模块的独立逻辑但未覆盖管线集成路径；(2) VirtualAccount 的 fee/slippage 路径在重构时从未被测试；(3) 新增的 predictor 集成在 pipeline 上下文中完全缺失。

## 解决策略
按优先级分三批补充测试，每批独立可运行：

**P0（核心契约）**：文档中标注 P0 且当前无测试的行为规格。聚焦 DecisionPipeline 的 predictor 集成、fill_order、fee/slippage。

**P1（重要路径）**：文档中标注 P1 的行为规格。聚焦 _evaluate_with_orders 的 add/reversal 路径、needs_retrain true 条件、ReplayRunner predictor 集成。

**P2（边界条件）**：余额不足、tranche chase/cancel、短向 tranche 等。

排除项：TradingRunner 的实时主循环端到端测试（需要 mock 数据源、DB、WebSocket，复杂度过高，收益低）。

## 范围边界

### 改动文件清单
| 文件 | 操作 | 说明 |
|------|------|------|
| tests/test_pipeline.py | 扩展 | +10 个测试：predictor 集成、add/reversal 路径、liquidation、PositionPlan |
| tests/test_virtual_account.py | 扩展 | +8 个测试：fill_order、fee/slippage、余额不足 |
| tests/test_prediction_predictor.py | 扩展 | +4 个测试：needs_retrain true、factor_weights、miss_streak 中间分支 |
| tests/test_replay.py | 扩展 | +3 个测试：predictor_factory、avg_wait_bars、持仓 equity fallback |

### 排除项
- TradingRunner 实时主循环端到端（需要 mock 太多依赖）
- PredictionEvolver._mutate 各分支（内部实现细节，evolve 已间接覆盖）
- API 路由测试（test_trading_api.py 已有 16 个测试，覆盖充分）

## 行为规格

### S1: DecisionPipeline + Predictor 集成 [测试验证]
- 传入 predictor+df 时，process_bar 依次调用 observe→predict→后续步骤
- observe 用上一 bar 的 prev_prediction 更新 GARCH
- predict 返回 PredictionResult，存入 state.prev_prediction
- 不传 predictor 时，observe 和 predict 均跳过，prev_prediction=None

### S2: DecisionPipeline _evaluate_with_orders 完整路径 [测试验证]
- 有持仓+同向入场信号 → generate_order(source="add") → OrderManager 收到 add 订单
- 有持仓+反向入场信号 → evaluate → pending_decision(action="close")
- 有持仓+同向入场+profit_add_only=True+亏损 → 不生成订单，直接返回
- 无持仓+入场信号+已有 pending entry → 不重复生成订单

### S3: VirtualAccount.fill_order [测试验证]
- entry order + 无持仓 → 以 order.price 开仓，返回 position_opened 事件
- entry order + 有持仓 → 跳过，返回空列表
- add order + 有持仓 → 加仓，更新入场价和数量
- add order + 无持仓 → 跳过，返回空列表
- order.price > 0 → 以 order.price 执行
- order.price == 0 → exec_price = 0.0（边界）

### S4: VirtualAccount fee/slippage [测试验证]
- 开仓时从 margin 扣除 fee（fee=0.001 时，10000 仓位扣 10）
- 平仓时从 PnL 扣除开仓成本（open_cost = 开仓fee + 滑点）
- slippage > 0 时开仓价偏移（slippage=0.001，long 入场价上浮 0.1%）
- 余额不足时返回 open_skipped

### S5: PriceRangePredictor 补充路径 [测试验证]
- needs_retrain() 在 total_count >= 50 且 hit_rate < 0.45 时返回 True
- needs_retrain() 在 total_count >= 50 但 hit_rate >= 0.45 时返回 False
- predict 使用非空 factor_weights 时，k_actual 与 k_base 不同

### S6: ReplayRunner predictor 集成 [测试验证]
- 传入 predictor_factory 时，predictor 被创建并传入 pipeline
- 回放结果中 avg_wait_bars 正确计算（有 filled orders 时 > 0）
- 结束时有持仓时 final_equity = balance + margin + unrealized_pnl

## 风险披露

**确定有风险**：
- 新测试可能发现现有代码的 bug（尤其是 fee/slippage 和 fill_order 路径从未被测试过）。缓解：发现 bug 时先记录，不在此任务中修复，除非修复量极小。

**不确定**：
- fill_order 的 order.price==0 边界行为是否是设计意图。缓解：先写测试观察实际行为，如不合理再讨论。

## 实施顺序

1. **S4: VirtualAccount fee/slippage** — 不依赖其他新增测试，最基础
2. **S3: VirtualAccount.fill_order** — 依赖 S4 验证基础费用逻辑正确
3. **S5: PriceRangePredictor 补充路径** — 独立模块，无依赖
4. **S1: DecisionPipeline + Predictor 集成** — 依赖 predictor 模块
5. **S2: DecisionPipeline _evaluate_with_orders 完整路径** — 依赖 S3 (fill_order 验证)
6. **S6: ReplayRunner predictor 集成** — 依赖 S1（pipeline+predictor 集成验证）

每个步骤独立可运行（pytest 指定文件），步骤间只有逻辑依赖无编译依赖。
