"""Verification script: performance benchmark + accuracy comparison for v0.2.0 optimizations.

Run from MyQuant/ directory:
    python tests/verify_v020.py
"""

import time
import numpy as np
import pandas as pd
import sys

# ---------------------------------------------------------------------------
# Helper: original implementations (pre-optimization)
# ---------------------------------------------------------------------------

def _original_resample_pulse(signal: pd.Series, target_index: pd.DatetimeIndex) -> pd.Series:
    if signal.empty or len(target_index) == 0:
        return pd.Series(False, index=target_index)
    result = pd.Series(False, index=target_index)
    for i in range(len(target_index)):
        bar_start = target_index[i]
        bar_end = target_index[i + 1] if i + 1 < len(target_index) else bar_start + pd.Timedelta(days=1)
        mask = (signal.index >= bar_start) & (signal.index < bar_end)
        if signal[mask].any():
            result.iloc[i] = True
    return result.astype(bool)


def _original_lookback_any(inner_signal: pd.Series, window: int) -> pd.Series:
    return inner_signal.rolling(window=window, min_periods=1).apply(any, raw=False).fillna(False).astype(bool)


def _original_lookback_all(inner_signal: pd.Series, window: int) -> pd.Series:
    return inner_signal.rolling(window=window, min_periods=1).apply(all, raw=False).fillna(False).astype(bool)


def _original_compute_proximity_score(price_levels, current_price, s_pct):
    if not price_levels or s_pct <= 0:
        return pd.Series(0.0, index=current_price.index)
    n = len(current_price)
    scores = np.zeros(n)
    for bar_idx in range(n):
        price = current_price.iloc[bar_idx]
        if price <= 0:
            continue
        min_rel_dist = float("inf")
        for level_series in price_levels:
            level = level_series.iloc[bar_idx] if bar_idx < len(level_series) else price
            if np.isnan(level) or level <= 0:
                continue
            rel_dist = abs(price - level) / price
            min_rel_dist = min(min_rel_dist, rel_dist)
        if min_rel_dist <= s_pct:
            scores[bar_idx] = max(0.0, 1.0 - min_rel_dist / s_pct)
    return pd.Series(scores, index=current_price.index)


# ---------------------------------------------------------------------------
# Test data generators
# ---------------------------------------------------------------------------

def make_ohlcv(n=500, freq="4h", base_price=40000.0, seed=42):
    rng = np.random.default_rng(seed)
    returns = rng.standard_normal(n) * 0.01 + 0.0001
    close = base_price * np.cumprod(1 + returns)
    high = close * (1 + np.abs(rng.standard_normal(n)) * 0.005)
    low = close * (1 - np.abs(rng.standard_normal(n)) * 0.005)
    opn = close * (1 + rng.standard_normal(n) * 0.002)
    volume = rng.integers(100, 10000, size=n).astype(float)
    dates = pd.date_range("2024-01-01", periods=n, freq=freq, tz="UTC")
    df = pd.DataFrame({"open": opn, "high": high, "low": low, "close": close, "volume": volume}, index=dates)
    df.index.name = "timestamp"
    return df


def make_enhanced_df(n=500, freq="4h", seed=42):
    from core.features.indicators import compute_all_indicators
    df = make_ohlcv(n=n, freq=freq, base_price=40000.0, seed=seed)
    return compute_all_indicators(df)


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def benchmark(name, fn_old, fn_new, *args, warmup=1, runs=5, **kwargs):
    """Run both old and new implementations, compare speed and accuracy."""
    # Warmup
    for _ in range(warmup):
        fn_old(*args, **kwargs)
        fn_new(*args, **kwargs)

    # Time old
    t0 = time.perf_counter()
    for _ in range(runs):
        old_result = fn_old(*args, **kwargs)
    t_old = (time.perf_counter() - t0) / runs

    # Time new
    t0 = time.perf_counter()
    for _ in range(runs):
        new_result = fn_new(*args, **kwargs)
    t_new = (time.perf_counter() - t0) / runs

    speedup = t_old / t_new if t_new > 0 else float("inf")

    # Accuracy check
    if isinstance(old_result, pd.Series) and isinstance(new_result, pd.Series):
        if old_result.dtype == bool:
            match = (old_result == new_result).all()
            diff_count = (old_result != new_result).sum()
            diff_pct = diff_count / len(old_result) * 100
        else:
            match = np.allclose(old_result.values, new_result.values, rtol=1e-10, equal_nan=True)
            max_diff = np.nanmax(np.abs(old_result.values - new_result.values))
            diff_pct = max_diff
    else:
        match = True
        diff_pct = 0

    return {
        "name": name,
        "t_old_ms": t_old * 1000,
        "t_new_ms": t_new * 1000,
        "speedup": speedup,
        "match": match,
        "diff": diff_pct,
    }


def print_result(r):
    status = "PASS" if r["match"] else "MISMATCH"
    print(f"  [{status}] {r['name']}")
    print(f"    Old: {r['t_old_ms']:.2f}ms | New: {r['t_new_ms']:.2f}ms | Speedup: {r['speedup']:.1f}x")
    if not r["match"]:
        print(f"    DIFF: {r['diff']}")
    return r


# ---------------------------------------------------------------------------
# Main verification
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("v0.2.0 Signal Optimization Verification")
    print("=" * 70)

    from core.strategy.executor import _resample_pulse, evaluate_condition, clear_indicator_cache
    from core.strategy.mtf_engine import compute_proximity_score
    from core.strategy.executor import batch_signal_sets, dna_to_signal_set
    from tests.helpers.data_factory import make_dna

    results = []

    # ------------------------------------------------------------------
    # 1. _resample_pulse: 15m -> 4h (production scale)
    # ------------------------------------------------------------------
    print("\n[1] _resample_pulse: 17377 bars 15m -> 1087 bars 4h")
    n_src = 17377
    n_tgt = 1087
    rng = np.random.default_rng(42)
    dates_15m = pd.date_range("2024-01-01", periods=n_src, freq="15min", tz="UTC")
    signal_15m = pd.Series(False, index=dates_15m)
    true_indices = rng.choice(n_src, size=500, replace=False)
    signal_15m.iloc[true_indices] = True
    dates_4h = pd.date_range("2024-01-01", periods=n_tgt, freq="4h", tz="UTC")

    r = benchmark(
        "_resample_pulse (17377->1087)",
        _original_resample_pulse,
        _resample_pulse,
        signal_15m, dates_4h,
        warmup=1, runs=3,
    )
    results.append(print_result(r))

    # ------------------------------------------------------------------
    # 2. lookback_any: 17377 bars, window=5
    # ------------------------------------------------------------------
    print("\n[2] lookback_any: 17377 bars, window=5")
    vals = rng.random(n_src)
    indicator = pd.Series(vals, index=dates_15m)
    close = pd.Series(rng.random(n_src) * 40000, index=dates_15m)
    inner_signal = indicator < 0.3

    r = benchmark(
        "lookback_any (17377 bars, window=5)",
        lambda: _original_lookback_any(inner_signal, 5),
        lambda: (inner_signal.astype(float).rolling(window=5, min_periods=1).sum() > 0).fillna(False).astype(bool),
        warmup=1, runs=3,
    )
    results.append(print_result(r))

    # ------------------------------------------------------------------
    # 3. lookback_all: 17377 bars, window=5 (BEHAVIOR CHANGE!)
    # ------------------------------------------------------------------
    print("\n[3] lookback_all: 17377 bars, window=5 (CHECK: min_periods change)")
    inner_signal_all = indicator > 0.7

    old_result = _original_lookback_all(inner_signal_all, 5)
    new_result = (inner_signal_all.astype(float).rolling(window=5, min_periods=5).sum() == 5).fillna(False).astype(bool)

    diff_count = (old_result != new_result).sum()
    total = len(old_result)
    # Show which bars differ
    diff_indices = np.where(old_result != new_result)[0]
    first_diff = diff_indices[:5] if len(diff_indices) > 0 else []

    print(f"  Old (min_periods=1, .apply(all)) vs New (min_periods=5, .sum()==5)")
    print(f"  Total bars: {total}, Differing: {diff_count} ({diff_count/total*100:.2f}%)")
    print(f"  Old True count: {old_result.sum()}, New True count: {new_result.sum()}")
    if len(first_diff) > 0:
        print(f"  First differing bar indices: {first_diff}")
        print(f"  (These are the first {5}-1 bars where partial window behavior differs)")
    results.append({
        "name": "lookback_all (behavior change)",
        "t_old_ms": 0, "t_new_ms": 0, "speedup": 0,
        "match": diff_count == 0,
        "diff": f"{diff_count} bars differ ({diff_count/total*100:.2f}%)",
    })

    # ------------------------------------------------------------------
    # 4. compute_proximity_score: 17377 bars, 3 levels
    # ------------------------------------------------------------------
    print("\n[4] compute_proximity_score: 17377 bars, 3 price levels")
    prices = pd.Series(40000 + rng.standard_normal(n_src) * 1000, index=dates_15m)
    level1 = pd.Series(prices.values + rng.standard_normal(n_src) * 200, index=dates_15m)
    level2 = pd.Series(prices.values - rng.standard_normal(n_src) * 200, index=dates_15m)
    level3 = pd.Series(prices.values + rng.standard_normal(n_src) * 500, index=dates_15m)
    s_pct = 0.02

    r = benchmark(
        "compute_proximity_score (17377 bars, 3 levels)",
        lambda: _original_compute_proximity_score([level1, level2, level3], prices, s_pct),
        lambda: compute_proximity_score([level1, level2, level3], prices, s_pct),
        warmup=1, runs=3,
    )
    results.append(print_result(r))

    # ------------------------------------------------------------------
    # 5. Full pipeline: batch_signal_sets vs per-individual (15 DNA, 500 bars)
    # ------------------------------------------------------------------
    print("\n[5] Full pipeline: batch_signal_sets vs 15x dna_to_signal_set (500 bars)")
    df = make_enhanced_df(n=500)
    population = [make_dna(entry_value=20 + i * 3, exit_value=60 + i * 3) for i in range(15)]

    # Per-individual
    t0 = time.perf_counter()
    for _ in range(3):
        ind_results = [dna_to_signal_set(dna, df) for dna in population]
    t_ind = (time.perf_counter() - t0) / 3

    # Batch
    t0 = time.perf_counter()
    for _ in range(3):
        batch_results = batch_signal_sets(population, df)
    t_batch = (time.perf_counter() - t0) / 3

    speedup = t_ind / t_batch if t_batch > 0 else float("inf")
    print(f"  Per-individual: {t_ind*1000:.2f}ms | Batch: {t_batch*1000:.2f}ms | Speedup: {speedup:.1f}x")

    # Accuracy: compare signals
    all_match = True
    for i, (br, ir) in enumerate(zip(batch_results, ind_results)):
        if not (br.entries == ir.entries).all():
            print(f"  MISMATCH entries[{i}]: {(br.entries != ir.entries).sum()} bars differ")
            all_match = False
        if not (br.exits == ir.exits).all():
            print(f"  MISMATCH exits[{i}]: {(br.exits != ir.exits).sum()} bars differ")
            all_match = False

    if all_match:
        print(f"  All 15 individuals: signals MATCH")

    results.append({
        "name": "Full pipeline (15 DNA, 500 bars)",
        "t_old_ms": t_ind * 1000,
        "t_new_ms": t_batch * 1000,
        "speedup": speedup,
        "match": all_match,
        "diff": 0,
    })

    # ------------------------------------------------------------------
    # 6. Full pipeline with production scale (15 DNA, 2000 bars)
    # ------------------------------------------------------------------
    print("\n[6] Full pipeline: batch_signal_sets vs 15x dna_to_signal_set (2000 bars)")
    df2 = make_enhanced_df(n=2000)

    # Per-individual
    t0 = time.perf_counter()
    ind_results2 = [dna_to_signal_set(dna, df2) for dna in population]
    t_ind2 = time.perf_counter() - t0

    # Batch
    clear_indicator_cache()
    t0 = time.perf_counter()
    batch_results2 = batch_signal_sets(population, df2)
    t_batch2 = time.perf_counter() - t0

    speedup2 = t_ind2 / t_batch2 if t_batch2 > 0 else float("inf")
    print(f"  Per-individual: {t_ind2*1000:.2f}ms | Batch: {t_batch2*1000:.2f}ms | Speedup: {speedup2:.1f}x")

    # Accuracy
    all_match2 = True
    for i, (br, ir) in enumerate(zip(batch_results2, ind_results2)):
        if not (br.entries == ir.entries).all():
            print(f"  MISMATCH entries[{i}]: {(br.entries != ir.entries).sum()} bars differ")
            all_match2 = False
        if not (br.exits == ir.exits).all():
            print(f"  MISMATCH exits[{i}]: {(br.exits != ir.exits).sum()} bars differ")
            all_match2 = False

    if all_match2:
        print(f"  All 15 individuals: signals MATCH")

    results.append({
        "name": "Full pipeline (15 DNA, 2000 bars)",
        "t_old_ms": t_ind2 * 1000,
        "t_new_ms": t_batch2 * 1000,
        "speedup": speedup2,
        "match": all_match2,
        "diff": 0,
    })

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for r in results:
        status = "OK" if r["match"] else "ISSUE"
        spd = f"{r['speedup']:.1f}x" if r["speedup"] > 0 else "N/A"
        print(f"  [{status}] {r['name']}: {spd} | diff={r['diff']}")

    issues = [r for r in results if not r["match"]]
    if issues:
        print(f"\nFOUND {len(issues)} ISSUES - see details above")
    else:
        print(f"\nAll checks passed")


if __name__ == "__main__":
    main()
