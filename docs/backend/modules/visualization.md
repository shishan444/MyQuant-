# B12: 可视化

## 定位

`core/visualization/` 是后端 Plotly 图表生成模块，为进化冠军报告和代际进度提供可视化。注意：前端 K 线图使用 lightweight-charts（见 F4），不依赖本模块。

## 文件职责

| 文件 | 行数 | 职责 |
|------|------|------|
| `chart_builder.py` | 139 | 编排器：DNA→信号→回测→图表集合 |
| `kline_chart.py` | 153 | K 线图：蜡烛图 + 买卖信号 + 指标叠加 + RSI 子图 |
| `equity_curve.py` | 67 | 权益曲线：策略 vs 买入持有基准 |
| `generation_chart.py` | 76 | 代际进度图：best/avg 分数趋势 + 目标线 |
| `quick_preview.py` | 45 | vectorbt Portfolio 快速预览 |
| `__init__.py` | 0 | 空 |

## 架构

```
chart_builder.py (facade)
  ├── build_champion_report() → kline + equity + quick_preview
  │     ├─ dna_to_signals() → 交易信号
  │     ├─ BacktestEngine.run_with_portfolio() → 回测结果
  │     ├─ build_kline_chart() → K 线 + 信号 + 指标叠加
  │     ├─ build_equity_curve() → 策略 vs 基准权益曲线
  │     └─ build_quick_preview() → vectorbt 原生图表
  └── build_evolution_dashboard() → generation
        └─ build_generation_chart() → 代际分数趋势
```

四个图表模块（kline/equity/generation/quick_preview）对项目内部零依赖，只依赖 pandas 和 plotly。`chart_builder.py` 是唯一引入 `core.backtest` 和 `core.strategy` 的文件。

## K 线图 (kline_chart.py)

`build_kline_chart(ohlcv_df, entries, exits, indicator_columns)`：

- 自动检测 RSI 列存在 → 双子图布局（70% 价格 + 30% RSI），否则单图
- 买入标记：绿色上三角，偏移 `low * 0.998` 避免遮挡蜡烛体
- 卖出标记：红色下三角，偏移 `high * 1.002`
- 指标叠加线：半透明 opacity=0.8，宽度 1.2
- RSI 子图：紫色线，30/70 水平虚线

## 权益曲线 (equity_curve.py)

`build_equity_curve(strategy_equity, benchmark_close)`：

- 基准线归一化到策略起始值：`(benchmark / benchmark.iloc[0]) * equity.iloc[0]`
- 策略线：实线亮蓝 `#00bfff`，基准线：虚线灰 `#888888`

## 代际进度图 (generation_chart.py)

`build_generation_chart(history, target_score)`：

- 输入 `[{"generation": N, "best_score": X, "avg_score": Y}, ...]`
- best_score：绿色实线，avg_score：橙色虚线
- target_score：红色水平点线 + 标注

## 快速预览 (quick_preview.py)

`build_quick_preview(portfolio)`：

- 直接包装 `vectorbt.Portfolio.plot(show=False)`
- 交易数为 0 或异常时降级为空占位图

## 指标选择策略 (chart_builder.py)

`_select_overlay_indicators(dna, available_cols)`：

- 扫描 `dna.signal_genes`，按指标类型匹配 DataFrame 列名前缀
- 支持 EMA/SMA/WMA/DEMA/TEMA（格式 `{indicator}_{period}`）和 BB（三线）
- 上限 5 条叠加线，避免视觉拥挤

## 已知问题

- `build_champion_report()` 即使传入了 `backtest_result` 仍会调用 `engine.run_with_portfolio()` 获取 portfolio 对象——回测被重复执行
- 四个图表模块全部使用 `plotly_dark` 模板，深色主题硬编码不可切换

## 数据流

```
api/ 路由层
  └─ build_champion_report(dna, enhanced_df, result, engine)
       → {"kline": go.Figure, "equity": go.Figure, "quick_preview": go.Figure}

  └─ build_evolution_dashboard(history, target_score)
       → {"generation": go.Figure}

前端不直接消费这些 Figure 对象——需要确认前后端图表的数据传输方式 (推断)
```

## 涉及文件

| 文件 | 核心内容 |
|------|---------|
| `core/visualization/chart_builder.py` | 编排器 facade |
| `core/visualization/kline_chart.py` | K 线图 + 信号标注 |
| `core/visualization/equity_curve.py` | 权益曲线 |
| `core/visualization/generation_chart.py` | 代际进度图 |
| `core/visualization/quick_preview.py` | vectorbt 快速预览 |
