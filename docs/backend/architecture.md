# MyQuant 系统架构

## 系统是什么

一个**策略进化工具**：给定交易对（如 BTCUSDT）和时间周期（如 4h），系统用遗传算法自动搜索、评估、优化交易策略，通过回测验证，产出可量化的策略评分。用户不需要编写策略代码——系统从 30 种技术指标、16 种条件类型、8 种信号角色的组合空间中自动探索。

**它不是**：交易机器人（不做实盘）、通用量化平台（只支持单标的回测）、因子研究工具（不做 Alpha 因子挖掘）。

## 为什么这样设计

核心设计约束来自一个问题：**如何在一个 30 指标 x 16 条件 x 8 角色 x 3 层 MTF 的搜索空间中，自动发现有效的交易策略？**

答案是一个三段式架构：

1. **表达**：`StrategyDNA` 把"RSI(14)<30 时做多，RSI(14)>70 时平仓"这样的交易逻辑编码为可序列化、可变异的基因结构
2. **评估**：回测引擎把 DNA 变成带杠杆/资金费率/爆仓检查的真实交易模拟，评分系统把交易结果变成 0-100 的标量分数
3. **搜索**：进化引擎用遗传算法（锦标赛选择 + 功能分区交叉 + 13 种变异算子）在 DNA 空间中搜索高分个体

每个设计决策都服务于这个三段式架构的可行性。

## 架构拓扑

```
                            用户交互层
                    ┌─────────────────────────┐
                    │   React 前端 (6 页面)    │
                    │   WebSocket 实时推送      │
                    └──────────┬──────────────┘
                               │ REST + WS
                    ┌──────────▼──────────────┐
                    │   FastAPI 路由层 (B1)     │
                    │   Pydantic 严格校验       │
                    │   后台线程 (进化)          │
                    └──┬────┬────┬────┬────┬──┘
                       │    │    │    │    │
          ┌────────────┘    │    │    │    └──────────────┐
          ▼                 ▼    │    ▼                   ▼
┌─────────────┐  ┌──────────────┐│ ┌──────────────┐ ┌──────────────┐
│ 数据层 (B2)  │  │ 评分 (B7)    ││ │ 验证 (B8)    │ │ 发现 (B9)    │
│ Parquet CRUD │  │ 10 维打分    ││ │ 假设/场景    │ │ 决策树/KNN   │
│ MTF 加载     │  │ 模板权重     ││ │ 10 种场景    │ │              │
└──────┬──────┘  └──────┬───────┘│ └──────────────┘ └──────────────┘
       │                │        │
       │  ┌─────────────▼────────▼──────────────────────────────┐
       │  │              信号生成层 (B3 + B4)                    │
       ▼  │                                                      │
┌──────────┤  DNA 四层基因 ──> 指标列查找 ──> 条件评估 ──> 布尔信号│
│ 全量指标  │         │                                            │
│ 56 种    │         ▼                                            │
│ 预计算   │  ┌──────────────────────────────────────────┐        │
│          │  │     MTF 共振引擎 (B4.1)                  │        │
│          │  │  层评估(上下文提取) -> 跨层综合(评分) -> 门控│        │
│          │  └──────────────────────────────────────────┘        │
│          └──────────────┬──────────────────────────────────────┘
│                         │ SignalSet
│                         ▼
│               ┌─────────────────────┐
│               │  回测引擎 (B5)       │
│               │  vectorbt + Numba    │
│               │  双向交易 + SL/TP    │
│               │  资金费率 + 爆仓     │
│               └──────────┬──────────┘
│                          │ BacktestResult
│                          ▼
│               ┌─────────────────────┐     ┌─────────────────────┐
│               │  进化引擎 (B6)       │◄───►│   SQLite 持久化      │
│               │  遗传算法 13 变异    │     │   (B10)              │
│               │  自适应 1/5 规则     │     │   5 张表             │
│               │  冠军追踪            │     │   checkpoint 恢复    │
│               └─────────────────────┘     └─────────────────────┘
```

## 模块定义

| 模块 | 定义 | 在系统中的角色 |
|------|------|---------------|
| B1 API 路由 | HTTP 接口层，连接前端和后端业务逻辑 | **边界守卫**：校验输入、管理后台线程、推送实时状态 |
| B2 数据存储 | OHLCV 数据的获取、存储和指标预计算 | **数据源**：所有模块的数据都从这里流入 |
| B3 指标与信号 | 56 种技术指标计算 + 信号构建器 | **翻译器**：把指标数值翻译成布尔交易信号 |
| B4 策略 DNA | 四层基因编码 + 信号转换 + MTF 引擎路由 | **核心类型**：所有模块围绕 StrategyDNA 运转 |
| B4.1 MTF 引擎 | 多时间周期共振评分 + 决策门控 | **上下文增强**：在布尔信号基础上叠加方向/共振/动量评分 |
| B5 回测引擎 | vectorbt 交易模拟 + 风控 + Walk-Forward | **裁判**：用历史数据验证策略的可行性和收益 |
| B6 进化引擎 | 手写遗传算法框架 | **搜索引擎**：在 DNA 空间中自动发现高分策略 |
| B7 评分系统 | 10 维度评分 + 模板权重 + 惩罚机制 | **标尺**：把回测结果变成可比较的标量分数 |
| B8 验证与场景 | 假设验证 + 10 种场景检测 | **预检**：用户手动构建假设时验证逻辑是否成立 |
| B9 规则发现 | 决策树 + KNN 相似案例 | **辅助**：从数据中发现交易规则，非主链路 |
| B10 持久化 | SQLite 5 张表 CRUD + checkpoint | **记忆**：保存进化任务、策略、回测结果 |
| B11 日志 | 统一 logger + 结构化格式 | **可观测性**：所有模块的日志走同一通道 |
| B12 可视化 | Plotly 图表生成 | **展示**：后端生成图表数据，前端渲染 |

## 核心工作流

### 工作流 1：策略进化（系统主链路）

用户点击"开始进化"到策略被发现，系统执行的完整链路：

```
1. 前端 POST /api/evolution/tasks
   payload: {symbol, timeframe, timeframe_pool, leverage, direction, target_score, ...}
      │
2. API 路由 (evolution.py:166)
   ├─ 解析 timeframe_pool, 确定 MTF 模式
   ├─ 生成 initial_dna (如果未提供种子)
   ├─ save_task() 写入 evolution_task 表
   └─ 返回 {task_id, status: "pending"}
      │
3. EvolutionRunner 后台线程 (runner.py:85)
   ├─ 每 2 秒轮询 pending 任务
   └─ 找到后调用 _run_task()
      │
4. 数据准备 (runner.py:152-172)
   ├─ load_and_prepare_df() 加载执行周期 Parquet
   │   └─ compute_all_indicators() 预计算 56 种指标
   ├─ load_mtf_data() 加载额外周期数据 (MTF 模式)
   └─ 产出 dfs_by_timeframe: Dict[str, DataFrame]
      │
5. 进化主循环 (engine.py:232)
   │
   ├─ init_population() 初始化种群 (15 个体)
   │   ├─ 40% 模板突变 (7 种经典策略模板)
   │   ├─ 40% Profile 引导随机
   │   └─ 20% 自由探索
   │
   └─ 逐代循环:
      │
      ├─ 评估: 每个个体走 "DNA -> 信号 -> 回测 -> 评分"
      │   │
      │   ├─ dna_to_signal_set() (executor.py:530)
      │   │   ├─ mtf_mode != None -> run_mtf_engine()
      │   │   │   ├─ evaluate_layer_with_context() (时机 + 上下文)
      │   │   │   ├─ synthesize_cross_layer() (direction/confluence 评分)
      │   │   │   └─ apply_decision_gate() (门控过滤)
      │   │   └─ 否则 -> 旧 AND/OR 路径
      │   │
      │   ├─ BacktestEngine.run() (engine.py:460)
      │   │   ├─ from_order_func() (Numba JIT 交易执行)
      │   │   ├─ _apply_funding_costs() (杠杆费率)
      │   │   └─ _check_liquidation() (爆仓检查)
      │   │
      │   └─ score_strategy() (scorer.py:16)
      │       └─ 10 维度加权评分 -> 总分 0-100
      │
      ├─ 选择: 锦标赛选择 tournsize=3
      ├─ 交叉: 功能分区 (entry from A, exit from B)
      ├─ 变异: random.choices(mutation_pool, n_mutations)
      │   └─ 13 种算子按停滞程度调整权重
      ├─ 新鲜血液: 3-5 个随机个体
      ├─ 多样性维护: 替换重复个体
      │
      └─ 每代回调 (runner.py:209-362):
          ├─ save_history() 记录分数曲线
          ├─ save_snapshot() 保存完整种群
          ├─ ChampionTracker 更新冠军
          ├─ 自动提取 strategy_threshold 以上的策略
          └─ WebSocket 推送 generation_complete
              │
6. 进化完成
   ├─ 保存 champion_dna 到 evolution_task 表
   ├─ WebSocket 推送 evolution_complete
   └─ (连续模式) 保留精英, 开始新一轮种群
```

### 工作流 2：假设验证 -> 保存策略 -> 回测

用户在策略实验室构建假设并验证：

```
1. 前端 POST /api/validate
   payload: {pair, timeframe, when: [...], then: [...]}
      │
2. validate_hypothesis() (validation/engine.py:48)
   ├─ 加载 Parquet + compute_all_indicators()
   ├─ 检测 MTF 条件, 加载高层级数据
   ├─ 逐 bar 评估 WHEN 条件
   ├─ 对每个触发点, 前瞻检查 THEN 条件
   └─ 返回 {match_rate, triggers, distribution, ...}
      │
3. (用户满意后) POST /api/strategies
   payload: {name, dna: {...}, symbol, timeframe}
      │
4. save_strategy() (db_ext.py:237)
   ├─ 计算 gene_signature 去重
   └─ 写入 strategy 表
      │
5. POST /api/strategies/backtest
   payload: {strategy_id} 或 {dna: {...}}
      │
6. backtest_strategy() (strategies.py:186)
   ├─ load_and_prepare_df() 加载数据
   ├─ load_mtf_data() (如果 MTF)
   ├─ dna_to_signal_set() 信号生成
   ├─ BacktestEngine.run() 回测
   ├─ score_strategy() 评分
   └─ 返回 {equity_curve, metrics, score, ...}
```

### 工作流 3：MTF 策略信号生成

MTF 策略从 DNA 到 SignalSet 的完整决策链：

```
输入: StrategyDNA (mtf_mode="direction+confluence")
      + dfs_by_timeframe: {"15m": df_15m, "4h": df_4h, "1d": df_1d}
      │
┌─────▼─────────────────────────────────────────────────────────┐
│ Stage 1: 层评估 + 上下文提取                                    │
│                                                                │
│ 1d 结构层 (role=structure):                                    │
│   evaluate_layer() -> 布尔信号 (entries/exits)                 │
│   extract_context():                                           │
│     - EMA + price_above -> direction = +1/-1                  │
│     - EMA 输出列 -> price_levels = [ema_series]               │
│   resample_values() ffill 到 15m 索引                          │
│   -> LayerResult(signal_set, direction=+1, price_levels=[...]) │
│                                                                │
│ 4h 判断层 (role=zone):                                         │
│   evaluate_layer() -> 布尔信号                                 │
│   extract_context():                                           │
│     - BB 输出列 -> price_levels = [upper, middle, lower]       │
│   resample_values() ffill 到 15m 索引                          │
│   -> LayerResult(signal_set, price_levels=[upper,mid,lower])   │
│                                                                │
│ 15m 执行层 (role=execution):                                   │
│   evaluate_layer() -> 布尔信号                                 │
│   -> LayerResult(signal_set, momentum=rsi_series)              │
└───────────────────────┬───────────────────────────────────────┘
                        │
┌───────────────────────▼───────────────────────────────────────┐
│ 信号组合: _build_exec_signal_set()                              │
│   entries = 1d_entries AND 4h_entries AND 15m_entries          │
│   exits = 1d_exits OR 4h_exits OR 15m_exits                    │
│   -> SignalSet(entries, exits, adds, reduces)                   │
│                                                                  │
│   已知问题: 扁平 AND 不区分 state/pulse 信号                     │
└───────────────────────┬───────────────────────────────────────┘
                        │
┌───────────────────────▼───────────────────────────────────────┐
│ Stage 2: 跨层综合 synthesize_cross_layer()                     │
│                                                                  │
│ direction_score:                                                │
│   结构层 direction 合并, 最高周期优先                            │
│   -> pd.Series (+1 做多 / -1 做空 / 0 中性)                    │
│                                                                  │
│ confluence_score:                                               │
│   对每根 bar:                                                   │
│   1. s% = (ATR / close) * proximity_mult                       │
│   2. 构建 1d EMA 价格区间 [P*(1-s%), P*(1+s%)]                 │
│   3. 构建 4h BB 价格区间 (3 条轨道)                             │
│   4. 各层区间内部合并 -> 层间区间取交集                           │
│   5. 评分 = 交集宽度 / max_zone_width                           │
│   -> pd.Series (0.0 ~ 1.0)                                     │
│                                                                  │
│ momentum_score:                                                 │
│   各层动量均值 + sigmoid 归一化 -> pd.Series (0.0 ~ 1.0)        │
│                                                                  │
│ -> MTFSynthesis(direction, confluence, momentum, strength)      │
└───────────────────────┬───────────────────────────────────────┘
                        │
┌───────────────────────▼───────────────────────────────────────┐
│ Stage 3: 决策门控 apply_decision_gate()                        │
│                                                                  │
│ mtf_mode = "direction+confluence":                              │
│   entry = timing_signal                                        │
│         AND direction_score 与 direction 匹配                    │
│         AND confluence_score >= threshold (0.3)                  │
│                                                                  │
│   exit = timing_signal (不过滤 -- 风控优先)                      │
│   add = timing_signal AND confluence >= threshold * 0.8          │
│   reduce = timing_signal (不过滤)                                │
│                                                                  │
│ -> 最终 SignalSet(entries, exits, adds, reduces,                │
│                   entry_direction, mtf_diagnostics)              │
└──────────────────────────────────────────────────────────────┘
```

## 设计约束

| 约束 | 原因 | 影响 |
|------|------|------|
| 全量指标预计算 | 避免在进化循环中按需计算的开销，一次计算 56 种指标供所有策略共用 | 每个 DataFrame 内存占用大（100+ 列），MTF 每个周期各一份 |
| Numba JIT 交易执行 | Python 循环逐 bar 交易太慢，Numba 编译后接近 C 速度 | `order_func_nb` 签名不可随意修改（破坏编译缓存），不支持 Python 对象 |
| 同步 API handler | 回测/进化是 CPU 密集型，async 无收益 | 进化跑在独立后台线程，避免阻塞 HTTP 请求 |
| Pydantic extra="forbid" | 防止前端传多余字段导致隐式 bug | 前后端字段必须严格对齐，升级接口时需同步更新 schema |
| 信号延迟 1 bar | 防止前瞻偏差 | entry/exit/add/reduce 信号全部 shift(1) 后才传给回测引擎 |
| exit 不受 confluence 限制 | 止损是风控底线，不应被市场结构状态阻挡 | MTF 门控对 exit/reduce 信号是透明的 |
| 爆仓模型是简化版 | 真实交易所保证金计算太复杂 | leverage=10 时 9% 亏损就"爆仓"，比真实交易所更严格 |

## 能力边界

### 系统能做的

- 在 30 指标 x 16 条件 x 8 角色 x 3 层 MTF 的组合空间中自动搜索策略
- 支持做多/做空/双向三种方向
- 支持杠杆（1x-10x）和资金费率模拟
- 支持 Walk-Forward 交叉验证评估过拟合
- 支持多时间周期（structure/zone/execution 三层）策略进化
- 支持假设验证（用户手动构建 WHEN/THEN 规则）
- 支持 10 种场景验证（均值回归/突破/支撑阻力等）

### 系统不能做的

- **不做实盘交易**：Trading 页面是 Mock 数据，无交易对接
- **不做跨标的策略**：每个策略只绑定一个交易对
- **不做高频策略**：最小周期 1m，无订单簿数据
- **不做因子研究**：不支持 Alpha 因子挖掘和因子组合
- **MTF 引擎已知限制**：`_build_exec_signal_set` 用扁平 AND 组合 state 和 pulse 信号（应改为 gate+trigger 模式）；动量 confluence 用 `> 0` 判断方向，对 RSI 等有界指标不正确（应用 `> 50`）
- **进化搜索的局限**：种群默认 15 个体，搜索空间有限；没有岛屿模型或协同进化

## 数据库模型

```
evolution_task (1) ──> (N) generation_snapshot  [task_id]
       │
       ├─────────────> (N) evolution_history    [task_id]
       │
       └─────────────> (N) strategy             [source_task_id, 逻辑外键]

strategy (1) ──> (N) backtest_result            [strategy_id, 物理外键 CASCADE]

dataset_meta                                      [独立表, Parquet 文件元数据]
```

## 技术选型动机

| 选型 | 为什么选它 | 不选什么 |
|------|-----------|---------|
| vectorbt | 向量化回测，比事件驱动快 100x | Backtrader/Zipline（太慢，不适合进化循环中每代 15 次回测） |
| Numba JIT | 交易执行逻辑需要逐 bar 循环，纯 Python 太慢 | 纯 Python 循环（进化每代 15x200bars = 3000 次 bar 循环） |
| 手写遗传算法 | 需要细粒度控制变异算子、MTF 层变异、自适应权重 | deap（太通用，MTF 变异难以集成） |
| Zustand | 前端状态管理轻量，不需要 Redux 的中间件复杂度 | Redux（对 3 个 store 来说太重） |
| react-query | 服务端数据缓存/重验证/乐观更新自动化 | 手写 useEffect + useState 数据获取 |
| SQLite | 单用户桌面工具，不需要分布式数据库 | PostgreSQL（增加部署复杂度，无收益） |
| Parquet | 列式存储，读 OHLCV + 100 指标列时高效 | CSV（太慢，体积大） |
