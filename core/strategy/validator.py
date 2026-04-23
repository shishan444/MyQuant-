"""DNA validation - checks strategy legality before backtesting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from core.strategy.dna import StrategyDNA, SignalRole


@dataclass
class ValidationResult:
    """Result of DNA validation."""
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)


def validate_dna(dna: StrategyDNA) -> ValidationResult:
    """Validate a StrategyDNA for legality.

    Checks:
    - At least 1 entry signal (trigger or guard)
    - At least 1 exit signal (trigger or guard)
    - Stop loss in [0.005, 0.20]
    - Position size in [0.10, 1.0]
    - Take profit > stop loss (if set)
    - Condition structure validity for new condition types
    """
    errors: List[str] = []

    # For non-MTF strategies, check top-level signal_genes
    if not dna.layers:
        entry_signals = [
            g for g in dna.signal_genes
            if g.role in (SignalRole.ENTRY_TRIGGER, SignalRole.ENTRY_GUARD)
        ]
        if not entry_signals:
            errors.append("No entry signal defined (need at least one entry_trigger or entry_guard)")

        exit_signals = [
            g for g in dna.signal_genes
            if g.role in (SignalRole.EXIT_TRIGGER, SignalRole.EXIT_GUARD)
        ]
        if not exit_signals:
            errors.append("No exit signal defined (need at least one exit_trigger or exit_guard)")

    # Also check layers for MTF strategies
    if dna.layers:
        has_execution = False
        for layer in dna.layers:
            layer_entry = [
                g for g in layer.signal_genes
                if g.role in (SignalRole.ENTRY_TRIGGER, SignalRole.ENTRY_GUARD)
            ]
            if not layer_entry:
                errors.append(f"Layer {layer.timeframe}: no entry signal defined")
            layer_exit = [
                g for g in layer.signal_genes
                if g.role in (SignalRole.EXIT_TRIGGER, SignalRole.EXIT_GUARD)
            ]
            if not layer_exit:
                errors.append(f"Layer {layer.timeframe}: no exit signal defined")
            if layer.role not in (None, "trend", "execution"):
                errors.append(f"Layer {layer.timeframe}: invalid role '{layer.role}'")
            if layer.role in (None, "execution"):
                has_execution = True
        if not has_execution:
            errors.append("MTF strategy needs at least one execution layer")

    # Validate condition structures
    for i, gene in enumerate(dna.signal_genes):
        cond_errors = _validate_condition_structure(gene.condition, i)
        errors.extend(cond_errors)

    # Risk genes validation
    risk = dna.risk_genes
    if not (0.005 <= risk.stop_loss <= 0.20):
        errors.append(f"Stop loss {risk.stop_loss} out of range [0.005, 0.20]")

    if risk.take_profit is not None and risk.take_profit <= risk.stop_loss:
        errors.append(f"Take profit ({risk.take_profit}) must be greater than stop loss ({risk.stop_loss})")

    if not (0.10 <= risk.position_size <= 1.0):
        errors.append(f"Position size {risk.position_size} out of range [0.10, 1.0]")

    if not (1 <= risk.leverage <= 10):
        errors.append(f"Leverage {risk.leverage} out of range [1, 10]")

    if risk.direction not in ("long", "short", "mixed"):
        errors.append(f"Direction must be 'long', 'short', or 'mixed', got '{risk.direction}'")

    return ValidationResult(is_valid=len(errors) == 0, errors=errors)


def _validate_condition_structure(condition: dict, gene_idx: int) -> List[str]:
    """Validate structure of a condition dict for new condition types."""
    errors: List[str] = []
    cond_type = condition.get("type", "")

    if cond_type in ("cross_above_series", "cross_below_series"):
        if "target_indicator" not in condition:
            errors.append(f"Gene {gene_idx}: {cond_type} requires 'target_indicator'")
    elif cond_type in ("lookback_any", "lookback_all"):
        if "window" not in condition:
            errors.append(f"Gene {gene_idx}: {cond_type} requires 'window'")
        if "inner" not in condition:
            errors.append(f"Gene {gene_idx}: {cond_type} requires 'inner' condition")
    elif cond_type == "touch_bounce":
        if "direction" not in condition:
            errors.append(f"Gene {gene_idx}: touch_bounce requires 'direction'")
    elif cond_type == "role_reversal":
        if "role" not in condition:
            errors.append(f"Gene {gene_idx}: role_reversal requires 'role'")
    elif cond_type == "wick_touch":
        if "direction" not in condition:
            errors.append(f"Gene {gene_idx}: wick_touch requires 'direction'")

    return errors
