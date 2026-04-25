# B1: API 入口与路由

## 定位

`api/` 是 HTTP 边界层，连接前端和后端核心逻辑。职责不是"做业务"，而是"校验输入、管理后台线程、推送实时状态"。所有路由处理函数都是薄层——解析请求、调用 core 模块、返回结果。

## 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `app.py` | 118 | 应用工厂：CORS、lifespan、路由挂载、EvolutionRunner 启停 |
| `schemas.py` | 418 | Pydantic V2 请求/响应模型（全部 `extra="forbid"`） |
| `runner.py` | 609 | 进化后台线程：轮询 pending 任务、执行进化、WS 推送 |
| `db_ext.py` | 669 | 扩展数据库操作：strategy/backtest_result/dataset_meta CRUD + 迁移 |
| `deps.py` | 17 | 依赖注入：从 `app.state` 取 db_path 和 data_dir |
| `routes/` | 9 个文件 | 按领域分组的路由处理函数 |

## 关键链路

### 应用启动链路

```
__main__.py:9 -> create_app(db_path, data_dir)
  app.py:34-39  默认路径解析 data/quant.db + data/market
  app.py:41-77  lifespan 异步上下文管理器:
    L44-45  创建目录
    L46     init_db_ext(db_path) 初始化 schema
    L49-50  db_path/data_dir 存入 app.state
    L56-71  创建 EvolutionRunner 后台线程
            通过 asyncio.run_coroutine_threadsafe 桥接线程->asyncio
  app.py:78-82  FastAPI(title="MyQuant API", version="0.14.0")
  app.py:85-91  CORS 全开放（开发阶段）
  app.py:94-102 挂载 9 个路由模块
```

### 创建进化任务 (POST /api/evolution/tasks)

```
routes/evolution.py:166 create_task()
  L173  生成 UUID
  L178-181  自动排序 timeframe_pool，最短周期为执行周期
  L184-216  构建初始 DNA（用户指定 or 默认 EMA 策略）
             MTF 任务会构建多层 DNA
  L218-222  强制覆盖 leverage/direction 约束
  L225-263  验证数据可用性，读取 parquet 时间范围
  L265-301  save_task() 写入数据库

runner.py:85 _tick() 轮询 pending 任务 (每 2 秒)
  L108-117  _find_pending_task() 查询 SQLite
  L119-502  _run_task() 执行进化:
    L159-172  load_and_prepare_df 加载市场数据
    L177-185  创建 EvolutionEngine
    L192-200  定义 evaluate_fn 闭包
    L365-369  engine.evolve() 启动进化
    L209-362  on_generation 回调:
      save_history() + save_snapshot() + ChampionTracker
      + 自动提取 strategy_threshold 以上策略 + WS 推送
```

### 回测策略 (POST /api/strategies/backtest)

```
routes/strategies.py:186 backtest_strategy()
  L199-216  解析 DNA（从已保存策略 or 内联 DNA）
  L219-224  加载 parquet 数据集
  L235-239  load_and_prepare_df 加载增强数据
  L262-273  如有 MTF 需求加载多时间周期数据
  L275      engine.run(dna, enhanced_df) 执行回测
  L278-284  compute_metrics + score_strategy
  L289-309  保存回测结果
  L341-362  构建响应
```

### WebSocket 实时推送

```
routes/ws.py:58  /ws/evolution/{task_id}
  ws.py:20-44  _ConnectionManager 管理 task_id -> Set[WebSocket]
  runner.py:42-48  _push_ws() 通过全局回调函数推送
  app.py:62-70  启动时注册 WS 推送桥接
```

## 关键机制

### 数据库版本迁移 (db_ext.py:163-230)

版本号递增迁移策略。`schema_version` 表记录已应用版本。行 181-202 扫描 `migrations/*.sql`，文件名前导数字为版本号。行 59-109 定义了 4 组列扩展，每组都有幂等性检查（先 `PRAGMA table_info` 检查已有列）。

### 策略去重 (db_ext.py:256-297)

`save_strategy` 通过 `gene_signature` 去重。行 261-268 自动计算基因签名。行 276-297 当 `gene_signature` 匹配且 `best_score` 更高时替换旧记录；手动保存（`best_score=None`）始终插入。

### 连续进化 (runner.py:374-452)

进化完成后如果 `continuous=True`，进入 while 循环。行 386-394 当原始方向为 "mixed" 时轮转 long/short。行 412-429 注入 2 个随机策略模板种子 + 前 3 名精英。行 431-437 收集已发现签名去重。行 451 累加 `global_gen_offset` 防止历史覆盖。

## 接口清单

| 方法 | 路径 | 处理函数 |
|------|------|---------|
| GET | `/api/health` | `app.py:105` |
| GET/PUT | `/api/config` | `routes/config.py:52-67` |
| GET/PUT | `/api/config/chart_indicators` | `routes/chart_config.py:46-61` |
| GET | `/api/data/datasets` | `routes/data.py:33` |
| GET | `/api/data/datasets/{id}` | `routes/data.py:66` |
| POST | `/api/data/import` | `routes/data.py:95` (timeout 120s) |
| POST | `/api/data/import-batch` | `routes/data.py:181` (timeout 300s) |
| DELETE | `/api/data/datasets/{id}` | `routes/data.py:270` |
| GET | `/api/data/datasets/{id}/ohlcv` | `routes/data.py:326` |
| GET | `/api/data/ohlcv/{symbol}/{tf}` | `routes/data.py:445` |
| GET | `/api/data/chart-indicators/{symbol}/{tf}` | `routes/data.py:489` |
| POST | `/api/strategies` | `routes/strategies.py:74` |
| GET | `/api/strategies` | `routes/strategies.py:102` |
| POST | `/api/strategies/backtest` | `routes/strategies.py:186` (timeout 60s) |
| POST | `/api/strategies/compare` | `routes/strategies.py:365` |
| POST | `/api/evolution/tasks` | `routes/evolution.py:166` |
| GET | `/api/evolution/tasks` | `routes/evolution.py:309` |
| POST | `/api/evolution/tasks/{id}/pause` | `routes/evolution.py:373` |
| POST | `/api/evolution/tasks/{id}/stop` | `routes/evolution.py:388` |
| POST | `/api/evolution/tasks/{id}/resume` | `routes/evolution.py:403` |
| GET | `/api/evolution/tasks/{id}/strategies` | `routes/evolution.py:421` |
| POST | `/api/validate` | `routes/validate.py:110` |
| POST | `/api/validate/rules` | `routes/validate.py:173` |
| POST | `/api/discovery/patterns` | `routes/discovery.py:50` |
| GET | `/api/scene/types` | `routes/scene.py:76` |
| POST | `/api/validate/scene` | `routes/scene.py:92` |
| WS | `/ws/evolution/{task_id}` | `routes/ws.py:58` |

## 关键参数

| 参数 | 位置 | 默认值 | 设计意图 |
|------|------|--------|---------|
| `poll_interval` | runner.py:58 | 2.0s | 后台线程轮询间隔 |
| `population_size` | schemas.py:269 | 15 | 进化种群大小，平衡探索广度与计算成本 |
| `max_generations` | schemas.py:270 | 200 | 硬上限 |
| `elite_ratio` | schemas.py:271 | 0.5 | 精英保留比例 |
| `strategy_threshold` | schemas.py:281 | 80.0 | 自动提取策略的分数阈值 |
| `continuous` | schemas.py:280 | True | 连续进化模式开关 |
| `init_cash` | schemas.py:192 | 100000 | 回测初始资金 |
| `fee` | schemas.py:193 | 0.001 | 交易手续费率 |
| `slippage` | schemas.py:194 | 0.0005 | 滑点率 |
| `leverage` | schemas.py:276 | 1 [1,10] | 杠杆倍数 |
| `direction` | schemas.py:277 | "long" | long/short/mixed |

## 约定与规则

- **路由前缀**: `/api/` + 领域分组（config/data/strategies/evolution/validate/discovery/scene）
- **依赖注入**: `deps.py` 的 `get_db_path(request)` / `get_data_dir(request)` 从 `app.state` 获取
- **Pydantic V2 严格模式**: 所有 schema 使用 `ConfigDict(extra="forbid")`
- **SQLite WAL**: 后台线程直连使用 `PRAGMA journal_mode=WAL`（runner.py:111,222,283）
- **错误处理**: 路由层 HTTPException，runner 层 try/except 兜底
- **命名约定**: `_function_name` 表示内部函数，路由函数以 `_endpoint` 后缀区分同名 db 函数
- **已知问题**: 版本号 `app.py:80,109` 硬编码 `"0.14.0"` 与 `schemas.py:416` 默认 `"0.9.0"` 不一致
