# B2: 数据存储与加载

## 定位

`core/data/` 管理量化交易数据的全生命周期——获取、导入、存储、加载、更新、多时间周期聚合。是所有模块的数据源。

## 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `storage.py` | 46 | Parquet 读写、合并 |
| `csv_importer.py` | 408 | CSV 导入（格式检测、解析、验证） |
| `fetcher.py` | 63 | Binance API 数据拉取 |
| `updater.py` | 81 | 增量更新 |
| `mtf_loader.py` | 118 | 统一加载入口 + 多时间周期聚合 |

## 关键链路

### CSV 单文件导入

```
csv_importer.py:249 import_csv(path, data_dir, symbol, interval, mode)
  L269-273  自动检测 symbol/interval（从文件名），不足则抛异常
  L276-279  read_csv(path) 读取并标准化 + validate_ohlcv(df) 验证
  L281-282  dataset_id = {symbol}_{interval}，确定 parquet 路径
  L285-287  detect_format() 检测格式和时间戳精度
  L290-298  根据 mode: REPLACE/MERGE/NEW 选择写入策略
```

格式检测 (detect_format, L86-122): 第一行检查列名 -> GENERIC_OHLCV；12列数字 -> BINANCE_OFFICIAL。

### 多时间周期数据加载

```
mtf_loader.py:41 load_and_prepare_df(data_dir, symbol, timeframe, ...)
  L56-58  符号清洗 + find_parquet 查找文件（支持别名）
  L61     load_parquet 读取原始 OHLCV
  L62-63  检查最小数据量 (50 bars)
  L65-70  日期范围切片
  L72     compute_all_indicators(df) -- 调用 B3 模块预计算

mtf_loader.py:75 load_mtf_data(data_dir, symbol, exec_timeframe, enhanced_df, needed_tfs)
  L93  初始化 {exec_timeframe: enhanced_df}
  L95-115  遍历额外时间周期，逐个加载 + 计算指标
  L117  返回 Dict[str, pd.DataFrame]
```

文件查找 (find_parquet, L28-38): 先尝试主路径，失败则遍历 `_TF_ALIASES` 别名列表。

### 增量更新

```
updater.py:18 update_market_data(symbol, interval, data_dir, history_years)
  L45  get_latest_timestamp(path) 检查本地最新数据
  L47-57  无本地数据 -> 全量拉取 (history_years 年)
  L60-67  有本地数据 -> 从最新时间增量拉取
  L74-79  合并、去重、排序、保存
```

## 关键机制

### OHLCV 数据验证 (csv_importer.py:161-193)

四重检查：(1) NaN 值 (2) high >= max(open,close,low) (3) low <= min(open,close,high) (4) 负成交量。向量化检查。

### Parquet 合并策略 (storage.py:31-45)

`merge_parquet`: concat + `duplicated(keep="last")` + sort_index + save。新数据优先。

### 时间戳精度检测 (csv_importer.py:127-141)

10位以下 -> 错误；10-13位 -> 毫秒；14-16位 -> 微秒。

## 接口定义

| 函数 | 签名 | 位置 |
|------|------|------|
| `save_parquet` | `(df, path) -> None` | storage.py:10 |
| `load_parquet` | `(path) -> DataFrame` | storage.py:16 |
| `get_latest_timestamp` | `(path) -> Timestamp or None` | storage.py:21 |
| `merge_parquet` | `(new_df, path) -> None` | storage.py:31 |
| `import_csv` | `(path, data_dir, ...) -> CsvImportResult` | csv_importer.py:249 |
| `import_csv_batch` | `(paths, data_dir, ...) -> CsvImportResult` | csv_importer.py:316 |
| `detect_format` | `(path) -> ImportFormat` | csv_importer.py:86 |
| `validate_ohlcv` | `(df) -> list[str]` | csv_importer.py:161 |
| `fetch_klines` | `(symbol, interval, ...) -> DataFrame` | fetcher.py:9 |
| `update_market_data` | `(symbol, interval, ...) -> DataFrame` | updater.py:18 |
| `find_parquet` | `(data_dir, symbol, tf) -> Path or None` | mtf_loader.py:28 |
| `load_and_prepare_df` | `(data_dir, symbol, tf, ...) -> DataFrame or None` | mtf_loader.py:41 |
| `load_mtf_data` | `(data_dir, symbol, exec_tf, ...) -> Dict[str, DataFrame]` | mtf_loader.py:75 |

## 关键参数

| 参数 | 位置 | 默认值 | 设计意图 |
|------|------|--------|---------|
| `min_bars` | mtf_loader.py:47 | 50 | 最小有效数据条数，避免指标计算不稳定 |
| `history_years` | updater.py:22 | 2 | 首次全量拉取的年数 |
| `mode` | csv_importer.py:36 | MERGE | MERGE=合并去重, REPLACE=覆盖, NEW=新文件 |
| `_TF_ALIASES` | mtf_loader.py:16-25 | -- | 时间周期别名 (1h=[1h,60m], 1d=[1d,1D]) |

## 约定与规则

- **Parquet 命名**: `{SYMBOL}_{TIMEFRAME}.parquet`
- **DataFrame 格式**: DatetimeIndex(UTC) + 列 `open, high, low, close, volume`
- **符号清洗**: `re.sub(r"[^A-Za-z0-9]", "", symbol)`
- **存储引擎**: pyarrow
- **数据验证**: 导入前强制 OHLCV 验证，不通过则 ValueError
