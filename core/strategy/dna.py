"""Strategy DNA data structures for BTC/ETH quantitative trading strategy evolution.

This module defines the core genetic building blocks used to represent, serialize,
and evolve trading strategies within the evolutionary optimization framework.
"""

import json
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ConditionType(Enum):
    """Comparison / relationship types used in signal conditions."""

    LT = "lt"                          # indicator < threshold
    GT = "gt"                          # indicator > threshold
    LE = "le"                          # indicator <= threshold
    GE = "ge"                          # indicator >= threshold
    CROSS_ABOVE = "cross_above"        # indicator crosses above threshold
    CROSS_BELOW = "cross_below"        # indicator crosses below threshold
    PRICE_ABOVE = "price_above"        # close price above indicator value
    PRICE_BELOW = "price_below"        # close price below indicator value
    # Phase 2: dynamic context conditions
    CROSS_ABOVE_SERIES = "cross_above_series"  # indicator A crosses above indicator B
    CROSS_BELOW_SERIES = "cross_below_series"  # indicator A crosses below indicator B
    LOOKBACK_ANY = "lookback_any"              # any bar in lookback window satisfies inner
    LOOKBACK_ALL = "lookback_all"              # all bars in lookback window satisfy inner
    # Phase 4: support/resistance conditions
    TOUCH_BOUNCE = "touch_bounce"      # price touches indicator line then bounces
    ROLE_REVERSAL = "role_reversal"    # indicator line switches support/resistance role
    WICK_TOUCH = "wick_touch"          # wick touches indicator line but close is other side


class SignalRole(Enum):
    """Role a signal gene plays within a strategy."""

    ENTRY_TRIGGER = "entry_trigger"   # directly triggers buy
    ENTRY_GUARD = "entry_guard"       # filters entry conditions
    EXIT_TRIGGER = "exit_trigger"     # directly triggers sell
    EXIT_GUARD = "exit_guard"         # filters exit conditions


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SignalGene:
    """A single signal condition derived from a technical indicator.

    Attributes:
        indicator: Name of the indicator (e.g. "RSI", "EMA", "MACD").
        params: Indicator parameters (e.g. {"period": 14}).
        role: The role this signal plays in the strategy.
        field_name: For multi-output indicators, which output to use
                    (e.g. "histogram" for MACD). ``None`` for single-output indicators.
        condition: Structured condition dict, e.g. {"type": "lt", "threshold": 30}
                   or {"type": "price_above"} (no threshold needed).
    """

    indicator: str
    params: Dict[str, Union[int, float]]
    role: SignalRole
    field_name: Optional[str] = None
    condition: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "indicator": self.indicator,
            "params": self.params,
            "role": self.role.value,
            "field": self.field_name,
            "condition": self.condition,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SignalGene":
        data = dict(data)  # shallow copy
        if isinstance(data.get("role"), str):
            data["role"] = SignalRole(data["role"])
        # Map JSON "field" to Python attribute "field_name"
        if "field" in data:
            data["field_name"] = data.pop("field")
        return cls(**{k: v for k, v in data.items() if k != "field"})


@dataclass
class LogicGenes:
    """Logical operators that combine signal genes for entry / exit decisions."""

    entry_logic: str = "AND"  # "AND" or "OR"
    exit_logic: str = "AND"   # "AND" or "OR"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "LogicGenes":
        return cls(**data)


@dataclass
class ExecutionGenes:
    """Execution-level genes: timeframe and trading symbol."""

    timeframe: str = "4h"        # "1h", "4h", "1d"
    symbol: str = "BTCUSDT"     # "BTCUSDT" or "ETHUSDT"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionGenes":
        return cls(**data)


@dataclass
class RiskGenes:
    """Risk management parameters."""

    stop_loss: float = 0.05               # e.g. 0.05 (5%)
    take_profit: Optional[float] = None   # e.g. 0.10 (10%) or None
    position_size: float = 0.3            # e.g. 0.3 (30%)
    leverage: int = 1                     # 1-10x
    direction: str = "long"               # "long" | "short"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RiskGenes":
        return cls(**data)


@dataclass
class TimeframeLayer:
    """A single timeframe layer within a multi-timeframe strategy.

    Each layer contains signal genes and logic genes evaluated
    independently on its own timeframe's data.
    """

    timeframe: str
    signal_genes: List[SignalGene] = field(default_factory=list)
    logic_genes: LogicGenes = field(default_factory=LogicGenes)

    def to_dict(self) -> dict:
        return {
            "timeframe": self.timeframe,
            "signal_genes": [sg.to_dict() for sg in self.signal_genes],
            "logic_genes": self.logic_genes.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TimeframeLayer":
        data = dict(data)
        if "signal_genes" in data and isinstance(data["signal_genes"], list):
            data["signal_genes"] = [
                SignalGene.from_dict(sg) if isinstance(sg, dict) else sg
                for sg in data["signal_genes"]
            ]
        if "logic_genes" in data and isinstance(data["logic_genes"], dict):
            data["logic_genes"] = LogicGenes.from_dict(data["logic_genes"])
        return cls(**data)


@dataclass
class StrategyDNA:
    """Complete genetic representation of a trading strategy.

    A StrategyDNA instance is the fundamental unit operated on by the
    evolutionary algorithm: selection, crossover, and mutation all work on
    this structure.

    Supports multi-timeframe (MTF) via ``layers``. For backward compatibility,
    ``signal_genes`` is available as a property proxying layers[0].
    """

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

    def __post_init__(self):
        # Auto-detect explicit layers (passed via constructor, not auto-wrap)
        if self.layers is not None:
            object.__setattr__(self, "_layers_explicit", True)

    @property
    def is_mtf(self) -> bool:
        """Whether this DNA uses multi-timeframe layers."""
        return self.layers is not None and len(self.layers) >= 1 and self._layers_explicit

    @property
    def timeframes(self) -> List[str]:
        """List of timeframes used across all layers."""
        if self.layers:
            return [layer.timeframe for layer in self.layers]
        return [self.execution_genes.timeframe]

    def _resolve_signal_genes(self) -> List[SignalGene]:
        """Resolve signal_genes from layers[0] if layers exist."""
        if self.layers and not self.signal_genes:
            return self.layers[0].signal_genes
        return self.signal_genes

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

    @classmethod
    def from_dict(cls, data: dict) -> "StrategyDNA":
        data = dict(data)  # shallow copy

        # Parse layers if present (MTF format)
        layers = None
        if "layers" in data and isinstance(data["layers"], list):
            layers = [
                TimeframeLayer.from_dict(l) if isinstance(l, dict) else l
                for l in data["layers"]
            ]
        data.pop("layers", None)

        # Parse cross_layer_logic
        cross_layer_logic = data.pop("cross_layer_logic", "AND")

        if "signal_genes" in data and isinstance(data["signal_genes"], list):
            data["signal_genes"] = [
                SignalGene.from_dict(sg) if isinstance(sg, dict) else sg
                for sg in data["signal_genes"]
            ]

        if "logic_genes" in data and isinstance(data["logic_genes"], dict):
            data["logic_genes"] = LogicGenes.from_dict(data["logic_genes"])

        if "execution_genes" in data and isinstance(data["execution_genes"], dict):
            data["execution_genes"] = ExecutionGenes.from_dict(data["execution_genes"])

        if "risk_genes" in data and isinstance(data["risk_genes"], dict):
            data["risk_genes"] = RiskGenes.from_dict(data["risk_genes"])

        if not data.get("strategy_id"):
            data["strategy_id"] = str(uuid.uuid4())

        instance = cls(**data)
        instance.layers = layers
        instance.cross_layer_logic = cross_layer_logic
        # Mark layers as explicit only if they came from the data (not auto-wrap)
        instance._layers_explicit = layers is not None

        # Auto-wrap: if no layers but has signal_genes, create a single layer
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

        return instance

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "StrategyDNA":
        return cls.from_dict(json.loads(json_str))
