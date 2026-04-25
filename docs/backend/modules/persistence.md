# B10: 持久化

## 定位

`core/persistence/` 是进化引擎的 SQLite 持久化层，支持 checkpoint-resume（中断恢复）和历史评分追踪。注意: 策略/回测结果/数据集的 CRUD 在 `api/db_ext.py`，不在本模块。

## 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `db.py` | 272 | 3 张表 CRUD (evolution_task/generation_snapshot/evolution_history) |
| `checkpoint.py` | 90 | 高级保存/恢复接口 |

## 关键链路

### 保存代 (checkpoint.py:14)

```
save_generation(db_path, task_id, generation, best_score, avg_score, best_dna, population)
  L31-41  save_snapshot(): 序列化 population 为 JSON -> INSERT OR REPLACE
  L43-51  save_history(): 创建 top3_summary JSON -> INSERT OR REPLACE
```

### 恢复进化 (checkpoint.py:54)

```
resume_evolution(db_path, task_id)
  L67  get_task(): 验证任务存在且 status=="running"
  L71  get_latest_snapshot(): 获取 generation 降序第一行
  L76  反序列化 population_json -> [StrategyDNA.from_dict(d)]
  L79  反序列化 best_dna -> StrategyDNA.from_json()
```

## 关键机制

### SQLite WAL 模式 (db.py:25)

允许并发读写。进化引擎长时间运行时 API 可同时读取进度。

### 双写策略 (checkpoint.py:14-51)

每代写入两个表: `generation_snapshot`(完整种群，用于恢复) + `evolution_history`(轻量记录，用于 UI 图表)。分离后图表查询无需解析大型种群 JSON。

### INSERT OR REPLACE

相同 (task_id, generation) 键静默覆盖。简化重试逻辑，但无法检测重复保存。

## 接口定义

| 函数 | 说明 |
|------|------|
| `init_db(db_path)` | 初始化 3 张表 + 迁移 |
| `save_task(db_path, task_id, ...)` | 保存任务 |
| `update_task(db_path, task_id, status, champion_dna, ...)` | 更新任务 |
| `get_task(db_path, task_id) -> Dict` | 获取任务 |
| `get_running_task(db_path) -> Dict` | 获取运行中任务 |
| `save_snapshot(db_path, task_id, gen, ...)` | 保存种群快照 |
| `get_latest_snapshot(db_path, task_id) -> Dict` | 获取最新快照 |
| `save_history(db_path, task_id, gen, ...)` | 保存历史记录 |
| `get_history(db_path, task_id) -> List[Dict]` | 获取历史列表 |
| `list_all_tasks(db_path, status, limit, offset)` | 分页任务列表 |
| `save_generation(db_path, task_id, gen, ...)` | 高级: 保存一代 |
| `resume_evolution(db_path, task_id) -> Dict` | 高级: 恢复进化 |

## 关键参数

| 参数 | 默认值 | 设计意图 |
|------|--------|---------|
| journal_mode | WAL | 并发读写 |
| limit (list) | 50 | 分页大小 |

## 约定与规则

- **每操作连接**: 每个函数开新连接，无连接池（单用户桌面工具够用）
- **UTC 时间戳**: `_now()` 返回 UTC ISO 格式
- **row_factory**: sqlite3.Row 返回类字典行
- **复合主键**: (task_id, generation) 保证每代一条记录
- **静默迁移**: ALTER TABLE 捕获"列已存在"异常
- **JSON 列**: population_json, initial_dna, champion_dna 等存储为 JSON 字符串，SQLite 不验证结构
