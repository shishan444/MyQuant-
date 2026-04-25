# B2: 数据存储与加载

## 定位

`core/data/` 负责 OHLCV K 线数据的获取、存储和加载。是回测引擎和进化引擎的数据入口——所有数据都从这里流入系统。

## 文件职责

| 文件 | 行数 | 职责 |
|------|------|------|
| `storage.py` | 46 | Parquet 文件 CRUD：save / load / merge / get_latest_timestamp |
| `mtf_loader.py` | 115 | 多时间周期数据加载：单周期 + 指标预计算 + MTF 扩展 |
| `fetcher.py` | 63 | 从 Binance API 拉取历史 K 线 |
| `updater.py` | 81 | 增量更新：检查本地最新时间戳，只拉取缺失数据 |
| `csv_importer.py` | 408 | CSV 导入：格式自动检测、时间戳精度识别、OHLCV 校验、批量导入 |
| `__init__.py` | 空 | 无导出 |

## 存储层: storage.py

极简的 Parquet 文件操作，用 pyarrow 引擎。

文件命名约定: `{SYMBOL}_{TIMEFRAME}.parquet`（如 `BTCUSDT_4h.parquet`），存放在 `data/market/` 目录。这个约定被 mtf_loader、updater、csv_importer 三处共同依赖。

`merge_parquet()` 的去重策略: `pd.concat` → `index.duplicated(keep="last")` → `sort_index`。新数据覆盖旧数据的同时间戳行。

## 数据加载: mtf_loader.py

### 文件查找: find_parquet()

直接路径拼接 `{data_dir}/{symbol}_{timeframe}.parquet`，找不到时尝试别名：

| 时间周期 | 别名 |
|----------|------|
| 1h | 60m |
| 1d | 1D |

其余周期没有别名。symbol 名会经过 `re.sub(r"[^A-Za-z0-9]", "", symbol)` 清洗——去掉所有非字母数字字符。

### load_and_prepare_df(): 单周期加载

```
find_parquet(data_dir, symbol, timeframe)
  ↓ load_parquet
  ↓ 按 data_start/data_end 切片
  ↓ 检查 min_bars (默认 50)
  ↓
compute_all_indicators(df)  ← B3 模块，全量 56 种指标预计算
  ↓
返回 enhanced_df (100+ 列)
```

这个函数被回测 API 和进化 runner 调用，是系统的数据主入口。

### load_mtf_data(): MTF 扩展加载

在已有执行周期 DataFrame 的基础上，加载 DNA 需要的其他时间周期数据。每个额外周期都独立做一次 `compute_all_indicators()`。

返回 `Dict[str, pd.DataFrame]`（key = 时间周期）。如果只成功加载了执行周期本身（没有额外周期），返回 None。

**静默失败**: 加载异常被 `except Exception: continue` 跳过。MTF 策略的部分时间周期数据缺失不会报错，只是缺失周期的信号无法计算。

## Binance 数据拉取: fetcher.py

封装 `binance.client.Client.get_historical_klines()`，返回标准化 DataFrame（DatetimeIndex UTC, columns: OHLCV + trades）。

默认拉取 2 年历史。不需要 API key 就能用（Binance 公开端点）。

## 增量更新: updater.py

```
get_latest_timestamp(path)
  ↓
  ├─ None → 全量拉取 (history_years 年)
  └─ 有值 → 从 latest_ts 开始增量拉取
  ↓
merge (concat + dedup + sort)
  ↓
save_parquet
```

`update_market_data()` 是前端"数据管理"页面的"更新数据"按钮的后端实现。

## CSV 导入: csv_importer.py

### 格式自动检测

| 格式 | 判定条件 |
|------|----------|
| BINANCE_OFFICIAL | 无 header，12 列，第一列是数字 |
| GENERIC_OHLCV | 有 header，列名可识别 |

### 时间戳精度

13 位 → 毫秒 (ms)，16 位 → 微秒 (us)。小于 10 位抛异常。

### 文件名解析

正则 `{SYMBOL}-{INTERVAL}-*.csv`（如 `BTCUSDT-4h-2025-01.csv`）。symbol 和 interval 可以显式传入覆盖自动检测。

### OHLCV 校验

导入前自动校验: NaN 检查、high >= max(O,C,L)、low <= min(O,C,H)、volume >= 0。校验失败直接抛 ValueError。

### 导入模式

| 模式 | 行为 |
|------|------|
| MERGE | 与已有 Parquet 合并（去重） |
| REPLACE | 覆盖已有 Parquet |
| NEW | 文件不存在时创建，等价于 REPLACE |

### 批量导入

`import_csv_batch()` 读取多个 CSV，concat → dedup → sort → 写入单个 Parquet。从第一个文件检测 metadata。

## 数据流

```
外部数据源:
  ├─ Binance API (fetcher.py) → update_market_data(updater.py) → Parquet
  ├─ CSV 文件 (csv_importer.py) → Parquet
  └─ 直接 Parquet 文件
      ↓
storage.load_parquet()
      ↓
mtf_loader.load_and_prepare_df()
  ├─ find_parquet → 文件查找（含别名）
  ├─ load_parquet → 读取
  ├─ 日期切片 + min_bars 检查
  └─ compute_all_indicators → 全量指标预计算
      ↓
enhanced_df → 回测引擎 / 进化引擎
      ↓
(可选) load_mtf_data() → 额外周期 enhanced_df
```

## 涉及文件

| 文件 | 核心内容 |
|------|---------|
| `core/data/storage.py` | Parquet CRUD |
| `core/data/mtf_loader.py` | 单周期 + MTF 数据加载与指标预计算 |
| `core/data/fetcher.py` | Binance K 线拉取 |
| `core/data/updater.py` | 增量更新 |
| `core/data/csv_importer.py` | CSV 导入（格式检测、校验、批量） |
