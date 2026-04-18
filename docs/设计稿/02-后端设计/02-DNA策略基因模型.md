# 02 - DNA 策略基因模型

## 1. 概述

StrategyDNA 是 MyQuant 系统的核心抽象，代表一个完整的交易策略。它采用基因编码思想，
将策略拆解为可独立变异和组合的基因组件。进化算法直接操作这些基因结构来完成策略的自动搜索。

**源码位置**: `core/strategy/dna.py`

**设计原则**:
- 每个基因组件职责单一，可独立变异
- 支持单时间框架和多时间框架两种模式
- 序列化/反序列化保持完整信息
- 向后兼容：单时间框架策略无需显式定义 layers

---

## 2. 枚举类型

### 2.1 SignalRole - 信号角色

```python
class SignalRole(Enum):
    ENTRY_TRIGGER = "entry_trigger"   # 直接触发买入
    ENTRY_GUARD   = "entry_guard"     # 入场条件过滤
    EXIT_TRIGGER  = "exit_trigger"    # 直接触发卖出
    EXIT_GUARD    = "exit_guard"      # 出场条件过滤
```

信号基因在策略中扮演四种角色。Trigger 和 Guard 的区别:
- Trigger: 产生交易信号的核心条件
- Guard: 辅助过滤条件，不单独触发交易，但必须满足

同一角色的信号通过 LogicGenes 的逻辑运算符组合。

### 2.2 ConditionType - 条件类型

共 17 种条件类型，分 4 个阶段引入:

**阶段 1 - 基础比较条件 (8 种)**:

| 枚举值 | 字符串 | 语义 | 参数 |
|--------|--------|------|------|
| LT | "lt" | 指标值 < 阈值 | threshold |
| GT | "gt" | 指标值 > 阈值 | threshold |
| LE | "le" | 指标值 <= 阈值 | threshold |
| GE | "ge" | 指标值 >= 阈值 | threshold |
| CROSS_ABOVE | "cross_above" | 指标从下方穿越阈值 | threshold |
| CROSS_BELOW | "cross_below" | 指标从上方穿越阈值 | threshold |
| PRICE_ABOVE | "price_above" | 收盘价高于指标值 | 无 |
| PRICE_BELOW | "price_below" | 收盘价低于指标值 | 无 |

**阶段 2 - 动态上下文条件 (4 种)**:

| 枚举值 | 字符串 | 语义 | 参数 |
|--------|--------|------|------|
| CROSS_ABOVE_SERIES | "cross_above_series" | 指标 A 从下方穿越指标 B | target_indicator, target_params |
| CROSS_BELOW_SERIES | "cross_below_series" | 指标 A 从上方穿越指标 B | target_indicator, target_params |
| LOOKBACK_ANY | "lookback_any" | 回溯窗口内任一 K 线满足条件 | window, inner |
| LOOKBACK_ALL | "lookback_all" | 回溯窗口内所有 K 线满足条件 | window, inner |

**阶段 4 - 支撑阻力条件 (3 种)**:

| 枚举值 | 字符串 | 语义 | 参数 |
|--------|--------|------|------|
| TOUCH_BOUNCE | "touch_bounce" | 价格触及指标线后反弹 | direction, proximity_pct |
| ROLE_REVERSAL | "role_reversal" | 指标线切换支撑/阻力角色 | role, lookback |
| WICK_TOUCH | "wick_touch" | 影线触及指标线但收盘在另一侧 | direction, proximity_pct |

总计: 8 + 4 + 3 = 15 种在 ConditionType 枚举中定义，但 evaluate_condition 还处理
cross_above_series 和 cross_below_series，合计 17 种运行时条件评估路径。

---

## 3. 基因组件

### 3.1 SignalGene - 信号基因

信号基因是最小的可变异单元，描述一条基于技术指标的交易条件。

```python
@dataclass
class SignalGene:
    indicator: str                                # 指标名称
    params: Dict[str, Union[int, float]]          # 指标参数
    role: SignalRole                              # 信号角色
    field_name: Optional[str] = None              # 多输出指标的字段选择
    condition: Dict[str, Any] = field(default_factory=dict)  # 条件字典
```

**字段说明**:

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| indicator | str | 指标名称 | "RSI", "EMA", "MACD" |
| params | Dict | 指标计算参数 | {"period": 14}, {"fast": 12, "slow": 26, "signal": 9} |
| role | SignalRole | 信号在策略中的角色 | ENTRY_TRIGGER |
| field_name | str/None | 多输出字段选择 | "histogram" (MACD), "k" (Stochastic) |
| condition | Dict | 条件结构 | {"type": "lt", "threshold": 30} |

**condition 字典结构**:

对于简单条件:
```json
{"type": "lt", "threshold": 30}
{"type": "price_above"}
```

对于动态上下文条件:
```json
{"type": "cross_above_series", "target_indicator": "EMA", "target_params": {"period": 50}}
```

对于回溯条件:
```json
{"type": "lookback_any", "window": 5, "inner": {"type": "gt", "threshold": 0}}
```

对于支撑阻力条件:
```json
{"type": "touch_bounce", "direction": "support", "proximity_pct": 0.01}
```

**序列化** (`to_dict`):

```json
{
  "indicator": "RSI",
  "params": {"period": 14},
  "role": "entry_trigger",
  "field": null,
  "condition": {"type": "lt", "threshold": 30}
}
```

注意: `field_name` 在序列化时映射为 `field`。

**反序列化** (`from_dict`): 自动将字符串形式的 role 转换为 SignalRole 枚举，
将 JSON 的 `field` 映射回 Python 的 `field_name`。

### 3.2 LogicGenes - 逻辑基因

控制同一组信号之间的组合逻辑。

```python
@dataclass
class LogicGenes:
    entry_logic: str = "AND"  # "AND" 或 "OR"
    exit_logic: str = "AND"   # "AND" 或 "OR"
```

- `entry_logic`: 组合所有 entry_trigger 和 entry_guard 信号的逻辑
- `exit_logic`: 组合所有 exit_trigger 和 exit_guard 信号的逻辑

AND 表示所有条件必须同时满足，OR 表示任一条件满足即可。

### 3.3 ExecutionGenes - 执行基因

定义策略的执行环境。

```python
@dataclass
class ExecutionGenes:
    timeframe: str = "4h"        # 执行时间框架
    symbol: str = "BTCUSDT"     # 交易对
```

**timeframe 取值**: "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h",
"12h", "1d", "3d", "1w"

**symbol 取值**: "BTCUSDT", "ETHUSDT" 等

### 3.4 RiskGenes - 风控基因

定义策略的风险管理参数。

```python
@dataclass
class RiskGenes:
    stop_loss: float = 0.05               # 止损比例
    take_profit: Optional[float] = None   # 止盈比例
    position_size: float = 0.3            # 仓位比例
    leverage: int = 1                     # 杠杆倍数
    direction: str = "long"               # 交易方向
```

**参数范围约束**:

| 参数 | 类型 | 范围 | 说明 |
|------|------|------|------|
| stop_loss | float | 0.005 - 0.20 | 止损，默认 5% |
| take_profit | float/None | - | 止盈，None 表示不设止盈 |
| position_size | float | 0.10 - 1.0 | 仓位比例，默认 30% |
| leverage | int | 1 - 10 | 杠杆倍数，1 表示无杠杆 |
| direction | str | "long"/"short"/"mixed" | 交易方向 |

### 3.5 TimeframeLayer - 时间框架层

多时间框架策略中的单层结构，每层独立在一个时间框架的数据上评估。

```python
@dataclass
class TimeframeLayer:
    timeframe: str
    signal_genes: List[SignalGene] = field(default_factory=list)
    logic_genes: LogicGenes = field(default_factory=LogicGenes)
```

每层包含:
- 自己的 `timeframe` (如 "1d" 代表日线层)
- 属于该层的 `signal_genes` 列表
- 该层的 `logic_genes` (独立于其他层的逻辑组合)

**序列化**:
```json
{
  "timeframe": "1d",
  "signal_genes": [SignalGene.to_dict(), ...],
  "logic_genes": {"entry_logic": "AND", "exit_logic": "AND"}
}
```

---

## 4. StrategyDNA - 完整策略基因组

### 4.1 数据结构

```python
@dataclass
class StrategyDNA:
    signal_genes: List[SignalGene] = field(default_factory=list)
    logic_genes: LogicGenes = field(default_factory=LogicGenes)
    execution_genes: ExecutionGenes = field(default_factory=ExecutionGenes)
    risk_genes: RiskGenes = field(default_factory=RiskGenes)
    strategy_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    generation: int = 0
    parent_ids: List[str] = field(default_factory=list)
    mutation_ops: List[str] = field(default_factory=list)
    layers: Optional[List[TimeframeLayer]] = None
    cross_layer_logic: str = "AND"
    _layers_explicit: bool = field(default=False, repr=False, init=False)
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| signal_genes | List[SignalGene] | 信号基因列表（单时间框架模式使用） |
| logic_genes | LogicGenes | 逻辑组合基因 |
| execution_genes | ExecutionGenes | 执行环境基因 |
| risk_genes | RiskGenes | 风控基因 |
| strategy_id | str | 策略唯一标识，自动生成 UUID |
| generation | int | 进化代数 |
| parent_ids | List[str] | 父代策略 ID 列表 |
| mutation_ops | List[str] | 历史变异操作记录 |
| layers | List[TimeframeLayer]/None | 多时间框架层列表 |
| cross_layer_logic | str | 跨层组合逻辑 ("AND"/"OR") |
| _layers_explicit | bool | 内部标记，是否显式设置了 layers |

### 4.2 MTF 属性判定

```python
@property
def is_mtf(self) -> bool:
    return self.layers is not None and len(self.layers) >= 1 and self._layers_explicit
```

MTF (Multi-Timeframe) 判定需要同时满足:
1. `layers` 不为 None
2. `layers` 至少包含 1 个元素
3. `_layers_explicit` 为 True（即 layers 是从外部数据显式设置的，而非自动包装的）

### 4.3 timeframes 属性

```python
@property
def timeframes(self) -> List[str]:
    if self.layers:
        return [layer.timeframe for layer in self.layers]
    return [self.execution_genes.timeframe]
```

返回策略使用的所有时间框架。MTF 模式从 layers 提取，否则返回执行时间框架。

---

## 5. 序列化与反序列化

### 5.1 to_dict()

将 StrategyDNA 序列化为字典:

```python
def to_dict(self) -> dict:
    result = {
        "strategy_id": self.strategy_id,
        "generation": self.generation,
        "parent_ids": self.parent_ids,
        "mutation_ops": self.mutation_ops,
        "signal_genes": [sg.to_dict() for sg in self.signal_genes],
        "logic_genes": self.logic_genes.to_dict(),
        "execution_genes": self.execution_genes.to_dict(),
        "risk_genes": self.risk_genes.to_dict(),
        "cross_layer_logic": self.cross_layer_logic,
    }
    if self.layers:
        result["layers"] = [layer.to_dict() for layer in self.layers]
    return result
```

关键行为:
- 始终包含顶层的 `signal_genes`, `logic_genes`
- 仅当 `layers` 不为 None 时才输出 `layers` 字段
- SignalGene 的 `field_name` 序列化为 `field`
- SignalRole 枚举序列化为字符串值

### 5.2 from_dict(data)

从字典反序列化为 StrategyDNA:

```python
@classmethod
def from_dict(cls, data: dict) -> "StrategyDNA":
```

**处理流程**:

1. 浅拷贝输入数据
2. 解析 `layers`（若存在），转换为 TimeframeLayer 对象列表
3. 提取 `cross_layer_logic`（默认 "AND"）
4. 将 `signal_genes` 列表中的字典转换为 SignalGene 对象
5. 将 `logic_genes` 字典转换为 LogicGenes 对象
6. 将 `execution_genes` 字典转换为 ExecutionGenes 对象
7. 将 `risk_genes` 字典转换为 RiskGenes 对象
8. 若 `strategy_id` 为空，自动生成 UUID
9. 构造实例，设置 layers 和 cross_layer_logic
10. **自动包装逻辑**: 若 layers 为 None 但有 signal_genes，自动创建一个包含所有顶层基因的单层

```python
# 自动包装示例
if instance.layers is None and instance.signal_genes:
    instance.layers = [
        TimeframeLayer(
            timeframe=instance.execution_genes.timeframe,
            signal_genes=list(instance.signal_genes),
            logic_genes=LogicGenes(
                entry_logic=instance.logic_genes.entry_logic,
                exit_logic=instance.logic_genes.exit_logic,
            ),
        )
    ]
```

**_layers_explicit 标记**: 仅当数据中包含 layers 时设为 True。自动包装创建的 layers 不设置此标记，因此不会触发 MTF 模式。

### 5.3 to_json() / from_json()

```python
def to_json(self) -> str:
    return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

@classmethod
def from_json(cls, json_str: str) -> "StrategyDNA":
    return cls.from_dict(json.loads(json_str))
```

JSON 序列化使用缩进格式，ensure_ascii=False 以支持中文注释。

---

## 6. 单时间框架与多时间框架模式

### 6.1 单时间框架模式

结构:
```
StrategyDNA
  signal_genes: [SignalGene, ...]     # 所有信号在同一时间框架
  logic_genes: LogicGenes             # 组合逻辑
  execution_genes: ExecutionGenes     # 执行时间框架
  layers: None (或自动包装的单层)
```

数据流: 所有信号基因在执行时间框架的增强 DataFrame 上直接评估。

### 6.2 多时间框架模式

结构:
```
StrategyDNA
  layers: [
    TimeframeLayer(timeframe="1d", signal_genes=[...], logic_genes=...),
    TimeframeLayer(timeframe="4h", signal_genes=[...], logic_genes=...),
  ]
  cross_layer_logic: "AND"            # 跨层组合逻辑
  execution_genes: ExecutionGenes(timeframe="4h")  # 执行时间框架
```

数据流:
1. 每层在其对应时间框架的 DataFrame 上独立评估
2. 非执行时间框架的信号通过 `resample_signals()` 前向填充到执行时间框架
3. 所有层的信号通过 `cross_layer_logic` (AND/OR) 组合
4. 最终得到执行时间框架上的 entry/exit 信号

### 6.3 模式切换

MTF 模式的启用由 `is_mtf` 属性决定。创建 MTF 策略的方式:

```python
dna = StrategyDNA(
    signal_genes=[...],
    logic_genes=LogicGenes(),
    execution_genes=ExecutionGenes(timeframe="4h", symbol="BTCUSDT"),
    risk_genes=RiskGenes(),
    layers=[
        TimeframeLayer(timeframe="1d", signal_genes=[...]),
        TimeframeLayer(timeframe="4h", signal_genes=[...]),
    ],
    cross_layer_logic="AND",
)
# layers 在构造时传入 -> __post_init__ 设置 _layers_explicit=True -> is_mtf=True
```

从 JSON 反序列化时:
```python
dna = StrategyDNA.from_dict({
    "signal_genes": [...],
    "layers": [...],              # 存在 -> _layers_explicit=True
    "cross_layer_logic": "AND",
    ...
})
# is_mtf = True
```

---

## 7. 默认种子 DNA

进化任务在未提供 initial_dna 时使用默认种子:

```python
StrategyDNA(
    signal_genes=[
        SignalGene(
            indicator="EMA",
            params={"period": 20},
            role=SignalRole.ENTRY_TRIGGER,
            condition={"type": "price_above"}
        ),
        SignalGene(
            indicator="EMA",
            params={"period": 20},
            role=SignalRole.EXIT_TRIGGER,
            condition={"type": "price_below"}
        ),
    ],
    logic_genes=LogicGenes(entry_logic="AND", exit_logic="AND"),
    execution_genes=ExecutionGenes(timeframe=payload.timeframe, symbol=payload.symbol),
    risk_genes=RiskGenes(
        stop_loss=0.03,
        take_profit=0.06,
        position_size=1.0,
        leverage=payload.leverage,
        direction=payload.direction,
    ),
)
```

这是一个简单的 EMA(20) 价格穿越策略: 价格在 EMA 上方时入场，价格跌破 EMA 时出场。

---

## 8. API 层映射

API 的 Pydantic 模型 (`api/schemas.py`) 与核心 dataclass 之间的映射:

| 核心类型 | Pydantic 模型 | 差异 |
|---------|--------------|------|
| SignalGene | SignalGeneModel | field_name -> field |
| LogicGenes | LogicGenesModel | 一致 |
| ExecutionGenes | ExecutionGenesModel | 一致 |
| RiskGenes | RiskGenesModel | leverage 增加 ge=1,le=10; direction 增加 pattern 校验 |
| StrategyDNA | DNAModel | layers 为 List[dict]; strategy_id 可选 |
| TimeframeLayer | TimeframeLayerModel | 一致 |

转换函数:

```python
def _dna_model_to_dna(dna_model: DNAModel) -> StrategyDNA:
    data = dna_model.model_dump()
    return StrategyDNA.from_dict(data)
```

使用 `model_dump()` 导出为字典，再通过 `from_dict()` 转换为核心对象。
`from_dict()` 内部的自动包装逻辑确保单时间框架策略也能正确创建 layers。

---

## 9. 完整序列化示例

### 9.1 单时间框架策略

```json
{
  "strategy_id": "a1b2c3d4-...",
  "generation": 0,
  "parent_ids": [],
  "mutation_ops": [],
  "signal_genes": [
    {
      "indicator": "RSI",
      "params": {"period": 14},
      "role": "entry_trigger",
      "field": null,
      "condition": {"type": "lt", "threshold": 30}
    },
    {
      "indicator": "EMA",
      "params": {"period": 50},
      "role": "exit_trigger",
      "field": null,
      "condition": {"type": "price_below"}
    }
  ],
  "logic_genes": {
    "entry_logic": "AND",
    "exit_logic": "AND"
  },
  "execution_genes": {
    "timeframe": "4h",
    "symbol": "BTCUSDT"
  },
  "risk_genes": {
    "stop_loss": 0.05,
    "take_profit": null,
    "position_size": 0.3,
    "leverage": 1,
    "direction": "long"
  },
  "cross_layer_logic": "AND"
}
```

### 9.2 多时间框架策略

```json
{
  "strategy_id": "e5f6g7h8-...",
  "generation": 5,
  "parent_ids": ["a1b2c3d4-...", "x9y8z7w6-..."],
  "mutation_ops": ["mutate_param", "crossover"],
  "signal_genes": [],
  "logic_genes": {
    "entry_logic": "AND",
    "exit_logic": "AND"
  },
  "execution_genes": {
    "timeframe": "4h",
    "symbol": "BTCUSDT"
  },
  "risk_genes": {
    "stop_loss": 0.03,
    "take_profit": 0.06,
    "position_size": 0.5,
    "leverage": 2,
    "direction": "long"
  },
  "layers": [
    {
      "timeframe": "1d",
      "signal_genes": [
        {
          "indicator": "EMA",
          "params": {"period": 50},
          "role": "entry_guard",
          "field": null,
          "condition": {"type": "price_above"}
        }
      ],
      "logic_genes": {"entry_logic": "AND", "exit_logic": "AND"}
    },
    {
      "timeframe": "4h",
      "signal_genes": [
        {
          "indicator": "RSI",
          "params": {"period": 14},
          "role": "entry_trigger",
          "field": null,
          "condition": {"type": "lt", "threshold": 30}
        }
      ],
      "logic_genes": {"entry_logic": "AND", "exit_logic": "AND"}
    }
  ],
  "cross_layer_logic": "AND"
}
```

此策略的含义:
- 日线层 (1d): EMA(50) 作为入场 Guard，要求价格在均线上方（趋势过滤）
- 4 小时层 (4h): RSI(14) < 30 作为入场 Trigger（超卖信号）
- 跨层逻辑 AND: 两层条件同时满足才入场
