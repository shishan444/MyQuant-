"""Tests for MTF engine evolution operator adaptations (Phase N1)."""

import random

import pytest

from core.strategy.dna import (
    StrategyDNA, TimeframeLayer, SignalGene, SignalRole,
    LogicGenes, ExecutionGenes, RiskGenes, derive_role,
)
from core.evolution.operators import (
    mutate_add_layer, mutate_remove_layer, crossover,
    mutate_params, mutate_indicator,
)


def _make_mtf_dna(mtf_mode="direction+confluence") -> StrategyDNA:
    """Create a simple MTF DNA for testing."""
    return StrategyDNA(
        signal_genes=[
            SignalGene("RSI", {"period": 14}, SignalRole.ENTRY_TRIGGER,
                       condition={"type": "gt", "threshold": 50}),
            SignalGene("RSI", {"period": 14}, SignalRole.EXIT_TRIGGER,
                       condition={"type": "lt", "threshold": 50}),
        ],
        logic_genes=LogicGenes(entry_logic="AND", exit_logic="AND"),
        execution_genes=ExecutionGenes(timeframe="15m", symbol="BTCUSDT"),
        risk_genes=RiskGenes(stop_loss=0.05, direction="long"),
        layers=[
            TimeframeLayer(
                timeframe="1d",
                signal_genes=[
                    SignalGene("EMA", {"period": 20}, SignalRole.ENTRY_TRIGGER,
                               condition={"type": "price_above"}),
                    SignalGene("EMA", {"period": 20}, SignalRole.EXIT_TRIGGER,
                               condition={"type": "price_below"}),
                ],
                role="structure",
            ),
            TimeframeLayer(
                timeframe="4h",
                signal_genes=[
                    SignalGene("BB", {"period": 20, "std": 2.0}, SignalRole.ENTRY_TRIGGER,
                               condition={"type": "price_above"}),
                    SignalGene("BB", {"period": 20, "std": 2.0}, SignalRole.EXIT_TRIGGER,
                               condition={"type": "price_below"}),
                ],
                role="zone",
            ),
            TimeframeLayer(
                timeframe="15m",
                signal_genes=[
                    SignalGene("RSI", {"period": 14}, SignalRole.ENTRY_TRIGGER,
                               condition={"type": "gt", "threshold": 50}),
                    SignalGene("RSI", {"period": 14}, SignalRole.EXIT_TRIGGER,
                               condition={"type": "lt", "threshold": 50}),
                ],
                role="execution",
            ),
        ],
        mtf_mode=mtf_mode,
        confluence_threshold=0.3,
        proximity_mult=1.5,
    )


class TestMutateAddLayerRoleAware:
    """mutate_add_layer should derive role from timeframe."""

    def test_mutate_add_layer_derives_role_from_timeframe(self):
        """Adding a layer should derive role based on timeframe."""
        random.seed(42)
        dna = _make_mtf_dna()
        # Remove the 4h layer so we have room
        dna_data = dna.to_dict()
        dna_data["layers"] = [dna_data["layers"][0], dna_data["layers"][2]]  # 1d + 15m
        dna = StrategyDNA.from_dict(dna_data)

        # Try adding layers with different timeframes
        for tf in ["4h", "1h", "30m"]:
            mutated = mutate_add_layer(dna, candidate_timeframes=[tf])
            if mutated.strategy_id != dna.strategy_id:
                # Mutation happened
                new_layer = None
                for layer in mutated.layers:
                    if layer.timeframe == tf:
                        new_layer = layer
                        break
                if new_layer:
                    expected_role = derive_role(tf)
                    assert new_layer.role == expected_role, \
                        f"Layer {tf} should have role '{expected_role}', got '{new_layer.role}'"

    def test_mutate_add_layer_preserves_role_diversity(self):
        """After multiple mutations, layers should have diverse roles."""
        random.seed(123)
        # Start with minimal DNA
        dna = StrategyDNA(
            signal_genes=[
                SignalGene("RSI", {"period": 14}, SignalRole.ENTRY_TRIGGER,
                           condition={"type": "gt", "threshold": 50}),
                SignalGene("RSI", {"period": 14}, SignalRole.EXIT_TRIGGER,
                           condition={"type": "lt", "threshold": 50}),
            ],
            execution_genes=ExecutionGenes(timeframe="15m"),
        )
        roles_seen = set()
        for _ in range(50):
            mutated = mutate_add_layer(dna)
            if mutated.strategy_id != dna.strategy_id:
                for layer in mutated.layers:
                    if layer.role:
                        roles_seen.add(layer.role)
                if len(roles_seen) >= 2:
                    break
        assert len(roles_seen) >= 2, f"Expected diverse roles, got: {roles_seen}"


class TestNewMutationOperators:
    """New MTF parameter mutation operators."""

    def test_mutate_mtf_mode_cycles_modes(self):
        """mutate_mtf_mode should cycle through valid modes."""
        from core.evolution.operators import mutate_mtf_mode
        random.seed(42)
        dna = _make_mtf_dna("direction")
        mutated = mutate_mtf_mode(dna)
        assert mutated.mtf_mode != "direction"
        assert mutated.mtf_mode in ("confluence", "direction+confluence", None)

    def test_mutate_confluence_threshold_in_range(self):
        """mutate_confluence_threshold should stay in [0.1, 0.9]."""
        from core.evolution.operators import mutate_confluence_threshold
        random.seed(42)
        dna = _make_mtf_dna()
        for _ in range(50):
            mutated = mutate_confluence_threshold(dna)
            assert 0.1 <= mutated.confluence_threshold <= 0.9, \
                f"confluence_threshold {mutated.confluence_threshold} out of range"

    def test_mutate_proximity_mult_in_range(self):
        """mutate_proximity_mult should stay in [0.5, 3.0]."""
        from core.evolution.operators import mutate_proximity_mult
        random.seed(42)
        dna = _make_mtf_dna()
        for _ in range(50):
            mutated = mutate_proximity_mult(dna)
            assert 0.5 <= mutated.proximity_mult <= 3.0, \
                f"proximity_mult {mutated.proximity_mult} out of range"


class TestCrossoverRolePreservation:
    """Crossover should handle new roles correctly."""

    def test_crossover_preserves_structure_role(self):
        """Crossover should preserve structure role from parents."""
        random.seed(42)
        parent_a = _make_mtf_dna()
        parent_b = _make_mtf_dna()
        child = crossover(parent_a, parent_b)
        # Child should inherit some layers with structure role
        roles = [layer.role for layer in child.layers] if child.layers else []
        assert "structure" in roles, f"Expected structure role in child, got: {roles}"

    def test_crossover_preserves_zone_role(self):
        """Crossover should preserve zone role from parents."""
        random.seed(42)
        parent_a = _make_mtf_dna()
        parent_b = _make_mtf_dna()
        child = crossover(parent_a, parent_b)
        roles = [layer.role for layer in child.layers] if child.layers else []
        assert "zone" in roles, f"Expected zone role in child, got: {roles}"

    def test_crossover_handles_different_mtf_modes(self):
        """Crossover with different mtf_mode parents should produce valid child."""
        random.seed(42)
        parent_a = _make_mtf_dna("direction")
        parent_b = _make_mtf_dna("confluence")
        child = crossover(parent_a, parent_b)
        assert child.mtf_mode in ("direction", "confluence", "direction+confluence", None)


class TestCreateRandomMTFDNA:
    """Random MTF DNA should have valid roles."""

    def test_create_random_mtf_dna_has_valid_roles(self):
        """Random DNA should have valid roles on layers."""
        from core.evolution.population import create_random_mtf_layer
        random.seed(42)
        for tf in ["1d", "4h", "1h", "15m", "30m"]:
            layer = create_random_mtf_layer(tf)
            assert layer.role in ("structure", "zone", "execution", None), \
                f"Invalid role '{layer.role}' for timeframe '{tf}'"

    def test_create_random_mtf_dna_role_diversity(self):
        """Creating layers for different timeframes should produce diverse roles."""
        from core.evolution.population import create_random_mtf_layer
        random.seed(42)
        roles = set()
        for tf in ["1d", "4h", "1h", "15m"]:
            layer = create_random_mtf_layer(tf)
            if layer.role:
                roles.add(layer.role)
        assert len(roles) >= 2, f"Expected diverse roles, got: {roles}"


class TestEvolutionRegression:
    """Existing evolution operators should still work."""

    def test_existing_mutation_operators_work(self):
        """Standard mutation operators should work with MTF DNA."""
        random.seed(42)
        dna = _make_mtf_dna()
        # These should not raise
        mutated = mutate_params(dna)
        assert isinstance(mutated, StrategyDNA)
        mutated = mutate_indicator(dna)
        assert isinstance(mutated, StrategyDNA)

    def test_crossover_produces_valid_dna(self):
        """Crossover should produce valid DNA."""
        random.seed(42)
        parent_a = _make_mtf_dna()
        parent_b = _make_mtf_dna()
        child = crossover(parent_a, parent_b)
        assert isinstance(child, StrategyDNA)
        assert child.layers is not None
        assert len(child.layers) > 0
