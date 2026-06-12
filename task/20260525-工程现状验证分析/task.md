# 工程现状验证分析：验证三个设计观点

## 任务目标
验证之前讨论中提出的三个观点是否与工程实际情况一致，基于验证结果给出修正后的分析。

## 验证结果

### 观点 1 验证：市场状态感知应基于K线分析
**原始论据被推翻。** 策略层并非完全基于 OHLCV——已存在完整的衍生数据管线：
- `derivatives_fetcher.py`：独立获取 OI + Funding Rate
- `derivatives_merger.py`：ffill 合并到 OHLCV DataFrame
- `mtf_loader.py:124-151`：自动尝试合并衍生数据（优雅降级）
- `indicators.py:279-312`：5 个衍生数据指标（OI_ChangeRate, OI_ZScore, FundingZScore, OIPriceDivergence, FundingPressure）
- `registry.py:370-399`：已注册 category="derivatives"，可被进化引擎搜索

**但核心观点仍成立**：无显式 REGIME 基因/角色。MTF 结构层 + FractalEntropy + DIRECTION 基因提供了间接感知。

### 观点 2 验证：回测和模拟交易设计不同
**完全确认。** 共享 `dna_to_signal_set()` 信号生成层，但差异显著：
- 回测：vectorbt/Numba JIT, 批量处理, 无判断规则, 无限价单, 同步
- 模拟交易：Python 循环, 流式处理, JudgmentConfig 规则引擎, 限价单概率成交, 异步后台线程
- ReplayRunner 使用模拟交易逻辑在历史数据上回放，是两者间的桥梁

### 观点 3 验证：进化引擎搜索空间盲区
**部分确认。** 搜索空间已超出纯入场/出场：
- 10 种 SignalRole（但无 REGIME）
- MTF 多时间框架结构感知（隐式市场状态）
- 方向决策（DIRECTION 基因）
- 仓位管理（ADD/REDUCE 角色）
- Fitness 评估无分市场状态维度（scorer.py 纯全周期聚合指标）

## 研究完成
