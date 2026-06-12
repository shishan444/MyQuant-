"""分析 6.4 进化产出策略的 mixed 方向实际交易情况

检查 direction=mixed 的策略在实际回测中是否真正进行了双向交易（多+空），
还是只进行了单方向交易（仅多或仅空）。
"""

import json
import sys
import sqlite3
import warnings
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from core.strategy.dna import StrategyDNA, SignalRole
from core.backtest.engine import BacktestEngine
from core.data.mtf_loader import load_and_prepare_df, load_mtf_data

warnings.filterwarnings("ignore")

DB_PATH = Path("data/quant.db")
DATA_DIR = Path("data/market")
TASK_ID = "0ea0f7d4-3307-49b6-9ef9-cee1c7d35a92"


def check_dna_direction_genes(dna_dict: dict) -> dict:
    """检查 DNA 中 DIRECTION 角色的信号基因。"""
    direction_genes = []

    # 顶层 signal_genes
    for sg in dna_dict.get("signal_genes", dna_dict.get("signals", [])):
        role = sg.get("role", "")
        if role == "direction":
            direction_genes.append({
                "source": "top_level",
                "indicator": sg.get("indicator", "?"),
                "condition": sg.get("condition", {}),
            })

    # 各层 signal_genes
    for layer in dna_dict.get("layers", []) or []:
        for sg in layer.get("signal_genes", []):
            role = sg.get("role", "")
            if role == "direction":
                direction_genes.append({
                    "source": f"layer_{layer.get('timeframe', '?')}",
                    "indicator": sg.get("indicator", "?"),
                    "condition": sg.get("condition", {}),
                })

    return {
        "has_direction_gene": len(direction_genes) > 0,
        "direction_gene_count": len(direction_genes),
        "direction_genes": direction_genes,
    }


def analyze_strategy_direction(dna_json: str, train_df, dfs_by_timeframe) -> dict:
    """重跑回测并分析交易方向。"""
    dna = StrategyDNA.from_dict(json.loads(dna_json))
    engine = BacktestEngine(init_cash=100000, fee=0.001, slippage=0.0005)
    result = engine.run(dna, train_df, dfs_by_timeframe=dfs_by_timeframe)

    long_trades = 0
    short_trades = 0

    if result.trades_df is not None and len(result.trades_df) > 0:
        side_col = None
        for col_name in ["Side", "side", "direction"]:
            if col_name in result.trades_df.columns:
                side_col = col_name
                break

        if side_col:
            side_counts = result.trades_df[side_col].value_counts()
            long_trades = int(side_counts.get(0, side_counts.get("Buy", 0)))
            short_trades = int(side_counts.get(1, side_counts.get("Sell", 0)))
        else:
            # 没有 Side 列，尝试从 Size 推断
            if "Size" in result.trades_df.columns:
                sizes = result.trades_df["Size"]
                long_trades = int((sizes > 0).sum())
                short_trades = int((sizes < 0).sum())

    total = long_trades + short_trades
    has_both = long_trades > 0 and short_trades > 0
    direction_type = "双向(多+空)" if has_both else (
        "仅做多" if long_trades > 0 else (
            "仅做空" if short_trades > 0 else "无交易"
        )
    )

    return {
        "total_trades": total,
        "long_trades": long_trades,
        "short_trades": short_trades,
        "has_both_directions": has_both,
        "direction_type": direction_type,
        "metrics_annual_return": result.metrics_dict.get("annual_return", 0) if result.metrics_dict else 0,
    }


def main():
    print("=" * 90)
    print("Mixed 方向策略实际交易分析")
    print(f"任务: {TASK_ID}")
    print("=" * 90)

    # 1. 加载所有策略
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT strategy_id, name, dna_json, best_score, generation "
        "FROM strategy WHERE source_task_id = ? ORDER BY best_score DESC",
        (TASK_ID,),
    ).fetchall()
    conn.close()

    strategies = [dict(r) for r in rows]
    print(f"\n共 {len(strategies)} 条策略")

    # 2. 先分析 DNA 中的 DIRECTION 基因分布
    print("\n" + "-" * 80)
    print("第一部分：DNA 中 DIRECTION 信号基因分布")
    print("-" * 80)

    has_dir_count = 0
    no_dir_count = 0
    dir_gene_indicators = Counter()

    for s in strategies:
        dna_dict = json.loads(s["dna_json"])
        info = check_dna_direction_genes(dna_dict)
        if info["has_direction_gene"]:
            has_dir_count += 1
            for dg in info["direction_genes"]:
                dir_gene_indicators[dg["indicator"]] += 1
        else:
            no_dir_count += 1

    print(f"  有 DIRECTION 基因: {has_dir_count} ({has_dir_count/len(strategies)*100:.1f}%)")
    print(f"  无 DIRECTION 基因: {no_dir_count} ({no_dir_count/len(strategies)*100:.1f}%)")

    if dir_gene_indicators:
        print(f"\n  DIRECTION 基因使用的指标:")
        for ind, cnt in dir_gene_indicators.most_common():
            print(f"    {ind}: {cnt} 次")

    # 3. 准备数据
    print("\n" + "-" * 80)
    print("第二部分：重跑回测分析实际交易方向")
    print("-" * 80)

    print("\n加载数据...")
    enhanced_df = load_and_prepare_df(
        DATA_DIR, "BTCUSDT", "1h",
        data_start="2024-01-01", data_end="2024-09-20",
    )
    split_idx = int(len(enhanced_df) * 0.7)
    train_df = enhanced_df.iloc[:split_idx].copy()
    dfs_by_timeframe = load_mtf_data(DATA_DIR, "BTCUSDT", "1h", enhanced_df, {"4h", "1h", "3d"})
    print(f"  训练集: {len(train_df)} bars")

    # 4. 分析所有策略（抽样 30 条以节省时间）
    sample_size = min(30, len(strategies))
    # 均匀采样覆盖不同分数段
    step = max(1, len(strategies) // sample_size)
    sampled = [strategies[i] for i in range(0, len(strategies), step)][:sample_size]

    print(f"\n分析 {len(sampled)} 条策略的交易方向...")
    print()

    results = []
    for i, s in enumerate(sampled):
        dna_dict = json.loads(s["dna_json"])
        dir_info = check_dna_direction_genes(dna_dict)
        trade_info = analyze_strategy_direction(s["dna_json"], train_df, dfs_by_timeframe)

        results.append({
            "name": s["name"][:45],
            "score": s["best_score"],
            "gen": s["generation"],
            "has_dir_gene": dir_info["has_direction_gene"],
            "dir_gene_count": dir_info["direction_gene_count"],
            **trade_info,
        })

    # 5. 输出结果
    print(f"{'策略名称':<45s} | {'评分':>6s} | {'方向基因':>6s} | {'总交易':>4s} | {'做多':>4s} | {'做空':>4s} | {'实际方向':>12s}")
    print("-" * 110)

    for r in results:
        dir_gene_str = f"{'有('+str(r['dir_gene_count'])+')' if r['has_dir_gene'] else '无':>6s}"
        print(
            f"{r['name']:<45s} | {r['score']:>6.1f} | {dir_gene_str} | "
            f"{r['total_trades']:>4d} | {r['long_trades']:>4d} | {r['short_trades']:>4d} | "
            f"{r['direction_type']:>12s}"
        )

    # 6. 统计汇总
    print("\n" + "=" * 90)
    print("统计汇总")
    print("=" * 90)

    total = len(results)
    both_dir = sum(1 for r in results if r["has_both_directions"])
    long_only = sum(1 for r in results if r["long_trades"] > 0 and r["short_trades"] == 0)
    short_only = sum(1 for r in results if r["short_trades"] > 0 and r["long_trades"] == 0)
    no_trade = sum(1 for r in results if r["total_trades"] == 0)

    print(f"\n  总分析策略数: {total}")
    print(f"  双向交易(多+空): {both_dir} ({both_dir/total*100:.1f}%)")
    print(f"  仅做多:          {long_only} ({long_only/total*100:.1f}%)")
    print(f"  仅做空:          {short_only} ({short_only/total*100:.1f}%)")
    print(f"  无交易:          {no_trade} ({no_trade/total*100:.1f}%)")

    # 有 DIRECTION 基因 vs 无 DIRECTION 基因的交易方向分布
    with_gene = [r for r in results if r["has_dir_gene"]]
    without_gene = [r for r in results if not r["has_dir_gene"]]

    if with_gene:
        both_wg = sum(1 for r in with_gene if r["has_both_directions"])
        long_wg = sum(1 for r in with_gene if r["long_trades"] > 0 and r["short_trades"] == 0)
        short_wg = sum(1 for r in with_gene if r["short_trades"] > 0 and r["long_trades"] == 0)
        print(f"\n  有 DIRECTION 基因 ({len(with_gene)} 条):")
        print(f"    双向: {both_wg}  仅多: {long_wg}  仅空: {short_wg}")

    if without_gene:
        both_ng = sum(1 for r in without_gene if r["has_both_directions"])
        long_ng = sum(1 for r in without_gene if r["long_trades"] > 0 and r["short_trades"] == 0)
        short_ng = sum(1 for r in without_gene if r["short_trades"] > 0 and r["long_trades"] == 0)
        print(f"\n  无 DIRECTION 基因 ({len(without_gene)} 条):")
        print(f"    双向: {both_ng}  仅多: {long_ng}  仅空: {short_ng}")

    # 7. 结论
    print("\n" + "=" * 90)
    print("结论")
    print("=" * 90)

    if both_dir > 0:
        print(f"\n  [结论] 有 {both_dir}/{total} 条策略进行了真正的双向交易（多+空）")
    if long_only > 0:
        print(f"  [结论] 有 {long_only}/{total} 条策略虽然标记为 mixed 但实际仅做多")
    if short_only > 0:
        print(f"  [结论] 有 {short_only}/{total} 条策略虽然标记为 mixed 但实际仅做空")

    if both_dir == 0:
        print(f"\n  [结论] 所有 {total} 条 mixed 策略均未进行双向交易")
        print("  原因：DIRECTION 基因信号在同一市场条件下始终输出相同方向")


if __name__ == "__main__":
    main()
