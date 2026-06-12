# 进化引擎架构限制突破

> 日期: 2026-06-04
> 状态: 推理链冻结，阶段 B 实施中
> 用户确认: 覆盖范围认可（解决限制1 + train/test split，限制2-4延后）

---

## 研究第 1 轮

### 任务结构性理解

进化引擎存在 4 层架构限制，导致搜索空间被锁死在预计算参数集合内，且进化产出无法排除过拟合。经代码验证确认：

**限制 1：预计算参数锁死搜索空间** [代码设计问题]

变异算子（mutate_params）通过 ParamDef 生成任意参数（如 EMA period=37），但 `_get_indicator_column()` (executor.py:294-336) 只在预计算的 enhanced_df 中查找列名，找不到则抛出 ValueError，被 `except ValueError: continue` (executor.py:390-391) 静默丢弃。

- 代码证据：executor.py:294-336（列查找逻辑），executor.py:362-391（evaluate_layer 中的 try/except）
- 代码证据：indicators.py:32-83（_DEFAULT_PARAMS 固定参数集），indicators.py:90（_compute_indicator 纯函数可按需计算）
- 影响：ParamDef 变异空间中 80-99% 的参数组合必然失败（EMA 断裂率 87.5%、RSI 88%、BB ~99%）

**限制 2：Train/test split 缺失** [架构设计问题]

`_evaluate_dna()` (runner.py:725-833) 对整个 `_enhanced_df`（由 data_start 到 data_end 定义的全部数据）进行回测评估，没有预留样本外数据。进化过程的所有代都使用相同的历史数据区间。

- 代码证据：runner.py:340-343（数据加载），runner.py:378-386（闭包捕获 _enhanced_df）
- 代码证据：runner.py:793-796（BacktestEngine.run 使用完整数据）
- 影响：进化找到的"好策略"可能是历史数据的巧合（过拟合），无法验证泛化能力

**限制 3（P1）：Profile 引导偏向基础条件类型** [代码设计问题]

Profile 以 70% 概率引导进化使用 lt/gt/cross_above/cross_below 四种基础条件。工程实际支持 13+ 种条件类型（包括 cross_above_series、lookback_any、lookback_all 等），但高级条件极少被生成。

- 代码证据：indicator_profile.py（推荐条件以 lt/gt 为主）
- 代码证据：executor.py:62-73（evaluate_condition 支持多种高级条件）

**限制 4（P2）：无元学习反馈闭环** [架构设计问题]

`_AdaptiveMutationController` (engine.py:92-122) 仅基于 Rechenberg 1/5 规则调整变异强度，不从进化历史中学习"哪些指标组合更有效"。进化每一代都是从相同的 Profile 出发，没有记忆。

- 代码证据：engine.py:92-122（仅调整 mutation_boost），engine.py:306-318（停滞权重调整仅分 3 档）

### 按需计算可行性验证

`_compute_indicator(df, name, params)` (indicators.py:90) 是纯函数：
- 输入：DataFrame + 指标名 + 参数字典
- 输出：Dict[str, pd.Series]（新列名 → Series 映射）
- 不修改输入 DataFrame，不依赖全局状态
- 对未知指标名返回空 dict（不抛异常）

`resolve_indicator_column()` (registry.py:454-551) 对所有注册指标的任意参数都能生成与 `_compute_indicator` 输出一致的列名（已验证 11 种 naming 模式）。

插入点：`_get_indicator_column()` 的 executor.py:329-336（ValueError 之前）。计算结果必须写入 df 以供同代其他基因复用（pandas DataFrame 是可变引用，直接 df[col] = series 即可）。

### 决策

限制 1（按需计算）和限制 2（train/test split）是 P0 优先级，互不依赖可并行实施。限制 3、4 依赖 P0 完成后再评估是否需要。进入推理链构建。

---

## 推理链

### 一、任务定义

为进化引擎实现两个核心能力：(1) 按需计算指标，突破预计算参数对搜索空间的锁死；(2) Train/test 数据分割，让进化产出可验证的策略。目标是将进化有效搜索空间从 ~200 个参数组合扩展到数千个，并让进化的最终策略通过样本外验证。

### 二、现状定位

**关键点 A：列查找失败路径** [代码设计问题]

`_get_indicator_column()` (executor.py:294-336) 的查找路径：
1. 先通过 `resolve_indicator_column()` 生成目标列名 (executor.py:311-315)
2. 精确匹配 `df.columns` (executor.py:324)
3. 前缀模糊匹配 (executor.py:330)
4. 全部失败 → 抛出 ValueError (executor.py:336)

调用方 `evaluate_layer()` 用 `except ValueError: continue` (executor.py:390-391) 吞掉异常，该基因被跳过。没有按需计算的尝试。

`_compute_indicator()` (indicators.py:90) 可以接受任意参数组合并返回计算结果，但当前只在 `compute_all_indicators()` 的预计算循环中被调用 (indicators.py:406-444)。

**关键点 B：评估数据无分割** [架构设计问题]

数据流路径：
```
Parquet → storage.load_parquet() → mtf_loader.load_and_prepare_df()
→ compute_all_indicators() → _enhanced_df
→ 闭包捕获 (runner.py:378-386) → _evaluate_dna() → BacktestEngine.run()
```

`_enhanced_df` 在 runner.py:340-343 被加载一次，通过闭包在整个进化过程中复用。没有任何分割逻辑。`BacktestEngine.run()` (runner.py:793-796) 直接使用完整的 `_enhanced_df`。

### 三、解决策略

**策略 S1：预计算优先 + 按需计算降级**

在 `_get_indicator_column()` 中，预计算列的查找路径保持不变（零开销）。只在查找失败时，插入按需计算逻辑：调用 `_compute_indicator()` 计算缺失指标，将结果写入 df 供同代复用，然后重新查找。

选这个策略的原因：
- 最小改动（1 个函数内部插入约 20 行），不影响预计算架构
- 预计算列优先命中，按需计算只在变异产生新参数时触发
- 计算结果写入 df 后，同代中相同参数组合的后续查找直接命中缓存
- `_compute_indicator` 是纯函数，线程安全（GIL 保护 pandas 操作）

排除的方案：
- 完全按需计算（废除预计算）：需要重构整个数据管道，风险太大
- 扩展 _DEFAULT_PARAMS 覆盖所有变异空间：内存和计算时间线性增长，且无法覆盖浮点参数（如 BB std=1.7）

**策略 S2：时间序列 Walk-Forward 分割**

在 runner.py 的 `_execute_task()` 中，将加载的 `_enhanced_df` 按时间分割为 train 和 test 两段。进化评估只使用 train 段，进化完成后用 test 段验证 champion 策略。

选这个策略的原因：
- 时间序列分割保留了时间依赖性（不会用未来数据训练）
- Walk-Forward 是量化回测的行业标准
- BacktestEngine.run() 接受任意 DataFrame（runner.py:793），只需传入 df 切片即可
- 实现简单：在 runner.py:343（数据加载完成）和 runner.py:378（闭包创建）之间插入分割逻辑

排除的方案：
- K-fold 交叉验证：时间序列不能随机打乱，会引入未来数据泄露
- 滚动窗口验证（多次 train/test）：计算开销成倍增加，第一版用单次分割即可
- 固定比例分割（如前 70% train）：不如按时间分割直观

### 四、范围边界

**改动文件**：

| 文件 | 改动内容 | 原因 |
|------|----------|------|
| `core/strategy/executor.py` | 在 `_get_indicator_column()` 中插入按需计算降级逻辑 | 策略 S1 的直接实现 |
| `api/runner.py` | 在 `_execute_task()` 中添加 train/test 分割，在进化完成后用 test 段验证 champion | 策略 S2 的直接实现 |
| `tests/test_on_demand_compute.py`（新建） | 按需计算的测试 | S1 验证 |
| `tests/test_train_test_split.py`（新建） | Train/test 分割的测试 | S2 验证 |

**不改的文件**：

| 文件 | 排除原因 |
|------|----------|
| `core/features/indicators.py` | `_compute_indicator` 已是纯函数，无需修改 |
| `core/features/registry.py` | `resolve_indicator_column` 对任意参数已正确工作 |
| `core/backtest/engine.py` | BacktestEngine.run() 已支持任意 DataFrame，无需修改 |
| `core/evolution/engine.py` | 进化引擎核心逻辑无 bug，按需计算在 executor 层透明完成 |
| `core/scoring/scorer.py` | 评分逻辑无问题 |
| `web/` 前端 | 本次改动不涉及前端变更（test 段验证结果可通过现有 champion 机制展示） |

### 五、行为规格

#### S1: 按需计算指标

**S1.1 预计算列优先命中** `[代码审查]`
- 前置：指标列已存在于 df 中（预计算命中）
- 行为：直接返回预计算列，不触发 `_compute_indicator`
- 后置：性能与当前完全一致（零额外开销）

**S1.2 按需计算降级** `[测试验证]`
- 前置：指标列不存在于 df 中，但指标在 INDICATOR_REGISTRY 中有注册
- 行为：调用 `_compute_indicator(df, indicator, params)` 计算指标，将所有输出列写入 df，通过 `resolve_indicator_column` 匹配目标列并返回
- 后置：变异产生的任意参数组合都能找到对应的指标列
- 边界：`_compute_indicator` 返回空 dict（未知指标或缺少前置数据）→ 仍抛出 ValueError

**S1.3 计算结果复用** `[测试验证]`
- 前置：同一代中多个基因使用相同 (indicator, params) 组合
- 行为：第一次查找触发按需计算并写入 df，后续查找直接从 df 命中
- 后置：同参数组合不重复计算
- 不变量：按需计算的列与预计算列在 df 中不可区分

**S1.4 缓存一致性** `[测试验证]`
- 前置：`clear_indicator_cache()` 在每代开始时被调用
- 行为：缓存基于 `(id(df), indicator, params, field_name)` 键，按需计算写入 df 后缓存键的 df.id 不变
- 后置：按需计算的列在新一代中仍然存在于 df 中（因为 enhanced_df 在整个进化过程中被复用）

#### S2: Train/Test 数据分割

**S2.1 数据分割** `[测试验证]`
- 前置：`_enhanced_df` 加载完成（runner.py:340-343），数据量 >= 100 bars
- 行为：按时间分割为 train_df（前 train_ratio）和 test_df（后 1-train_ratio），train_ratio 默认 0.7
- 后置：train_df 和 test_df 是完整且不重叠的时间序列片段
- 边界：数据量 < 100 bars → 不分割，使用完整数据 + 警告日志

**S2.2 进化评估使用 train 段** `[代码审查]`
- 前置：train_df 和 test_df 已分割
- 行为：evaluate_fn 闭包捕获 train_df 而非完整 _enhanced_df，BacktestEngine.run() 只在 train_df 上评估
- 后置：进化过程中个体从未见过 test 段数据

**S2.3 Champion 样本外验证** `[测试验证]`
- 前置：进化完成，champion 已选出
- 行为：在 test_df 上对 champion 运行 BacktestEngine.run()，产出 oos_result（out-of-sample result）
- 后置：champion 的 oos_result 包含 fitness、total_trades、max_drawdown 等指标，且这些指标基于未见数据
- 边界：oos_result.total_trades == 0 → champion 在样本外不交易，标记为 oos_qualified=False

**S2.4 OOS 结果持久化** `[代码审查]`
- 前置：oos_result 计算完成
- 行为：将 oos fitness、oos_qualified、oos_metrics 写入 task 表的 champion 记录
- 后置：前端可展示 champion 的 in-sample 和 out-of-sample 对比

### 六、风险披露

| 风险 | 确定性 | 影响 | 缓解 |
|------|--------|------|------|
| 按需计算对每个变异个体增加计算时间 | 确定 | pandas-ta 向量化计算 sub-millisecond/指标，每代约 90 个独立基因签名，总增 ~9ms | 可忽略 |
| 按需计算写入 df 增加内存占用 | 确定 | 每个新参数组合增加 1-3 列 Series，典型 OHLCV ~10K 行，每列 ~80KB | 远小于预计算的内存占用 |
| 按需计算的列名与预计算列名可能不一致 | 不确定 | 如果 `resolve_indicator_column` 和 `_compute_indicator` 的命名逻辑不匹配，列查找会失败 | 已验证 11 种 naming 模式一致性，但需测试覆盖边界情况 |
| Train/test 分割比例选择影响结果 | 确定 | 70/30 是常见默认值，但可能不适合所有品种和周期 | 参数化 train_ratio，允许用户在创建任务时指定 |
| test 段数据量不足导致验证不可靠 | 确定 | 短周期（如 1 个月 15m 数据）的 30% 可能只有几天 | 数据量 < 100 bars 时不分割并警告 |
| df 按需写入的线程安全性 | 不确定 | 进化引擎单线程顺序评估个体，不存在并发写入 | 已安全，但 batch_run 模式需要确认 |

### 七、实施顺序

```
Step 1: S1 按需计算 [高风险，核心]
  ├─ 1a: 在 _get_indicator_column() 中插入按需计算降级逻辑
  ├─ 1b: 编写按需计算测试（正常路径 + 边界路径 + 复用验证）
  └─ 1c: 运行测试确认预计算路径不受影响
  → 依赖：无
  → 验证：变异产生的任意参数组合都能找到指标列

Step 2: S2 Train/Test 分割 [中风险]
  ├─ 2a: 在 runner.py _execute_task() 中实现数据分割
  ├─ 2b: 修改 evaluate_fn 闭包使用 train_df
  ├─ 2c: 实现 champion 样本外验证
  ├─ 2d: 编写分割和验证测试
  └─ 2e: 运行测试确认进化流程正常
  → 依赖：无（与 Step 1 独立）
  → 验证：champion 有 in-sample 和 out-of-sample 两组指标

Step 3: 集成验证
  └─ 3a: 运行全量测试确认无回归
  → 依赖：Step 1, 2 全部完成
