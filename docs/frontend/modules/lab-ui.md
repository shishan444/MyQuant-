# F3: 策略实验室 UI

## 定位

`web/src/components/lab/` (23 个组件) + `pages/Lab.tsx` 构成策略实验室页面——前端两大核心交互区之一。三个互斥模式面板：假设验证（规则构建器）、策略回测、场景验证。

## 文件职责

### 页面与模式面板

| 文件 | 行数 | 职责 |
|------|------|------|
| `Lab.tsx` (page) | 1157 | 三模式页面主组件，状态管理，路由状态接收，DNA 构建 |
| `BacktestModePanel.tsx` | 285 | 回测模式面板：DNA 摘要 + K 线信号图 + 权益曲线 + 指标 |
| `SceneModePanel.tsx` | 543 | 场景验证面板：场景选择 + K 线标注 + 并行验证 + 聚合结果 |
| `SceneSelector.tsx` | 240 | 场景类型多选器（分组复选框 + 参数滑块 + 方向选择） |
| `SceneResult.tsx` | 304 | 场景验证结果：统计卡片 + 周期细分表 + 分布图 + 触发列表 |

### 假设验证条件构建器

| 文件 | 行数 | 职责 |
|------|------|------|
| `RuleConditionGroup.tsx` | 106 | 管理条件列表（增/删/改），第一个条件强制 `logic: "IF"` |
| `RuleConditionRow.tsx` | 128 | 单行条件编辑器：逻辑 + 时间周期 + 主体 + 动作 + 目标 |
| `SubjectDropdown.tsx` | 157 | 主体选择器（35 个选项，7 类：价格/成交量/震荡/波动率/结构/动态参考） |
| `ActionDropdown.tsx` | 173 | 动作选择器（上下文相关：价格动作/成交量动作/指标动作/方向动作） |
| `TargetInput.tsx` | 346 | 目标输入（6 种表单变体：穿越/比较/尖峰/连续/回望/支撑阻力） |

### 图表与可视化

| 文件 | 行数 | 职责 |
|------|------|------|
| `BacktestMetricsPanel.tsx` | 69 | 6 指标网格（收益/夏普/回撤/胜率/交易/评分） |
| `EquityCurveChart.tsx` | 71 | lightweight-charts 权益曲线（动态 import） |
| `DistributionChart.tsx` | 112 | Recharts 堆叠柱状图（匹配/不匹配分布） |

### 辅助组件

| 文件 | 行数 | 职责 |
|------|------|------|
| `DropdownPortal.tsx` | 71 | 通用 portal 定位基座（createPortal + getBoundingClientRect） |
| `SaveStrategyDialog.tsx` | 127 | 保存策略对话框（名称/描述/标签） |
| `ReferencePanel.tsx` | 131 | 验证参考数据（百分位/极值/频率） |
| `TriggerTable.tsx` | 254 | 触发记录表格（排序/分页/CSV 导出） |
| `TriggerDetailDrawer.tsx` | 154 | 触发详情抽屉 |
| `ValidationConclusion.tsx` | 95 | 验证结论栏（匹配率 + 操作按钮） |
| `TimeframeLabel.tsx` | 22 | 颜色编码时间周期徽章 |
| `TimeframeSelector.tsx` | 59 | 时间周期下拉选择器 |
| `ConditionPill.tsx` | 168 | 药丸状条件编辑器（双模式：显示/编辑） |
| `ConditionPillGroup.tsx` | 167 | 条件药丸组（带 AND/OR 连接器） |

## 三模式面板

### Hypothesis 模式（假设验证）

用户通过 `RuleConditionGroup` 构建入场/出场条件，每个条件包含：
- **主体** (subject): 价格/成交量/RSI/EMA/BB 等 35 种
- **动作** (action): 穿越固定值/穿越指标线/突破/尖峰/连续 N 根等
- **目标** (target): 阈值/参考指标/倍数/周期数等

点击"验证策略"调用 `useValidateRules()` mutation，返回触发记录和统计。K 线图上标注买卖信号。可保存为策略（DNA）。

### Backtest 模式（策略回测）

DNA 来源：
1. 策略库下拉选择（`useStrategies` 查询）
2. 从 `/evolution` 页面路由 state 传入（`location.state.dna`）

`BacktestModePanel` 使用 `forwardRef + useImperativeHandle` 暴露 `runBacktest()` 方法。父组件 Lab.tsx 通过 `backtestPanelRef.current?.runBacktest()` 触发执行。`autoRun=true` 时（来自 Evolution 页面的视觉验证）组件挂载时自动执行回测。

### Scene 模式（场景验证）

用户选择场景类型（双顶/成交量尖峰/均值回归/支撑阻力等），可选在 K 线图上绘制标注。对每个选中的场景类型并行调用 `verifyScene()`，结果由 `mergeResponses()` 聚合。

## forwardRef + useImperativeHandle 模式

```
Lab.tsx
  ↓ useRef<BacktestModePanelHandle>
  ↓ backtestPanelRef.current?.runBacktest()
  ↓
BacktestModePanel
  ↓ useImperativeHandle(ref, () => ({ runBacktest: runBacktestAction }))
  ↓
runBacktestAction():
  ├─ Promise.all([runBacktest(dna, ...), getOhlcvBySymbol(...)])
  ├─ 结果 → K 线信号图 + 权益曲线 + 指标面板
  └─ 错误/警告处理（ohlcvWarning 状态）
```

## DNA 构建（Hypothesis 模式保存）

```
RuleCondition[] (UI 表单数据)
  ↓ Lab.tsx handleSaveStrategy (line 436-457)
  ↓ 每个 condition 映射为 SignalGene:
  {
    indicator: condition.subject,
    params: {},
    role: entry_trigger | exit_trigger,
    field_name: null,
    condition: { type: condition.action, threshold: condition.target },
    timeframe: condition.timeframe
  }
  ↓
signal_genes = [...entrySignals, ...exitSignals]
logic_genes = { entry_logic: "AND", exit_logic: "OR" }
risk_genes = { stop_loss: 0.05, take_profit: 0.1, position_size: 0.3, leverage: 1 }
  ↓
useCreateStrategy() → POST /api/strategies
```

## API 交互

| 端点 | 用途 | 模式 |
|------|------|------|
| `POST /api/validate/rules` | 规则条件评估 | Hypothesis |
| `POST /api/strategies/backtest` | DNA 回测 | Backtest |
| `POST /api/validate/scene` | 场景验证 | Scene |
| `GET /api/scene/types` | 场景模板定义 | Scene |
| `GET /api/data/ohlcv/{symbol}/{tf}` | OHLCV K 线数据 | 全部 |
| `GET /api/data/chart-indicators/{symbol}/{tf}` | EMA/BOLL/RSI/MACD/KDJ | Hypothesis/Scene |
| `GET /api/data/available-sources` | 可用数据源 | 全部 |
| `POST /api/strategies` | 保存策略 | Hypothesis/Backtest |
| `GET /api/strategies` | 策略库列表 | Backtest |

## 组件组合树

```
Lab (page)
  ├─ [hypothesis]
  │   ├─ RuleConditionGroup (entry conditions)
  │   │   └─ RuleConditionRow × N
  │   │       ├─ SubjectDropdown → DropdownPortal
  │   │       ├─ ActionDropdown → DropdownPortal
  │   │       └─ TargetInput → CrossTargetDropdown → DropdownPortal
  │   ├─ RuleConditionGroup (exit conditions)
  │   ├─ SaveStrategyDialog
  │   ├─ KlineChart + ChartToolbar
  │   └─ ValidationConclusion / TriggerTable / ReferencePanel
  │
  ├─ [backtest]
  │   └─ BacktestModePanel (forwardRef)
  │       ├─ StrategyDetail (DNA 摘要)
  │       ├─ KlineChart (带信号标注)
  │       ├─ EquityCurveChart (动态 import lightweight-charts)
  │       └─ BacktestMetricsPanel
  │
  └─ [scene]
      └─ SceneModePanel
          ├─ SceneSelector
          ├─ KlineChart + AnnotationLayer
          └─ SceneResult
              ├─ StatCard
              ├─ DistributionBarChart
              └─ TriggerList
```

**未使用组件**: `ConditionPill` 和 `ConditionPillGroup` 是旧版/替代条件编辑器，当前 Lab.tsx 使用 `RuleConditionGroup`/`RuleConditionRow`。

## 涉及文件

| 文件 | 核心内容 |
|------|---------|
| `pages/Lab.tsx` | 三模式页面、状态管理、DNA 构建 |
| `components/lab/BacktestModePanel.tsx` | 回测面板（forwardRef 暴露 runBacktest） |
| `components/lab/SceneModePanel.tsx` | 场景验证面板 |
| `components/lab/Rule*.tsx` (4 个) | 条件构建器系列组件 |
| `components/lab/*Dropdown.tsx` (2 个) | 主体/动作下拉选择 |
| `components/lab/TargetInput.tsx` | 6 种目标输入表单变体 |
| `components/lab/Scene*.tsx` (2 个) | 场景选择器和结果展示 |
| `components/lab/*.tsx` (9 个) | 图表、对话框、表格等辅助组件 |
