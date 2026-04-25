# B10: 持久化

## 定位

`core/persistence/` 是进化引擎的 SQLite 持久化层，支持 checkpoint-resume（中断恢复）和历史评分追踪。注意：策略/回测结果/数据集的 CRUD 在 `api/db_ext.py`，不在本模块。

## 文件职责

| 文件 | 行数 | 职责 |
|------|------|------|
| `db.py` | 272 | SQLite 操作：3 张表的 CRUD + WAL 模式 |
| `checkpoint.py` | 90 | 进化 checkpoint 保存与恢复 |
| `__init__.py` | 空 | 无导出 |

## 三张表

### evolution_task

每行一个进化任务，核心字段：

| 字段 | 类型 | 含义 |
|------|------|------|
| task_id | TEXT PK | UUID |
| status | TEXT | pending/running/paused/stopped/completed |
| target_score | REAL | 目标分数 |
| symbol / timeframe | TEXT | 交易对和周期 |
| initial_dna | TEXT (JSON) | 初始 DNA |
| champion_dna | TEXT (JSON) | 冠军 DNA |
| stop_reason | TEXT | 停止原因 |
| current_generation | INTEGER | 当前代数 |
| best_score | REAL | 最佳分数 |
| leverage / direction | INT/TEXT | 任务约束 |
| continuous | INTEGER | 是否连续进化 |
| strategy_threshold | REAL | 自动提取阈值 |

### generation_snapshot

每代一个快照，用于 checkpoint-resume：

| 字段 | 类型 | 含义 |
|------|------|------|
| task_id + generation | 复合 PK | 任务 + 代数 |
| population_json | TEXT (JSON) | 完整种群序列化 |
| best_dna | TEXT (JSON) | 本代最佳 DNA |
| best_score / avg_score | REAL | 分数 |

### evolution_history

轻量历史记录，用于 UI 图表：

| 字段 | 类型 | 含义 |
|------|------|------|
| task_id + generation | 复合 PK | 任务 + 代数 |
| best_score / avg_score | REAL | 分数 |
| top3_summary | TEXT | 诊断信息 JSON |

## 连接模式

所有连接使用 WAL (Write-Ahead Logging) 模式支持并发读。短连接模式：每次操作 open → execute → close。

## Checkpoint 机制

```
save_generation() (checkpoint.py)
  ├─ save_snapshot() → 完整种群写入 generation_snapshot
  └─ save_history() → 分数写入 evolution_history

resume_evolution() (checkpoint.py)
  ├─ get_task(status='running')
  ├─ get_latest_snapshot()
  └─ 反序列化 population + best_dna → 返回恢复状态
```

只恢复 status="running" 的任务。

## 数据流

```
api/runner.py (EvolutionRunner)
  ├─ 创建任务 → save_task() [db.py]
  ├─ 每代回调 → save_generation() [checkpoint.py]
  │                → save_snapshot() + save_history() [db.py]
  ├─ 更新状态 → update_task() [db.py]
  ├─ 读取历史 → get_history() [db.py] → 前端图表
  └─ 恢复进化 → resume_evolution() [checkpoint.py]
```

## 涉及文件

| 文件 | 核心内容 |
|------|---------|
| `core/persistence/db.py` | SQLite 3 张表 CRUD |
| `core/persistence/checkpoint.py` | 进化 checkpoint 保存与恢复 |
