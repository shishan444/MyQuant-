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
from core.features.registry import IndicatorDef


def _new_id() -> str:
    return str(uuid.uuid4())


def _pick_signal_pool(data: dict) -> dict:
    """Pick a signal gene pool to mutate: base signal_genes or a random MTF layer.

    Returns a dict with a mutable reference to the gene list:
      {"genes": <list>}
    For base: data["signal_genes"]
    For layer: data["layers"][i]["signal_genes"]
    """
    layers = data.get("layers")
    if not layers:
        return {"genes": data["signal_genes"]}

    # 50% chance base, 50% split among layers
    n_targets = 1 + len(layers)  # base + each layer
    choice = random.randint(0, n_targets - 1)
    if choice == 0:
        return {"genes": data["signal_genes"]}
    else:
        layer_idx = choice - 1
        return {"genes": layers[layer_idx]["signal_genes"]}


def generate_random_condition(
    indicator_name: str,
    reg: IndicatorDef | None = None,
    df_columns: list | None = None,
) -> dict:
    """Generate a random condition dict for a given indicator.

    Handles both legacy (8 types) and new condition types (cross_above_series,
    lookback_any, lookback_all, touch_bounce, role_reversal, wick_touch).

    Args:
        indicator_name: Name of the indicator.
        reg: IndicatorDef from registry (fetched if None).
        df_columns: Optional list of available DataFrame columns (unused for now).
    """
    if reg is None:
        reg = INDICATOR_REGISTRY.get(indicator_name)
    if reg is None or not reg.supported_conditions:
        return {"type": "gt", "threshold": 0.0}

    cond_type = random.choice(reg.supported_conditions)
    condition: dict = {"type": cond_type}

    if cond_type in ("lt", "gt", "le", "ge"):
        if indicator_name == "RSI":
            condition["threshold"] = random.choice([25, 30, 35, 40, 60, 65, 70, 75])
        else:
            condition["threshold"] = round(random.uniform(-1, 1), 2)
    elif cond_type == "cross_above_series":
        # Pick a target indicator from same category or trend category
        target = _pick_series_target(indicator_name, reg)
        condition["target_indicator"] = target
        target_reg = INDICATOR_REGISTRY.get(target)
        if target_reg and target_reg.params:
            condition["target_params"] = {
                k: int(v.default) if v.type == "int" else float(v.default)
                for k, v in target_reg.params.items()
            }
        else:
            condition["target_params"] = {}
    elif cond_type == "cross_below_series":
        target = _pick_series_target(indicator_name, reg)
        condition["target_indicator"] = target
        target_reg = INDICATOR_REGISTRY.get(target)
        if target_reg and target_reg.params:
            condition["target_params"] = {
                k: int(v.default) if v.type == "int" else float(v.default)
                for k, v in target_reg.params.items()
            }
        else:
            condition["target_params"] = {}
    elif cond_type in ("lookback_any", "lookback_all"):
        window = random.choice([3, 5, 8, 10])
        # Generate a simple inner condition
        inner_types = ["price_above", "price_below", "gt", "lt"]
        inner_type = random.choice(inner_types)
        inner: dict = {"type": inner_type}
        if inner_type in ("lt", "gt"):
            inner["threshold"] = round(random.uniform(-1, 1), 2)
            if inner_type == "gt":
                inner["threshold"] = random.choice([0.0, 0.5, 1.0])
            else:
                inner["threshold"] = random.choice([0.0, -0.5, -1.0])
        condition["window"] = window
        condition["inner"] = inner
    elif cond_type == "touch_bounce":
        condition["direction"] = random.choice(["support", "resistance"])
        condition["proximity_pct"] = random.choice([0.005, 0.01, 0.02])
        condition["bounce_pct"] = random.choice([0.003, 0.005, 0.01])
    elif cond_type == "role_reversal":
        condition["role"] = random.choice(["support", "resistance"])
        condition["lookback"] = random.choice([5, 10, 15, 20])
    elif cond_type == "wick_touch":
        condition["direction"] = random.choice(["above", "below"])
        condition["proximity_pct"] = random.choice([0.005, 0.01, 0.02])

    return condition


def _pick_series_target(indicator_name: str, reg: IndicatorDef) -> str:
    """Pick a suitable target indicator for cross_above/below_series."""
    # Prefer same-category indicators
    same_cat = get_interchangeable(indicator_name)
    # Also add trend indicators as common targets
    trend_indicators = [name for name, d in INDICATOR_REGISTRY.items()
                        if d.category == "trend" and name != indicator_name]
    candidates = same_cat + trend_indicators
    # Remove guard_only
    candidates = [c for c in candidates if not INDICATOR_REGISTRY.get(c, IndicatorDef("", {}, [], [], guard_only=True)).guard_only]
    if not candidates:
        return "EMA"
    return random.choice(candidates)


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
    """Mutate a random parameter in a random signal gene (base or MTF layer)."""
    data = dna.to_dict()
    data["strategy_id"] = _new_id()
    data["parent_ids"] = [dna.strategy_id]
    data["mutation_ops"] = list(dna.mutation_ops) + ["param_mutation"]
    data["generation"] = dna.generation + 1

    # Pick which signal gene pool to mutate: base or a random layer
    gene_pool = _pick_signal_pool(data)

    if not gene_pool["genes"]:
        return StrategyDNA.from_dict(data)

    # Pick a random signal gene with params
    candidates = [i for i, sg in enumerate(gene_pool["genes"])
                  if sg.get("params")]
    if not candidates:
        return StrategyDNA.from_dict(data)

    idx = random.choice(candidates)
    gene = gene_pool["genes"][idx]
    indicator = gene["indicator"]
    params = dict(gene["params"])

    if indicator in INDICATOR_REGISTRY:
        reg = INDICATOR_REGISTRY[indicator]
        param_name = random.choice(list(reg.params.keys()))
        pdef = reg.params[param_name]
        current = params.get(param_name, pdef.default)
        range_size = pdef.max - pdef.min
        delta = random.choice([-1, 1]) * range_size * random.uniform(0.05, 0.30)
        new_val = current + delta
        new_val = pdef.clamp(round(new_val / pdef.step) * pdef.step)
        params[param_name] = int(new_val) if pdef.type == "int" else round(float(new_val), 4)
        gene["params"] = params

    return StrategyDNA.from_dict(data)


def mutate_indicator(dna: StrategyDNA) -> StrategyDNA:
    """Replace a random indicator with a same-category alternative (base or layer)."""
    data = dna.to_dict()
    data["strategy_id"] = _new_id()
    data["parent_ids"] = [dna.strategy_id]
    data["mutation_ops"] = list(dna.mutation_ops) + ["indicator_replacement"]
    data["generation"] = dna.generation + 1

    gene_pool = _pick_signal_pool(data)

    if not gene_pool["genes"]:
        return StrategyDNA.from_dict(data)

    idx = random.randint(0, len(gene_pool["genes"]) - 1)
    gene = gene_pool["genes"][idx]
    current = gene["indicator"]

    alternatives = get_interchangeable(current)
    if not alternatives:
        return StrategyDNA.from_dict(data)

    role = gene.get("role", "entry_trigger")
    is_trigger = role.endswith("_trigger")
    if is_trigger:
        alternatives = [a for a in alternatives
                        if not INDICATOR_REGISTRY[a].guard_only]

    if not alternatives:
        return StrategyDNA.from_dict(data)

    new_indicator = random.choice(alternatives)
    reg = INDICATOR_REGISTRY[new_indicator]

    new_params = {k: int(v.default) if v.type == "int" else float(v.default)
                  for k, v in reg.params.items()}

    condition = generate_random_condition(new_indicator, reg)

    gene["indicator"] = new_indicator
    gene["params"] = new_params
    gene["field"] = None if len(reg.output_fields) == 1 else random.choice(reg.output_fields)
    gene["condition"] = condition

    return StrategyDNA.from_dict(data)


def mutate_logic(dna: StrategyDNA) -> StrategyDNA:
    """Flip AND/OR logic in base layer or a random MTF layer."""
    data = dna.to_dict()
    data["strategy_id"] = _new_id()
    data["parent_ids"] = [dna.strategy_id]
    data["mutation_ops"] = list(dna.mutation_ops) + ["logic_mutation"]
    data["generation"] = dna.generation + 1

    action = random.choice(["flip_entry", "flip_exit", "flip_both"])

    # Pick which logic_genes to mutate: base or a random layer
    targets = [("base", data["logic_genes"])]
    for i, layer in enumerate(data.get("layers", [])):
        targets.append((f"layer_{i}", layer["logic_genes"]))

    _, target_logic = random.choice(targets)

    if action == "flip_entry" or action == "flip_both":
        current = target_logic["entry_logic"]
        target_logic["entry_logic"] = "OR" if current == "AND" else "AND"
    if action == "flip_exit" or action == "flip_both":
        current = target_logic["exit_logic"]
        target_logic["exit_logic"] = "OR" if current == "AND" else "AND"

    return StrategyDNA.from_dict(data)


def mutate_add_signal(dna: StrategyDNA) -> StrategyDNA:
    """Add a random guard signal gene to the strategy (base or layer)."""
    data = dna.to_dict()
    data["strategy_id"] = _new_id()
    data["parent_ids"] = [dna.strategy_id]
    data["mutation_ops"] = list(dna.mutation_ops) + ["add_signal"]
    data["generation"] = dna.generation + 1

    gene_pool = _pick_signal_pool(data)

    if not gene_pool["genes"]:
        return StrategyDNA.from_dict(data)

    # Check if we already have guards
    has_entry_guard = any(sg.get("role") == "entry_guard" for sg in gene_pool["genes"])
    has_exit_guard = any(sg.get("role") == "exit_guard" for sg in gene_pool["genes"])

    # Decide which guard to add (prefer missing one)
    if not has_entry_guard and (has_exit_guard or random.random() < 0.5):
        role = "entry_guard"
    elif not has_exit_guard:
        role = "exit_guard"
    else:
        role = random.choice(["entry_guard", "exit_guard"])

    # Pick indicator (all indicators eligible for guards)
    all_indicators = [name for name in INDICATOR_REGISTRY.keys()
                      if not INDICATOR_REGISTRY[name].guard_only or role.endswith("_guard")]
    if not all_indicators:
        return StrategyDNA.from_dict(data)

    indicator_name = random.choice(all_indicators)
    reg = INDICATOR_REGISTRY[indicator_name]

    new_params = {}
    for pname, pdef in reg.params.items():
        val = random.uniform(pdef.min, pdef.max)
        new_params[pname] = int(round(val / pdef.step) * pdef.step) if pdef.type == "int" \
            else round(round(val / pdef.step) * pdef.step, 2)

    condition = generate_random_condition(indicator_name, reg)
    field_name = None if len(reg.output_fields) <= 1 else random.choice(reg.output_fields)

    new_gene = {
        "indicator": indicator_name,
        "params": new_params,
        "role": role,
        "field": field_name,
        "condition": condition,
    }

    gene_pool["genes"].append(new_gene)
    return StrategyDNA.from_dict(data)


def mutate_remove_signal(dna: StrategyDNA) -> StrategyDNA:
    """Remove a random guard signal gene from the strategy (base or layer)."""
    data = dna.to_dict()
    data["strategy_id"] = _new_id()
    data["parent_ids"] = [dna.strategy_id]
    data["mutation_ops"] = list(dna.mutation_ops) + ["remove_signal"]
    data["generation"] = dna.generation + 1

    gene_pool = _pick_signal_pool(data)

    # Only remove guards, never remove triggers
    guard_indices = [i for i, sg in enumerate(gene_pool["genes"])
                     if sg.get("role", "").endswith("_guard")]
    if not guard_indices:
        return StrategyDNA.from_dict(data)

    idx = random.choice(guard_indices)
    gene_pool["genes"].pop(idx)
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

    Preserves MTF layer structure: crosses corresponding layers' signal genes.
    Both parents must have the same layer structure (same timeframe count).
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

    # --- Cross MTF layers (preserve structure) ---
    child_layers = None
    child_cross_logic = "AND"

    a_has_layers = parent_a.layers is not None and len(parent_a.layers) > 0
    b_has_layers = parent_b.layers is not None and len(parent_b.layers) > 0

    if a_has_layers and b_has_layers:
        # Both have layers: cross corresponding layers
        from core.strategy.dna import TimeframeLayer, LogicGenes
        child_layers = []
        for la, lb in zip(parent_a.layers, parent_b.layers):
            # Same timeframe position: take entry from one, exit from other
            layer_entry_a = [g for g in la.signal_genes
                             if g.role in (SignalRole.ENTRY_TRIGGER, SignalRole.ENTRY_GUARD)]
            layer_exit_b = [g for g in lb.signal_genes
                            if g.role in (SignalRole.EXIT_TRIGGER, SignalRole.EXIT_GUARD)]
            layer_signals = []
            layer_signals.extend(layer_entry_a if layer_entry_a else
                                 [la.signal_genes[0]] if la.signal_genes else [])
            layer_signals.extend(layer_exit_b if layer_exit_b else
                                 [lb.signal_genes[-1]] if lb.signal_genes else [])
            if not layer_signals:
                layer_signals = list(la.signal_genes)
            layer_logic = random.choice([la.logic_genes, lb.logic_genes])
            child_layers.append(TimeframeLayer(
                timeframe=la.timeframe,
                signal_genes=layer_signals,
                logic_genes=layer_logic,
            ))
        child_cross_logic = random.choice(
            [parent_a.cross_layer_logic, parent_b.cross_layer_logic]
        )
    elif a_has_layers:
        child_layers = list(parent_a.layers)
        child_cross_logic = parent_a.cross_layer_logic
    elif b_has_layers:
        child_layers = list(parent_b.layers)
        child_cross_logic = parent_b.cross_layer_logic

    child = StrategyDNA(
        signal_genes=child_signals,
        logic_genes=logic,
        risk_genes=risk,
        execution_genes=parent_a.execution_genes,
        parent_ids=[parent_a.strategy_id, parent_b.strategy_id],
        mutation_ops=["crossover"],
        generation=max(parent_a.generation, parent_b.generation) + 1,
        layers=child_layers,
        cross_layer_logic=child_cross_logic,
        _layers_explicit=child_layers is not None,
    )
    return child
