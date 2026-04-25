# F1: 页面与路由

## 定位

`web/src/pages/` + `web/src/components/layout/` 构成前端的路由骨架和 6 个顶级页面。React Router 驱动，Zustand 管理侧边栏状态。

## 路由配置 (App.tsx)

使用 `createBrowserRouter`，所有页面嵌套在 `AppLayout` 下：

| 路径 | 组件 | 说明 |
|------|------|------|
| `/` | Navigate -> `/lab` | 默认跳转到策略实验室 |
| `/lab` | Lab | 策略实验室（假设验证/回测/场景） |
| `/evolution` | Evolution | 进化中心 |
| `/strategies` | Strategies | 策略库 |
| `/trading` | Trading | 模拟交易 |
| `/data` | DataManagement | 数据管理 |
| `/settings` | Settings | 设置 |

`QueryClientProvider` 配置：staleTime=30s, retry=1。

## 布局 (AppLayout + Sidebar)

`AppLayout`: Flex 布局 -- Sidebar + Header + main(Outlet)。

`Sidebar` (147 行):
- 6 个导航项：策略实验室/进化中心/策略库/模拟交易/数据管理/设置
- 状态管理：`useAppStore` (Zustand, persisted) 控制折叠/展开
- 折叠模式：仅显示图标 + tooltip
- 活跃链接金色高亮

`Header`：显示当前页面标题（从 `getPageTitle()` 映射）。

## 页面详情

### Lab (1087 行)

最复杂的前端页面，三个模式切换：

**假设验证模式**：
- 规则构建器：entry/exit 条件组（`RuleConditionGroup`）
- 调用 `useValidateRules` 验证
- KlineChart 展示买卖信号标注
- 保存为策略

**回测模式**：
- 策略选择器（从策略库）
- 数据源配置（symbol/timeframe/日期范围）
- 高级参数（leverage/fee/slippage/init_cash）
- 委托 `BacktestModePanel` 执行

**场景模式**：
- 委托 `SceneModePanel`

通用功能：
- 从 Evolution 页面通过 route state 接收 seed DNA
- 动态 symbol/timeframe 选项（从 `useAvailableSources` 获取）
- 快捷日期范围（3m/6m/1y/YTD/全部）

### Evolution (631 行)

两种探索模式：
- **自动模式**：`AutoConfigForm` 全自动配置
- **种子模式**：从 Lab 页面传入的 DNA 作为种子

5 个区域：
1. 配置面板（可折叠，auto/seed form）
2. 进度面板 + 评分趋势图（`ScoreTrendChart`）
3. 发现策略列表（seed evolve/save/backtest 按钮）
4. 算法变异日志（`AlgorithmLog`）
5. 历史任务表（`HistoryTable`）

实时更新：`useEvolutionWebSocket` 订阅 `/ws/evolution/{taskId}`，处理 4 种消息类型（population_started/strategy_discovered/generation_complete/evolution_complete），2 秒 debounce 批量刷新缓存。

### Strategies (325 行)

策略库列表：
- 搜索（name/symbol/ID）
- 按来源筛选（lab/evolution/import）
- 收藏切换（本地 state，未持久化）
- 删除确认
- 展示：名称、收益率、Sharpe、symbol/timeframe、日期、参数摘要

### DataManagement (583 行)

数据集管理：
- 数据集列表（搜索/筛选 symbol 或 interval）
- CSV 上传对话框（单个 + 批量），文件名自动解析 symbol/interval
- 质量状态条（complete/warning/error/unknown）
- 删除确认

### Trading (402 行)

**当前使用 Mock 数据**（MOCK_RUNNING_STRATEGIES, MOCK_POSITIONS），未对接真实交易：
- 投资组合统计（初始资金/当前总值/总回报/vs BTC）
- 运行中策略卡片（持仓标记 long/short/flat）
- 持仓明细表

### Settings (603 行)

4 个标签页：
- 通用：语言/时区/通知
- Binance API：密钥配置 + 测试连接
- 交易：初始资金/手续费率/最大持仓数
- 指标：EMA 列表（增删改周期颜色）、BOLL/RSI/VOL 配置

保存通过 `api.put("/api/config")` 和 `api.put("/api/config/chart_indicators")`。

## 涉及文件

| 文件 | 行数 | 核心内容 |
|------|------|---------|
| `web/src/App.tsx` | 43 | 路由配置 + QueryClientProvider |
| `web/src/pages/Lab.tsx` | 1087 | 策略实验室三模式 |
| `web/src/pages/Evolution.tsx` | 631 | 进化中心 |
| `web/src/pages/Strategies.tsx` | 325 | 策略库 |
| `web/src/pages/DataManagement.tsx` | 583 | 数据管理 |
| `web/src/pages/Trading.tsx` | 402 | 模拟交易（Mock） |
| `web/src/pages/Settings.tsx` | 603 | 设置页面 |
| `web/src/components/layout/AppLayout.tsx` | 27 | 全局布局 |
| `web/src/components/layout/Sidebar.tsx` | 147 | 侧边栏导航 |
