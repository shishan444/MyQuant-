# F5: 服务层

## 定位

`web/src/services/` 封装所有后端 REST API 调用。共 7 个文件，1 个共享 axios 实例 + 6 个领域服务。

## 共享 Axios 实例 (api.ts)

```typescript
baseURL: VITE_API_BASE_URL || ""
timeout: 30000ms  // 全局 30s
transformRequest: FormData 去除 Content-Type, JSON 对象 JSON.stringify
```

响应拦截器：从 `response.data.detail` 或 `error.message` 提取错误信息。

## 领域服务

### strategies.ts (79 行)

| 函数 | 方法 | 端点 | 超时 |
|------|------|------|------|
| getStrategies(params?) | GET | /api/strategies | 30s |
| getStrategy(id) | GET | /api/strategies/{id} | 30s |
| createStrategy(payload) | POST | /api/strategies | 30s |
| updateStrategy(id, payload) | PUT | /api/strategies/{id} | 30s |
| deleteStrategy(id) | DELETE | /api/strategies/{id} | 30s |
| runBacktest(payload) | POST | /api/strategies/backtest | **60s** |
| compareStrategies(payload) | POST | /api/strategies/compare | 30s |

回测接口独立 60s 超时（计算密集）。

### evolution.ts (95 行)

| 函数 | 方法 | 端点 |
|------|------|------|
| getEvolutionTasks(params?) | GET | /api/evolution/tasks |
| getEvolutionTask(id) | GET | /api/evolution/tasks/{id} |
| createEvolutionTask(payload) | POST | /api/evolution/tasks |
| pauseEvolutionTask(id) | POST | /api/evolution/tasks/{id}/pause |
| stopEvolutionTask(id) | POST | /api/evolution/tasks/{id}/stop |
| resumeEvolutionTask(id) | POST | /api/evolution/tasks/{id}/resume |
| getEvolutionHistory(id, params?) | GET | /api/evolution/tasks/{id}/history |
| getTaskStrategies(taskId) | GET | /api/evolution/tasks/{taskId}/strategies |
| getDiscoveredStrategies(taskId?, params?) | GET | /api/evolution/tasks/{taskId}/discovered-strategies |
| getAllDiscoveredStrategies(params?) | GET | /api/evolution/strategies |

`getEvolutionHistory` 内部将后端的 `generations` 字段重命名为 `records`。

### datasets.ts (106 行)

| 函数 | 方法 | 端点 | 超时 |
|------|------|------|------|
| getDatasets(params?) | GET | /api/data/datasets | 30s |
| getDataset(id) | GET | /api/data/datasets/{id} | 30s |
| importCsv(formData) | POST | /api/data/import | **120s** |
| importCsvBatch(formData) | POST | /api/data/import-batch | **300s** |
| deleteDataset(id) | DELETE | /api/data/datasets/{id} | 30s |
| getOhlcv(id, params?) | GET | /api/data/datasets/{id}/ohlcv | 30s |
| getDatasetPreview(id, params?) | GET | /api/data/datasets/{id}/preview | 30s |
| getAvailableSources() | GET | /api/data/available-sources | 30s |
| getOhlcvBySymbol(symbol, tf, params?) | GET | /api/data/ohlcv/{symbol}/{tf} | 30s |
| getChartIndicators(symbol, tf, params?) | GET | /api/data/chart-indicators/{symbol}/{tf} | 30s |

CSV 导入超时显著增加：单文件 120s，批量 300s。

### discovery.ts (125 行)

| 函数 | 方法 | 端点 |
|------|------|------|
| discoverPatterns(params) | POST | /api/discovery/patterns |
| findSimilar(params) | POST | /api/discovery/similar |
| predictRange(params) | POST | /api/discovery/predict |

注意：使用原生 `fetch()` 而非共享 axios 实例。

接口定义在文件内：`DiscoveryRule`（条件/置信度/提升度）、`SimilarCase`（距离/未来收益）、`PredictResponse`（预测方向/范围/置信度）。

### validation.ts (17 行)

| 函数 | 方法 | 端点 |
|------|------|------|
| validateHypothesis(payload) | POST | /api/validate |
| validateRules(payload) | POST | /api/validate/rules |

### scene.ts (20 行)

| 函数 | 方法 | 端点 |
|------|------|------|
| getSceneTypes() | GET | /api/scene/types |
| verifyScene(payload) | POST | /api/validate/scene |

## 涉及文件

| 文件 | 行数 | 核心内容 |
|------|------|---------|
| `web/src/services/api.ts` | 32 | 共享 axios 实例 |
| `web/src/services/strategies.ts` | 79 | 策略 CRUD + 回测 |
| `web/src/services/evolution.ts` | 95 | 进化任务 CRUD + WebSocket |
| `web/src/services/datasets.ts` | 106 | 数据集 CRUD + CSV 导入 |
| `web/src/services/discovery.ts` | 125 | 模式发现 + 相似案例 + 预测 |
| `web/src/services/validation.ts` | 17 | 假设/规则验证 |
| `web/src/services/scene.ts` | 20 | 场景验证 |
