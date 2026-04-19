"""Evolution engine: main loop with early stopping and parallel evaluation."""
from __future__ import annotations

import random
from typing import Callable, Dict, List, Optional, Tuple

from core.strategy.dna import StrategyDNA
from core.evolution.operators import (
    mutate_params, mutate_indicator, mutate_logic, mutate_risk, crossover,
    mutate_cross_logic,
    mutate_add_signal, mutate_remove_signal,
)
from core.evolution.population import init_population, create_random_dna
from core.evolution.diversity import (
    compute_diversity, inject_fresh_blood, check_and_maintain_diversity,
)


class EarlyStopChecker:
    """Check early stopping conditions after each generation.

    4 rules:
    1. Target reached: best_score >= target
    2. Stagnation: no improvement for patience generations
    3. Decline: best_score declining for decline_limit generations
    4. Max generations: reached max_generations
    """

    def __init__(
        self,
        target_score: float = 80.0,
        max_generations: int = 200,
        patience: int = 15,
        min_improvement: float = 0.5,
        decline_limit: int = 10,
        min_generations: int = 20,
    ):
        self.target_score = target_score
        self.max_generations = max_generations
        self.patience = patience
        self.min_improvement = min_improvement
        self.decline_limit = decline_limit
        self.min_generations = min_generations
        self.best_score = -float("inf")
        self.no_improve_count = 0
        self.decline_count = 0

    def check(self, current_best: float, generation: int) -> Tuple[str, str]:
        """Check if evolution should stop.

        Returns:
            (action, reason) where action is "continue" or "stop".
        """
        # Target reached: only stop after min_generations to avoid premature exit
        if current_best >= self.target_score and generation >= self.min_generations:
            return ("stop", "target_reached")

        # Check improvement
        improvement = current_best - self.best_score
        if improvement < self.min_improvement:
            self.no_improve_count += 1
        else:
            self.no_improve_count = 0

        if self.no_improve_count >= self.patience:
            return ("stop", "stagnation")

        # Check decline
        if current_best < self.best_score:
            self.decline_count += 1
        else:
            self.decline_count = 0

        if self.decline_count >= self.decline_limit:
            return ("stop", "decline")

        # Check max generations
        if generation >= self.max_generations:
            return ("stop", "max_generations")

        # Update best
        if current_best > self.best_score:
            self.best_score = current_best

        return ("continue", "")


class EvolutionEngine:
    """Main evolution loop.

    Coordinates population management, evaluation, selection, crossover,
    mutation, and early stopping. Designed for CLI/programmatic use.
    """

    def __init__(
        self,
        target_score: float = 80.0,
        template_name: str = "profit_first",
        population_size: int = 15,
        max_generations: int = 200,
        patience: int = 15,
        decline_limit: int = 10,
        elite_ratio: float = 0.25,
        leverage: int = 1,
        direction: str = "long",
        timeframe_pool: Optional[list] = None,
    ):
        self.target_score = target_score
        self.template_name = template_name
        self.population_size = population_size
        self.max_generations = max_generations
        self.patience = patience
        self.decline_limit = decline_limit
        self.elite_ratio = elite_ratio
        self.leverage = leverage
        self.direction = direction
        self.timeframe_pool = timeframe_pool or []

    def evolve(
        self,
        ancestor: StrategyDNA,
        evaluate_fn: Callable[[StrategyDNA], float],
        on_generation: Optional[Callable[[int, float, float], None]] = None,
        extra_ancestors: Optional[List[StrategyDNA]] = None,
    ) -> Dict:
        """Run the full evolution loop.

        Args:
            ancestor: Starting strategy.
            evaluate_fn: Function that takes a StrategyDNA and returns a score (0-100).
            on_generation: Optional callback(gen, best_score, avg_score) after each gen.

        Returns:
            Dict with champion, history, stop_reason, total_generations.
        """
        # Initialize population
        population = init_population(
            self.population_size, ancestor,
            extra_ancestors=extra_ancestors,
            leverage=self.leverage, direction=self.direction,
            timeframe_pool=self.timeframe_pool if len(self.timeframe_pool) > 1 else None,
        )
        self._population = population
        stop_checker = EarlyStopChecker(
            target_score=self.target_score,
            max_generations=self.max_generations,
            patience=self.patience,
            decline_limit=self.decline_limit,
        )

        history = []
        champion = None
        champion_score = -1.0
        stagnation_count = 0  # Track consecutive generations without improvement

        for gen in range(1, self.max_generations + 1):
            # Enforce task-level constraints on all individuals before evaluation
            for ind in population:
                ind.risk_genes.leverage = self.leverage
                # mixed mode: allow evolution to explore both directions
                if self.direction != "mixed":
                    ind.risk_genes.direction = self.direction

            # Evaluate all individuals
            scored = [(ind, evaluate_fn(ind)) for ind in population]
            scored.sort(key=lambda x: x[1], reverse=True)

            best_score = scored[0][1]
            avg_score = sum(s for _, s in scored) / len(scored)

            history.append({
                "generation": gen,
                "best_score": best_score,
                "avg_score": avg_score,
            })

            # Track champion and stagnation
            if best_score > champion_score:
                champion = scored[0][0]
                champion_score = best_score
                stagnation_count = 0
            else:
                stagnation_count += 1

            # Callback
            if on_generation:
                on_generation(gen, best_score, avg_score)

            # Early stop check
            action, reason = stop_checker.check(best_score, gen)
            if action == "stop":
                return {
                    "champion": champion,
                    "champion_score": champion_score,
                    "history": history,
                    "stop_reason": reason,
                    "total_generations": gen,
                    "target_reached": reason == "target_reached",
                }

            # Selection: keep top elite_ratio
            elite_count = max(2, int(len(scored) * self.elite_ratio))
            elites = [ind for ind, _ in scored[:elite_count]]

            # Crossover: breed new individuals from elites
            children = []

            # Adaptive mutation pool weights based on stagnation
            # More structural changes when stuck, more refinement when improving
            if stagnation_count > 8:
                mut_weights = [15, 30, 10, 15, 20, 10]  # Heavy on indicator replacement
                n_mutations_choices = [2, 3, 4]
                n_mut_weights = [30, 45, 25]
            elif stagnation_count > 4:
                mut_weights = [25, 20, 15, 20, 10, 10]  # Balanced
                n_mutations_choices = [1, 2, 3]
                n_mut_weights = [25, 45, 30]
            else:
                mut_weights = [35, 10, 10, 25, 10, 10]  # Heavy on params + risk (fine-tuning)
                n_mutations_choices = [1, 2, 3]
                n_mut_weights = [50, 35, 15]

            mutation_pool = [
                mutate_params, mutate_indicator, mutate_logic, mutate_risk,
                mutate_add_signal, mutate_remove_signal,
            ]
            # Add cross_logic mutation for MTF strategies
            if len(self.timeframe_pool) > 1:
                mutation_pool.append(mutate_cross_logic)
                mut_weights.append(10)

            while len(children) < self.population_size - elite_count - 2:
                if len(elites) >= 2:
                    p1, p2 = random.sample(elites, 2)
                    try:
                        child = crossover(p1, p2)
                        # Adaptive mutation intensity
                        n_mutations = random.choices(
                            n_mutations_choices, weights=n_mut_weights,
                        )[0]
                        for _ in range(n_mutations):
                            mut = random.choices(mutation_pool, weights=mut_weights)[0]
                            child = mut(child)
                        children.append(child)
                    except Exception:
                        children.append(create_random_dna(
                            leverage=self.leverage, direction=self.direction,
                            timeframe_pool=self.timeframe_pool if len(self.timeframe_pool) > 1 else None,
                        ))
                else:
                    children.append(create_random_dna(
                        leverage=self.leverage, direction=self.direction,
                        timeframe_pool=self.timeframe_pool if len(self.timeframe_pool) > 1 else None,
                    ))

            # Fresh blood: 1-2 random individuals
            fresh_count = random.randint(1, 2)
            population = elites + children
            population = inject_fresh_blood(
                population, n=max(0, self.population_size - len(population)),
                leverage=self.leverage, direction=self.direction,
                timeframe_pool=self.timeframe_pool if len(self.timeframe_pool) > 1 else None,
            )

            # Diversity maintenance: replace clones with fresh individuals
            population = check_and_maintain_diversity(
                population,
                leverage=self.leverage, direction=self.direction,
                timeframe_pool=self.timeframe_pool if len(self.timeframe_pool) > 1 else None,
            )

            self._population = population

            # Trim to exact size
            population = population[:self.population_size]

        return {
            "champion": champion,
            "champion_score": champion_score,
            "history": history,
            "stop_reason": "max_generations",
            "total_generations": self.max_generations,
            "target_reached": champion_score >= self.target_score,
        }
