# 01 - API 路由设计

## 1. 概述

MyQuant 后端基于 FastAPI 框架，采用模块化路由架构。所有 HTTP API 路由按功能域拆分到独立文件中，
WebSocket 路由用于进化任务的实时推送。应用入口通过 `create_app()` 工厂函数组装所有路由。

**源码位置**: `api/app.py` (入口), `api/routes/` (路由模块), `api/schemas.py` (请求/响应模型)
**版本**: v0.14.0

### 路由挂载

| 路由模块 | 文件 | 前缀 | 标签 |
|---------|------|------|------|
| config | `routes/config.py` | `/api/config` | config |
| chart_config | `routes/chart_config.py` | `/api/config` | chart_config |
| strategies | `routes/strategies.py` | `/api/strategies` | strategies |
| evolution | `routes/evolution.py` | `/api/evolution` | evolution |
| data | `routes/data.py` | `/api/data` | data |
| ws | `routes/ws.py` | (无前缀) | websocket |
| validate | `routes/validate.py` | `/api` | validation |
| health | `app.py` 内联 | `/api/health` | (无) |

### 应用生命周期

- **启动**: 初始化数据库 (`init_db_ext`)，创建 `EvolutionRunner` 后台线程，
  通过 `asyncio.run_coroutine_threadsafe` 将 WebSocket 推送函数绑定到事件循环。
- **关闭**: 停止 `EvolutionRunner` 后台线程。
- **CORS**: 允许所有来源 (`allow_origins=["*"]`)。

### 依赖注入

| 依赖 | 函数 | 返回 | 说明 |
|------|------|------|------|
| get_db_path | `api/deps.py` | Path | SQLite 路径，默认 `data/quant.db` |
| get_data_dir | `api/deps.py` | Path | 数据目录，默认 `data/market` |

---

## 2. 健康检查

### GET /api/health

**响应** (`HealthResponse`): `{"status": "ok", "version": "0.14.0", "timestamp": "<ISO8601 UTC>"}`

---

## 3. 配置管理 (config)

配置数据存储在 `data/config.json`，采用 JSON 文件持久化方案。

### GET /api/config -- 读取全局配置

**响应** `Dict[str, Any]`:

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| language | str | "zh-CN" | 界面语言 |
| timezone | str | "UTC+8" | 时区 |
| notify_evolution | bool | true | 进化完成通知 |
| notify_signal | bool | true | 信号通知 |
| binance_api_key | str | "" | 交易所 API Key |
| binance_secret_key | str | "" | 交易所 Secret Key |
| binance_connected | bool | false | 交易所连接状态 |
| init_cash | int | 100000 | 默认初始资金 |
| maker_fee | float | 0.1 | Maker 费率 (%) |
| taker_fee | float | 0.1 | Taker 费率 (%) |
| max_positions | int | 1 | 最大持仓数 |

### PUT /api/config -- 更新全局配置

仅更新请求体中包含且在默认配置中存在的键。返回更新后的完整配置。

---

## 4. 图表指标配置 (chart_config)

配置存储在 `data/chart_indicators.json` 中。

### GET /api/config/chart_indicators

**响应** `Dict[str, Any]`:

| 键 | 类型 | 默认值 | 说明 |
|----|------|--------|------|
| ema_periods | List[int] | [10,20,50] | EMA 周期列表 |
| ema_colors | List[str] | ["#3B82F6","#10B981","#F59E0B"] | EMA 颜色 (HEX) |
| boll | Dict | {enabled:true,period:20,std:2.0} | 布林带配置 |
| rsi | Dict | {enabled:true,period:14,overbought:70,oversold:30} | RSI 配置 |
| vol | Dict | {enabled:true,position:"overlay"} | 成交量配置 |

### PUT /api/config/chart_indicators

仅更新 `ema_periods`, `ema_colors`, `boll`, `rsi`, `vol` 五个键。返回更新后完整配置。

---

## 5. 策略管理 (strategies)

**路由文件**: `api/routes/strategies.py`

### POST /api/strategies (201) -- 创建策略

**请求** (`StrategyCreate`):

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | str | 否 | 策略名称 |
| dna | DNAModel | 是 | 策略基因结构 |
| symbol | str | 是 | 交易对 |
| timeframe | str | 是 | 时间框架 |
| source | str | 否 | 来源，默认 "manual" |
| source_task_id | str | 否 | 来源进化任务 ID |
| tags / notes | str | 否 | 标签 / 备注 |

**响应** (`StrategyResponse`): strategy_id (UUID), name, dna, symbol, timeframe, source, source_task_id, best_score, generation, parent_ids, tags, notes, created_at, updated_at

### GET /api/strategies -- 列出策略

**查询参数**: symbol, source, tags (筛选), sort_by ("created_at"), sort_order ("desc"), limit (100)

**响应** (`StrategyListResponse`): `{"items": [StrategyResponse], "total": int}`

### GET /api/strategies/{strategy_id} -- 获取策略详情

**错误**: 404。**响应**: `StrategyResponse`

### PUT /api/strategies/{strategy_id} -- 更新策略

**请求** (`StrategyUpdate`): name, dna, tags, notes, best_score (均为可选)。**错误**: 404。

### DELETE /api/strategies/{strategy_id} (204) -- 删除策略

**错误**: 404。

### POST /api/strategies/backtest -- 执行回测

支持两种模式: (1) 传入 `strategy_id` 从数据库加载 DNA; (2) 直接传入 `dna` + `symbol` + `timeframe`。

**请求** (`BacktestRequest`):

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| strategy_id | str | null | 已保存策略 ID |
| dna | DNAModel | null | 直接传入的 DNA |
| symbol | str | null | 交易对 (直接传入模式) |
| timeframe | str | null | 时间框架 (直接传入模式) |
| dataset_id | str | 必填 | 数据集 ID |
| init_cash | float | 100000.0 | 初始资金 |
| fee / slippage | float | 0.001 / 0.0005 | 手续费率 / 滑点 |
| score_template | str | "profit_first" | 评分模板 |
| data_start / data_end | str | null | 数据日期范围 |
| timeframe_pool | List[str] | null | 多时间框架池 |

**数据加载**: 优先 `mtf_loader.load_and_prepare_df()` 加载增强数据; 回退按 gene 逐个计算指标; MTF 时调用 `load_mtf_data()`。

**响应** (`BacktestResponse`): result_id, strategy_id, symbol, timeframe, data_start, data_end, init_cash, fee, slippage, total_return, sharpe_ratio, max_drawdown, win_rate, total_trades, total_score, template_name, dimension_scores, run_source ("lab"), equity_curve (List[Dict]), signals (List[Dict]), total_funding_cost, liquidated

### POST /api/strategies/compare -- 策略比较

**请求** (`CompareRequest`): strategy_ids (List[str]), dataset_id, init_cash, fee, slippage, score_template

**响应** (`CompareResponse`): `{"results": [CompareResultItem]}`

`CompareResultItem`: strategy_id, result_id, total_return, sharpe_ratio, max_drawdown, win_rate, total_trades, total_score, dimension_scores, error

---

## 6. 进化任务管理 (evolution)

**路由文件**: `api/routes/evolution.py`

### POST /api/evolution/tasks (201) -- 创建进化任务

服务端自动验证数据可用性、生成默认 DNA (若未提供)、设置执行时间框架。

**请求** (`EvolutionTaskCreate`):

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| initial_dna | DNAModel | null | 种子 DNA |
| symbol | str | 必填 | 交易对 |
| timeframe | str | 必填 | 执行时间框架 |
| target_score | float | 80.0 | 目标评分 |
| score_template | str | "profit_first" | 评分模板 |
| population_size | int | 15 | 种群大小 |
| max_generations | int | 200 | 最大进化代数 |
| elite_ratio | float | 0.5 | 精英比例 |
| n_workers | int | 6 | 并行工作数 |
| indicator_pool / timeframe_pool | List[str] | null | 指标/时间框架池 |
| mode | str | null | 进化模式 |
| leverage | int | 1 | 杠杆 (1-10) |
| direction | str | "long" | 方向 (long/short/mixed) |
| data_start / data_end | str | null | 训练数据范围 |

**关键逻辑**: timeframe_pool 多时间框架时自动排序取最短为执行 TF; 未提供 DNA 时生成 EMA(20) 默认种子; 强制覆盖 leverage; direction "mixed" 时不覆盖。

**响应** (`EvolutionTaskResponse`):

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | str | 任务 ID |
| status | str | 任务状态 (pending/running/paused/stopped/completed) |
| target_score | float | 目标评分 |
| score_template | str | 评分模板 |
| symbol / timeframe | str | 交易对 / 时间框架 |
| initial_dna / champion_dna | DNAModel | 初始 / 冠军 DNA |
| population_size / max_generations | int | 种群大小 / 最大代数 |
| elite_ratio / n_workers | float / int | 精英比例 / 并行数 |
| current_generation | int | 当前进化代数 |
| best_score | float | 最佳评分 |
| stop_reason | str | 停止原因 |
| leverage / direction | int / str | 杠杆 / 方向 |
| data_start / data_end | str | 训练数据范围 |
| data_time_start / data_time_end | str | 实际数据时间范围 |
| data_row_count | int | 数据行数 |
| indicator_pool / timeframe_pool / mode | - | 进化参数 |
| created_at / updated_at | str | 时间戳 |

### GET /api/evolution/tasks -- 列出任务

**查询参数**: status (筛选), limit (50)。**响应**: `{"items": [EvolutionTaskResponse], "total": int}`

### GET /api/evolution/tasks/{task_id} -- 获取任务详情

**错误**: 404。**响应**: `EvolutionTaskResponse`

### GET /api/evolution/tasks/{task_id}/history -- 代际历史

**响应** (`EvolutionHistoryResponse`): `{"task_id": "...", "generations": [{"generation": N, "best_score": F, "avg_score": F, "top3_summary": "...", "created_at": "..."}]}`

### POST /api/evolution/tasks/{task_id}/pause -- 暂停任务

状态设为 "paused"。**错误**: 404。**响应**: `EvolutionTaskResponse`

### POST /api/evolution/tasks/{task_id}/stop -- 停止任务

状态设为 "stopped"，stop_reason 设为 "user_stop"。**错误**: 404。

### POST /api/evolution/tasks/{task_id}/resume -- 恢复任务

状态设为 "pending"。**错误**: 404 (不存在), 400 (未暂停)。

### GET /api/evolution/tasks/{task_id}/strategies -- 发现的策略

返回冠军策略和评分 > 0 的快照策略 (按评分降序，最多 10 条)。

**响应**: `{"task_id": "...", "strategies": [{"strategy_id": "...", "dna": {...}, "source": "champion"|"snapshot", "generation": N, "score": F}]}`

---

## 7. 数据管理 (data)

**路由文件**: `api/routes/data.py`

### GET /api/data/datasets -- 列出数据集

**查询参数**: symbol, interval (筛选), limit (100)。
**响应** (`DatasetListResponse`): `{"items": [DatasetResponse], "total": int}`

### GET /api/data/datasets/{dataset_id} -- 数据集详情

**错误**: 404。**响应** (`DatasetResponse`): dataset_id, symbol, interval, parquet_path, row_count, time_start, time_end, file_size_bytes, source, format_detected, timestamp_precision, quality_status, quality_notes, gap_count, created_at, updated_at

### POST /api/data/import -- 导入 CSV

**Content-Type**: multipart/form-data
**表单参数**: file (File, 必填), symbol, interval (可选，可从文件名推断), mode ("merge"/"replace"/"new")
**响应** (`DataImportResponse`): dataset_id, symbol, interval, rows_imported, format_detected, timestamp_precision, files_processed, time_range

### POST /api/data/import-batch -- 批量导入 CSV

**表单参数**: files (List[File], 必填), symbol, interval, mode。
**错误**: 400 (未提供文件)。**响应**: `DataImportResponse`

### DELETE /api/data/datasets/{dataset_id} (204) -- 删除数据集

**错误**: 404

### GET /api/data/datasets/{dataset_id}/preview -- 预览数据

**查询参数**: limit (20)。**响应** (`DatasetPreviewResponse`): dataset_id, total_rows, rows (List[Dict])

### GET /api/data/datasets/{dataset_id}/ohlcv -- OHLCV 数据

**查询参数**: start, end (时间范围), limit (1000)。
**响应** (`OhlcvResponse`): dataset_id, data (List[{timestamp, open, high, low, close, volume}])

### GET /api/data/available-sources -- 可用数据源

扫描 data 目录 Parquet 文件，从文件名 `{SYMBOL}_{TIMEFRAME}.parquet` 解析。
**响应** (`AvailableSourcesResponse`): `{"sources": [{"symbol": "...", "timeframe": "...", "time_start": "...", "time_end": "..."}]}`

### GET /api/data/ohlcv/{symbol}/{timeframe} -- 按交易对获取 OHLCV

**查询参数**: start, end, limit (10000)。**错误**: 404。
**响应** (`OhlcvResponse`): dataset_id 为 `{symbol}_{timeframe}`

### GET /api/data/chart-indicators/{symbol}/{timeframe} -- 图表指标

**查询参数**:

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| start / end | str | null | 时间范围 |
| ema_periods | str | null | 逗号分隔 EMA 周期 (如 "10,20,50") |
| boll_enabled | bool | true | 是否计算布林带 |
| boll_period / boll_std | int / float | 20 / 2.0 | 布林带参数 |
| rsi_enabled / rsi_period | bool / int | true / 14 | RSI 开关/周期 |
| rvol_enabled / rvol_period | bool / int | false / 20 | RVOL 开关/周期 |
| vwma_enabled / vwma_period | bool / int | false / 20 | VWMA 开关/周期 |

**响应**: `{"ema": {"10": [{time, value},...], ...}, "boll": {upper: [...], middle: [...], lower: [...]}, "rsi": [...], "rvol": [...], "vwma": [...]}`

---

## 8. WebSocket 实时推送

### WS /ws/evolution/{task_id} -- 进化进度

**路径参数**: task_id (str)

`_ConnectionManager` 维护 task_id -> Set[WebSocket] 的映射，支持多客户端订阅。

**协议**:

客户端 -> 服务端: `{"type": "ping"}` (心跳), `{"type": "subscribe"}` (订阅确认)

服务端 -> 客户端:
- `{"type": "pong"}` -- 心跳响应
- `{"type": "subscribed", "task_id": "..."}` -- 连接时自动发送
- `{"type": "generation_complete", "task_id": "...", "generation": N, ...}` -- 单代完成
- `{"type": "evolution_complete", "task_id": "...", ...}` -- 进化完成
- `{"type": "echo", "data": {...}}` -- 未知消息回显

**推送机制**: `EvolutionRunner` 后台线程通过 `asyncio.run_coroutine_threadsafe` 将推送任务调度到 FastAPI 事件循环。

---

## 9. 假设验证 (validate)

### POST /api/validate -- 验证 WHEN->THEN 假设

**请求** (`ValidateRequest`):

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pair | str | 是 | 交易对 |
| timeframe | str | 是 | 时间框架 |
| start / end | str | 是 | 时间范围 |
| when | List[ConditionInput] | 是 | WHEN 条件列表 |
| then | List[ConditionInput] | 是 | THEN 条件列表 |
| indicator_params | Dict | 否 | 指标参数覆盖 |
| base_timeframe | str | 否 | 基础时间框架 (MTF) |

`ConditionInput`: subject, action, target, window (int), logic ("AND"/"OR"), timeframe

**响应** (`ValidateResponse`): match_rate, total_count, match_count, mismatch_count, triggers (List[TriggerRecordResponse]), distribution, percentiles, concentration, signal_frequency, extremes, warnings

### GET /api/validate/{task_id}/triggers -- 触发记录 (占位)

**查询参数**: page (1), per_page (20), sort ("time"/"trigger_price"/"change_pct"), order ("asc"/"desc")
**当前响应** (占位): `{"total": 0, "page": 1, "per_page": 20, "records": []}`

---

## 10. 错误处理

统一错误格式: `{"detail": "错误描述"}`

| HTTP 状态码 | 场景 |
|-------------|------|
| 400 | 请求参数错误、任务状态不允许操作 |
| 404 | 资源不存在 (策略/任务/数据集/文件) |
| 500 | 服务端内部错误 |
