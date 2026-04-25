# B4: 策略 DNA

## 定位

`core/strategy/` 定义了整个工程的核心数据结构。所有模块——指标计算、回测引擎、进化算子、评分系统、API 序列化——都围绕 `StrategyDNA` 这个类型运转。

## 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `dna.py` | 389 | StrategyDNA 四层基因编码 + derive_role + 序列化 |
| `validator.py` | 166 | DNA 合法性校验（信号完整性 + 条件结构 + 参数范围） |
| `executor.py` | 750 | DNA -> 信号转换路由（单周期 + MTF 双轨道） |
| `mtf_engine.py` | 790 | MTF 共振引擎（见 B4.1 独立文档） |

## 核心类型: StrategyDNA

```
StrategyDNA (dna.py)
  signal_genes: List[SignalGene]     -- 信号条件 (indicator + params + role + condition)
  logic_genes: LogicGenes            -- AND/OR 组合 (entry/exit/add/reduce 各一)
  execution_genes: ExecutionGenes    -- timeframe + symbol
  risk_genes: RiskGenes              -- SL/TP/position_size/leverage/direction
  layers: Optional[List[TimeframeLayer]]  -- MTF 多层 (最多3层)
  cross_layer_logic: str             -- "AND"/"OR"
  mtf_mode: Optional[str]            -- None/"direction"/"confluence"/"direction+confluence"
  confluence_threshold: float        -- [0.1, 0.9] 共振门槛
  proximity_mult: float              -- [0.5, 3.0] 接近度乘数
  metadata: strategy_id, generation, parent_ids, mutation_ops
```

### derive_role() 三角色系统 (dna.py:54-68)

```
>=1d -> "structure"   (方向判定 + 价格位输出)
>=1h -> "zone"        (价格区间共振)
<1h  -> "execution"   (交易信号触发)
```

`is_mtf` 属性 (L236-238): layers 非空且 `_layers_explicit=True`。

## 关键链路

### 序列化 (from_dict)

```
dna.py:273 from_dict(data)
  L278-282  解析 layers -> TimeframeLayer.from_dict
  L289-291  解析 mtf_mode, confluence_threshold, proximity_mult
  L294-297  legacy: "trend" role -> "structure"
  L299-303  解析 signal_genes -> SignalGene.from_dict
  L327-337  自动包装: 无 layers 但有 signal_genes -> 创建单层
```

### 校验 (validate_dna)

```
validator.py:19 validate_dna(dna)
  L36-49   非 MTF: 检查 entry/exit signals
  L52-79   MTF: 每层需 entry/exit + 至少一个 execution 层 + 最多3层
  L82-85   cross_layer_logic 必须为 AND/OR
  L94-106  条件结构校验 (cross_above_series 需要 target_indicator 等)
  L109-134 参数范围校验:
    stop_loss [0.005, 0.20], position_size [0.10, 1.0]
    leverage [1, 10], mtf_mode 枚举, threshold [0.1, 0.9], mult [0.5, 3.0]
```

### 信号转换路由 (executor.py)

```
executor.py:530 dna_to_signal_set(dna, enhanced_df, dfs_by_timeframe)
  if dna.mtf_mode is not None:
    -> run_mtf_engine() (B4.1 MTF 共振引擎)
  elif dna.is_mtf:
    -> 旧 AND/OR 路径 (evaluate_layer per layer + _build_exec_signal_set)
  else:
    -> 单周期路径 (build_signal_set from B3)
```

## 关键机制

### SignalRole 八角色系统

| 角色组 | 角色 | 用途 |
|--------|------|------|
| 入场 | entry_trigger, entry_guard | trigger=触发信号, guard=过滤信号 |
| 出场 | exit_trigger, exit_guard | 同上 |
| 加仓 | add_trigger, add_guard | 同上 |
| 减仓 | reduce_trigger, reduce_guard | 同上 |

trigger 和 guard 的区别: trigger 是脉冲信号（如 cross_above），guard 是状态信号（如 price_above）。AND 组合时 trigger AND guard = "触发时检查状态"。

### 自动包装机制

`from_dict` (L327-337): 如果 DNA 有 signal_genes 但无 layers，自动将顶层信号包装为单层 TimeframeLayer。只在反序列化时触发，直接构造不触发。

### generate_strategy_name (dna.py:365-388)

格式: `{indicator}{type} {direction} {timeframe}-{hash4}`。hash4 = 所有信号基因+逻辑+风控参数的 MD5 前4位。INDICATOR_TYPE_MAP 将 23 种指标分为趋势/动量/波动/量价/趋势五类。

## 接口定义

| 函数/类 | 说明 |
|---------|------|
| `derive_role(timeframe) -> str` | 时间框架 -> 角色 |
| `StrategyDNA.to_dict() -> dict` | 完整序列化 |
| `StrategyDNA.from_dict(data) -> StrategyDNA` | 完整反序列化（含自动包装） |
| `StrategyDNA.from_json(str) -> StrategyDNA` | JSON 反序列化 |
| `StrategyDNA.is_mtf -> bool` | MTF 策略判断 |
| `validate_dna(dna) -> ValidationResult` | 主校验入口 |
| `generate_strategy_name(dna) -> str` | 人类可读名称 |
| `dna_to_signal_set(dna, df, dfs) -> SignalSet` | 信号转换路由 |

## 关键参数

| 参数 | 默认值 | 设计意图 |
|------|--------|---------|
| stop_loss | 0.05 | 5% 止损，BTC/ETH 日内波动参考 |
| position_size | 0.3 | 30% 资金，避免过度集中 |
| leverage | 1 | 默认无杠杆 |
| direction | "long" | 默认做多 |
| cross_layer_logic | "AND" | 层间默认严格组合 |
| mtf_mode | None | None=向后兼容，不启用评分门控 |
| confluence_threshold | 0.3 | 共振评分门槛 |
| proximity_mult | 1.5 | s% 区间宽度倍数 |

## 约定与规则

- **枚举值小写字符串**: ConditionType 和 SignalRole 的 value 均小写
- **JSON 字段映射**: Python `field_name` 在 JSON 中为 `field`
- **不可变模式**: 通过 `to_dict()` -> 修改 -> `from_dict()` 模拟不可变
- **legacy 兼容**: "trend" role 自动映射为 "structure"
