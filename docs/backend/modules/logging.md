# B11: 日志

## 定位

`core/logging/` 提供统一的、AI 友好的日志系统。所有模块通过 `get_logger(tag)` 获取日志实例，输出到控制台和按日期分割的文件。

## 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `__init__.py` | 62 | Logger 工厂 (带缓存) |
| `config.py` | 64 | 日志路径生成 + 全局配置 |
| `formatter.py` | 76 | AIFormatter 结构化格式 |

## 关键链路

### Logger 创建 (__init__.py:18)

```
get_logger(tag: str) -> Logger
  L31  检查 _loggers 缓存
  L34  logging.getLogger(tag)
  L38  清除已有 handler (防重复)
  L41  添加 ConsoleHandler(AIFormatter, DEBUG)
  L47  添加 FileHandler(logs/api/app_{date}.log, INFO)
  L55  propagate=False (防冒泡到 root)
  L57  存入缓存
```

### 格式化 (formatter.py:28)

```
输出格式: [timestamp] [TAG] [LEVEL] msg | k=v | file:line
  L38  时间戳: 本地时间 YYYY-MM-DD HH:MM:SS
  L41  TAG: Logger 名大写
  L58-64  context: dict -> k=v 对; str -> 直接追加
  L67-70  源位置: filename:lineno
```

## 关键机制

### AI 友好格式设计

`[TS] [TAG] [LEVEL] msg | context | file:line` 固定结构，分隔符分隔，LLM 可正则解析，人类可扫描。

### Logger 缓存 (__init__.py:15)

`_loggers: dict[str, Logger]` 保证 `get_logger("API")` 每次返回相同实例。

## 接口定义

| 函数 | 说明 |
|------|------|
| `get_logger(tag) -> Logger` | 获取带 tag 的 Logger |
| `get_log_path(module, log_type) -> Path` | `logs/{module}/{type}_{YYYYMMDD}.log` |
| `configure_logging(level, log_to_file)` | 全局配置 |

## 关键参数

| 参数 | 默认值 | 设计意图 |
|------|--------|---------|
| Console 级别 | DEBUG | 所有消息显示控制台 |
| File 级别 | INFO | 只记录 INFO+ 到文件 |
| Logger 级别 | DEBUG | 允许所有消息 |
| 日志路径模块 | "api" | 硬编码，所有 Logger 写同一目录 |

## 约定与规则

- **DEV**: `tag . msg . why . file:line`
- **PROD**: 最少必要字段，无敏感信息
- **Tag 大写缩写**: "API", "BACKTEST", "DB", "SCENE"
- **Context 传递**: `logger.info(msg, extra={"context": {"rid": "abc"}})`
- **无日志轮转**: 依赖日期分割自然轮转
- **已知限制**: FileHandler 硬编码 module="api"，所有 tag 写同一文件
