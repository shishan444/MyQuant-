"""Population initialization and random DNA generation."""
from __future__ import annotations

import random
import uuid
from typing import List, Optional

from MyQuant.core.strategy.dna import (
    SignalRole, SignalGene, LogicGenes, RiskGenes, ExecutionGenes, StrategyDNA,
)
from MyQuant.core.strategy.validator import validate_dna
from MyQuant.core.features.indicators import INDICATOR_REGISTRY
from MyQuant.core.evolution.operators import mutate_params, mutate_indicator, mutate_logic, mutate_risk


def create_random_dna(
    timeframe: str = "4h",
    symbol: str = "BTCUSDT",
) -> StrategyDNA:
    """Generate a completely random but valid StrategyDNA."""
    # Pick random indicators for entry and exit
    # Filter to trigger-capable indicators
    trigger_indicators = [
        name for name, defn in INDICATOR_REGISTRY.items()
        if not defn.guard_only
    ]
    all_indicators = list(INDICATOR_REGISTRY.keys())

    def _make_signal(role: SignalRole, indicator_pool: list) -> SignalGene:
        indicator_name = random.choice(indicator_pool)
        reg = INDICATOR_REGISTRY[indicator_name]

        # Random params
        params = {}
        for pname, pdef in reg.params.items():
            val = random.uniform(pdef.min, pdef.max)
            params[pname] = int(round(val / pdef.step) * pdef.step) if pdef.type == "int" \
                else round(round(val / pdef.step) * pdef.step, 2)

        # Random condition
        cond_type = random.choice(reg.supported_conditions)
        condition = {"type": cond_type}
        if cond_type in ("lt", "gt", "le", "ge"):
            if indicator_name == "RSI":
                condition["threshold"] = random.choice([25, 30, 35, 40, 60, 65, 70, 75])
            else:
                condition["threshold"] = round(random.uniform(-1, 1), 2)

        field_name = None
        if len(reg.output_fields) > 1:
            field_name = random.choice(reg.output_fields)

        return SignalGene(
            indicator=indicator_name,
            params=params,
            role=role,
            field_name=field_name,
            condition=condition,
        )

    # Build signal genes: at least 1 entry trigger + 1 exit trigger
    signals = []
    signals.append(_make_signal(SignalRole.ENTRY_TRIGGER, trigger_indicators))

    # Optionally add entry guard
    if random.random() < 0.5:
        signals.append(_make_signal(SignalRole.ENTRY_GUARD, all_indicators))

    signals.append(_make_signal(SignalRole.EXIT_TRIGGER, trigger_indicators))

    # Optionally add exit guard
    if random.random() < 0.4:
        signals.append(_make_signal(SignalRole.EXIT_GUARD, all_indicators))

    # Random logic
    entry_logic = random.choice(["AND", "OR"])
    exit_logic = random.choice(["AND", "OR"])

    # Random risk
    stop_loss = round(random.uniform(0.01, 0.15), 4)
    position_size = round(random.uniform(0.10, 0.60), 2)
    take_profit = None

    dna = StrategyDNA(
        signal_genes=signals,
        logic_genes=LogicGenes(entry_logic=entry_logic, exit_logic=exit_logic),
        execution_genes=ExecutionGenes(timeframe=timeframe, symbol=symbol),
        risk_genes=RiskGenes(stop_loss=stop_loss, take_profit=take_profit,
                             position_size=position_size),
    )

    # Validate and retry if needed
    result = validate_dna(dna)
    if not result.is_valid:
        # Fallback to a simple valid strategy
        dna = StrategyDNA(
            signal_genes=[
                SignalGene("RSI", {"period": 14}, SignalRole.ENTRY_TRIGGER, None,
                           {"type": "lt", "threshold": 30}),
                SignalGene("RSI", {"period": 14}, SignalRole.EXIT_TRIGGER, None,
                           {"type": "gt", "threshold": 70}),
            ],
            logic_genes=LogicGenes(entry_logic="AND", exit_logic="OR"),
            risk_genes=RiskGenes(stop_loss=0.05, position_size=0.3),
            execution_genes=ExecutionGenes(timeframe=timeframe, symbol=symbol),
        )

    return dna


def init_population(
    size: int = 15,
    ancestor: Optional[StrategyDNA] = None,
    timeframe: str = "4h",
    symbol: str = "BTCUSDT",
) -> List[StrategyDNA]:
    """Initialize population by mutating an ancestor.

    Args:
        size: Population size.
        ancestor: Initial strategy (first individual).
        timeframe: K-line timeframe.
        symbol: Trading pair.

    Returns:
        List of StrategyDNA individuals.
    """
    population = []

    # First individual is the ancestor itself
    if ancestor is not None:
        population.append(ancestor)
    else:
        population.append(create_random_dna(timeframe, symbol))

    # Generate rest by mutating the ancestor
    mutation_funcs = [mutate_params, mutate_indicator, mutate_logic, mutate_risk]

    while len(population) < size:
        parent = random.choice(population[:min(len(population), 5)])
        mut_func = random.choice(mutation_funcs)
        try:
            child = mut_func(parent)
            result = validate_dna(child)
            if result.is_valid:
                population.append(child)
            else:
                population.append(create_random_dna(timeframe, symbol))
        except Exception:
            population.append(create_random_dna(timeframe, symbol))

    return population
