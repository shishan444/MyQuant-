# F4: 图表组件

## 定位

`web/src/components/charts/` 基于 TradingView lightweight-charts 构建的金融图表系统。KlineChart 是核心编排器，管理主图（K 线 + 指标叠加）和副图（RSI/成交量/MACD/KDJ）的双图表实例生命周期。AnnotationLayer 提供用户绘图能力。

## 文件职责

| 文件 | 行数 | 职责 |
|------|------|------|
| `KlineChart.tsx` | 921 | 核心图表编排器：双图表实例 + 指标/信号/标注系列管理 + forwardRef 暴露控制 |
| `AnnotationLayer.tsx` | 193 | 透明 Canvas 叠加层：水平线和矩形框绘图工具 |
| `ChartEmbeddedLegend.tsx` | 67 | 分组可折叠图例（十字线联动实时值 + 系列可见性切换） |
| `ChartLegend.tsx` | 46 | 扁平图例（旧版，当前未使用） |
| `ChartToolbar.tsx` | 48 | 缩放/全屏/重置工具栏（纯展示） |
| `core/useChartSync.ts` | 55 | 主图/副图可见范围双向同步 hook |
| `core/chartThemes.ts` | 77 | 暗色主题配置 + 语义颜色常量 |

## 架构分层

```
┌─────────────────────────────────────────┐
│  KlineChart (forwardRef, 921 行)         │
│  ┌─────────────────────────────────────┐│
│  │ ChartToolbar (absolute top-right)   ││
│  │ ChartEmbeddedLegend (absolute top-left) │
│  │                                     ││
│  │ ┌─────────────────┐ ┌────────────┐ ││
│  │ │  主图 (flex-3)   │ │ 副图 (flex-1)│ ││
│  │ │  K 线 + EMA/BOLL │ │ RSI/Vol/MACD│ ││
│  │ │  + 信号标注      │ │ /KDJ       │ ││
│  │ └─────────────────┘ └────────────┘ ││
│  │        useChartSync 双向同步         ││
│  └─────────────────────────────────────┘│
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  AnnotationLayer (独立组件, 外层使用)     │
│  Canvas overlay on chartContainer       │
│  Props: chartApi + candleSeries         │
└─────────────────────────────────────────┘
```

## KlineChart 核心实现

### forwardRef 暴露接口

```typescript
interface KlineChartHandle {
  scrollToTime(time: number): void;
  zoomIn(): void;
  zoomOut(): void;
  resetView(): void;
}
```

父组件（BacktestModePanel、Lab、SceneModePanel）通过 ref 调用这些方法控制图表。

### 数据输入 Props

| Prop | 类型 | 用途 |
|------|------|------|
| data | `CandleData[]` | OHLCV K 线数据 |
| indicators | `IndicatorData[]` | 指标线（EMA 等） |
| signals | `SignalData[]` | 买卖信号标注 |
| triggers | `TriggerMarker[]` | 触发器标注（场景验证用） |
| bollData | `IndicatorData[]` | 布林带数据 |
| volumeData | `IndicatorData[]` | 成交量柱状图 |
| macdData | `IndicatorData[]` | MACD 副图数据 |
| kdjData | `IndicatorData[]` | KDJ 副图数据 |
| mtfIndicators | 按时间周期分组 | 多周期指标叠加 |
| subChartType | `"volume" \| "macd" \| "rsi" \| "kdj"` | 副图类型切换 |

### 双图表实例

`useLayoutEffect` 创建两个独立的 lightweight-charts 实例：
- **主图**: K 线 + 指标叠加（EMA/BOLL/MTF 指标）+ 信号标注
- **副图**: 根据 `subChartType` 显示 RSI/成交量/MACD/KDJ

`useChartSync` 通过 `subscribeVisibleLogicalRangeChange` 实现双向滚动/缩放同步，用 `syncing` ref 防止循环更新。

### 触发器标注

触发器标注（场景验证用）放在一条偏移线系列上，位于 K 线高点上方 1.2%。每种子类型有特定颜色：double_top = 琥珀色，head_shoulders_top = 紫色，triple_top = 蓝色等。

### 状态依赖

唯一的 store 依赖是 `useChartSettings()`（来自 `@/stores/chart-settings`），控制 EMA 列表和 BOLL 开关。图例的系列可见性由 `ChartEmbeddedLegend` 的 `onToggle` 回调在组件内部管理。

## AnnotationLayer

独立于 KlineChart 的透明 Canvas 叠加层。接收父页面传入的 `chartApi` 和 `candleSeries` 引用。

| 工具 | 操作 | 渲染 |
|------|------|------|
| line | 单击放置 | 琥珀色虚线 + 价格标签 |
| box | 拖拽绘制 | 紫色虚线矩形 + 半透明填充 |

Canvas 尺寸 DPR 感知。通过 `subscribeVisibleLogicalRangeChange` 订阅图表平移/缩放事件触发重绘。`activeTool` 控制 pointer-events：有工具激活时接收鼠标事件，否则穿透到下层图表。

## 涉及文件

| 文件 | 核心内容 |
|------|---------|
| `components/charts/KlineChart.tsx` | 双图表编排器，forwardRef，系列生命周期管理 |
| `components/charts/AnnotationLayer.tsx` | Canvas 绘图覆盖层 |
| `components/charts/ChartEmbeddedLegend.tsx` | 分组图例 + 可见性控制 |
| `components/charts/ChartToolbar.tsx` | 缩放/全屏控件 |
| `components/charts/core/chartThemes.ts` | 暗色主题 + 颜色常量 |
| `components/charts/core/useChartSync.ts` | 主图/副图范围同步 |
