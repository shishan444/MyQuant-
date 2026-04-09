"""Diversity protection: detect homogeneity and inject fresh blood."""
from __future__ import annotations

from typing import List

from MyQuant.core.strategy.dna import StrategyDNA
from MyQuant.core.evolution.population import create_random_dna


def _gene_signature(dna: StrategyDNA) -> str:
    """Create a simple signature string for similarity comparison."""
    parts = []
    for gene in sorted(dna.signal_genes, key=lambda g: g.role.value):
        parts.append(f"{gene.indicator}:{gene.role.value}")
    return "|".join(parts)


def compute_diversity(population: List[StrategyDNA]) -> float:
    """Compute population diversity as ratio of unique gene signatures.

    Returns:
        Float 0-1 where 1 = all individuals unique, 0 = all identical.
    """
    if len(population) <= 1:
        return 0.0

    signatures = [_gene_signature(ind) for ind in population]
    unique = len(set(signatures))
    return unique / len(population)


def inject_fresh_blood(
    population: List[StrategyDNA],
    n: int = 2,
) -> List[StrategyDNA]:
    """Add n random individuals to the population for diversity.

    Args:
        population: Current population.
        n: Number of fresh individuals to add.

    Returns:
        Population with fresh individuals appended.
    """
    for _ in range(n):
        fresh = create_random_dna(
            timeframe=population[0].execution_genes.timeframe if population else "4h",
            symbol=population[0].execution_genes.symbol if population else "BTCUSDT",
        )
        population.append(fresh)
    return population


def check_and_maintain_diversity(
    population: List[StrategyDNA],
    threshold: float = 0.30,
) -> List[StrategyDNA]:
    """If diversity is below threshold, replace similar individuals.

    Args:
        population: Current population.
        threshold: Minimum acceptable diversity ratio.

    Returns:
        Population with diversity maintained.
    """
    diversity = compute_diversity(population)
    if diversity < threshold:
        # Replace the most common individuals
        signatures = [_gene_signature(ind) for ind in population]
        from collections import Counter
        counts = Counter(signatures)
        most_common_sig, most_common_count = counts.most_common(1)[0]

        if most_common_count > len(population) * 0.3:
            # Replace duplicates with fresh individuals
            seen = set()
            new_pop = []
            for ind in population:
                sig = _gene_signature(ind)
                if sig in seen:
                    fresh = create_random_dna(
                        timeframe=ind.execution_genes.timeframe,
                        symbol=ind.execution_genes.symbol,
                    )
                    new_pop.append(fresh)
                else:
                    seen.add(sig)
                    new_pop.append(ind)
            return new_pop

    return population
