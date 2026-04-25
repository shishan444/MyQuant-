# B1: API 入口与路由

## 定位

`api/` 是 HTTP 层，把后端各 core 模块的能力暴露给前端。包含 FastAPI 应用构建、Pydantic V2 严格校验 schema、WebSocket 实时推送、进化后台线程控制器、SQLite 数据库操作。

## 文件职责

| 文件 | 行数 | 职责 |
|------|------|------|
| `app.py` | 118 | FastAPI 应用工厂：CORS、lifespan、路由挂载、EvolutionRunner 启停 |
| `schemas.py` | 414 | Pydantic V2 请求/响应模型（全部 `extra="forbid"`） |
| `runner.py` | 632 | 进化引擎后台线程：轮询 SQLite pending 任务、执行进化、WS 推送 |
| `db_ext.py` | 671 | 扩展数据库操作：strategy/backtest_result/dataset_meta CRUD + 迁移 |
| `deps.py` | ~15 | FastAPI 依赖注入：从 app.state 取 db_path 和 data_dir |
| `routes/strategies.py` | ~250 | 策略 CRUD + 回测 + 多策略对比 |
| `routes/evolution.py` | ~300 | 进化任务 CRUD + 暂停/停止/恢复 + 历史查询 + 发现策略 |
| `routes/data.py` | ~300 | 数据集 CRUD + CSV 导入 + OHLCV 查询 + 可用数据源扫描 |
| `routes/ws.py` | ~80 | WebSocket `/ws/evolution/{task_id}` 实时推送 |
| `routes/validate.py` | ~200 | 假设验证（WHEN→THEN）+ 规则条件评估 |
| `routes/config.py` | ~60 | 应用配置读写 |
| `routes/chart_config.py` | ~60 | 图表指标配置读写 |
| `routes/scene.py` | ~150 | 场景验证类型列表 + 场景检测 |
| `routes/discovery.py` | ~150 | 决策树模式发现 + KNN 相似案例 + 价格预测 |

共 40 个端点（38 HTTP + 1 WebSocket + health check）。

## 应用生命周期 (app.py)

```
create_app(db_path, data_dir)
  ↓
lifespan startup:
  ├─ init_db_ext(db_path)          → SQLite 建表 + 迁移
  ├─ app.state.db_path/data_dir    → 依赖注入
  ├─ EvolutionRunner(daemon=True)  → 后台线程启动
  └─ set_ws_push_fn                → 接线 WS 推送
  ↓
yield (app 运行中)
  ↓
lifespan shutdown:
  └─ runner.stop()
```

CORS 配置: `allow_origins=["*"]`，全开放。进化 runner 和 WS 推送的桥接通过 `asyncio.run_coroutine_threadsafe()` 实现——从 runner 的同步线程跨到 FastAPI 的异步事件循环。

## Pydantic Schema (schemas.py)

所有模型用 `extra="forbid"` 严格模式——前端多传任何字段返回 422。

关键模型：

| 模型 | 用途 |
|------|------|
| `DNAModel` | DNA 的 API 表征，嵌套 SignalGene/Logic/Risk/Execution |
| `BacktestRequest` | 回测请求：可传 strategy_id 或 dna + dataset_id |
| `BacktestResponse` | 回测结果：含 equity_curve 和 signals（JSON 序列化） |
| `EvolutionTaskCreate` | 创建进化任务：含 timeframe_pool/indicator_pool/leverage/direction |
| `EvolutionTaskResponse` | 进化任务详情：含 champion_metrics/dimension_scores/exploration_efficiency |
| `CompareRequest` | 多策略对比回测 |

**`StrategyListResponse`** 用 `items` 字段（不是 `strategies`），之前的 `strategies` vs `items` 不匹配 bug 已修复。

## 进化后台线程 (runner.py)

### EvolutionRunner

继承 `threading.Thread(daemon=True)`，每 2 秒轮询一次 SQLite。

```
run() → 循环 _tick()
  ├─ 有 active_task → 检查状态是否被暂停/停止
  └─ 无 active_task → _find_pending_task()
       └─ 有 → _run_task(task)
```

### _run_task(): 任务执行全流程

```
解析 initial_dna → StrategyDNA
  ↓
load_and_prepare_df() → enhanced_df (数据只加载一次)
  ↓
load_mtf_data() → dfs_by_timeframe (MTF 时)
  ↓
engine.evolve(ancestor, evaluate_fn, on_generation)
  ↓
连续进化模式:
  while continuous:
    ├─ 保留 champion 作为新祖先
    ├─ 注入 2 个随机策略模板种子
    ├─ 保留上代 top 3 精英作为 extra_ancestors
    ├─ exclude_signatures = 所有已见签名
    └─ engine.evolve(新种群)
  ↓
Walk-Forward 验证 champion (score > 20 时)
  ↓
保存 champion metrics 到 DB
```

### _evaluate_dna(): 单个体评估

被 EvolutionEngine 的 evaluate_fn 调用。数据已预加载，避免每个个体重复 I/O。

```
dna_to_signal_set(individual, enhanced_df)
  ↓ 无入场信号 → score=5.0 (保底分)
  ↓
BacktestEngine.run(individual, enhanced_df, signal_set)
  ↓
score_strategy(metrics, template_name)
  ↓
返回 diagnostics dict (score + raw_metrics + dimension_scores)
  ↓ 附加到 individual._eval_diagnostics
```

### on_generation(): 每代回调

每代结束后执行：
1. 检查任务是否被暂停/停止（`_StopEvolution` 异常跳出循环）
2. 更新 `current_generation` 到 DB
3. 计算种群多样性诊断
4. 保存 history 记录和 snapshot
5. 原子更新 champion（via ChampionTracker）
6. **自动提取**高分策略（score >= strategy_threshold）到 strategy 表
7. WebSocket 推送进度

### 连续进化模式

`continuous=True`（默认）时，进化不会在单次 evolve 结束后停止，而是循环启动新种群：
- "mixed" 方向时交替 long/short
- 上代 champion 作为新祖先
- 注入随机模板种子扩展搜索空间
- 累积 `global_gen_offset` 避免历史记录覆盖
- 用 `exclude_signatures` 避免重复探索同一基因

## 数据库操作 (db_ext.py)

### 迁移系统

`init_db_ext()` 先调 `core.persistence.db.init_db()` 建核心表，再执行：
1. SQL 文件迁移（`migrations/*.sql`，跳过 005/006）
2. ALTER TABLE 添加 evolution_task 扩展列（migration 005）
3. ALTER TABLE 添加 MTF 列（migration 006）
4. ALTER TABLE 添加约束列（migration 007）
5. ALTER TABLE 添加 strategy.metrics_json（migration 008）

所有迁移幂等——检查 `schema_version` 表判断是否已应用。

### Strategy 去重

`save_strategy()` 基于 `gene_signature` 去重：
- 有 `best_score` 的进化策略：同签名时保留高分版本（UPDATE 替换）
- 手动保存（`best_score=None`）：跳过去重，直接插入

### CRUD 操作

| 表 | 操作 |
|------|------|
| strategy | save / get / list / update / delete / count_by_tasks |
| backtest_result | save / get / list |
| dataset_meta | save / get / list / update_stats / delete |

所有操作都是手写 SQL，非 ORM。`update_strategy` 和 `update_dataset_stats` 用 `**fields` 动态构建 UPDATE 语句，有白名单过滤。

## 路由端点总览

### `/api/strategies` (7 端点)

| 方法 | 路径 | 作用 |
|------|------|------|
| POST | `/` | 创建策略 |
| GET | `/` | 列出策略（过滤/排序/分页） |
| GET | `/{id}` | 获取单个策略 |
| PUT | `/{id}` | 更新策略 |
| DELETE | `/{id}` | 删除策略 |
| POST | `/backtest` | 运行回测（核心端点） |
| POST | `/compare` | 多策略对比回测 |

### `/api/evolution` (10 端点)

| 方法 | 路径 | 作用 |
|------|------|------|
| GET | `/strategies` | 列出所有进化发现的策略 |
| POST | `/tasks` | 创建进化任务 |
| GET | `/tasks` | 列出任务（分页） |
| GET | `/tasks/{id}` | 任务详情 |
| GET | `/tasks/{id}/history` | 逐代历史 |
| POST | `/tasks/{id}/pause` | 暂停 |
| POST | `/tasks/{id}/stop` | 停止 |
| POST | `/tasks/{id}/resume` | 恢复 |
| GET | `/tasks/{id}/strategies` | 任务冠军 + 快照 DNA |
| GET | `/tasks/{id}/discovered-strategies` | 任务自动提取的策略 |

### `/api/data` (10 端点)

| 方法 | 路径 | 作用 |
|------|------|------|
| GET | `/datasets` | 列出数据集 |
| GET | `/datasets/{id}` | 数据集元数据 |
| POST | `/import` | CSV 单文件导入 |
| POST | `/import-batch` | CSV 批量导入 |
| DELETE | `/datasets/{id}` | 删除数据集 |
| GET | `/datasets/{id}/preview` | 预览前 N 行 |
| GET | `/datasets/{id}/ohlcv` | 获取 OHLCV 数据 |
| GET | `/available-sources` | 扫描可用数据源 |
| GET | `/ohlcv/{symbol}/{tf}` | 按 symbol+tf 直接取 OHLCV |
| GET | `/chart-indicators/{symbol}/{tf}` | 图表指标计算 |

### `/ws/evolution/{task_id}` (WebSocket)

实时推送进化进度：`generation_complete`、`strategy_discovered`、`population_started`、`evolution_complete`。带 ping/pong 心跳。

### 其他端点

| 路径 | 端点数 | 作用 |
|------|--------|------|
| `/api/validate` | 3 | 假设验证 + 规则评估 |
| `/api/config` | 4 | 应用配置 + 图表指标配置 |
| `/api/scene` | 2 | 场景类型列表 + 场景检测 |
| `/api/discovery` | 3 | 模式发现 + KNN 相似 + 价格预测 |

## 数据流

```
前端请求
  ↓
FastAPI handler (同步, 非async)
  ↓ deps.get_db_path/get_data_dir (依赖注入)
  ↓
  ├─ 策略 CRUD → db_ext.* → SQLite
  ├─ 回测 → mtf_loader.load_and_prepare_df → executor.dna_to_signal_set
  │          → BacktestEngine.run → score_strategy → BacktestResponse
  ├─ 进化任务 → runner._run_task → EvolutionEngine.evolve
  │             → WS push → 前端实时更新
  ├─ 数据管理 → csv_importer / fetcher / updater → Parquet
  └─ 验证/发现 → core.validation / core.discovery
```

## 涉及文件

| 文件 | 核心内容 |
|------|---------|
| `api/app.py` | FastAPI 应用工厂、lifespan、CORS |
| `api/schemas.py` | Pydantic V2 严格校验模型 |
| `api/runner.py` | 进化后台线程、个体评估、连续进化 |
| `api/db_ext.py` | 数据库迁移 + strategy/backtest_result/dataset_meta CRUD |
| `api/deps.py` | FastAPI 依赖注入 |
| `api/routes/*.py` | 9 个路由模块，40 个端点 |
