"""API-level end-to-end verification: leverage=1 vs leverage=3 vs leverage=5.

Calls /api/strategies/backtest directly, compares results across leverage levels
to verify the entire pipeline (API -> Engine -> Equity -> Metrics -> Response).
"""
import json
import requests
import numpy as np

BASE = "http://localhost:8000/api/strategies"

# Minimal RSI-based DNA that will generate trades on BTCUSDT data
DNA_TEMPLATE = {
    "signal_genes": [
        {
            "indicator": "RSI",
            "params": {"period": 14},
            "role": "entry_trigger",
            "field": None,
            "condition": {"type": "lt", "threshold": 30},
        },
        {
            "indicator": "RSI",
            "params": {"period": 14},
            "role": "exit_trigger",
            "field": None,
            "condition": {"type": "gt", "threshold": 70},
        },
    ],
    "logic_genes": {"entry_logic": "AND", "exit_logic": "OR"},
    "execution_genes": {"timeframe": "4h", "symbol": "BTCUSDT"},
    "risk_genes": {
        "stop_loss": 0.05,
        "take_profit": 0.10,
        "position_size": 0.5,
        "leverage": 1,  # will be overwritten per test
        "direction": "long",
    },
}


def run_backtest(leverage: int) -> dict:
    """Call /api/strategies/backtest with given leverage."""
    dna = {**DNA_TEMPLATE}
    dna["risk_genes"] = {**DNA_TEMPLATE["risk_genes"], "leverage": leverage}

    payload = {
        "dna": dna,
        "symbol": "BTCUSDT",
        "timeframe": "4h",
        "dataset_id": "BTCUSDT_4h",
        "init_cash": 100000,
        "fee": 0.001,
        "slippage": 0.0005,
        "score_template": "profit_first",
    }

    resp = requests.post(f"{BASE}/backtest", json=payload, timeout=60)
    assert resp.status_code == 200, f"API error: {resp.status_code} {resp.text[:200]}"
    return resp.json()


def extract_equity_array(result: dict) -> np.ndarray:
    """Extract equity values from API response."""
    if not result.get("equity_curve"):
        return np.array([])
    return np.array([p["value"] for p in result["equity_curve"]])


def main():
    print("=" * 70)
    print("API-LEVEL END-TO-END LEVERAGE VERIFICATION")
    print("=" * 70)
    print()

    # Run 3 backtests
    results = {}
    for lev in [1, 3, 5]:
        print(f"  Running backtest with leverage={lev}...", end="", flush=True)
        r = run_backtest(lev)
        results[lev] = r
        print(f" done (trades={r['total_trades']}, return={r['total_return']:+.2%})")

    print()
    print("-" * 70)
    print("SECTION 1: Basic sanity checks")
    print("-" * 70)

    for lev, r in results.items():
        eq = extract_equity_array(r)
        print(f"\n  leverage={lev}:")
        print(f"    total_trades     = {r['total_trades']}")
        print(f"    total_return     = {r['total_return']:+.4f}")
        print(f"    sharpe_ratio     = {r['sharpe_ratio']:.4f}")
        print(f"    max_drawdown     = {r['max_drawdown']:.4f}")
        print(f"    win_rate         = {r['win_rate']:.4f}")
        print(f"    total_score      = {r['total_score']:.2f}")
        print(f"    funding_cost     = {r['total_funding_cost']:.4f}")
        print(f"    liquidated       = {r['liquidated']}")
        print(f"    equity_curve_len = {len(eq)}")
        if len(eq) > 0:
            print(f"    equity_first     = {eq[0]:.2f}")
            print(f"    equity_last      = {eq[-1]:.2f}")
            print(f"    equity_min       = {eq.min():.2f}")
            print(f"    equity_max       = {eq.max():.2f}")

    print()
    print("-" * 70)
    print("SECTION 2: Cross-leverage comparison")
    print("-" * 70)

    r1, r3, r5 = results[1], results[3], results[5]
    eq1 = extract_equity_array(r1)
    eq3 = extract_equity_array(r3)
    eq5 = extract_equity_array(r5)

    # Check 1: equity curves should differ
    if len(eq1) > 0 and len(eq3) > 0:
        same_1_3 = np.allclose(eq1, eq3, atol=1)
        print(f"\n  [CHECK] equity_curve L=1 vs L=3 identical? {same_1_3}")
        if same_1_3:
            print(f"    FAIL: L=1 and L=3 should produce different curves!")
        else:
            print(f"    PASS: Curves differ as expected")

        diff_1_3 = np.abs(eq3 - eq1).max()
        print(f"    Max absolute difference: {diff_1_3:.2f}")

    if len(eq1) > 0 and len(eq5) > 0:
        same_1_5 = np.allclose(eq1, eq5, atol=1)
        print(f"\n  [CHECK] equity_curve L=1 vs L=5 identical? {same_1_5}")
        if same_1_5:
            print(f"    FAIL: L=1 and L=5 should produce different curves!")
        else:
            print(f"    PASS: Curves differ as expected")

    # Check 2: funding costs
    print(f"\n  [CHECK] funding_cost L=1 == 0? {r1['total_funding_cost'] == 0}")
    print(f"    L=1: {r1['total_funding_cost']:.4f}  {'PASS' if r1['total_funding_cost'] == 0 else 'FAIL'}")
    print(f"    L=3: {r3['total_funding_cost']:.4f}  {'PASS' if r3['total_funding_cost'] > 0 else 'WARN: no trades or no funding'}")
    print(f"    L=5: {r5['total_funding_cost']:.4f}  {'PASS' if r5['total_funding_cost'] > 0 else 'WARN: no trades or no funding'}")

    if r3['total_funding_cost'] > 0 and r5['total_funding_cost'] > 0:
        print(f"    L=5 cost > L=3 cost? {r5['total_funding_cost'] > r3['total_funding_cost']}  {'PASS' if r5['total_funding_cost'] > r3['total_funding_cost'] else 'UNEXPECTED'}")

    # Check 3: returns should differ
    print(f"\n  [CHECK] total_return differs across leverage levels:")
    ret1, ret3, ret5 = r1['total_return'], r3['total_return'], r5['total_return']
    print(f"    L=1: {ret1:+.4f}")
    print(f"    L=3: {ret3:+.4f}")
    print(f"    L=5: {ret5:+.4f}")
    if r1['total_trades'] > 0:
        differ = not (abs(ret1 - ret3) < 0.0001 and abs(ret3 - ret5) < 0.0001)
        print(f"    Returns differ? {differ}  {'PASS' if differ else 'FAIL'}")

    # Check 4: equity starts at init_cash
    print(f"\n  [CHECK] equity_curve starts at init_cash (100000):")
    for lev, r in results.items():
        eq = extract_equity_array(r)
        if len(eq) > 0:
            start_ok = abs(eq[0] - 100000) < 1
            print(f"    L={lev}: start={eq[0]:.2f}  {'PASS' if start_ok else 'FAIL'}")

    # Check 5: equity curve return matches total_return field
    print(f"\n  [CHECK] equity_curve return matches total_return field:")
    for lev, r in results.items():
        eq = extract_equity_array(r)
        if len(eq) >= 2 and eq[0] > 0:
            curve_ret = eq[-1] / eq[0] - 1
            field_ret = r['total_return']
            match = abs(curve_ret - field_ret) < 0.0001
            print(f"    L={lev}: curve_ret={curve_ret:+.4f} field_ret={field_ret:+.4f}  {'PASS' if match else 'FAIL'}")

    # Check 6: max_drawdown should be larger with higher leverage
    print(f"\n  [CHECK] max_drawdown amplification:")
    dd1, dd3, dd5 = abs(r1['max_drawdown']), abs(r3['max_drawdown']), abs(r5['max_drawdown'])
    print(f"    L=1: {dd1:.4f}")
    print(f"    L=3: {dd3:.4f}")
    print(f"    L=5: {dd5:.4f}")
    if r1['total_trades'] > 0:
        dd_amplifies = dd3 > dd1 and dd5 > dd3
        print(f"    DD amplifies with leverage? {dd_amplifies}  {'PASS' if dd_amplifies else 'UNEXPECTED (may be normal in some cases)'}")

    print()
    print("-" * 70)
    print("SECTION 3: Score consistency")
    print("-" * 70)
    for lev, r in results.items():
        ds = r.get('dimension_scores', {}) or {}
        print(f"\n  L={lev}: total_score={r['total_score']:.2f}")
        for dim, score in ds.items():
            print(f"    {dim}: {score:.2f}")

    print()
    print("=" * 70)
    print("VERIFICATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
