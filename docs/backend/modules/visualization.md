# B12: 可视化

## 定位

`core/visualization/` 是后端 Plotly 图表生成模块，为进化冠军报告和代际进度提供可视化。前端 K 线图使用 lightweight-charts（见 F4），不依赖本模块。

## 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `chart_builder.py` | 140 | 冠军报告 + 进化仪表盘入口 |
| `kline_chart.py` | 154 | K 线图 + 买卖标记 + RSI 子图 |
| `equity_curve.py` | 68 | 策略权益 vs 买入持有基准 |
| `generation_chart.py` | 77 | 代际最佳/平均分数曲线 |
| `quick_preview.py` | 46 | vectorbt 原生图表预览 |

## 关键链路

### 冠军报告 (chart_builder.py:19)

```
build_champion_report(dna, enhanced_df, backtest_result, engine)
  L42  dna_to_signals(dna, enhanced_df) -> entries, exits
  L45-48  如果无 backtest_result -> 运行回测
  L51-55  过滤指标列 (排除 OHLCV 和 RSI)
  L57  _select_overlay_indicators(dna, indicator_cols)
         匹配 DNA 信号基因中的指标 (最多 5 个)
  L59-65  build_kline_chart() -> K 线 + 买卖标记 + 指标叠加
  L67-71  build_equity_curve() -> 策略权益 vs 基准
  L73  build_quick_preview() -> vectorbt 原生图
```

### K 线图构建 (kline_chart.py:12)

```
build_kline_chart(ohlcv_df, entries, exits, indicator_columns)
  L35-37  检测 RSI -> 2行布局 [0.7, 0.3]
  L39-45  make_subplots(rows, shared_xaxes)
  L48-60  CandlestickSeries
  L63-77  买入标记: triangle-up, y = low * 0.998
  L80-94  卖出标记: triangle-down, y = high * 1.002
  L97-112 指标叠加 Scatter
  L115-132 RSI 子图 + 30/70 参考线
```

## 关键机制

### 指标叠加选择 (chart_builder.py:108)

`_select_overlay_indicators()`: 根据 DNA signal_genes 匹配指标列。EMA/SMA/WMA/DEMA/TEMA -> `{ind}_{period}`, BB -> `bb_lower/upper/middle_{p}_{s}`。最多 5 个叠加层防拥挤。

### 基准标准化 (equity_curve.py:38)

买入持有基准归一化到相同起始权益: `(benchmark/benchmark[0]) * equity[0]`。视觉比较相对表现。

### 快速预览回退 (quick_preview.py:19)

尝试 `portfolio.plot()`；无交易或异常 -> 返回占位图。保证可视化层永不崩溃。

## 接口定义

| 函数 | 说明 |
|------|------|
| `build_champion_report(dna, df, result, engine) -> Dict[str, Figure]` | 冠军报告 ("kline","equity","quick_preview") |
| `build_evolution_dashboard(history, target) -> Dict[str, Figure]` | 进化仪表盘 ("generation") |
| `build_kline_chart(df, entries, exits, indicators) -> Figure` | K 线图 |
| `build_equity_curve(equity, benchmark) -> Figure` | 权益曲线 |
| `build_generation_chart(history, target) -> Figure` | 代际图 |
| `build_quick_preview(portfolio) -> Figure` | 快速预览 |

## 关键参数

| 参数 | 默认值 | 设计意图 |
|------|--------|---------|
| height (kline) | 700 | K 线图高度 |
| height (equity) | 400 | 权益曲线高度 |
| row_heights | [0.7, 0.3] | 价格 70%, RSI 30% |
| max overlays | 5 | 防图表拥挤 |
| buy marker offset | 0.998 | 低点下方 0.2% |
| sell marker offset | 1.002 | 高点上方 0.2% |
| template | "plotly_dark" | 暗色主题 |

## 约定与规则

- **统一 Plotly**: 返回 `go.Figure` 对象，不生成静态图像
- **暗色主题**: `template="plotly_dark"`
- **颜色约定**: 蓝=策略权益, 灰=基准, 绿=买入/最佳, 红=卖出/目标, 橙=平均
- **空数据降级**: 返回带文字注释的占位图
- **无副作用**: 不写文件不显示，只返回 Figure
- **shared_xaxes**: K 线图价格和 RSI 缩放/平移同步
