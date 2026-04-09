"""Tests for Strategy DNA data structure."""
import json
import pytest
from MyQuant.core.strategy.dna import (
    ConditionType,
    SignalRole,
    SignalGene,
    LogicGenes,
    ExecutionGenes,
    RiskGenes,
    StrategyDNA,
)


class TestConditionType:
    """ConditionType enum tests."""

    def test_all_condition_types_defined(self):
        assert len(ConditionType) == 8

    def test_condition_values(self):
        assert ConditionType.LT.value == "lt"
        assert ConditionType.GT.value == "gt"
        assert ConditionType.LE.value == "le"
        assert ConditionType.GE.value == "ge"
        assert ConditionType.CROSS_ABOVE.value == "cross_above"
        assert ConditionType.CROSS_BELOW.value == "cross_below"
        assert ConditionType.PRICE_ABOVE.value == "price_above"
        assert ConditionType.PRICE_BELOW.value == "price_below"


class TestSignalRole:
    """SignalRole enum tests."""

    def test_all_roles_defined(self):
        assert len(SignalRole) == 4

    def test_role_values(self):
        assert SignalRole.ENTRY_TRIGGER.value == "entry_trigger"
        assert SignalRole.ENTRY_GUARD.value == "entry_guard"
        assert SignalRole.EXIT_TRIGGER.value == "exit_trigger"
        assert SignalRole.EXIT_GUARD.value == "exit_guard"


class TestSignalGene:
    """SignalGene dataclass tests."""

    def test_create_basic_signal(self):
        gene = SignalGene(
            indicator="RSI",
            params={"period": 14},
            role=SignalRole.ENTRY_TRIGGER,
            field_name=None,
            condition={"type": "lt", "threshold": 30},
        )
        assert gene.indicator == "RSI"
        assert gene.params == {"period": 14}
        assert gene.role == SignalRole.ENTRY_TRIGGER
        assert gene.field_name is None
        assert gene.condition == {"type": "lt", "threshold": 30}

    def test_create_multi_output_signal(self):
        gene = SignalGene(
            indicator="MACD",
            params={"fast": 12, "slow": 26, "signal": 9},
            role=SignalRole.ENTRY_TRIGGER,
            field_name="histogram",
            condition={"type": "cross_above", "threshold": 0},
        )
        assert gene.field_name == "histogram"

    def test_to_dict(self):
        gene = SignalGene(
            indicator="EMA",
            params={"period": 100},
            role=SignalRole.ENTRY_GUARD,
            field_name=None,
            condition={"type": "price_above"},
        )
        d = gene.to_dict()
        assert d["indicator"] == "EMA"
        assert d["role"] == "entry_guard"
        assert d["field"] is None  # JSON uses "field" not "field_name"
        assert d["condition"] == {"type": "price_above"}

    def test_from_dict(self):
        d = {
            "indicator": "RSI",
            "params": {"period": 14},
            "role": "entry_trigger",
            "field": None,
            "condition": {"type": "lt", "threshold": 30},
        }
        gene = SignalGene.from_dict(d)
        assert gene.indicator == "RSI"
        assert gene.role == SignalRole.ENTRY_TRIGGER


class TestStrategyDNA:
    """StrategyDNA full structure tests."""

    @pytest.fixture
    def sample_dna(self):
        return StrategyDNA(
            strategy_id="test-001",
            generation=0,
            parent_ids=[],
            mutation_ops=[],
            signal_genes=[
                SignalGene("RSI", {"period": 14}, SignalRole.ENTRY_TRIGGER, None,
                           {"type": "lt", "threshold": 30}),
                SignalGene("EMA", {"period": 100}, SignalRole.ENTRY_GUARD, None,
                           {"type": "price_above"}),
                SignalGene("RSI", {"period": 14}, SignalRole.EXIT_TRIGGER, None,
                           {"type": "gt", "threshold": 70}),
            ],
            logic_genes=LogicGenes(entry_logic="AND", exit_logic="OR"),
            execution_genes=ExecutionGenes(timeframe="4h", symbol="BTCUSDT"),
            risk_genes=RiskGenes(stop_loss=0.05, take_profit=None, position_size=0.3),
        )

    def test_dna_creation(self, sample_dna):
        assert sample_dna.strategy_id == "test-001"
        assert sample_dna.generation == 0
        assert len(sample_dna.signal_genes) == 3

    def test_to_dict_roundtrip(self, sample_dna):
        d = sample_dna.to_dict()
        restored = StrategyDNA.from_dict(d)
        assert restored.strategy_id == sample_dna.strategy_id
        assert len(restored.signal_genes) == len(sample_dna.signal_genes)
        assert restored.logic_genes.entry_logic == "AND"
        assert restored.risk_genes.stop_loss == 0.05

    def test_to_json_roundtrip(self, sample_dna):
        json_str = sample_dna.to_json()
        restored = StrategyDNA.from_json(json_str)
        assert restored.strategy_id == sample_dna.strategy_id
        assert restored.generation == sample_dna.generation

    def test_json_is_valid_structure(self, sample_dna):
        json_str = sample_dna.to_json()
        parsed = json.loads(json_str)
        assert "strategy_id" in parsed
        assert "signal_genes" in parsed
        assert "logic_genes" in parsed
        assert "execution_genes" in parsed
        assert "risk_genes" in parsed

    def test_default_values(self):
        dna = StrategyDNA(
            signal_genes=[],
            logic_genes=LogicGenes(entry_logic="AND", exit_logic="OR"),
            execution_genes=ExecutionGenes(timeframe="4h", symbol="BTCUSDT"),
            risk_genes=RiskGenes(stop_loss=0.05, take_profit=None, position_size=0.3),
        )
        assert dna.generation == 0
        assert dna.parent_ids == []
        assert dna.mutation_ops == []
        assert dna.strategy_id  # auto-generated UUID should be non-empty
