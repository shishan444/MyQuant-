"""Evolution operators: 4 mutation types + crossover.

Mutation types:
1. Parameter mutation: adjust indicator parameters within valid ranges
2. Indicator replacement: swap with same-category indicator
3. Logic mutation: flip AND/OR, add/remove guard conditions
4. Risk mutation: adjust stop_loss, take_profit, position_size
"""
from __future__ import annotations

import copy
import random
import uuid
from typing import Optional

from core.strategy.dna import (
    SignalRole, SignalGene, StrategyDNA,
)
from core.strategy.validator import validate_dna
from core.features.indicators import INDICATOR_REGISTRY, get_interchangeable


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# MTF (Multi-Timeframe) Mutation Operators
# ---------------------------------------------------------------------------

# Standard timeframe hierarchy for candidate selection
_STANDARD_TIMEFRAMES = ["15m", "30m", "1h", "4h", "1d", "3d"]


def mutate_add_layer(dna: StrategyDNA, candidate_timeframes: list | None = None) -> StrategyDNA:
    """Insert a new timeframe layer with random signals.

    Picks an adjacent timeframe not already present.
    """
    if candidate_timeframes is None:
        candidate_timeframes = _STANDARD_TIMEFRAMES

    existing = set(dna.timeframes)
    candidates = [tf for tf in candidate_timeframes if tf not in existing]
    if not candidates:
        return dna

    # Pick a timeframe adjacent to existing ones
    new_tf = random.choice(candidates)

    # Create random signals for new layer
    from core.evolution.population import create_random_dna
    seed_dna = create_random_dna(timeframe=new_tf, symbol=dna.execution_genes.symbol)

    new_layer_data = {
        "timeframe": new_tf,
        "signal_genes": [sg.to_dict() for sg in seed_dna.signal_genes],
        "logic_genes": seed_dna.logic_genes.to_dict(),
    }

    data = dna.to_dict()
    data["strategy_id"] = _new_id()
    data["parent_ids"] = [dna.strategy_id]
    data["mutation_ops"] = list(dna.mutation_ops) + ["add_layer"]
    data["generation"] = dna.generation + 1

    if "layers" not in data or not data["layers"]:
        # Wrap existing signals into first layer
        data["layers"] = [{
            "timeframe": dna.execution_genes.timeframe,
            "signal_genes": data["signal_genes"],
            "logic_genes": data["logic_genes"],
        }]

    data["layers"].append(new_layer_data)
    return StrategyDNA.from_dict(data)


def mutate_remove_layer(dna: StrategyDNA) -> StrategyDNA:
    """Remove a non-execution timeframe layer (keep at least 1)."""
    if not dna.is_mtf:
        return dna

    data = dna.to_dict()
    layers = data.get("layers", [])
    if len(layers) <= 1:
        return dna

    exec_tf = data["execution_genes"]["timeframe"]
    removable = [i for i, l in enumerate(layers) if l["timeframe"] != exec_tf]
    if not removable:
        return dna

    idx = random.choice(removable)
    layers.pop(idx)

    data["strategy_id"] = _new_id()
    data["parent_ids"] = [dna.strategy_id]
    data["mutation_ops"] = list(dna.mutation_ops) + ["remove_layer"]
    data["generation"] = dna.generation + 1
    data["layers"] = layers
    return StrategyDNA.from_dict(data)


def mutate_layer_timeframe(dna: StrategyDNA, candidate_timeframes: list | None = None) -> StrategyDNA:
    """Change the timeframe of a random non-execution layer."""
    if candidate_timeframes is None:
        candidate_timeframes = _STANDARD_TIMEFRAMES

    if not dna.is_mtf:
        return dna

    data = dna.to_dict()
    layers = data.get("layers", [])
    exec_tf = data["execution_genes"]["timeframe"]
    changeable = [i for i, l in enumerate(layers) if l["timeframe"] != exec_tf]
    if not changeable:
        return dna

    idx = random.choice(changeable)
    current_tf = layers[idx]["timeframe"]
    alternatives = [tf for tf in candidate_timeframes if tf != current_tf and tf != exec_tf]
    if not alternatives:
        return dna

    layers[idx]["timeframe"] = random.choice(alternatives)

    data["strategy_id"] = _new_id()
    data["parent_ids"] = [dna.strategy_id]
    data["mutation_ops"] = list(dna.mutation_ops) + ["layer_timeframe"]
    data["generation"] = dna.generation + 1
    data["layers"] = layers
    return StrategyDNA.from_dict(data)


def mutate_cross_logic(dna: StrategyDNA) -> StrategyDNA:
    """Flip the cross-layer logic (AND <-> OR)."""
    if not dna.is_mtf:
        return dna

    data = dna.to_dict()
    current = data.get("cross_layer_logic", "AND")
    data["cross_layer_logic"] = "OR" if current == "AND" else "AND"
    data["strategy_id"] = _new_id()
    data["parent_ids"] = [dna.strategy_id]
    data["mutation_ops"] = list(dna.mutation_ops) + ["cross_logic"]
    data["generation"] = dna.generation + 1
    return StrategyDNA.from_dict(data)


def mutate_params(dna: StrategyDNA) -> StrategyDNA:
    """Mutate a random parameter in a random signal gene."""
    data = dna.to_dict()
    data["strategy_id"] = _new_id()
    data["parent_ids"] = [dna.strategy_id]
    data["mutation_ops"] = list(dna.mutation_ops) + ["param_mutation"]
    data["generation"] = dna.generation + 1

    if not data["signal_genes"]:
        return StrategyDNA.from_dict(data)

    # Pick a random signal gene with params
    candidates = [i for i, sg in enumerate(data["signal_genes"])
                  if sg.get("params")]
    if not candidates:
        return StrategyDNA.from_dict(data)

    idx = random.choice(candidates)
    gene = data["signal_genes"][idx]
    indicator = gene["indicator"]
    params = dict(gene["params"])

    if indicator in INDICATOR_REGISTRY:
        reg = INDICATOR_REGISTRY[indicator]
        param_name = random.choice(list(reg.params.keys()))
        pdef = reg.params[param_name]
        current = params.get(param_name, pdef.default)
        delta = random.choice([-1, 1]) * pdef.step * random.randint(1, 3)
        new_val = pdef.clamp(current + delta)
        params[param_name] = int(new_val) if pdef.type == "int" else float(new_val)
        gene["params"] = params

    return StrategyDNA.from_dict(data)


def mutate_indicator(dna: StrategyDNA) -> StrategyDNA:
    """Replace a random indicator with a same-category alternative."""
    data = dna.to_dict()
    data["strategy_id"] = _new_id()
    data["parent_ids"] = [dna.strategy_id]
    data["mutation_ops"] = list(dna.mutation_ops) + ["indicator_replacement"]
    data["generation"] = dna.generation + 1

    if not data["signal_genes"]:
        return StrategyDNA.from_dict(data)

    idx = random.randint(0, len(data["signal_genes"]) - 1)
    gene = data["signal_genes"][idx]
    current = gene["indicator"]

    alternatives = get_interchangeable(current)
    if not alternatives:
        return StrategyDNA.from_dict(data)

    # Filter out guard_only if this gene is a trigger
    role = gene.get("role", "entry_trigger")
    is_trigger = role.endswith("_trigger")
    if is_trigger:
        alternatives = [a for a in alternatives
                        if not INDICATOR_REGISTRY[a].guard_only]

    if not alternatives:
        return StrategyDNA.from_dict(data)

    new_indicator = random.choice(alternatives)
    reg = INDICATOR_REGISTRY[new_indicator]

    # Generate default params for new indicator
    new_params = {k: int(v.default) if v.type == "int" else float(v.default)
                  for k, v in reg.params.items()}

    # Generate a valid condition
    cond_type = random.choice(reg.supported_conditions) if reg.supported_conditions else "gt"
    condition = {"type": cond_type}
    if cond_type in ("lt", "gt", "le", "ge"):
        if new_indicator == "RSI":
            condition["threshold"] = random.choice([30, 35, 40, 60, 65, 70])
        else:
            condition["threshold"] = 0.0

    gene["indicator"] = new_indicator
    gene["params"] = new_params
    gene["field"] = None if len(reg.output_fields) == 1 else random.choice(reg.output_fields)
    gene["condition"] = condition

    return StrategyDNA.from_dict(data)


def mutate_logic(dna: StrategyDNA) -> StrategyDNA:
    """Flip AND/OR logic or add/remove a guard condition."""
    data = dna.to_dict()
    data["strategy_id"] = _new_id()
    data["parent_ids"] = [dna.strategy_id]
    data["mutation_ops"] = list(dna.mutation_ops) + ["logic_mutation"]
    data["generation"] = dna.generation + 1

    action = random.choice(["flip_entry", "flip_exit", "flip_both"])

    if action == "flip_entry" or action == "flip_both":
        current = data["logic_genes"]["entry_logic"]
        data["logic_genes"]["entry_logic"] = "OR" if current == "AND" else "AND"
    if action == "flip_exit" or action == "flip_both":
        current = data["logic_genes"]["exit_logic"]
        data["logic_genes"]["exit_logic"] = "OR" if current == "AND" else "AND"

    return StrategyDNA.from_dict(data)


def mutate_risk(dna: StrategyDNA) -> StrategyDNA:
    """Adjust risk parameters within valid ranges."""
    data = dna.to_dict()
    data["strategy_id"] = _new_id()
    data["parent_ids"] = [dna.strategy_id]
    data["mutation_ops"] = list(dna.mutation_ops) + ["risk_mutation"]
    data["generation"] = dna.generation + 1

    risk = data["risk_genes"]

    # Mutate stop_loss: range [0.005, 0.20], step 0.005
    if random.random() < 0.5:
        current = risk["stop_loss"]
        delta = random.choice([-1, 1]) * 0.005 * random.randint(1, 5)
        risk["stop_loss"] = round(max(0.005, min(0.20, current + delta)), 4)

    # Mutate position_size: range [0.10, 1.0], step 0.05
    if random.random() < 0.5:
        current = risk["position_size"]
        delta = random.choice([-1, 1]) * 0.05 * random.randint(1, 3)
        risk["position_size"] = round(max(0.10, min(1.0, current + delta)), 2)

    # Mutate take_profit
    if random.random() < 0.3:
        if risk["take_profit"] is None:
            risk["take_profit"] = round(risk["stop_loss"] * random.uniform(1.5, 3.0), 4)
        else:
            delta = random.choice([-1, 1]) * 0.01 * random.randint(1, 3)
            risk["take_profit"] = round(
                max(risk["stop_loss"] + 0.005, risk["take_profit"] + delta), 4
            )

    data["risk_genes"] = risk
    return StrategyDNA.from_dict(data)


def crossover(parent_a: StrategyDNA, parent_b: StrategyDNA) -> StrategyDNA:
    """Create offspring by combining genes from two parents.

    Mixes signal_genes, logic_genes, and risk_genes from both parents.
    """
    child_signals = []
    # Take some genes from each parent
    a_genes = parent_a.signal_genes
    b_genes = parent_b.signal_genes

    # Mix: take entry from one, exit from other
    entry_a = [g for g in a_genes if g.role in (SignalRole.ENTRY_TRIGGER, SignalRole.ENTRY_GUARD)]
    exit_b = [g for g in b_genes if g.role in (SignalRole.EXIT_TRIGGER, SignalRole.EXIT_GUARD)]

    child_signals.extend(entry_a if entry_a else [a_genes[0]] if a_genes else [])
    child_signals.extend(exit_b if exit_b else [b_genes[-1]] if b_genes else [])

    if not child_signals:
        child_signals = list(a_genes)

    # Logic from random parent
    logic = random.choice([parent_a.logic_genes, parent_b.logic_genes])
    # Risk from random parent
    risk = random.choice([parent_a.risk_genes, parent_b.risk_genes])

    child = StrategyDNA(
        signal_genes=child_signals,
        logic_genes=logic,
        risk_genes=risk,
        execution_genes=parent_a.execution_genes,
        parent_ids=[parent_a.strategy_id, parent_b.strategy_id],
        mutation_ops=["crossover"],
        generation=max(parent_a.generation, parent_b.generation) + 1,
    )
    return child
