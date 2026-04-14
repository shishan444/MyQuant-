# MyQuant 日志目录

## 目录结构

- `start/` - 启动脚本日志
- `api/` - 后端 API 日志
- `web/` - 前端日志
- `archive/` - 历史归档

## 命名规则

{module}_{type}_{YYYYMMDD}.log

## 日志格式

[TS] [TAG] [LEVEL] msg | context | src

## 清理策略

- 自动删除 >7 天的日志
- 归档到 archive/ 目录

## 查看日志

# 查看今天的日志
tail -f logs/api/api_$(date +%Y%m%d).log

# 搜索错误
grep ERROR logs/api/api_*.log

# 查看回测日志
tail -f logs/api/backtest_*.log
