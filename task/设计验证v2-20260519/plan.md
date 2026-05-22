# Plan: v2-version-plan 设计方案代码层验证

## 任务定义
对照 `works/设计稿/v2-version-plan.md` 全部设计项，逐条验证实际代码实现。对每个偏差给出评估：更好/更差/偏离/遗漏。

## 验证结果

### 研究发现汇总

#### 合规项: 27/32 (84.4%)
#### 更好: 4项
#### 偏离: 2项（含1个严重运行时bug）
#### 遗漏: 5项

#### 严重发现: from_signal_set 类归属错误（运行时 bug）
- 文件: types.py:131-159, runner.py:427
- from_signal_set 定义在 PositionPlan 类上，但 runner.py 调用 BarSignals.from_signal_set
- Python 确认 BarSignals 无此属性 -> AttributeError
- 测试未覆盖此路径（runner 交易循环是长运行服务）
- 评估: 偏离（严重，运行时崩溃）

## 状态: 研究完成，待向用户汇报
