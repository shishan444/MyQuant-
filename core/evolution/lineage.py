"""Lineage tracking: record mutation history and evolution path."""
from __future__ import annotations

from typing import List

from core.strategy.dna import StrategyDNA


def record_mutation(dna: StrategyDNA, op_description: str) -> StrategyDNA:
    """Record a mutation operation in the DNA's lineage.

    Args:
        dna: Strategy to update.
        op_description: Human-readable description of the mutation.

    Returns:
        The same DNA with mutation_ops updated.
    """
    dna.mutation_ops = list(dna.mutation_ops) + [op_description]
    return dna


def get_lineage(dna: StrategyDNA) -> List[str]:
    """Get the complete mutation history of a strategy.

    Returns:
        List of mutation operation descriptions.
    """
    return list(dna.mutation_ops)


def format_lineage(dna: StrategyDNA) -> str:
    """Format lineage as a readable string."""
    lines = [f"Strategy {dna.strategy_id[:8]}  Gen {dna.generation}"]
    if dna.parent_ids:
        lines.append(f"  Parents: {', '.join(pid[:8] for pid in dna.parent_ids)}")
    for op in dna.mutation_ops:
        lines.append(f"  -> {op}")
    return "\n".join(lines)
