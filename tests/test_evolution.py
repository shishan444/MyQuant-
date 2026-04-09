"""Tests for evolution engine: operators, population, diversity, lineage, early stopping."""
import pytest
import numpy as np

from MyQuant.core.strategy.dna import (
    SignalRole, SignalGene, LogicGenes, RiskGenes, ExecutionGenes, StrategyDNA,
)
from MyQuant.core.strategy.validator import validate_dna
from MyQuant.core.evolution.operators import (
    mutate_params, mutate_indicator, mutate_logic, mutate_risk, crossover,
)
from MyQuant.core.evolution.population import create_random_dna, init_population
from MyQuant.core.evolution.diversity import compute_diversity, inject_fresh_blood
from MyQuant.core.evolution.lineage import record_mutation, get_lineage
from MyQuant.core.evolution.engine import EarlyStopChecker, EvolutionEngine


def _make_simple_dna() -> StrategyDNA:
    return StrategyDNA(
        signal_genes=[
            SignalGene("RSI", {"period": 14}, SignalRole.ENTRY_TRIGGER, None,
                       {"type": "lt", "threshold": 30}),
            SignalGene("EMA", {"period": 50}, SignalRole.ENTRY_GUARD, None,
                       {"type": "price_above"}),
            SignalGene("RSI", {"period": 14}, SignalRole.EXIT_TRIGGER, None,
                       {"type": "gt", "threshold": 70}),
        ],
        logic_genes=LogicGenes(entry_logic="AND", exit_logic="OR"),
        risk_genes=RiskGenes(stop_loss=0.05, take_profit=None, position_size=0.3),
        strategy_id="test-parent",
        generation=0,
    )


class TestMutateParams:
    def test_changes_a_parameter(self):
        dna = _make_simple_dna()
        mutated = mutate_params(dna)
        # At least something should be different (high probability)
        assert mutated.strategy_id != dna.strategy_id
        assert mutated.parent_ids == [dna.strategy_id]

    def test_preserves_structure(self):
        dna = _make_simple_dna()
        mutated = mutate_params(dna)
        assert len(mutated.signal_genes) == len(dna.signal_genes)
        result = validate_dna(mutated)
        assert result.is_valid, f"Mutated DNA invalid: {result.errors}"

    def test_multiple_mutations_still_valid(self):
        dna = _make_simple_dna()
        for _ in range(10):
            dna = mutate_params(dna)
            result = validate_dna(dna)
            assert result.is_valid, f"After mutation: {result.errors}"


class TestMutateIndicator:
    def test_replaces_an_indicator(self):
        dna = _make_simple_dna()
        mutated = mutate_indicator(dna)
        assert mutated.strategy_id != dna.strategy_id
        result = validate_dna(mutated)
        assert result.is_valid, f"Mutated DNA invalid: {result.errors}"


class TestMutateLogic:
    def test_changes_logic(self):
        dna = _make_simple_dna()
        mutated = mutate_logic(dna)
        assert mutated.strategy_id != dna.strategy_id

    def test_logic_values_valid(self):
        dna = _make_simple_dna()
        for _ in range(20):
            mutated = mutate_logic(dna)
            assert mutated.logic_genes.entry_logic in ("AND", "OR")
            assert mutated.logic_genes.exit_logic in ("AND", "OR")


class TestMutateRisk:
    def test_changes_risk_params(self):
        dna = _make_simple_dna()
        mutated = mutate_risk(dna)
        result = validate_dna(mutated)
        assert result.is_valid, f"Risk mutation invalid: {result.errors}"

    def test_risk_stays_in_range(self):
        dna = _make_simple_dna()
        for _ in range(20):
            dna = mutate_risk(dna)
            assert 0.005 <= dna.risk_genes.stop_loss <= 0.20
            assert 0.10 <= dna.risk_genes.position_size <= 1.0


class TestCrossover:
    def test_produces_valid_offspring(self):
        parent_a = _make_simple_dna()
        parent_b = create_random_dna()
        child = crossover(parent_a, parent_b)
        result = validate_dna(child)
        assert result.is_valid, f"Crossover child invalid: {result.errors}"

    def test_child_has_both_parents(self):
        parent_a = _make_simple_dna()
        parent_b = create_random_dna()
        child = crossover(parent_a, parent_b)
        assert parent_a.strategy_id in child.parent_ids
        assert parent_b.strategy_id in child.parent_ids


class TestPopulation:
    def test_creates_population_of_size(self):
        pop = init_population(size=15, ancestor=_make_simple_dna())
        assert len(pop) == 15

    def test_all_individuals_valid(self):
        pop = init_population(size=10, ancestor=_make_simple_dna())
        for ind in pop:
            result = validate_dna(ind)
            assert result.is_valid, f"Individual invalid: {result.errors}"

    def test_random_dna_is_valid(self):
        dna = create_random_dna()
        result = validate_dna(dna)
        assert result.is_valid, f"Random DNA invalid: {result.errors}"

    def test_random_dna_has_entry_and_exit(self):
        dna = create_random_dna()
        entry_roles = {SignalRole.ENTRY_TRIGGER, SignalRole.ENTRY_GUARD}
        exit_roles = {SignalRole.EXIT_TRIGGER, SignalRole.EXIT_GUARD}
        has_entry = any(g.role in entry_roles for g in dna.signal_genes)
        has_exit = any(g.role in exit_roles for g in dna.signal_genes)
        assert has_entry, "Random DNA missing entry signal"
        assert has_exit, "Random DNA missing exit signal"


class TestDiversity:
    def test_compute_diversity_returns_float(self):
        pop = init_population(size=10, ancestor=_make_simple_dna())
        div = compute_diversity(pop)
        assert isinstance(div, float)
        assert 0 <= div <= 1.0

    def test_identical_population_low_diversity(self):
        dna = _make_simple_dna()
        pop = [dna for _ in range(10)]
        div = compute_diversity(pop)
        assert div <= 0.1

    def test_inject_fresh_blood_increases_size(self):
        pop = init_population(size=10, ancestor=_make_simple_dna())
        original_size = len(pop)
        pop = inject_fresh_blood(pop, n=2)
        assert len(pop) == original_size + 2


class TestLineage:
    def test_record_mutation(self):
        dna = _make_simple_dna()
        dna = record_mutation(dna, "RSI_period_14->21")
        assert "RSI_period_14->21" in dna.mutation_ops

    def test_get_lineage(self):
        dna = _make_simple_dna()
        dna = record_mutation(dna, "mut_1")
        lineage = get_lineage(dna)
        assert isinstance(lineage, list)
        assert len(lineage) == 1


class TestEarlyStopChecker:
    def test_target_reached(self):
        checker = EarlyStopChecker(target_score=80.0)
        action, reason = checker.check(85.0, 1)
        assert action == "stop"
        assert reason == "target_reached"

    def test_stagnation(self):
        checker = EarlyStopChecker(target_score=100.0, patience=3, min_improvement=0.5)
        checker.check(50.0, 1)
        checker.check(50.2, 2)
        checker.check(50.3, 3)
        action, reason = checker.check(50.3, 4)
        assert action == "stop"
        assert reason == "stagnation"

    def test_continue_when_improving(self):
        checker = EarlyStopChecker(target_score=100.0, patience=5)
        action, _ = checker.check(50.0, 1)
        assert action == "continue"
        action, _ = checker.check(55.0, 2)
        assert action == "continue"

    def test_max_generations(self):
        checker = EarlyStopChecker(target_score=100.0, max_generations=5)
        for gen in range(4):
            action, _ = checker.check(50.0 + gen, gen)
            assert action == "continue"
        action, reason = checker.check(54.0, 5)
        assert action == "stop"
        assert reason == "max_generations"

    def test_decline(self):
        checker = EarlyStopChecker(target_score=100.0, decline_limit=3)
        checker.check(60.0, 1)
        action, _ = checker.check(59.0, 2)
        assert action == "continue"
        action, _ = checker.check(58.0, 3)
        assert action == "continue"
        action, reason = checker.check(57.0, 4)
        assert action == "stop"
        assert reason == "decline"
