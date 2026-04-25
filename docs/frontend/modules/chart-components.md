# F4: 图表组件

## 定位

`web/src/components/charts/` 基于 TradingView lightweight-charts 构建金融图表系统。KlineChart 是核心，管理主图(K线+指标)和副图(RSI/成交量/MACD/KDJ)的双实例生命周期。AnnotationLayer 提供用户绘图。

## 文件清单

| 文件 | 职责 |
|------|------|
| `KlineChart.tsx` | 核心图表 (~917 行), forwardRef 暴露命令式 API |
| `core/useChartSync.ts` | 主图/子图时间轴同步 |
| `core/chartThemes.ts` | 暗色主题配置 |
| `AnnotationLayer.tsx` | Canvas 注释层 (水平线+矩形) |
| `ChartEmbeddedLegend.tsx` | 分组折叠式图例 |
| `ChartToolbar.tsx` | 缩放/全屏工具栏 |

## 关键链路

### 图表创建 (useLayoutEffect, KlineChart.tsx:304)

```
createChart(mainRef, DARK_CHART_THEME)          -- 主图 78% 高度
addSeries(CandlestickSeries)                      -- K 线
ResizeObserver 监听尺寸变化
subscribeCrosshairMove 更新图例数值
useChartSync 同步主图/子图时间轴
```

### 数据更新 (useEffect, KlineChart.tsx:410)

单个 useEffect 处理所有数据: candle, indicators, BOLL, volume, MTF, signals, triggers。使用 `initialFitDoneRef` 确保仅首次 fit。

### 子图数据 (KlineChart.tsx:672-832)

| 子图类型 | 内容 |
|---------|------|
| volume | HistogramSeries + 绿红色柱 |
| macd | histogram + macd 线 + signal 线 |
| rsi | 主线 + 70/30 参考线 |
| kdj | K/D/J 三线 + 80/20 参考线 |

## 关键机制

### 时间轴同步 (useChartSync.ts:14)

`syncing` ref 防双向订阅无限循环。`subscribeVisibleLogicalRangeChange` 双向绑定。

### 暗色主题 (chartThemes.ts:9)

半透明深色 `rgba(13,17,23,0.8)`，点状网格。颜色: 上涨 #00C853, 下跌 #FF1744。

### 注释层 (AnnotationLayer.tsx:24)

Canvas 叠加层，支持水平线和矩形框。`subscribeVisibleLogicalRangeChange` 平移/缩放时重绘。鼠标: mousedown 起点, mouseup 完成绘制。

### 图例 (ChartEmbeddedLegend.tsx:12)

分组折叠式，`onToggle` 控制可见性 (设 `color: "transparent"`)。显示实时十字光标数值。

### 价格范围控制 (KlineChart.tsx:637)

首次加载计算 tight range + 8% margin。autoScale 禁用，用户自由缩放。

## 接口定义

| 接口 | 说明 |
|------|------|
| KlineChartProps | data, indicators?, signals?, triggers?, height?=450, bollData?, volumeData?, mtfIndicators?, subChartType?, macdData?, kdjData? |
| KlineChartHandle | scrollToTime(time), zoomIn(), zoomOut(), resetView() |
| Annotation | id, type("line"|"box"), price?, timeStart?, timeEnd?, priceEnd?, label? |
| CandleData/IndicatorData/SignalData | 核心数据类型 |

## 关键参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 主图高度 | 78% | |
| 子图高度 | 22% | |
| 默认总高度 | 450px | |
| 价格范围 margin | 8% | |
| 触发点偏移 | 1.012x | 高点上方 1.2% |
| 缩放 | 放大 0.8x, 缩小 1.25x | |

## 约定与规则

- forwardRef + useImperativeHandle 暴露控制方法
- 系列引用存 useRef: indicatorSeriesRefs, bollSeriesRefs 等
- 数据更新先清除旧系列再创建新系列
- 时间转换 toTime: 兼容带/不带 T 的 ISO 字符串
- initialFitDoneRef 防重复 fitContent
