# F1: 页面与路由

## 定位

`web/src/pages/` + `web/src/components/layout/` 构成前端路由骨架和 6 个顶级页面。React Router 驱动，Zustand 管理侧边栏状态。

## 文件清单

| 文件 | 职责 |
|------|------|
| `App.tsx` | createBrowserRouter + QueryClientProvider |
| `main.tsx` | createRoot 挂载 |
| `components/layout/AppLayout.tsx` | Sidebar + Header + Outlet + Toaster |
| `components/layout/Sidebar.tsx` | 导航 + 折叠控制 + Header 标题 |
| `pages/Lab.tsx` | 策略实验室 |
| `pages/Evolution.tsx` | 进化中心 |
| `pages/Strategies.tsx` | 策略库 |
| `pages/Trading.tsx` | 模拟交易 (Mock 数据) |
| `pages/Data.tsx` | 数据管理 |
| `pages/Settings.tsx` | 系统设置 |

## 关键链路

### 路由结构 (App.tsx:21-34)

```
createBrowserRouter:
  / -> Navigate to /lab
  /lab -> Lab.tsx
  /evolution -> Evolution.tsx
  /strategies -> Strategies.tsx
  /trading -> Trading.tsx (Mock)
  /data -> Data.tsx
  /settings -> Settings.tsx
所有路由为 AppLayout 子路由
```

### 布局 (AppLayout.tsx:7-26)

左右两栏: Sidebar 固定左侧 + 右侧 Header + `<Outlet />` + Toaster(dark, 360px)。

### 侧边栏 (Sidebar.tsx:43-127)

`useAppStore` 读取 `sidebarCollapsed` 控制宽度 (w-16/w-60)。6 个 NavLink，激活态 `bg-accent-gold/10 + border-l-2`。折叠时用 Tooltip 显示标签。

## 关键机制

### 全局状态持久化

`stores/app.ts:10-24`: Zustand persist 中间件，key `myquant-app`，仅持久化 `sidebarCollapsed`。

### React Query 全局配置

`App.tsx:15-19`: staleTime 30s, retry 1。

## 关键参数

| 参数 | 值 | 说明 |
|------|-----|------|
| QueryClient.staleTime | 30s | 全局 |
| QueryClient.retry | 1 | 全局 |
| Sidebar 折叠宽度 | w-16 (64px) | |
| Sidebar 展开宽度 | w-60 (240px) | |
| AppConfig.init_cash | 100000 | 默认初始资金 |
| AppConfig.max_positions | 1 | 默认最大持仓 |

## 约定与规则

- 页面使用 `export function Xxx()` 模式
- 路由 path 全小写单段
- 统一使用 `<PageTransition>` 包裹 + `flex flex-col gap-4` 布局
- 空数据: `<EmptyState>`，加载: `<Skeleton>`，删除: `<ConfirmDialog variant="destructive">`
- Trading 页面使用硬编码 Mock 数据，未接入 API
