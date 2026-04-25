# 后端架构

## 技术选型

- **Web 框架**: FastAPI (同步 handler，非 async) + Uvicorn
- **数据库**: SQLite（通过 `api/db_ext.py` 手写 SQL，非 ORM），数据库文件 `data/quant.db`
- **数据存储**: Parquet 文件存 OHLCV K 线数据，位于 `data/market/{SYMBOL}_{TIMEFRAME}.parquet`
- **回测引擎**: vectorbt（向量化回测，非事件驱动）
- **进化算法**: deap（遗传算法框架）
- **指标计算**: pandas-ta + 自定义指标函数，统一通过 `core/features/indicators.py` 的 `_DEFAULT_PARAMS` 注册

## 架构分层

```
api/                     ← HTTP 层：路由 + schema + 后台线程
  routes/                ← 9 个路由模块
  runner.py              ← 进化引擎后台线程（独立于请求线程运行）
  db_ext.py              ← 数据库操作（手写 SQL，非 ORM）
  schemas.py             ← Pydantic V2 模型（extra="forbid" 严格校验）

core/                    ← 业务逻辑层
  strategy/              ← DNA 数据结构 + 信号转换（核心类型）
  features/              ← 技术指标计算 + 信号构建
  backtest/              ← 回测执行（vectorbt）
  evolution/             ← 遗传算法引擎
  scoring/               ← 策略评分
  data/                  ← 数据加载、存储、拉取
  validation/            ← 假设验证 + 场景验证
  discovery/             ← 决策树/KNN 规则发现
  persistence/           ← 数据库操作（checkpoint 级别）
  logging/               ← 日志配置
  visualization/         ← Plotly 图表生成
```

## 关键设计决策

1. **同步 handler**: 所有 API handler 都是同步函数（非 async def）。这意味着回测/进化等 CPU 密集操作会阻塞事件循环。进化引擎通过独立后台线程（`runner.py`）规避这个问题。
2. **extra="forbid"**: Pydantic schema 使用严格模式，前端多传任何字段都会返回 422。这导致前后端字段必须严格对齐（之前出现过 `strategies` vs `items` 的不匹配 bug）。
3. **gene_signature 去重**: `db_ext.py` 的 `save_strategy()` 基于 DNA 哈希做去重，仅对有 `best_score` 的进化策略生效。手动保存跳过去重直接插入。
4. **Parquet 直接文件查找**: 回测时通过 `data_dir / f"{symbol}_{timeframe}.parquet"` 直接定位文件，不走数据库。这意味着文件命名是隐含契约。
5. **compute_all_indicators**: 每次回测预计算全部 56 种指标（`indicators.py:340-364`），无论 DNA 实际用到哪些。MTF DNA 对每个时间周期都做一次全量计算。

## 数据流（主路径）

```
前端请求 → FastAPI 路由
  → core/data/mtf_loader.load_and_prepare_df()     加载 Parquet + compute_all_indicators
  → core/strategy/executor.dna_to_signal_set()      DNA → 布尔信号 Series
  → core/backtest/engine.BacktestEngine.run()       信号 + 数据 → vectorbt 回测
  → core/scoring/scorer.score_strategy()            回测结果 → 多维评分
  → API 返回 JSON
```

## 进化数据流（后台线程）

```
api/runner.py (独立线程)
  → core/evolution/engine.EvolutionEngine.run_continuous()
    → 每代: 种群进化 → 逐个体回测 + 评分 → 选择 + 交叉 + 变异
    → 优秀个体: api/db_ext.save_strategy() 写入 SQLite
    → 进度推送: WebSocket → 前端实时更新
```
