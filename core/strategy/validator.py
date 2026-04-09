"""DNA validation - checks strategy legality before backtesting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from MyQuant.core.strategy.dna import StrategyDNA, SignalRole


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
    """
    errors: List[str] = []

    # Check entry signals
    entry_signals = [
        g for g in dna.signal_genes
        if g.role in (SignalRole.ENTRY_TRIGGER, SignalRole.ENTRY_GUARD)
    ]
    if not entry_signals:
        errors.append("No entry signal defined (need at least one entry_trigger or entry_guard)")

    # Check exit signals
    exit_signals = [
        g for g in dna.signal_genes
        if g.role in (SignalRole.EXIT_TRIGGER, SignalRole.EXIT_GUARD)
    ]
    if not exit_signals:
        errors.append("No exit signal defined (need at least one exit_trigger or exit_guard)")

    # Risk genes validation
    risk = dna.risk_genes
    if not (0.005 <= risk.stop_loss <= 0.20):
        errors.append(f"Stop loss {risk.stop_loss} out of range [0.005, 0.20]")

    if risk.take_profit is not None and risk.take_profit <= risk.stop_loss:
        errors.append(f"Take profit ({risk.take_profit}) must be greater than stop loss ({risk.stop_loss})")

    if not (0.10 <= risk.position_size <= 1.0):
        errors.append(f"Position size {risk.position_size} out of range [0.10, 1.0]")

    return ValidationResult(is_valid=len(errors) == 0, errors=errors)
