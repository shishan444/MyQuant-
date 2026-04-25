# MyQuant 工程文档

## 一句话

BTC/ETH 量化交易策略进化工具 -- 用手写遗传算法自动发现、评估、优化多时间周期交易策略，前端提供进化中心、策略实验室、策略库等交互界面。

## 技术栈

- **后端**: Python 3.12 / FastAPI / SQLite / vectorbt / pandas / Numba JIT
- **前端**: React 19 / TypeScript / Vite / Tailwind CSS 4 / Zustand / react-query / lightweight-charts (TradingView K 线)
- **数据**: Parquet 文件存储 OHLCV 数据，SQLite 存储策略/回测结果/进化任务

## 模块地图

### 后端 (`api/` + `core/`)

| # | 模块 | 路径 | 职责 | 置信度 | 状态 |
|---|------|------|------|--------|------|
| B1 | API 入口与路由 | `api/` (15 files) | FastAPI 应用、CORS、路由挂载、Pydantic schema、WebSocket 推送、进化后台线程 | 高 | 已完成 2026-04-23 |
| B2 | 数据存储与加载 | `core/data/` (6 files) | Parquet 读写、CSV 导入、Binance 数据拉取、多时间周期数据加载与指标预计算 | 高 | 已完成 2026-04-25 |
| B3 | 技术指标与信号 | `core/features/` + `core/features/patterns/` (8 files) | 56 个指标统一计算引擎、蜡烛图形态识别（10+ 种）、信号构建器（DNA->交易信号）、指标注册表 | 高 | 已完成 2026-04-23 |
| B4 | 策略 DNA | `core/strategy/` (4 files) | 策略基因编码（四层基因 + 三角色系统 + MTF 控制参数）、DNA->信号转换（双路由）、多时间周期多层 DNA 支持、双向交易 | 高 | 已完成 2026-04-25 |
| B4.1 | MTF 共振引擎 | `core/strategy/mtf_engine.py` (789 行) | 双轨道三阶段管线：层评估+上下文提取、跨层综合（direction/confluence/momentum评分）、决策门控 | 高 | 已完成 2026-04-25 |
| B5 | 回测引擎 | `core/backtest/` (3 files) | vectorbt from_order_func 回测执行、双向交易（long/short/mixed）、Walk-Forward 验证、杠杆/做空/资金费率处理 | 高 | 已完成 2026-04-25 |
| B6 | 进化引擎 | `core/evolution/` (7 files) | 手写遗传算法框架：种群管理、6+7 变异算子、锦标赛选择、自适应 1/5 规则、MTF 层感知多样性维护、冠军追踪、血统记录 | 高 | 已完成 2026-04-25 |
| B7 | 评分系统 | `core/scoring/` (5 files) | 多维度策略评分（收益/风险/稳定性/效率）、归一化、评分模板（收益优先/风险优先/均衡） | 高 | 已完成 2026-04-23 |
| B8 | 验证与场景 | `core/validation/` + `core/validation/scene/` (16 files) | 假设验证引擎、规则条件评估、10 种场景验证（均值回归/突破/支撑阻力/跨周期/成交量异动等） | 中 | 已完成 2026-04-23 |
| B9 | 规则发现 | `core/discovery/` (7 files) | 决策树策略发现、KNN 相似案例检索、标签生成、统计验证、特征编码 | 中 | 已完成 2026-04-23 |
| B10 | 持久化 | `core/persistence/` (3 files) | SQLite 3 张表 CRUD、checkpoint 快照恢复（evolution_task/generation_snapshot/evolution_history） | 高 | 已完成 2026-04-23 |
| B11 | 日志 | `core/logging/` (3 files) | 统一 logger 工厂 + AIFormatter 结构化格式化器（所有 tag 写同一文件） | 高 | 已完成 2026-04-23 |
| B12 | 可视化 | `core/visualization/` (6 files) | Plotly 图表编排器（K 线+信号/权益曲线/代际进度/vectorbt 预览） | 中 | 已完成 2026-04-23 |

### 前端 (`web/src/`)

| # | 模块 | 路径 | 职责 | 置信度 | 状态 |
|---|------|------|------|--------|------|
| F1 | 页面与路由 | `pages/` (6 files) + `components/layout/` (2 files) | 6 个顶级页面（Lab/Evolution/Strategies/Trading/Data/Settings）+ React Router + 侧边栏导航 | 高 | 已完成 2026-04-25 |
| F2 | 进化中心 UI | `components/evolution/` (12 files) | 自动探索配置、种子探索配置、进度面板、评分趋势图、策略列表、历史任务表、任务详情抽屉 | 高 | 已完成 2026-04-23 |
| F3 | 策略实验室 UI | `components/lab/` (23 files) | 三个模式面板：假设验证（规则构建器）、策略回测（forwardRef + useImperativeHandle 暴露 runBacktest）、场景验证；辅助组件 | 高 | 已完成 2026-04-23 |
| F4 | 图表组件 | `components/charts/` (5 files) | TradingView lightweight-charts K 线图封装、标注层（买卖信号/止损线）、图例、工具栏 | 高 | 已完成 2026-04-23 |
| F5 | 服务层 | `services/` (7 files) | Axios 单例（30s 全局超时，回测 60s 独立超时）、REST API 封装（strategies/evolution/datasets/validation/scene/discovery） | 高 | 已完成 2026-04-25 |
| F6 | 状态管理 | `stores/` (3 files) + `hooks/` (7 files) | Zustand stores（app/chart-settings/lab）、react-query hooks（含 WebSocket 实时更新） | 高 | 已完成 2026-04-25 |
| F7 | 类型与工具 | `types/` (4 files) + `lib/` (4 files) + `utils/` (1 file) | 35+ API 类型定义、全局常量（指标/时间周期/条件类型）、DNA 生成器、格式化工具 | 高 | 已完成 2026-04-25 |

## 需要确认的结构性问题

1. `core/visualization/` 有 6 个 Plotly 图表文件，但前端用的是 lightweight-charts 和 recharts。后端 visualization 模块是否还在使用？（推断：仍用于后端 API 返回图表数据）
2. `core/discovery/` 的决策树和 KNN 发现引擎 -- 前端 discovery 服务使用原生 fetch 而非共享 axios 实例，是否有意为之？
3. `web/src/pages/Trading.tsx` 模拟交易页面 -- 当前使用 Mock 数据，未对接真实交易
