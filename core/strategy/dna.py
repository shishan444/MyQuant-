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

    LT = "lt"                      # indicator < threshold
    GT = "gt"                      # indicator > threshold
    LE = "le"                      # indicator <= threshold
    GE = "ge"                      # indicator >= threshold
    CROSS_ABOVE = "cross_above"    # indicator crosses above threshold
    CROSS_BELOW = "cross_below"    # indicator crosses below threshold
    PRICE_ABOVE = "price_above"    # close price above indicator value
    PRICE_BELOW = "price_below"    # close price below indicator value


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

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RiskGenes":
        return cls(**data)


@dataclass
class StrategyDNA:
    """Complete genetic representation of a trading strategy.

    A StrategyDNA instance is the fundamental unit operated on by the
    evolutionary algorithm: selection, crossover, and mutation all work on
    this structure.
    """

    signal_genes: List[SignalGene] = field(default_factory=list)
    logic_genes: LogicGenes = field(default_factory=LogicGenes)
    execution_genes: ExecutionGenes = field(default_factory=ExecutionGenes)
    risk_genes: RiskGenes = field(default_factory=RiskGenes)
    strategy_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    generation: int = 0
    parent_ids: List[str] = field(default_factory=list)
    mutation_ops: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "generation": self.generation,
            "parent_ids": self.parent_ids,
            "mutation_ops": self.mutation_ops,
            "signal_genes": [sg.to_dict() for sg in self.signal_genes],
            "logic_genes": self.logic_genes.to_dict(),
            "execution_genes": self.execution_genes.to_dict(),
            "risk_genes": self.risk_genes.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StrategyDNA":
        data = dict(data)  # shallow copy

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

        return cls(**data)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "StrategyDNA":
        return cls.from_dict(json.loads(json_str))
