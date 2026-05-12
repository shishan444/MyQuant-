"""PredictionEvolver -- offline evolution of prediction formulas.

Independent from the strategy evolution engine (core/evolution/).
Evolves PredictionDNA using GARCH params + factor weights + window params.
"""

from __future__ import annotations

import math
import random
from typing import List, Tuple

import pandas as pd

from core.prediction.genes import PredictionDNA
from core.prediction.predictor import PriceRangePredictor, PredictionResult


def _compute_fitness(
    predicted: List[PredictionResult],
    actual_highs: List[float],
    actual_lows: List[float],
) -> float:
    """Compute fitness: hit_rate * 0.6 + tightness * 0.4."""
    n = len(predicted)
    if n == 0:
        return 0.0

    score_sum = 0.0
    for i in range(n):
        pred = predicted[i]
        ah, al = actual_highs[i], actual_lows[i]
        actual_width = ah - al

        if al >= pred.low and ah <= pred.high:
            # Hit: reward tightness
            score_sum += actual_width / (2 * pred.width)
        else:
            # Miss: penalize overshoot
            overshoot = 0.0
            if al < pred.low:
                overshoot += pred.low - al
            if ah > pred.high:
                overshoot += ah - pred.high
            score_sum -= overshoot / max(actual_width, 1e-8)

    avg_score = max(score_sum / n, 0.0)
    # Hit rate component
    hits = sum(
        1 for i in range(n)
        if actual_lows[i] >= predicted[i].low and actual_highs[i] <= predicted[i].high
    )
    hit_rate = hits / n
    return hit_rate * 0.6 + avg_score * 0.4


def _evaluate_dna(dna: PredictionDNA, df: pd.DataFrame) -> float:
    """Evaluate a single PredictionDNA on historical data."""
    predictor = PriceRangePredictor(dna)
    predictor.warmup(df, n_bars=min(100, len(df) // 2))

    predicted = []
    actual_highs = []
    actual_lows = []

    start = min(100, len(df) // 2)
    for i in range(start, len(df) - 1):
        result = predictor.predict(df, i)
        row = df.iloc[i + 1]
        predicted.append(result)
        actual_highs.append(float(row["high"]))
        actual_lows.append(float(row["low"]))
        predictor.observe(float(row["high"]), float(row["low"]), result)

    return _compute_fitness(predicted, actual_highs, actual_lows)


def _random_dna() -> PredictionDNA:
    """Generate a random PredictionDNA within search bounds."""
    alpha = random.uniform(0.01, 0.30)
    beta = random.uniform(0.70, 0.94 - alpha)  # ensure alpha + beta < 0.95
    dna = PredictionDNA(
        omega=random.uniform(1e-6, 1e-3),
        alpha=alpha,
        beta=beta,
        k_base=random.uniform(0.3, 1.2),
        k_min=random.uniform(0.2, 0.5),
        factor_weights={
            name: random.uniform(-1.0, 1.0)
            for name in [
                "vol_regime", "bb_squeeze", "rvol",
                "tension_short", "tension_mid", "tension_long",
                "tension_divergence", "adx_strength",
            ]
        },
        short_window=random.randint(5, 30),
        mid_window=random.randint(30, 100),
        long_window=random.randint(100, 300),
    )
    dna.clamp_params()
    return dna


def _mutate(dna: PredictionDNA) -> PredictionDNA:
    """Mutate a PredictionDNA."""
    d = dna.to_dict()
    d["prediction_id"] = _new_id()

    # Pick 1-3 params to perturb
    n_mutations = random.choice([1, 1, 2, 2, 3])
    continuous_keys = ["omega", "alpha", "beta", "k_base", "k_min"]

    for _ in range(n_mutations):
        choice = random.random()
        if choice < 0.5:
            # Perturb a continuous param
            key = random.choice(continuous_keys)
            d[key] *= random.gauss(1.0, 0.2)
        elif choice < 0.7:
            # Toggle or perturb a factor weight
            if d["factor_weights"]:
                fk = random.choice(list(d["factor_weights"].keys()))
                if random.random() < 0.2:
                    d["factor_weights"][fk] = 0.0
                else:
                    d["factor_weights"][fk] += random.gauss(0, 0.3)
                    d["factor_weights"][fk] = max(-1.0, min(1.0, d["factor_weights"][fk]))
        else:
            # Adjust window
            wk = random.choice(["short_window", "mid_window", "long_window"])
            d[wk] = int(d[wk] * random.gauss(1.0, 0.15))
            d[wk] = max(5, min(300, d[wk]))

    result = PredictionDNA.from_dict(d)
    result.clamp_params()
    return result


def _new_id() -> str:
    import uuid
    return str(uuid.uuid4())[:8]


class PredictionEvolver:
    """Offline evolution of prediction formulas."""

    def __init__(
        self,
        df: pd.DataFrame,
        population_size: int = 60,
        max_generations: int = 50,
    ):
        self._df = df
        self._pop_size = population_size
        self._max_gen = max_generations

    def evolve(self) -> PredictionDNA:
        """Run evolution, return best PredictionDNA."""
        population = self._init_population()

        best_dna = population[0]
        best_score = -1.0

        for gen in range(1, self._max_gen + 1):
            # Evaluate
            scored = [(dna, _evaluate_dna(dna, self._df)) for dna in population]
            scored.sort(key=lambda x: x[1], reverse=True)

            gen_best_dna, gen_best_score = scored[0]
            if gen_best_score > best_score:
                best_score = gen_best_score
                best_dna = gen_best_dna

            # Selection: keep top 30%
            n_elite = max(2, self._pop_size // 3)
            survivors = [dna for dna, _ in scored[:n_elite]]

            # Create next generation
            next_pop = list(survivors)
            while len(next_pop) < self._pop_size:
                parent = random.choice(survivors)
                child = _mutate(parent)
                next_pop.append(child)

            population = next_pop

        best_dna.fitness_score = best_score
        best_dna.generation = self._max_gen
        return best_dna

    def _init_population(self) -> List[PredictionDNA]:
        return [_random_dna() for _ in range(self._pop_size)]
