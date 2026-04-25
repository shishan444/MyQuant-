# B9: 规则发现

## 定位

`core/discovery/` 用决策树和 KNN 从历史数据中发现指标状态与价格方向之间的映射关系。是前端"数据管理"页面中模式发现和相似案例功能的后端支撑。

## 文件职责

| 文件 | 行数 | 职责 |
|------|------|------|
| `tree_engine.py` | 132 | 决策树规则发现引擎：标签生成→特征编码→交叉验证→训练→规则提取 |
| `rule_extractor.py` | 102 | 从训练好的决策树中提取可解释的交易规则 |
| `knn_engine.py` | 188 | KNN 相似案例检索引擎：构建近邻索引→查找相似→预测方向 |
| `feature_encoder.py` | 110 | 指标列→归一化特征向量（MinMaxScaler，16-20 维） |
| `label_generator.py` | 62 | 从未来价格变动生成分类标签（UP/DOWN/FLAT）+ 回归目标 |
| `stat_validator.py` | 161 | 统计验证：Wilson 置信区间、条件概率表、规则提升度 |

## 决策树发现 (tree_engine.py)

```
FeatureEncoder.fit_transform(df) → 归一化特征矩阵
  ↓
generate_labels(df, horizon) → UP/DOWN/FLAT 标签
  ↓
TimeSeriesSplit(3) 交叉验证
  ↓
DecisionTreeClassifier(max_depth=5) 训练
  ↓
extract_rules(tree) → Top 10 RuleItem (置信度 * 提升度排序)
  ↓
DiscoveryResult { rules, feature_importance, cv_score }
```

只保留 UP/DOWN 样本做二分类。最少需要 `min_samples_leaf * 3` 个样本。

### 规则提取 (rule_extractor.py)

遍历决策树每个叶节点，构建根到叶的完整条件链。每条规则包含：
- 条件序列（特征名 + 阈值）
- 置信度（叶节点中正例比例）
- 样本数
- 提升度（lift > 1.2 才保留，即优于随机基线）

## KNN 引擎 (knn_engine.py)

```
fit(df): 特征编码 → 保存未来收益/高/低数据 → NearestNeighbors 索引
  ↓
find_similar(current_state, k): 查询 k 个最近邻 → 返回 SimilarCase[]
  ↓
predict(current_state, k): 多数投票 → PredictionResult { direction, confidence, range }
```

预测逻辑：UP 邻居 >= 60% → UP，<= 40% → DOWN，其余 FLAT。置信度 = 偏离 50/50 的程度。

## 特征编码 (feature_encoder.py)

从 DataFrame 中选择 ~16 个代表性指标列（RSI、EMA、MACD、BB、ATR、RVOL、ADX、Stochastic、CCI、MFI、pattern），用 `MinMaxScaler` 归一化到 [0,1]。每个类别取第一个匹配列，上限 20 维。找不到特征时回退到零数组。

## 标签生成 (label_generator.py)

根据未来 `horizon` 根 K 线的价格变动生成标签：
- UP: 未来收盘涨幅 > threshold
- DOWN: 未来收盘跌幅 > threshold
- FLAT: 中间

同时生成回归目标：future_close_pct、future_high_pct、future_low_pct。

## 统计验证 (stat_validator.py)

- `wilson_confidence()`: Wilson 得分置信区间（适合小样本比例）
- `discretize_indicator()`: 指标值分箱（RSI 用 30/50/70，BB 用 0.2/0.5/0.8 等）
- `build_conditional_prob_table()`: 条件概率表
- `validate_rule_lift()`: 规则提升度计算（至少 10 个样本）

## 数据流

```
前端请求
  ├─ POST /api/discovery/patterns → tree_engine.discover() → 规则列表
  ├─ POST /api/discovery/similar → knn_engine.find_similar() → 相似案例
  └─ POST /api/discovery/predict → knn_engine.predict() → 价格预测
```

## 涉及文件

| 文件 | 核心内容 |
|------|---------|
| `core/discovery/tree_engine.py` | 决策树发现引擎 |
| `core/discovery/rule_extractor.py` | 决策树规则提取 |
| `core/discovery/knn_engine.py` | KNN 相似案例 + 预测 |
| `core/discovery/feature_encoder.py` | 指标→特征向量编码 |
| `core/discovery/label_generator.py` | 未来收益标签生成 |
| `core/discovery/stat_validator.py` | 统计验证工具 |
