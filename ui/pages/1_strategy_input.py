"""Page 1: Strategy Input - build or edit strategy DNA, preview backtest, start evolution."""

import sys
from pathlib import Path

_parent = str(Path(__file__).resolve().parents[3])
if _parent not in sys.path:
    sys.path.insert(0, _parent)

import json
import multiprocessing
import uuid

import numpy as np
import pandas as pd
import streamlit as st
import yaml

from MyQuant.core.backtest.engine import BacktestEngine
from MyQuant.core.features.indicators import INDICATOR_REGISTRY, compute_all_indicators
from MyQuant.core.persistence.db import init_db, save_task
from MyQuant.core.scoring.metrics import compute_metrics
from MyQuant.core.scoring.scorer import score_strategy
from MyQuant.core.strategy.dna import (
    ExecutionGenes, LogicGenes, RiskGenes, SignalGene, SignalRole, StrategyDNA,
)
from MyQuant.core.strategy.validator import validate_dna
from MyQuant.core.visualization.chart_builder import build_champion_report
from MyQuant.ui.components.dna_viewer import render_dna_card
from MyQuant.ui.components.metrics_card import render_metrics_card

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "market"
DB_PATH = Path(__file__).resolve().parents[2] / "data" / "evolution.db"


def _load_config() -> dict:
    config_path = Path(__file__).resolve().parents[2] / "config.yaml"
    if config_path.exists():
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


def _load_enhanced_df(symbol: str, timeframe: str) -> pd.DataFrame | None:
    parquet_path = DATA_DIR / f"{symbol}_{timeframe}.parquet"
    if not parquet_path.exists():
        return None
    df = pd.read_parquet(parquet_path, engine="pyarrow")
    return compute_all_indicators(df)


def _run_evolution_process(task_id: str, config: dict):
    """Subprocess entry point for evolution. WSL2-safe: uses spawn."""
    # This function is called inside a subprocess.
    # It must import everything it needs locally.
    from MyQuant.core.evolution.engine import EvolutionEngine
    from MyQuant.core.backtest.engine import BacktestEngine
    from MyQuant.core.scoring.metrics import compute_metrics
    from MyQuant.core.scoring.scorer import score_strategy
    from MyQuant.core.strategy.dna import StrategyDNA
    from MyQuant.core.features.indicators import compute_all_indicators
    from MyQuant.core.data.storage import load_parquet
    from MyQuant.core.persistence.db import (
        init_db, update_task, save_snapshot, save_history,
    )
    from pathlib import Path
    import pandas as pd

    db_path = Path(config["db_path"])
    init_db(db_path)

    dna = StrategyDNA.from_json(config["initial_dna"])
    symbol = config["symbol"]
    timeframe = config["timeframe"]
    template_name = config["template"]
    target_score = config["target_score"]
    population_size = config["population_size"]
    max_generations = config["max_generations"]

    # Load data
    parquet_path = Path(config["data_dir"]) / f"{symbol}_{timeframe}.parquet"
    df = load_parquet(parquet_path)
    enhanced_df = compute_all_indicators(df)

    bt_engine = BacktestEngine()

    def evaluate(individual: StrategyDNA) -> float:
        try:
            result = bt_engine.run(individual, enhanced_df)
            metrics = compute_metrics(result.equity_curve, result.total_trades)
            score_detail = score_strategy(metrics, template_name)
            return score_detail["total_score"]
        except Exception:
            return 0.0

    def on_generation(gen, best_score, avg_score):
        try:
            save_history(db_path, task_id, gen, best_score, avg_score, "")
        except Exception:
            pass

    engine = EvolutionEngine(
        target_score=target_score,
        template_name=template_name,
        population_size=population_size,
        max_generations=max_generations,
    )

    result = engine.evolve(dna, evaluate, on_generation)

    # Save final state
    update_task(
        db_path, task_id,
        status="completed",
        champion_dna=result["champion"],
        stop_reason=result["stop_reason"],
    )


st.title("Strategy Input")
st.markdown("Build a strategy DNA, preview its backtest, then launch evolution.")

# --- Load market data ---
symbol = st.session_state.get("selected_symbol", "BTCUSDT")
timeframe = st.session_state.get("selected_timeframe", "4h")
template = st.session_state.get("selected_template", "profit_first")

enhanced_df = _load_enhanced_df(symbol, timeframe)
if enhanced_df is None:
    st.warning(f"No market data found for {symbol} {timeframe}. Please download data first.")
    st.info("Run: `python -c \"from MyQuant.core.data.updater import update_market_data; update_market_data('BTCUSDT','4h')\"`")
    st.stop()

# --- Strategy Builder Form ---
st.subheader("Signal Genes")

indicators = sorted(INDICATOR_REGISTRY.keys())
roles = ["entry_trigger", "entry_guard", "exit_trigger", "exit_guard"]
conditions = ["lt", "gt", "le", "ge", "cross_above", "cross_below", "price_above", "price_below"]

signal_genes_data = []
num_signals = st.number_input("Number of Signals", min_value=2, max_value=8, value=2, step=1)

for i in range(num_signals):
    with st.expander(f"Signal #{i+1}", expanded=(i < 2)):
        col1, col2 = st.columns(2)
        with col1:
            indicator = st.selectbox(f"Indicator #{i+1}", indicators, key=f"ind_{i}",
                                     index=indicators.index("RSI") if "RSI" in indicators else 0)
            role = st.selectbox(f"Role #{i+1}", roles, key=f"role_{i}", index=0)
        with col2:
            condition_type = st.selectbox(f"Condition #{i+1}", conditions, key=f"cond_{i}",
                                          index=0)
            threshold = st.number_input(f"Threshold #{i+1}", value=50.0, key=f"thresh_{i}",
                                        disabled=(condition_type in ("price_above", "price_below")))

        # Parse params based on indicator
        ind_def = INDICATOR_REGISTRY.get(indicator)
        params = {}
        if ind_def:
            for pname, pdef in ind_def.params.items():
                val = st.number_input(
                    f"{pname}",
                    value=float(pdef.default),
                    key=f"param_{i}_{pname}",
                    min_value=float(pdef.min),
                    max_value=float(pdef.max),
                    step=float(pdef.step),
                )
                params[pname] = int(val) if pdef.type == "int" else val

        cond = {"type": condition_type}
        if condition_type not in ("price_above", "price_below"):
            cond["threshold"] = threshold

        signal_genes_data.append({
            "indicator": indicator,
            "params": params or {"period": 14},
            "role": role,
            "condition": cond,
        })

st.subheader("Logic & Risk")
col1, col2 = st.columns(2)
with col1:
    entry_logic = st.selectbox("Entry Logic", ["AND", "OR"], index=0)
    exit_logic = st.selectbox("Exit Logic", ["AND", "OR"], index=1)
with col2:
    stop_loss = st.slider("Stop Loss", 0.005, 0.20, 0.05, 0.005, format="%.3f")
    take_profit = st.slider("Take Profit", 0.0, 0.50, 0.10, 0.01, format="%.2f")
    position_size = st.slider("Position Size", 0.1, 1.0, 0.3, 0.1)

tp_value = take_profit if take_profit > 0 else None

# --- Build DNA ---
if st.button("Build Strategy DNA"):
    signal_genes = [
        SignalGene(
            indicator=sg["indicator"],
            params=sg["params"],
            role=SignalRole(sg["role"]),
            condition=sg["condition"],
        )
        for sg in signal_genes_data
    ]

    dna = StrategyDNA(
        signal_genes=signal_genes,
        logic_genes=LogicGenes(entry_logic=entry_logic, exit_logic=exit_logic),
        execution_genes=ExecutionGenes(timeframe=timeframe, symbol=symbol),
        risk_genes=RiskGenes(stop_loss=stop_loss, take_profit=tp_value, position_size=position_size),
    )

    validation = validate_dna(dna)
    if not validation.is_valid:
        st.error("Invalid DNA: " + "; ".join(validation.errors))
    else:
        st.session_state["current_dna"] = dna
        st.success("Strategy DNA built successfully!")

# --- Preview ---
if "current_dna" in st.session_state:
    dna = st.session_state["current_dna"]
    render_dna_card(dna)

    if st.button("Preview Backtest"):
        with st.spinner("Running backtest..."):
            engine = BacktestEngine()
            result = engine.run(dna, enhanced_df)
            metrics = compute_metrics(result.equity_curve, result.total_trades)
            score_detail = score_strategy(metrics, template)

            st.session_state["preview_result"] = result
            st.session_state["preview_score"] = score_detail

    if "preview_result" in st.session_state:
        result = st.session_state["preview_result"]
        score_detail = st.session_state.get("preview_score")
        render_metrics_card(result, score_detail)

        # Charts
        try:
            charts = build_champion_report(dna, enhanced_df, result)
            st.plotly_chart(charts["kline"], use_container_width=True)
            st.plotly_chart(charts["equity"], use_container_width=True)
        except Exception as e:
            st.warning(f"Chart generation failed: {e}")

# --- Evolution Launch ---
st.divider()
st.subheader("Launch Evolution")

if "current_dna" not in st.session_state:
    st.info("Build a strategy DNA first to enable evolution launch.")
    st.stop()

config = _load_config()
evo_config = config.get("evolution", {})

col1, col2, col3 = st.columns(3)
with col1:
    target_score = st.slider("Target Score", 60, 95, 80, 1)
with col2:
    pop_size = st.slider("Population Size", 10, 30, evo_config.get("population_size", 15))
with col3:
    max_gens = st.slider("Max Generations", 50, 300, evo_config.get("max_generations", 200))

if st.button("Start Evolution", type="primary"):
    dna = st.session_state["current_dna"]
    task_id = str(uuid.uuid4())[:8]

    init_db(DB_PATH)
    save_task(
        db_path=DB_PATH,
        task_id=task_id,
        target_score=target_score,
        template=template,
        symbol=symbol,
        timeframe=timeframe,
        initial_dna=dna,
    )

    # Launch subprocess
    mp_config = multiprocessing.get_context("spawn")
    process_config = {
        "db_path": str(DB_PATH),
        "data_dir": str(DATA_DIR),
        "initial_dna": dna.to_json(),
        "symbol": symbol,
        "timeframe": timeframe,
        "template": template,
        "target_score": target_score,
        "population_size": pop_size,
        "max_generations": max_gens,
    }

    p = mp_config.Process(
        target=_run_evolution_process,
        args=(task_id, process_config),
        daemon=True,
    )
    p.start()

    st.session_state["evolution_pid"] = p.pid
    st.session_state["evolution_task_id"] = task_id
    st.success(f"Evolution started! Task ID: {task_id}")
    st.switch_page("MyQuant/ui/pages/2_evolution_monitor.py")
