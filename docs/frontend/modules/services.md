# F5: 服务层

## 定位

`web/src/services/` 封装所有后端 REST API 调用。1 个共享 axios 实例 + 6 个领域服务。

## 文件清单

| 文件 | 职责 |
|------|------|
| `api.ts` | Axios 实例工厂 (baseURL from env, 30s timeout) |
| `datasets.ts` | 数据集 CRUD + CSV 导入 + OHLCV + 图表指标 |
| `evolution.ts` | 进化任务 CRUD + 暂停/停止/恢复 + 历史 + 策略 |
| `strategies.ts` | 策略 CRUD + 回测(60s) + 对比 |
| `validation.ts` | 假设验证 + 规则验证 |
| `scene.ts` | 场景类型 + 场景验证 |
| `discovery.ts` | 模式发现 + 相似案例 + 预测 (原生 fetch，非 axios) |

## 关键链路

### 数据适配 (evolution.ts:65)

后端返回 `generations`，前端统一转为 `records` 兼容接口。

### 超时设计

| 操作 | 超时 |
|------|------|
| 默认 | 30s |
| CSV 单文件导入 | 120s |
| CSV 批量导入 | 300s |
| 回测 | 60s |

## 关键机制

### discovery.ts 独立性

使用原生 `fetch` 而非共享 axios 实例。自行定义本地接口类型 (DiscoveryRule, SimilarCase 等)，未使用 types/api.ts。

## 接口清单

| 服务 | 端点 |
|------|------|
| datasets | GET/POST/DELETE datasets, GET ohlcv, GET chart-indicators, GET available-sources |
| evolution | CRUD tasks, pause/stop/resume, GET history, GET strategies, GET discovered |
| strategies | CRUD strategies, POST backtest, POST compare |
| validation | POST validate, POST validate/rules |
| scene | GET scene/types, POST validate/scene |
| discovery | POST patterns, POST similar, POST predict |

## 关键参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| timeout | 30000 | 全局默认 |
| discovery.horizon | 12 | 前向周期 |
| discovery.maxDepth | 5 | 决策树深度 |
| discovery.nNeighbors | 50 | KNN 邻居数 |

## 约定与规则

- 返回 `Promise<T>`，使用 `const { data } = await api.xxx()` 解构
- URL kebab-case: `/api/data/import-batch`
- 命名前缀: get/create/update/delete/run
- discovery.ts 是唯一不用共享 axios 的服务
