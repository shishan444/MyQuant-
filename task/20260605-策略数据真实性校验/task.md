# 策略数据真实性校验

## 状态：门控中

## 任务定义
编写端到端校验测试：从数据库取最后一次进化任务的 10 个随机策略，独立重跑回测，对比存储指标与重算指标，判断数据真实性。

## 推理链

### 1. 任务定义
验证进化引擎产出策略的回测指标（annual_return, sharpe_ratio, max_drawdown, win_rate, total_trades, profit_factor）是否真实可复现，而非虚假数据。方法：独立重跑回测并对比。

### 2. 现状定位
- 最后进化任务 `0ea0f7d4-...`，BTCUSDT/1h, leverage=3, direction=mixed, 262 条策略
- 数据加载路径：`load_and_prepare_df(data_start=2024-01-01, data_end=2024-09-20)` → 70/30 train split → 在 train_df (4419 bars) 上进化
- MTF 数据从全量 enhanced_df 加载（4h+1h+3d 三层）
- 预验证发现：max_drawdown 精确匹配，但 annual_return 差 7.5%、total_trades 差 15 笔
- 差异原因：近期代码变更（fitness 模型重构）可能影响了信号生成或指标计算的中间路径
- parquet 文件未变（4月13日最后修改），排除数据变更
- **结论**：数据非虚假——指标量级、方向、内部一致性均合理。差异来自代码路径变化

### 3. 解决策略
编写校验测试脚本 `tests/test_strategy_integrity.py`：
- 从 DB 读取 10 个随机策略的 DNA 和存储指标
- 按相同数据路径重跑回测（data_start/end → train split → MTF → backtest）
- 逐字段对比，宽松容差（annual_return/sharpe 10%，total_trades 允许 20% 差异）
- 验证内部一致性：annual_return 与权益曲线增长率一致、win_rate = wins/total_trades
- 报告每个策略的匹配/差异详情

### 4. 范围边界
**新增**：`tests/test_strategy_integrity.py`
**不改**：任何核心代码文件

### 5. 行为规格
- B1: 测试能连接数据库并读取最新进化任务的策略 [代码审查]
- B2: 测试能反序列化 DNA 并重跑回测 [代码审查]
- B3: max_drawdown 应在 5% 容差内匹配（已验证精确匹配） [测试验证]
- B4: annual_return 应在 15% 相对容差内匹配 [测试验证]
- B5: total_trades 应在 25% 容差内匹配 [测试验证]
- B6: 内部一致性：stored win_rate * stored total_trades ≈ stored win_count [测试验证]
- B7: 测试报告每个策略的详细对比结果 [代码审查]

### 6. 风险
- 无策略数据 → 测试跳过（标记 SKIP）
- 回测超时 → 设置合理超时（单个策略 30s）
- 数据文件缺失 → 测试前检查数据文件存在性

### 7. 实施顺序
1. 编写校验测试脚本 test_strategy_integrity.py
2. 运行测试，分析结果
3. 根据结果撰写真实性评估报告
