# 多时间周期(MTF)实盘交易实现方案研究报告

## 1. 概述

本报告深入分析主流 Python 量化交易框架在实盘/实时交易中如何处理多时间周期(Multi-Timeframe, MTF)数据，重点关注：
- 高周期数据的刷新策略（是否每秒刷新，或有更智能的策略）
- 形成中的K线(forming bar)在高中周期中的处理方式
- "只在bar收盘时更新"模式的实现
- 代码级别的实现方式

研究涵盖框架：Freqtrade、Jesse Trade、NautilusTrader、vectorbt。

---

## 2. Freqtrade 的 MTF 实盘实现

### 2.1 核心架构：Informative Pairs 机制

Freqtrade 通过 `informative_pairs()` 方法和 `@informative` 装饰器定义额外需要的时间周期数据。

```python
# 方式一：informative_pairs() 方法
def informative_pairs(self):
    pairs = self.dp.current_whitelist()
    informative_pairs = [(pair, '1d') for pair in pairs]
    informative_pairs += [("ETH/USDT", "5m"), ("BTC/TUSD", "15m")]
    return informative_pairs

# 方式二：@informative 装饰器（更简洁）
@informative('1h')
def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
    dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
    return dataframe
```

### 2.2 数据刷新策略：基于时间周期的智能节流

**关键发现：高周期数据不会每秒刷新。** Freqtrade 实现了基于时间周期的智能刷新节流机制。

核心逻辑在 `exchange.py` 的 `_now_is_time_to_refresh()` 方法中：

```python
# freqtrade/exchange/exchange.py
def _now_is_time_to_refresh(self, pair: str, timeframe: str, candle_type: CandleType) -> bool:
    # 将时间周期转换为毫秒数
    interval_in_sec = timeframe_to_msecs(timeframe)
    # 上次刷新时间 + 一个完整时间周期
    plr = self._pairs_last_refresh_time.get((pair, timeframe, candle_type), 0) + interval_in_sec
    # 当前活跃K线的开盘时间
    now = dt_ts(timeframe_to_prev_date(timeframe))
    # 只有当上次刷新已经过期（进入新的K线周期）时才返回True
    return plr < now
```

**工作原理**：
- 对于 1d 时间周期：只有当进入新的一天时才刷新（约每86400秒刷新一次）
- 对于 1h 时间周期：只有当进入新的一小时时才刷新（约每3600秒刷新一次）
- 对于 5m 时间周期：只有当进入新的5分钟K线时才刷新（约每300秒刷新一次）

### 2.3 主交易循环中的数据刷新流程

```python
# freqtrade/freqtradebot.py - process() 主循环
def process(self) -> None:
    # ...
    # 刷新数据：传入白名单交易对 + informative pairs
    self.dataprovider.refresh(
        self.pairlists.create_pair_list(self.active_pair_whitelist),
        self.strategy.gather_informative_pairs(),  # 包含所有MTF数据
    )
    # ...
    self.strategy.analyze(self.active_pair_whitelist)
```

```python
# freqtrade/data/dataprovider.py - refresh() 方法
def refresh(self, pairlist, helping_pairs=None):
    final_pairs = (pairlist + helping_pairs) if helping_pairs else pairlist
    # 所有交易对和所有时间周期一起刷新
    self._exchange.refresh_latest_ohlcv(final_pairs)
```

### 2.4 refresh_latest_ohlcv 的智能分发

```python
# freqtrade/exchange/exchange.py
def _build_ohlcv_dl_jobs(self, pair_list, since_ms, cache):
    input_coroutines = []
    cached_pairs = []

    for pair, timeframe, candle_type in set(pair_list):
        # 三种情况需要下载：
        # 1. 该(pair, timeframe)尚不在缓存中
        # 2. cache=False 强制不使用缓存
        # 3. _now_is_time_to_refresh() 返回True（进入新周期）
        if (
            (pair, timeframe, candle_type) not in self._klines
            or not cache
            or self._now_is_time_to_refresh(pair, timeframe, candle_type)
        ):
            input_coroutines.append(
                self._build_coroutine(pair, timeframe, candle_type, since_ms, cache)
            )
        else:
            # 使用缓存数据，不发起网络请求
            logger.debug(f"Using cached candle data for {pair}, {timeframe}...")
            cached_pairs.append((pair, timeframe, candle_type))

    return input_coroutines, cached_pairs
```

### 2.5 process_only_new_candles：策略层面的K线去重

```python
# freqtrade/strategy/interface.py
class IStrategy:
    process_only_new_candles: bool = True  # 默认开启
    __last_candle_seen_per_pair: dict[str, datetime] = {}

    def _analyze_ticker_internal(self, dataframe, metadata):
        pair = str(metadata.get("pair"))
        # 检查是否是新K线
        new_candle = self.__last_candle_seen_per_pair.get(pair, None) != dataframe.iloc[-1]["date"]

        if not self.process_only_new_candles or new_candle:
            # 只有新K线才执行策略分析
            dataframe = self.analyze_ticker(dataframe, metadata)
            self.__last_candle_seen_per_pair[pair] = dataframe.iloc[-1]["date"]
        else:
            # 跳过已分析过的K线
            logger.debug("Skipping TA Analysis for already analyzed candle")
            dataframe = remove_entry_exit_signals(dataframe)

        return dataframe
```

**注意**：`process_only_new_candles` 只作用于策略主时间周期，不直接控制 informative pairs 的刷新。

### 2.6 merge_informative_pair 与 ffill 机制

```python
# 将高周期数据合并到低周期DataFrame中
dataframe = merge_informative_pair(dataframe, informative, self.timeframe, inf_tf, ffill=True)
```

`ffill=True`(前向填充)确保高周期值在低周期的每一行都可用。例如1d RSI在当天内每根5m K线上都有相同的值，避免"一天只有一次匹配"的问题。

### 2.7 Freqtrade MTF 总结

| 特性 | 实现方式 |
|------|---------|
| 高周期刷新策略 | **按时间周期节流**，1d数据仅在新一天开始时刷新 |
| 形成中K线 | `_ohlcv_partial_candle` 配置控制是否丢弃最后一根不完整K线 |
| 只在收盘时更新 | `_now_is_time_to_refresh` 天然实现此模式 |
| 数据合并 | `merge_informative_pair` + ffill |
| 并发下载 | `asyncio.gather` 并发获取所有需要的数据 |

---

## 3. Jesse Trade 的 MTF 实盘实现

### 3.1 核心架构：1m K线聚合方案

**Jesse 的 MTF 方案与 Freqtrade 有本质区别**：所有高周期K线都从1分钟K线实时聚合生成。

```
数据源(1m K线) -> generate_candle_from_one_minutes() -> 高周期K线
```

### 3.2 K线状态存储

```python
# jesse/store/state_candles.py
class CandlesState:
    def init_storage(self, bucket_size: int = 1000):
        for r in router.all_formatted_routes:
            exchange, symbol = r['exchange'], r['symbol']

            # 为每个交易对初始化1m存储
            key = jh.key(exchange, symbol, '1m')
            self.storage[key] = DynamicNumpyArray((bucket_size, 6))

            # 为每个需要的时间周期初始化更大的存储
            for timeframe in config['app']['considering_timeframes']:
                key = jh.key(exchange, symbol, timeframe)
                total = int((bucket_size / jh.timeframe_to_one_minutes(timeframe)) + 1)
                self.storage[key] = DynamicNumpyArray((total, 6))

    def forming_estimation(self, exchange, symbol, timeframe):
        """计算当前形成中的K线进度"""
        required_1m = jh.timeframe_to_one_minutes(timeframe)
        current_1m_count = len(self.get_storage(exchange, symbol, '1m'))
        dif = current_1m_count % required_1m_to_complete_count
        return dif, long_key, short_key
```

### 3.3 实时K线生成：_generate_bigger_timeframes

```python
# jesse/services/candle_service.py
def _generate_bigger_timeframes(candle, exchange, symbol, with_execution):
    """每收到一根新的1m K线时，重新聚合所有高周期K线"""
    if not jh.is_live():
        return

    for timeframe in config['app']['considering_timeframes']:
        if timeframe == '1m':
            continue

        last_candle = get_current_candle(exchange, symbol, timeframe)
        # 计算需要用多少根1m K线来生成
        generate_from_count = int((candle[0] - last_candle[0]) / 60_000)
        short_candles = get_candles(exchange, symbol, '1m')[-1 - generate_from_count:]

        # 从1m K线聚合生成高周期K线
        generated_candle = generate_candle_from_one_minutes(
            timeframe, short_candles, accept_forming_candles=True
        )

        # 更新高周期K线存储
        add_candle(generated_candle, exchange, symbol, timeframe,
                   with_execution, with_generation=False)
```

### 3.4 get_candles 中的形成中K线处理

```python
def get_candles(exchange, symbol, timeframe):
    if timeframe == '1m':
        return store.candles.get_storage(exchange, symbol, '1m')[:]

    # 计算形成进度
    dif, long_key, short_key = store.candles.forming_estimation(
        exchange, symbol, timeframe
    )

    if dif == 0:
        # 完整K线，直接返回
        return store.candles.storage[long_key][:long_count]
    elif not jh.is_live():
        # 回测模式：生成形成中的K线用于计算
        forming_candle = generate_candle_from_one_minutes(
            timeframe,
            store.candles.storage[short_key][short_count - dif:short_count],
            True
        )
        return existing_candles_arr[:]
    else:
        # 实盘模式：只返回已完成的K线（不含形成中的K线）
        return store.candles.storage[long_key][:long_count]
```

**关键设计决策**：
- **实盘模式：get_candles 不返回形成中的K线** -- 策略看到的高周期数据永远是已收盘的完整K线
- **回测模式：会临时生成形成中K线** 用于指标计算
- **通过 `forming_estimation` 追踪形成进度**：知道当前高周期K线已经走了多少1m K线

### 3.5 从 Trade tick 生成 K 线

```python
def add_candle_from_trade(trade, exchange, symbol):
    """当交易所不提供K线WebSocket时，从逐笔交易生成K线"""
    current_candle = get_current_candle(exchange, symbol, t)
    new_candle = current_candle.copy()
    new_candle[2] = trade['price']                    # close
    new_candle[3] = max(new_candle[3], trade['price']) # high
    new_candle[4] = min(new_candle[4], trade['price']) # low
    new_candle[5] += trade['volume']                   # volume

    add_candle(new_candle, exchange, symbol, t)
```

### 3.6 防止K线缺失的定时器

```python
def generate_new_candles_loop():
    """每秒检查一次，在每分钟的第一秒生成空K线"""
    @t.job(interval=timedelta(seconds=1))
    def time_loop_per_second():
        if jh.now() % 60_000 != 1000:  # 只在每分钟的第1秒执行
            return
        for c in router.all_formatted_routes:
            current_candle = get_current_candle(...)
            # 如果发现缺失的K线，用上一根K线的收盘价生成空K线
            if jh.next_candle_timestamp(current_candle, timeframe) < jh.now():
                new_candle = _generate_empty_candle_from_previous_candle(current_candle)
                add_candle(new_candle, ...)
```

### 3.7 Jesse MTF 总结

| 特性 | 实现方式 |
|------|---------|
| 高周期刷新策略 | **从1m K线实时聚合**，每收到1m K线即更新所有高周期 |
| 形成中K线 | 实盘模式不返回形成中K线；内部通过 `_generate_bigger_timeframes` 实时更新 |
| 只在收盘时更新 | 策略层面天然实现：get_candles在实盘只返回完整K线 |
| 数据源 | WebSocket 或 Trade tick -> 1m K线 -> 聚合高周期 |
| 配置选项 | `env.data.generate_candles_from_1m` 控制是否从1m生成高周期 |

---

## 4. NautilusTrader 的 MTF 实盘实现

### 4.1 核心架构：事件驱动的 Bar 聚合引擎

NautilusTrader 采用完全不同的事件驱动架构，通过 `BarType` 和聚合器(Aggregator)链来处理多时间周期。

### 4.2 BarType 系统

```python
# BarType 格式：INSTRUMENT_ID-AGGREGRATION-PRICE_SOURCE-INTERNAL|EXTERNAL[@SOURCE_BAR_TYPE]

# 基础K线类型
bar_type_1m = BarType.from_str("BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL")

# 内部聚合：从Trade tick聚合
bar_type_internal = BarType.from_str("BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-INTERNAL")

# 聚合链：1m -> 5m -> 1h
intermediate = BarType.from_str("6EH4.XCME-5-MINUTE-LAST-INTERNAL@1-MINUTE-INTERNAL")
hourly = BarType.from_str("6EH4.XCME-1-HOUR-LAST-INTERNAL@5-MINUTE-INTERNAL")
```

- **EXTERNAL**：从交易所直接获取已完成的K线
- **INTERNAL**：引擎内部从tick数据聚合，bar只在收盘时触发一次回调

### 4.3 策略订阅模式

```python
class MyStrategy(Strategy):
    def on_start(self):
        # 定义1m K线
        self.bar_type_1m = BarType.from_str("BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-INTERNAL")
        # 定义1h K线（从1m聚合）
        self.bar_type_1h = BarType.from_str(
            "BTCUSDT-PERP.BINANCE-1-HOUR-LAST-INTERNAL@1-MINUTE-INTERNAL"
        )

        # 订阅历史数据
        self.request_bars(self.bar_type_1m, start=self.clock.utc_now() - timedelta(days=30))
        self.request_bars(self.bar_type_1h, start=self.clock.utc_now() - timedelta(days=30))

        # 订阅实时数据
        self.subscribe_bars(self.bar_type_1m)
        self.subscribe_bars(self.bar_type_1h)

        # 注册指标到特定bar类型，自动更新
        self.register_indicator_for_bars(self.bar_type_1m, self.my_indicator_1m)
        self.register_indicator_for_bars(self.bar_type_1h, self.my_indicator_1h)

    def on_bar(self, bar: Bar):
        # 只在K线收盘时被调用！
        # bar_type 标识是哪个时间周期的K线
        if bar.bar_type == self.bar_type_1m:
            # 处理1m K线
            pass
        elif bar.bar_type == self.bar_type_1h:
            # 处理1h K线
            pass
```

### 4.4 TimeBarAggregator 内部机制

```python
# NautilusTrader 的 Bar 聚合器（Rust实现核心，Python暴露API）
class TimeBarAggregator:
    """
    从tick数据构建时间K线。
    当时间到达下一个时间周期边界时，创建并发送bar到handler。

    关键参数：
    - interval_type: 'left-open' 或 'right-open'
    - timestamp_on_close: True=使用收盘时间戳, False=使用开盘时间戳
    - skip_first_non_full_bar: 跳过不完整的首根K线
    - build_with_no_updates: 即使无更新也构建空K线
    - time_bars_build_delay: 延迟构建（微秒），确保边界数据处理完成
    """
```

### 4.5 聚合链示例

```python
# 完整的聚合链：Tick -> 1m -> 5m -> 1h
#
# TradeTick stream
#     |
#     v
# TimeBarAggregator(1-MINUTE)  -- on_bar 只在每分钟收盘时触发
#     |
#     v
# TimeBarAggregator(5-MINUTE)  -- 从1m bar聚合，只在每5分钟收盘时触发
#     |
#     v
# TimeBarAggregator(1-HOUR)    -- 从5m bar聚合，只在每小时收盘时触发
```

### 4.6 NautilusTrader MTF 总结

| 特性 | 实现方式 |
|------|---------|
| 高周期刷新策略 | **事件驱动**，只有bar收盘时才触发回调 |
| 形成中K线 | **不暴露形成中K线给策略**，on_bar只在收盘时调用 |
| 只在收盘时更新 | **天然实现**，这是核心设计理念 |
| 数据聚合 | 多级Aggregator链，每级聚合只在源bar收盘时更新 |
| 性能 | Rust核心引擎，纳秒级延迟 |
| 适用场景 | 高频交易、对延迟极度敏感的场景 |

---

## 5. vectorbt 的 MTF 处理

### 5.1 定位说明

vectorbt 本质上是一个**回测研究框架**，不是实盘交易引擎。它的设计重心在向量化回测和参数优化，而非实盘执行。

### 5.2 实时数据更新方式

```python
# vectorbt 的 DataUpdater 机制
class MyDataUpdater(vbt.DataUpdater):
    def update(self, count_limit=None):
        prev_index_len = len(self.data.wrapper.index)
        super().update()  # 从数据源拉取新数据
        new_index_len = len(self.data.wrapper.index)

# 定时更新（不适合高频交易）
my_updater = MyDataUpdater(data)
my_updater.update_every(5, 'seconds')  # 每5秒更新
```

### 5.3 vectorbt MTF 总结

| 特性 | 实现方式 |
|------|---------|
| 高周期刷新策略 | **简单定时拉取**，无智能节流 |
| 形成中K线 | **不处理**，依赖数据源 |
| 只在收盘时更新 | **不内置支持** |
| 适用场景 | 研究、回测、信号生成；需自行对接执行层 |

---

## 6. 综合对比与设计模式总结

### 6.1 三种主流 MTF 实盘设计模式

| 模式 | 代表框架 | 核心思路 | 优点 | 缺点 |
|------|---------|---------|------|------|
| **时间周期节流模式** | Freqtrade | 按TF决定刷新频率，1d仅在新一天刷新 | API调用少，资源节省 | 依赖交易所API质量 |
| **1m聚合模式** | Jesse | 统一从1m K线聚合所有高周期 | 数据一致性好，不依赖交易所高周期API | 1m数据量最大，存储成本高 |
| **事件驱动聚合链模式** | NautilusTrader | Tick -> Bar -> Higher Bar，只在收盘时回调 | 延迟最低，逻辑最清晰 | 架构复杂度高 |

### 6.2 关键设计决策对比

#### 高周期数据是否每秒刷新？

| 框架 | 答案 | 机制 |
|------|------|------|
| Freqtrade | **否** | `_now_is_time_to_refresh()` 按 TF 节流 |
| Jesse | **否**（但1m数据可能每秒更新） | 高周期从1m聚合，但只在完整K线时暴露给策略 |
| NautilusTrader | **否** | 事件驱动，只在bar收盘回调 |

#### 形成中的K线如何处理？

| 框架 | 策略 |
|------|------|
| Freqtrade | `_ohlcv_partial_candle` 配置控制是否丢弃最后一根不完整K线；`drop_incomplete` 参数 |
| Jesse | 实盘：**策略不看到形成中K线**；内部：`_generate_bigger_timeframes` 持续更新 |
| NautilusTrader | **on_bar 只在K线收盘时调用**，策略永远不看到形成中的K线 |

#### "只在bar收盘时更新"模式

| 框架 | 实现 |
|------|------|
| Freqtrade | `process_only_new_candles=True`(默认) + `_now_is_time_to_refresh()` 组合实现 |
| Jesse | 天然实现：`get_candles()` 实盘模式下只返回完整K线 |
| NautilusTrader | 天然实现：`on_bar` 回调只在收盘时触发 |

### 6.3 对 MyQuant 框架的设计建议

基于以上研究，建议 MyQuant 框架采用**混合模式**：

#### 方案：时间周期节流 + 事件通知

```
数据管理层（DataFeed）
    |
    +-- 按时间周期注册数据需求
    |   [(BTCUSDT, 5m), (BTCUSDT, 1h), (BTCUSDT, 1d)]
    |
    +-- 智能刷新调度器
    |   - 5m: 每300秒刷新（或新K线时）
    |   - 1h: 每3600秒刷新（或新K线时）
    |   - 1d: 每86400秒刷新（或新K线时）
    |
    +-- K线收盘事件通知
    |   - on_bar_close(pair, timeframe, bar_data)
    |   - 策略只在收到通知时才重新计算
    |
    +-- 形成中K线隔离
        - is_forming 标志
        - 策略默认只使用收盘K线
        - 可选：实时价格更新走单独通道（不影响K线数据）
```

#### 推荐的数据结构设计

```python
class TimeframeData:
    """单个时间周期的数据容器"""
    timeframe: str           # "5m", "1h", "1d"
    last_refresh_ts: int     # 上次刷新时间戳
    refresh_interval: int    # 刷新间隔（秒）
    candles: DataFrame       # K线数据
    is_forming: bool         # 最后一根是否在形成中
    last_complete_bar_ts: int  # 最后一根完整K线的时间戳

    def should_refresh(self, now: int) -> bool:
        """是否需要刷新：基于时间周期节流"""
        bar_open = to_prev_date(self.timeframe, now)
        return self.last_refresh_ts < bar_open

class MTFDataManager:
    """多时间周期数据管理器"""
    _data: dict[tuple[str, str], TimeframeData]  # (pair, tf) -> data

    def register(self, pair: str, timeframe: str):
        """注册需要的数据"""

    def refresh_all(self):
        """只刷新需要更新的数据"""
        for key, tf_data in self._data.items():
            if tf_data.should_refresh(now()):
                self._fetch_and_update(key, tf_data)

    def get_candles(self, pair: str, timeframe: str,
                    include_forming: bool = False) -> DataFrame:
        """获取K线数据，默认排除形成中的K线"""

    def on_bar_close(self, pair: str, timeframe: str,
                     callback: Callable):
        """注册K线收盘回调"""
```

---

## 7. 各框架源码参考

| 框架 | 关键文件 | 功能 |
|------|---------|------|
| Freqtrade | `freqtrade/exchange/exchange.py` | `_now_is_time_to_refresh()`, `_build_ohlcv_dl_jobs()`, `refresh_latest_ohlcv()` |
| Freqtrade | `freqtrade/data/dataprovider.py` | `refresh()`, `get_pair_dataframe()`, `ohlcv()` |
| Freqtrade | `freqtrade/strategy/interface.py` | `process_only_new_candles`, `_analyze_ticker_internal()` |
| Jesse | `jesse/store/state_candles.py` | `forming_estimation()`, K线存储管理 |
| Jesse | `jesse/services/candle_service.py` | `_generate_bigger_timeframes()`, `get_candles()`, `add_candle()` |
| NautilusTrader | Rust核心 + Python绑定 | `TimeBarAggregator`, `BarType`, `subscribe_bars()` |
