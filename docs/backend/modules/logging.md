# B11: 日志

## 定位

`core/logging/` 是工程的轻量日志基础设施，提供统一的 logger 工厂和结构化格式化器。所有模块通过 `get_logger(tag)` 获取日志实例。

## 文件职责

| 文件 | 行数 | 职责 |
|------|------|------|
| `__init__.py` | 62 | logger 工厂：缓存 + 双 handler（console + file） |
| `config.py` | 64 | 日志路径生成 + 根 logger 配置 |
| `formatter.py` | 76 | AIFormatter 结构化格式化器 |

## AIFormatter (formatter.py)

自定义格式化器，输出管道分隔的结构化日志行：

```
[2026-04-11 15:30:00] | [TAG] | [LEVEL] | message | context | file:line
```

- 时间戳取本地时间（`datetime.now(timezone.utc).astimezone()`）
- context 通过 `extra={"context": ...}` 传入，dict 展开为 `key=value` 对
- 源码位置附加 `filename:lineno`，只取文件名不取全路径

## Logger 工厂 (__init__.py)

`get_logger(tag)` 流程：

```
检查缓存 _loggers[tag]
  ├─ 命中 → 直接返回
  └─ 未命中 → logging.getLogger(tag)
       ├─ 设置 level=DEBUG
       ├─ 添加 StreamHandler (DEBUG, AIFormatter)
       ├─ 添加 FileHandler (INFO, AIFormatter) → logs/api/app_YYYYMMDD.log
       ├─ propagate=False
       └─ 存入缓存返回
```

## 日志路径 (config.py)

`get_log_path(module, log_type)` 从当前文件向上 3 级定位项目根目录，生成路径：

```
{project_root}/logs/{module}/{log_type}_YYYYMMDD.log
```

`configure_logging()` 配置根 logger，但只加 console handler，使用基础 `Formatter` 而非 `AIFormatter`。

## 已知问题

- `get_logger()` 硬编码 `get_log_path("api", "app")`——不管 tag 传什么值，所有 logger 写同一个文件 `logs/api/app_YYYYMMDD.log`，无法按模块分文件
- `configure_logging()` 接受 `log_to_file` 参数但**未使用**——函数体内没有任何文件 handler 逻辑，参数是空壳
- 根 logger 和 get_logger 创建的 logger 使用不同的 Formatter（根 logger 用 `logging.Formatter`，get_logger 用 `AIFormatter`），格式不统一

## 数据流

```
各业务模块
  └─ get_logger("EVOLUTION") → 缓存 Logger
       ├─ console → AIFormatter → 标准输出
       └─ file → AIFormatter → logs/api/app_YYYYMMDD.log

app.py 启动时
  └─ configure_logging() → 根 logger (基础 Formatter, 仅 console)
```

## 涉及文件

| 文件 | 核心内容 |
|------|---------|
| `core/logging/__init__.py` | logger 工厂 + 双 handler |
| `core/logging/config.py` | 日志路径生成 + 根 logger 配置 |
| `core/logging/formatter.py` | AIFormatter 结构化格式化 |
