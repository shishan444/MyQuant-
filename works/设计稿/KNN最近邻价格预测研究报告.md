# KNN 最近邻价格预测研究报告

## 基于技术指标状态的加密货币短期价格预测深度研究

**项目**: MyQuant 模式发现引擎
**日期**: 2026-04-19
**范围**: BTC/ETH, 15m-4h 时间框架, 20,000-50,000 根 K 线

---

## 目录

- [一、GitHub 项目分析](#一github-项目分析)
- [二、KNN 技术参数推荐](#二knn-技术参数推荐)
- [三、替代方案对比分析](#三替代方案对比分析)
- [四、推荐方案与理由](#四推荐方案与理由)
- [五、关键风险与缓解措施](#五关键风险与缓解措施)

---

## 一、GitHub 项目分析

### 1.1 asavinov/intelligent-trading-bot (1,665 stars)

**URL**: https://github.com/asavinov/intelligent-trading-bot
**核心价值**: 最成熟的加密货币 ML 交易系统，特征工程体系完整

**架构分析**:
- 特征生成器架构: 可插拔的 generator 设计 (`talib`, `itblib`, `itbstats`, `tsfresh`, 自定义)
- 标签系统: `gen_labels_highlow.py` 实现了精细的标签生成，包括:
  - 未来 N 根 K 线最高价/最低价相对当前价的百分比变动
  - 阈值分类: 高阈值(1.0, 1.5, 2.0, 2.5, 3.0%)判断是否突破，低阈值(0.1-0.5%)判断是否受限
  - 高低比 (`high_to_low_ratio`): 衡量未来价格偏上还是偏下，范围 [-1, +1]
- 分类器: 使用 LightGBM 而非 KNN，但其特征工程方法对我们有直接参考价值
- 数据标准化: 支持 StandardScaler 和可选的缩放

**可借鉴要点**:
1. 特征相对化处理 (`rel_base`, `rel_func`) -- 将绝对值转为相对差值/比率
2. 滚动聚合特征 (MA, std, area_ratio, linear_trend)
3. 多窗口参数 (2, 3, 5, 8, 13, 21, 34) -- 类似斐波那契数列
4. 标签生成方法: 基于未来价格极值相对当前价格的百分比变动

**不足**: 未使用 KNN，使用 LightGBM 作为核心分类器，可解释性较差

---

### 1.2 sammanthp007/Stock-Price-Prediction-Using-KNN-Algorithm (84 stars)

**URL**: https://github.com/sammanthp007/Stock-Price-Prediction-Using-KNN-Algorithm
**核心价值**: 最直接的 KNN 股价预测实现，从零手写 KNN 算法

**架构分析**:
- 距离度量: 手写欧几里得距离 `euclideanDistance`
- KNN 实现: 从零手写，包括邻居查找 (`getNeighbors`)、投票 (`getResponse`)、准确率计算
- 数据: 使用 `pandas_datareader` 获取 NASDAQ 股票数据
- 特征: 直接使用 OHLCV 原始价格 + 涨跌标签 (up/down)
- 分割: 67/33 随机分割

**关键代码片段** (距离计算):
```python
def euclideanDistance(instance1, instance2, length):
    distance = 0
    for x in range(1, length):
        distance += pow((instance1[x] - instance2[x]), 2)
    return math.sqrt(distance)
```

**可借鉴要点**:
1. 纯 KNN 实现思路清晰，便于理解和定制
2. 70% 准确率的二分类 (涨/跌) 结果
3. 距离加权的投票机制

**不足**: 使用原始价格作为特征 (非指标状态)，无标准化处理，使用随机分割而非时间序列分割

---

### 1.3 siddiquimaaz/stock-price-prediction-ml-technical-indicators (0 stars, 代码质量高)

**URL**: https://github.com/siddiquimaaz/stock-price-prediction-ml-technical-indicators
**核心价值**: 技术指标特征工程的完整实现，与本项目指标体系高度吻合

**架构分析**:
- 技术指标特征 (26个): 完整覆盖用户需求的所有指标类型
  - RSI (14周期)
  - EMA (12, 26)
  - MACD, MACD_signal, MACD_histogram
  - Bollinger Bands: BB_width, **BB_position** (价格在布林带中的位置, 0-1)
  - Volume_ratio (成交量比率)
  - Lag features (1, 3, 5, 10 延迟)
- 标准化: **StandardScaler** + **MinMaxScaler** 双缩放
- 时间序列分割: 使用 `TimeSeriesSplit` 避免数据泄露
- 模型: LinearRegression, Ridge, Lasso, RandomForest, GradientBoosting, SVR

**关键特征工程** (BB_position 计算 -- 与本项目的 BOLL 位置完全一致):
```python
df['BB_position'] = (df['Close'] - df['BB_lower']) / (df['BB_upper'] - df['BB_lower'])
```

**可借鉴要点**:
1. 特征列定义完整: 26 个特征列覆盖所有主要指标
2. MinMaxScaler + StandardScaler 双缩放策略
3. 时间序列专用分割而非随机分割
4. Volume_ratio 特征: 当前成交量 / 10日均线成交量

**不足**: 未实现 KNN 回归器 (使用 SVR 和 RandomForest 替代)

---

### 1.4 tslearn-team/tslearn (3,143 stars)

**URL**: https://github.com/tslearn-team/tslearn
**核心价值**: 专业时间序列 ML 工具库，内置 KNN 时间序列分类/回归器

**架构分析**:
- `KNeighborsTimeSeriesClassifier`: 基于时间序列距离的 KNN 分类器
- `KNeighborsTimeSeriesRegressor`: 基于时间序列距离的 KNN 回归器
- 距离度量: DTW (Dynamic Time Warping), Soft-DTW, Global Alignment Kernel
- 与 scikit-learn API 完全兼容

**可借鉴要点**:
1. DTW 距离度量可替代欧几里得距离，对时间序列形态匹配更有效
2. KNeighborsTimeSeriesRegressor 可直接用于回归预测
3. TimeSeriesScalerMinMax 标准化器专为时间序列设计
4. Shapelet 学习可发现最具判别力的子序列模式

**不足**: DTW 计算复杂度 O(n^2)，对 50,000 条数据量需要优化; 更适合子序列匹配而非指标状态向量匹配

---

### 1.5 juliusHin/KNR_Stock_Prediction (3 stars)

**URL**: https://github.com/juliusHin/KNR_Stock_Prediction
**核心价值**: 专门使用 K Nearest Neighbors Regressor (KNR) 的股票预测项目

**核心思路**: 使用 sklearn.neighbors.KNeighborsRegressor 预测连续价格值而非分类

---

### 项目对比总结

| 项目 | Stars | 核心算法 | 特征类型 | 可解释性 | 加密货币适用 |
|------|-------|----------|----------|----------|------------|
| asavinov/intelligent-trading-bot | 1,665 | LightGBM | 滚动统计+TA-Lib | 中 | 高 |
| sammanthp007/Stock-Price-Prediction-Using-KNN-Algorithm | 84 | KNN (手写) | OHLCV原始值 | 高 | 低 |
| siddiquimaaz/stock-price-prediction-ml-technical-indicators | 0 | 多模型对比 | 26个技术指标 | 中 | 中 |
| tslearn-team/tslearn | 3,143 | DTW-KNN | 时间序列 | 高 | 通用 |
| juliusHin/KNR_Stock_Prediction | 3 | KNR (sklearn) | 待分析 | 高 | 低 |

---

## 二、KNN 技术参数推荐

### 2.1 K 值选择

**推荐: K = 15 ~ 25 (对于 20,000-50,000 条数据)**

| 数据量 | 推荐K范围 | 理由 |
|--------|----------|------|
| 20,000 | 11 ~ 17 | sqrt(20000) ~ 141, 但金融数据噪声大，取其 1/10 ~ 1/8 |
| 30,000 | 13 ~ 21 | |
| 50,000 | 17 ~ 29 | |

**K值选择策略**:
1. **起始值**: K = round(sqrt(N) * 0.08)，N 为样本数
2. **网格搜索范围**: [5, 7, 9, 11, 15, 21, 25, 31, 41]
3. **选择标准**: 使用 walk-forward validation (非标准 cross-validation)
4. **原则**: 奇数K避免平票; 过小K过拟合噪声，过大K平滑掉局部模式

**重要警告**: 金融时间序列不可使用标准 k-fold CV，必须使用 TimeSeriesSplit 或 walk-forward validation。

---

### 2.2 距离度量

**推荐: 带特征权重的标准化欧几里得距离 (Weighted Euclidean)**

| 距离度量 | 适用场景 | 优缺点 |
|----------|----------|--------|
| **标准化欧几里得** (推荐) | 指标状态向量 | 计算快，各维度贡献均匀 |
| Mahalanobis | 特征间有相关性 | 考虑协方差，但计算慢，N>特征数时协方差矩阵不稳定 |
| 曼哈顿 (L1) | 异常值较多 | 对异常值更鲁棒 |
| DTW | 时间序列子序列匹配 | 对形态匹配好，但 O(n^2) 计算量过大 |
| 余弦相似度 | 方向比大小重要 | 适合高维稀疏，不适合本场景 |

**推荐配置** (scikit-learn):
```python
from sklearn.neighbors import KNeighborsRegressor

knn = KNeighborsRegressor(
    n_neighbors=21,
    weights='distance',     # 距离倒数加权，近邻贡献更大
    metric='minkowski',     # 默认即为欧几里得 (p=2)
    p=2,                    # p=2 欧几里得, p=1 曼哈顿
    algorithm='ball_tree',  # 对中等维度 (10-30) 效率好
    leaf_size=30,           # 默认值
)
```

**权重函数**:
- `weights='distance'` (强烈推荐): w_i = 1 / d(x, x_i)，近邻的贡献与距离成反比
- `weights='uniform'`: 所有近邻等权，不推荐 -- 金融数据中相似度高的近邻参考价值更大

---

### 2.3 特征编码

**推荐: 混合编码策略，每类指标按其特性处理**

#### 2.3.1 各指标编码方法

| 指标 | 原始范围 | 编码方法 | 编码后范围 | 说明 |
|------|---------|----------|-----------|------|
| RSI | [0, 100] | **直接使用** | [0, 100] | 天然归一化，无需变换 |
| EMA 排列 | bool (多均线) | **one-hot / 序数编码** | {0,1,2,3,4} | 0=空头排列, 4=完美多头 |
| BOLL 位置 | [0, 1] | **直接使用** | [0, 1] | 已归一化 |
| MACD | (-inf, +inf) | **百分比化** | [-5, +5]% | MACD/close*100 |
| MACD histogram | (-inf, +inf) | **百分比化** | [-3, +3]% | |
| KDJ-K, KDJ-D | [0, 100] | **直接使用** | [0, 100] | 天然归一化 |
| VOL ratio | (0, +inf) | **log 变换** | [-2, +2] | log(volume/volume_ma) |
| ATR | (0, +inf) | **百分比化** | (0, 10)% | ATR/close*100 |
| CCI | (-inf, +inf) | **tanh 压缩** | [-1, +1] | tanh(CCI/200) |
| 价格动量 | (-inf, +inf) | **百分比收益率** | [-10, +10]% | (close-prev_close)/prev_close |

#### 2.3.2 EMA 排列编码详解

EMA 排列是一个多维布尔特征，需要特殊编码:

```
EMA排列状态编码 (序数编码):
  0 = 空头排列 (EMA10 < EMA20 < EMA50)
  1 = 弱空头 (EMA10 < EMA20, EMA20 > EMA50)
  2 = 纠缠 (三线缠绕)
  3 = 弱多头 (EMA10 > EMA20, EMA20 < EMA50)
  4 = 多头排列 (EMA10 > EMA20 > EMA50)

或者使用 one-hot 编码 (5个二进制列):
  ema_bearish, ema_weak_bear, ema_intertwined, ema_weak_bull, ema_bullish
```

#### 2.3.3 最终特征向量示例

```python
feature_vector = [
    # 动量类 (4维) - 天然归一化
    rsi_14,                          # [0, 100]
    stoch_k_14,                      # [0, 100]
    stoch_d_14,                      # [0, 100]
    willr_14,                        # [-100, 0] -> 映射到 [0, 100]

    # 趋势类 (5维) - 需归一化
    ema_alignment,                   # {0,1,2,3,4} 序数
    macd_pct,                        # MACD/close*100
    macd_hist_pct,                   # histogram/close*100
    roc_12,                          # 收益率%
    trix_12,                         # 三重指数变化率%

    # 波动率类 (3维) - 部分归一化
    bb_position,                     # [0, 1]
    bb_width_pct,                    # (upper-lower)/close*100
    atr_pct,                         # ATR/close*100

    # 成交量 (1维)
    vol_ratio_log,                   # log(vol/vol_ma)

    # KDJ (2维) - 天然归一化
    kdj_k,                           # [0, 100]
    kdj_d,                           # [0, 100]

    # CCI (1维) - 需压缩
    cci_normalized,                  # tanh(CCI/200)
]
# 共 16 维特征向量
```

---

### 2.4 标准化/归一化

**推荐: MinMaxScaler 到 [0, 1] 范围**

| 标准化方法 | 公式 | 适用场景 | 金融适用性 |
|-----------|------|----------|-----------|
| **MinMaxScaler** (推荐) | (x - min) / (max - min) | 有界特征 | 好 -- 保持原始分布形状 |
| StandardScaler | (x - mean) / std | 正态分布特征 | 一般 -- 金融数据非正态 |
| RobustScaler | (x - median) / IQR | 有异常值 | 较好 -- 但会改变范围 |
| RankScaler | rank(x) / N | 任意分布 | 好 -- 但丢失幅度信息 |

**推荐策略: 分层标准化**

```python
from sklearn.preprocessing import MinMaxScaler
import numpy as np

# 已经在 [0, 100] 范围的指标: 缩放到 [0, 1]
normalized_features = {}
for col in ['rsi_14', 'stoch_k', 'stoch_d', 'kdj_k', 'kdj_d']:
    normalized_features[col] = df[col] / 100.0

# 已经在 [0, 1] 范围的指标: 直接使用
for col in ['bb_position']:
    normalized_features[col] = df[col]

# 无界指标: 先百分比化/压缩，再 MinMaxScaler
scaler = MinMaxScaler(feature_range=(0, 1))
unbounded_cols = ['macd_pct', 'macd_hist_pct', 'atr_pct', 'vol_ratio_log', 'roc_12']
normalized_features[unbounded_cols] = scaler.fit_transform(df[unbounded_cols])
```

**关键原则**:
1. **必须使用 fit_transform 在训练集上，transform 在测试集上** -- 避免数据泄露
2. **滚动窗口标准化**优于全局标准化 -- 金融数据的分布会随时间漂移
3. EMA 排列序数编码: 除以最大值 (4) 得到 [0, 0.25, 0.5, 0.75, 1.0]

---

### 2.5 输出类型

**推荐: 多目标输出 -- 分类 + 回归 + 分布**

| 输出类型 | 方法 | 说明 | 可解释性 |
|---------|------|------|---------|
| 涨跌方向 | KNeighborsClassifier | 3分类: UP/DOWN/FLAT | 高 -- 可展示投票比例作为概率 |
| 价格变动幅度 | KNeighborsRegressor | 预测 N 根 K 线后的价格变动% | 高 -- 可展示 K 个近邻的历史变动 |
| 变动范围 | KNeighborsRegressor (多输出) | 同时预测 max_high% 和 min_low% | 高 -- 可展示 K 个近邻的历史极值 |
| 置信度 | 近邻一致性 | K 个近邻中涨跌方向一致的比例 | 高 |

```python
# 多输出回归: 同时预测最高涨幅和最大跌幅
from sklearn.neighbors import KNeighborsRegressor

# 标签: 未来 N 根 K 线的最高价涨幅%和最低价跌幅%
y_high = (future_max_high - current_close) / current_close * 100
y_low = (future_min_low - current_close) / current_close * 100
y = np.column_stack([y_high, y_low])

knn = KNeighborsRegressor(n_neighbors=21, weights='distance')
knn.fit(X_train, y_train)
y_pred = knn.predict(X_test)  # 返回 [predicted_high_pct, predicted_low_pct]
```

---

### 2.6 算法选择与性能优化

| 参数 | 推荐值 | 理由 |
|------|--------|------|
| `algorithm` | `'ball_tree'` 或 `'kd_tree'` | 16维特征，ball_tree 在 10-30 维效率最优 |
| `leaf_size` | 30 (默认) | 影响查询/构建时间平衡 |
| `n_jobs` | -1 | 使用所有 CPU 核心，并行距离计算 |
| `metric` | `'minkowski'` (p=2) | 即欧几里得距离 |

**性能预估**:
- 50,000 条数据, 16 维特征, ball_tree
- 构建索引: ~1-5秒
- 单次查询 (K=21): ~0.1ms
- 预测 1,000 个点: ~100ms
- 内存: ~50,000 * 16 * 8 bytes = ~6.4MB

---

## 三、替代方案对比分析

### 3.1 方案概览

| 方案 | 核心思路 | 可解释性 | 实现复杂度 | 精度潜力 | 数据量要求 |
|------|---------|---------|-----------|---------|-----------|
| **KNN 回归** (推荐) | 指标状态向量相似度 -> 历史近邻 -> 加权平均 | 极高 | 低 | 中 | 20K+ |
| 条件概率表 (CPT) | 指标离散化 -> 联合概率 -> 条件概率 | 高 | 低 | 中低 | 50K+ |
| 核密度估计 (KDE) | 指标连续值 -> 核函数平滑 -> 概率密度 | 中 | 中 | 中 | 20K+ |
| DTW 形态匹配 | K 线序列形态相似度 -> 动态时间弯曲 | 极高 | 高 | 中 | 10K+ |
| 决策树 | 指标阈值组合 -> 树分裂 -> 规则提取 | 极高 | 低 | 中 | 5K+ |
| Analog Forecasting | 相似日分析 -> 历史重演 | 极高 | 中 | 中 | 20K+ |

---

### 3.2 方案详细对比

#### A. KNN 回归 (sklearn KNeighborsRegressor)

**原理**: 将当前技术指标状态编码为特征向量，在历史数据中找到 K 个指标状态最相似的 K 线，用它们的未来价格变动作为预测。

**优势**:
- 可解释性极强: 可以直接展示 "当前状态与以下 N 个历史案例相似，它们之后的价格变动是..."
- 非参数模型: 不假设数据分布，适合金融数据的非正态特性
- 实现简单: scikit-learn 几行代码即可
- 天然支持概率输出: K 个近邻的投票比例/变动分布
- 在线学习友好: 新数据直接加入训练集

**劣势**:
- 维度灾难: 特征超过 20 维时效果急剧下降
- 概念漂移: 市场机制变化时，旧数据可能误导
- 距离度量选择: 对异构特征，欧几里得距离可能不是最优
- 预测延迟: 每次预测需要扫描整个历史数据 (可用 ball_tree 缓解)

**适用场景**: 特征维度 10-20，数据量 20K-50K，需要可解释性的短期预测

---

#### B. 条件概率表 (Conditional Probability Table)

**原理**: 将每个指标离散化为 3-5 个状态 (如 RSI: 超卖/中性/超买)，计算联合状态到未来收益的条件概率。

```
P(future_return > threshold | RSI=oversold, EMA=bullish, BB=lower, MACD=positive, ...)
```

**优势**:
- 可解释性极高: 直接输出 "在历史上，当 RSI<30 & EMA多头 & BB下轨时，未来上涨概率为 68%"
- 计算快速: 查表操作 O(1)
- 无需标准化: 离散化后各指标天然统一

**劣势**:
- **组合爆炸**: 16 个指标各 3 个状态 = 3^16 = 43,046,721 种组合，大多数组合在数据中从未出现
- **信息损失**: 连续指标离散化会丢失精度
- **数据稀疏**: 需要极大样本量才能可靠估计高维条件概率
- **边界问题**: 在离散化边界附近，微小变化导致状态跳跃

**适用场景**: 限制指标数量到 4-6 个，每个指标 3 状态; 或使用贝叶斯网络降维

---

#### C. 核密度估计 (Kernel Density Estimation)

**原理**: 用核函数 (如高斯核) 对指标-收益的联合分布进行非参数估计，然后计算条件密度。

```
f(return | indicators) = f(return, indicators) / f(indicators)
```

**优势**:
- 保持连续性: 不需要离散化，保留完整信息
- 输出完整分布: 可以计算任意分位数 (VaR, 预测区间)
- 非参数: 不假设分布形状

**劣势**:
- **维度灾难更严重**: 高维 KDE 的带宽选择非常困难
- **计算量**: 每次预测需要遍历所有样本计算核函数
- **带宽选择**: 对结果影响极大，需要交叉验证
- scikit-learn 的 KernelDensity 仅支持到约 20 维

**适用场景**: 低维 (3-5个核心指标)，需要完整概率分布输出

---

#### D. DTW 形态匹配 (tslearn)

**原理**: 将最近 M 根 K 线的价格序列作为模式，使用 DTW 距离在历史中寻找最相似的子序列。

**优势**:
- 形态匹配直觉好: "当前走势与历史上某段走势最相似"
- 容忍时间轴拉伸: DTW 允许形态在时间维度上有弹性
- tslearn 库提供现成实现: `KNeighborsTimeSeriesRegressor`

**劣势**:
- **计算复杂度**: DTW 距离 O(L^2) per pair, 50K 样本时非常慢
- **不使用指标信息**: 纯价格形态匹配忽略了指标状态
- **过拟合风险**: DTW 可能匹配到宏观环境完全不同的历史形态
- 需要合理选择子序列长度 L

**适用场景**: 价格形态识别，辅助 KNN 的二次确认

---

#### E. 决策树

**原理**: 使用 CART 算法，递归地找到最优的指标阈值分裂点，形成树状规则。

**优势**:
- 可解释性最高: 每个预测可以展示完整决策路径
- 自动特征选择: 信息增益低的特征不会被使用
- 处理异构特征: 天然支持混合类型
- 规则提取: 可以直接从树中提取交易规则

**劣势**:
- 不稳定性: 数据微小变化可能导致完全不同的树
- 过拟合: 需要严格剪枝
- 边界是轴平行的: 无法学习斜决策边界

**适用场景**: 规则发现，与 KNN 互补 (详见已有的决策树研究报告)

---

#### F. Analog Forecasting (相似日分析)

**原理**: 源自气象学的方法，寻找历史上与当前市场环境最相似的"日"(K线)，用其后续走势作为预测。

**优势**:
- 学术基础: 在气象、电力负荷预测领域有成熟应用
- 直觉清晰: "历史上类似的行情后续怎么走"
- 可展示多个相似案例

**劣势**:
- 缺少成熟的 Python 金融实现
- 特征选择和权重分配需要领域知识
- 本质上与 KNN 等价 (Analog Forecasting 就是指标空间中的 KNN)

**结论**: Analog Forecasting 在数学上与 KNN 等价，KNN 就是 Analog Forecasting 的一种实现

---

### 3.3 综合评分

| 维度 (权重) | KNN (30%) | CPT (15%) | KDE (15%) | DTW (15%) | 决策树 (25%) |
|------------|-----------|-----------|-----------|-----------|------------|
| 可解释性 (30%) | 9 | 10 | 6 | 9 | 10 |
| 实现难度 (15%) | 9 | 8 | 6 | 5 | 9 |
| 精度潜力 (20%) | 7 | 5 | 7 | 7 | 7 |
| 数据量适配 (15%) | 8 | 4 | 7 | 7 | 8 |
| 计算性能 (10%) | 7 | 10 | 4 | 3 | 9 |
| 集成难度 (10%) | 9 | 7 | 5 | 6 | 9 |
| **加权总分** | **8.35** | **6.75** | **6.05** | **6.65** | **8.80** |

---

## 四、推荐方案与理由

### 4.1 推荐方案: KNN 回归 + 决策树规则提取 (双引擎)

**核心思路**: KNN 作为预测引擎提供可解释的相似案例; 决策树作为规则引擎提取交易规则。两者互补。

#### 4.1.1 为什么选择 KNN 作为主方案

1. **可解释性完美匹配需求**: 用户要求"展示相似历史案例"，这正是 KNN 的核心输出
   - 输入: 当前技术指标状态向量
   - 输出: K 个最相似历史案例 (时间、指标值、后续N根K线的价格变动)
   - 预测: K 个近邻的加权平均变动 (涨跌幅、最大涨幅、最大跌幅)
   - 置信度: 近邻一致性 (K 个近邻中涨跌方向一致的比例)

2. **非参数特性适合金融数据**: 不假设价格变动的分布形状，避免分布假设错误的风险

3. **实现简洁**: scikit-learn 标准接口，代码量小，维护成本低

4. **与现有系统兼容**: 特征向量可直接从现有指标计算模块输出获取

#### 4.1.2 为什么不是纯决策树

决策树在"可解释性"和"规则提取"方面更优，但无法提供"相似历史案例"这一核心功能。KNN 天然提供近邻信息，决策树不提供。

**推荐组合**: KNN 做预测+案例展示，决策树做规则提取+特征重要性分析。

#### 4.1.3 架构设计

```
                    模式发现引擎 (PatternDiscoveryEngine)
                    ====================================

                    输入: 技术指标状态 (16维特征向量)
                              |
                    +---------+---------+
                    |                   |
            KNN 预测引擎          决策树规则引擎
            (KNeighborsRegressor)   (DecisionTreeClassifier)
                    |                   |
                    |                   |
            +-------+-------+   规则提取 (文本规则)
            |       |       |         |
        预测变动  置信度   近邻案例   规则条件列表
        (回归值)  (一致性)  (展示)    (if-then)
            |       |       |         |
            +-------+-------+---------+
                    |
              综合输出:
              - 预测方向 + 幅度
              - 概率估计
              - K个相似历史案例 (时间、指标值、后续走势图)
              - 匹配到的决策规则
```

---

### 4.2 实现路线图

#### Phase 1: 特征工程模块 (2-3天)

```python
# feature_encoder.py -- 技术指标状态编码器
class IndicatorStateEncoder:
    """将原始技术指标值编码为 KNN 特征向量"""

    def encode(self, indicator_df: pd.DataFrame) -> np.ndarray:
        """
        输入: 包含所有原始指标值的 DataFrame
        输出: shape (n_samples, 16) 的标准化特征矩阵
        """
        features = pd.DataFrame()

        # 动量类 (天然 [0,100])
        features['rsi'] = indicator_df['rsi_14'] / 100.0
        features['stoch_k'] = indicator_df['stoch_k_14'] / 100.0
        features['stoch_d'] = indicator_df['stoch_d_14'] / 100.0
        features['willr'] = (indicator_df['willr_14'] + 100) / 100.0

        # 趋势类
        features['ema_alignment'] = self._encode_ema_alignment(indicator_df) / 4.0
        features['macd_pct'] = self._safe_pct(indicator_df['macd_12_26_9'], indicator_df['close'])
        features['macd_hist_pct'] = self._safe_pct(indicator_df['macd_histogram'], indicator_df['close'])
        features['roc'] = indicator_df['roc_12']
        features['trix'] = indicator_df['trix_12']

        # 波动率类
        features['bb_position'] = indicator_df['bb_position']  # 已在 [0,1]
        features['bb_width'] = self._safe_pct(
            indicator_df['bb_upper_20'] - indicator_df['bb_lower_20'],
            indicator_df['close']
        )
        features['atr_pct'] = self._safe_pct(indicator_df['atr_14'], indicator_df['close'])

        # 成交量
        features['vol_ratio'] = np.log1p(indicator_df['volume'] / indicator_df['volume_ma_20'])

        # KDJ
        features['kdj_k'] = indicator_df['kdj_k'] / 100.0
        features['kdj_d'] = indicator_df['kdj_d'] / 100.0

        # CCI
        features['cci'] = np.tanh(indicator_df['cci_20'] / 200.0)

        return features.values
```

#### Phase 2: KNN 预测引擎 (1-2天)

```python
# knn_predictor.py -- KNN 预测核心
from sklearn.neighbors import KNeighborsRegressor
import numpy as np

class KNNPricePredictor:
    def __init__(self, n_neighbors=21, weights='distance', horizon=4):
        self.knn = KNeighborsRegressor(
            n_neighbors=n_neighbors,
            weights=weights,
            metric='minkowski',
            p=2,
            algorithm='ball_tree',
            n_jobs=-1,
        )
        self.horizon = horizon  # 预测未来 N 根 K 线
        self.training_metadata = None  # 存储时间戳等信息用于展示

    def fit(self, X: np.ndarray, y: np.ndarray, metadata: pd.DataFrame):
        """
        X: shape (n_samples, n_features) 特征矩阵
        y: shape (n_samples, 3) 目标 [high_pct, low_pct, close_pct]
        metadata: DataFrame with columns [timestamp, close_price]
        """
        self.knn.fit(X, y)
        self.training_metadata = metadata
        return self

    def predict(self, X: np.ndarray) -> dict:
        """返回预测结果和相似案例"""
        prediction = self.knn.predict(X)

        # 获取近邻信息
        distances, indices = self.knn.kneighbors(X)

        # 收集相似案例
        similar_cases = []
        for i in range(len(X)):
            neighbors = []
            for j, (dist, idx) in enumerate(zip(distances[i], indices[i])):
                meta = self.training_metadata.iloc[idx]
                neighbors.append({
                    'rank': j + 1,
                    'distance': dist,
                    'timestamp': meta['timestamp'],
                    'close_price': meta['close_price'],
                    'future_high_pct': self.knn._y[idx, 0],
                    'future_low_pct': self.knn._y[idx, 1],
                    'future_close_pct': self.knn._y[idx, 2],
                })
            similar_cases.append(neighbors)

        return {
            'prediction': prediction,        # shape (n_samples, 3)
            'similar_cases': similar_cases,   # 相似历史案例
            'distances': distances,           # 距离
            'confidence': self._calc_confidence(indices),  # 置信度
        }

    def _calc_confidence(self, indices):
        """近邻一致性作为置信度"""
        # 检查近邻中涨跌方向的一致性
        neighbor_returns = self.knn._y[indices]  # (n_samples, k, 3)
        # 未来收盘价变动方向
        directions = np.sign(neighbor_returns[:, :, 2])  # 1=涨, -1=跌, 0=平
        # 一致性 = |涨的个数 - 跌的个数| / K
        consistency = np.abs(np.sum(directions == 1, axis=1) -
                           np.sum(directions == -1, axis=1)) / self.knn.n_neighbors
        return consistency
```

#### Phase 3: 标签生成模块 (1天)

```python
# label_generator.py -- 未来价格变动标签
import numpy as np
import pandas as pd

class LabelGenerator:
    @staticmethod
    def generate_highlow_labels(df: pd.DataFrame, horizon: int) -> np.ndarray:
        """
        生成未来 horizon 根 K 线的价格变动标签

        返回: shape (n_samples, 3) 的数组
          - future_high_pct: 未来最高价相对当前价的涨幅%
          - future_low_pct: 未来最低价相对当前价的跌幅% (负数)
          - future_close_pct: 未来第 horizon 根收盘价相对当前价的涨跌幅%
        """
        n = len(df)
        labels = np.full((n, 3), np.nan)

        for i in range(n - horizon):
            current_close = df['close'].iloc[i]

            # 未来 horizon 根 K 线的数据
            future = df.iloc[i+1 : i+1+horizon]

            labels[i, 0] = (future['high'].max() - current_close) / current_close * 100
            labels[i, 1] = (future['low'].min() - current_close) / current_close * 100
            labels[i, 2] = (df['close'].iloc[i+horizon] - current_close) / current_close * 100

        return labels
```

#### Phase 4: Walk-Forward 验证 (1-2天)

```python
# validation.py -- Walk-Forward 验证框架
from sklearn.model_selection import TimeSeriesSplit

def walk_forward_validate(X, y, n_splits=5, n_neighbors=21):
    """
    Walk-Forward 验证，模拟真实交易场景
    """
    tscv = TimeSeriesSplit(n_splits=n_splits)
    results = []

    for train_idx, test_idx in tscv.split(X):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        knn = KNeighborsRegressor(n_neighbors=n_neighbors, weights='distance')
        knn.fit(X_train, y_train)
        y_pred = knn.predict(X_test)

        # 方向准确率
        direction_accuracy = np.mean(np.sign(y_pred[:, 2]) == np.sign(y_test[:, 2]))

        # 平均绝对误差
        mae_high = np.mean(np.abs(y_pred[:, 0] - y_test[:, 0]))
        mae_low = np.mean(np.abs(y_pred[:, 1] - y_test[:, 1]))
        mae_close = np.mean(np.abs(y_pred[:, 2] - y_test[:, 2]))

        results.append({
            'direction_accuracy': direction_accuracy,
            'mae_high': mae_high,
            'mae_low': mae_low,
            'mae_close': mae_close,
            'train_size': len(train_idx),
            'test_size': len(test_idx),
        })

    return results
```

---

### 4.3 预期性能指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 方向准确率 (UP/DOWN) | 55-65% | 随机基线 50%，需超过此值 |
| MAE (close %) | 0.3-0.8% | BTC 1h 级别的典型波动 |
| 高低预测覆盖 | 80%+ | 实际价格在预测 [low, high] 范围内的比例 |
| 查询延迟 | < 50ms | 50K 数据量下的单次预测延迟 |
| 内存占用 | < 100MB | 特征矩阵 + ball_tree 索引 |

---

## 五、关键风险与缓解措施

### 5.1 技术风险

| 风险 | 严重程度 | 概率 | 缓解措施 |
|------|---------|------|---------|
| **市场机制漂移** | 高 | 高 | 使用滚动窗口 (仅保留最近 N 个月数据)，定期重新训练 |
| **维度灾难** | 高 | 中 | 控制特征维度在 10-20 之间; 使用特征选择去除低信息量特征 |
| **过拟合** | 中 | 中 | Walk-Forward 验证; 避免在测试集上调参 |
| **数据泄露** | 高 | 中 | 严格时间序列分割; 标签只使用未来数据; 标准化仅在训练集上 fit |
| **计算性能** | 低 | 低 | ball_tree 索引; K 值适中 (15-25); 特征维度合理 |
| **异常值影响** | 中 | 中 | RobustScaler 作为备选; 距离加权 (weights='distance') 降低远距离近邻影响 |

### 5.2 金融风险

| 风险 | 严重程度 | 概率 | 缓解措施 |
|------|---------|------|---------|
| **预测精度不足以盈利** | 高 | 高 | KNN 仅作为辅助信号，不作为唯一决策依据; 结合其他策略 |
| **黑天鹅事件** | 高 | 低 | 预测结果附带置信度; 低置信度时降低仓位; 设置止损 |
| **过度依赖历史相似性** | 中 | 高 | 添加时间衰减权重 (近期的近邻权重更高); 监控近邻时间分布 |
| **指标钝化** | 中 | 中 | 定期评估指标预测力; 动态特征选择 |

### 5.3 缓解措施详解

#### 5.3.1 时间衰减加权

```python
def time_decay_weights(distances, timestamps, current_time, half_life_days=90):
    """
    近邻的时间衰减权重: 越近期的近邻权重越高
    """
    time_diffs = (current_time - timestamps).days
    time_weights = np.exp(-np.log(2) * time_diffs / half_life_days)
    # 距离权重 * 时间权重
    combined_weights = (1.0 / (distances + 1e-8)) * time_weights
    return combined_weights / combined_weights.sum()
```

#### 5.3.2 滚动窗口训练

```python
def rolling_train_predict(df, feature_cols, label_cols, window_size=20000, step=5000):
    """
    滚动窗口: 仅使用最近 window_size 条数据训练
    """
    results = []
    for start in range(0, len(df) - window_size, step):
        train = df.iloc[start : start + window_size]
        test = df.iloc[start + window_size : start + window_size + step]

        # 训练
        knn.fit(train[feature_cols].values, train[label_cols].values)

        # 预测
        pred = knn.predict(test[feature_cols].values)
        results.append(pred)

    return np.concatenate(results)
```

#### 5.3.3 置信度过滤

```python
def filter_by_confidence(predictions, confidence, threshold=0.6):
    """
    仅在置信度超过阈值时输出预测
    """
    mask = confidence >= threshold
    return {
        'filtered_predictions': predictions[mask],
        'filter_rate': 1.0 - mask.mean(),  # 被过滤掉的比例
        'filtered_accuracy': ...,  # 过滤后的准确率 (应高于未过滤)
    }
```

---

## 附录

### A. sklearn KNeighborsRegressor 关键参数速查

```python
from sklearn.neighbors import KNeighborsRegressor

knn = KNeighborsRegressor(
    n_neighbors=21,          # K值: 推荐范围 15-25
    weights='distance',      # 权重: 'distance'(推荐) 或 'uniform'
    algorithm='ball_tree',   # 搜索算法: 'auto', 'ball_tree', 'kd_tree', 'brute'
    leaf_size=30,            # 叶节点大小
    p=2,                     # Minkowski 距离的 p 值: 1=曼哈顿, 2=欧几里得
    metric='minkowski',      # 距离度量
    metric_params=None,      # 距离度量的额外参数
    n_jobs=-1,               # 并行数: -1=全部核心
)
```

### B. 特征选择方法推荐

```python
from sklearn.feature_selection import mutual_info_regression, SelectKBest

# 基于互信息的特征选择
selector = SelectKBest(mutual_info_regression, k=12)
X_selected = selector.fit_transform(X_train, y_train[:, 2])  # 用 close_pct 作为目标

# 查看被选中的特征
selected_features = [feature_names[i] for i in selector.get_support(indices=True)]
```

### C. 超参数搜索

```python
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit

param_grid = {
    'n_neighbors': [9, 11, 15, 21, 25, 31, 41],
    'weights': ['distance'],
    'metric': ['minkowski'],
    'p': [1, 2],  # 曼哈顿 vs 欧几里得
}

tscv = TimeSeriesSplit(n_splits=5)
grid_search = GridSearchCV(
    KNeighborsRegressor(),
    param_grid,
    cv=tscv,
    scoring='neg_mean_absolute_error',
    n_jobs=-1,
)
grid_search.fit(X_train, y_train)
```

### D. 参考资源

1. **asavinov/intelligent-trading-bot** (1,665 stars): https://github.com/asavinov/intelligent-trading-bot
   - 特征工程架构、标签生成方法
2. **sammanthp007/Stock-Price-Prediction-Using-KNN-Algorithm** (84 stars): https://github.com/sammanthp007/Stock-Price-Prediction-Using-KNN-Algorithm
   - 纯 KNN 实现参考
3. **tslearn-team/tslearn** (3,143 stars): https://github.com/tslearn-team/tslearn
   - DTW-KNN 时间序列分类/回归
4. **scikit-learn KNeighborsRegressor 文档**: https://scikit-learn.org/stable/modules/generated/sklearn.neighbors.KNeighborsRegressor.html
5. **siddiquimaaz/stock-price-prediction-ml-technical-indicators**: https://github.com/siddiquimaaz/stock-price-prediction-ml-technical-indicators
   - 技术指标特征工程参考
6. **tslearn 文档**: https://tslearn.readthedocs.io/en/stable/
   - KNeighborsTimeSeriesRegressor, DTW 距离
