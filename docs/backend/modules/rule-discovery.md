# B9: 规则发现

## 定位

`core/discovery/` 用决策树和 KNN 从历史数据中发现指标状态与价格方向的映射关系。非主链路模块，是前端"数据管理"页面中模式发现和相似案例功能的后端支撑。

## 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `feature_encoder.py` | 110 | 特征选择 + MinMaxScaler 归一化 |
| `tree_engine.py` | 132 | 决策树规则发现引擎 |
| `knn_engine.py` | 188 | KNN 相似案例检索 |
| `label_generator.py` | 62 | 前向收益标签生成 |
| `rule_extractor.py` | 102 | 决策树 -> 可解释规则 |
| `stat_validator.py` | 161 | Wilson 置信区间 + 规则提升验证 |

## 关键链路

### 决策树管道

```
tree_engine.py:44 PatternDiscoveryEngine.discover(df)
  L55  generate_labels(df, horizon=12) -> UP/DOWN/FLAT
  L58  encoder.fit_transform(df) -> ~20维特征矩阵
  L75-94  TimeSeriesSplit(n_splits=3) 3折交叉验证
  L97-109  DecisionTreeClassifier(max_depth=5, min_samples_leaf=50)
           仅 UP/DOWN 样本训练（排除 FLAT）
  L114  extract_rules(clf, feature_names, max_rules=10)
```

### KNN 管道

```
knn_engine.py:60 SimilarCaseEngine.fit(df)
  L67  encoder.fit_transform(df) 构建特征矩阵
  L79-83  预计算 future_returns/highs/lows
  L86-95  NearestNeighbors(n_neighbors=50, metric="euclidean")

knn_engine.py:134 predict(current_features)
  L159-165  方向判断: >60% positive=UP, <40%=DOWN
  置信度 = |positive_pct - 0.5| * 2
```

## 关键机制

### 特征选择 (feature_encoder.py:47-109)

按类别选最多 20 个指标列: RSI(1), EMA(最多3), MACD histogram(1), BB pct+bandwidth(2), ATR(1), RVOL(1), ADX(1), Stoch(1), CCI(1), MFI(1), Pattern(最多4)。MinMaxScaler 归一化到 [0,1]。

### 标签生成 (label_generator.py:13)

前向收益: >1% -> UP, <-1% -> DOWN, 其余 -> FLAT。

### Wilson 置信区间 (stat_validator.py:18)

小样本比例的稳健置信区间。z=1.96 (95%)。用于条件概率表。

### 规则提升 (stat_validator.py:112)

lift = P(target|conditions) / P(target)。> 1.2 表示比随机好 20%。最少 10 个匹配样本。

## 接口定义

| 函数 | 说明 |
|------|------|
| `PatternDiscoveryEngine.discover(df, target) -> DiscoveryResult` | 决策树发现 |
| `SimilarCaseEngine.fit(df) -> self` | KNN 拟合 |
| `SimilarCaseEngine.predict(features) -> PredictionResult` | KNN 预测 |
| `generate_labels(df, horizon, up_thresh, down_thresh) -> DataFrame` | 标签生成 |
| `extract_rules(clf, feature_names, max_rules) -> List[RuleItem]` | 规则提取 |
| `wilson_confidence(successes, total, z) -> (low, high)` | Wilson 区间 |
| `validate_rule_lift(df, conditions, target) -> float` | 提升验证 |

## 关键参数

| 参数 | 默认值 | 设计意图 |
|------|--------|---------|
| max_depth | 5 | 限制树深保持可解释性 |
| min_samples_leaf | 50 | 防止过拟合稀疏模式 |
| horizon | 12 | 前向周期 (4h K线=2天) |
| up_threshold | 0.01 | UP 标签最小 1% 收益 |
| lift filter | 1.2 | 比随机好 20% |
| n_neighbors | 50 | KNN 邻居数 |
| direction threshold | 0.6/0.4 | UP/DOWN 判定边界 |

## 约定与规则

- **仅二分类**: 决策树只训练 UP/DOWN（排除 FLAT）
- **时间序列 CV**: TimeSeriesSplit 防止未来数据泄漏
- **MinMaxScaler**: 统一 [0,1] 归一化
- **规则条件格式**: `{feature, operator: "le"|"gt", threshold}`
- **KNN 邻居上限**: predict() 最多返回 20 个 similar_cases
