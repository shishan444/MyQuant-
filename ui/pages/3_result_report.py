"""Page 3: Result Report - view champion strategy, K-line chart, and export report."""

import sys
from pathlib import Path

_parent = str(Path(__file__).resolve().parents[3])
if _parent not in sys.path:
    sys.path.insert(0, _parent)

import json

import pandas as pd
import streamlit as st

from MyQuant.core.backtest.engine import BacktestEngine
from MyQuant.core.data.storage import load_parquet
from MyQuant.core.features.indicators import compute_all_indicators
from MyQuant.core.persistence.db import get_history, get_task, init_db, list_all_tasks
from MyQuant.core.scoring.metrics import compute_metrics
from MyQuant.core.scoring.scorer import score_strategy
from MyQuant.core.strategy.dna import StrategyDNA
from MyQuant.core.visualization.chart_builder import build_champion_report
from MyQuant.ui.components.dna_viewer import render_dna_card, render_dna_json
from MyQuant.ui.components.metrics_card import render_metrics_card

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "market"
DB_PATH = Path(__file__).resolve().parents[2] / "data" / "evolution.db"


@st.cache_data(ttl=300)
def _load_enhanced_df(symbol: str, timeframe: str) -> pd.DataFrame:
    parquet_path = DATA_DIR / f"{symbol}_{timeframe}.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(f"No data for {symbol} {timeframe}")
    df = load_parquet(parquet_path)
    return compute_all_indicators(df)


st.title("Result Report")

init_db(DB_PATH)

# --- Task Selection ---
completed_tasks = list_all_tasks(DB_PATH, status="completed")

# Also check for a task passed from page 2
preselected_task_id = st.session_state.get("report_task_id")

if not completed_tasks:
    st.info("No completed evolution tasks yet. Run an evolution first.")
    if st.button("Go to Strategy Input"):
        st.switch_page("MyQuant/ui/pages/1_strategy_input.py")
    st.stop()

task_options = {t["task_id"]: f"{t['task_id']} ({t['symbol']} {t['timeframe']})" for t in completed_tasks}

default_idx = 0
if preselected_task_id and preselected_task_id in task_options:
    default_idx = list(task_options.keys()).index(preselected_task_id)

selected_task_id = st.selectbox(
    "Select Completed Task",
    options=list(task_options.keys()),
    format_func=lambda x: task_options[x],
    index=default_idx,
)

task = get_task(DB_PATH, selected_task_id)
if not task or not task.get("champion_dna"):
    st.error("No champion DNA found for this task.")
    st.stop()

# --- Load Champion ---
champion_dna = StrategyDNA.from_json(task["champion_dna"])
symbol = task["symbol"]
timeframe = task["timeframe"]
template = task.get("score_template", "profit_first")

st.subheader("Champion Strategy")
render_dna_card(champion_dna)

# --- Load Data & Run Backtest ---
try:
    enhanced_df = _load_enhanced_df(symbol, timeframe)
except FileNotFoundError as e:
    st.error(str(e))
    st.stop()

engine = BacktestEngine()
result = engine.run(champion_dna, enhanced_df)
metrics = compute_metrics(result.equity_curve, result.total_trades)
score_detail = score_strategy(metrics, template)

# --- Metrics ---
st.subheader("Performance Metrics")
render_metrics_card(result, score_detail)

# --- Charts ---
st.subheader("Charts")
try:
    charts = build_champion_report(champion_dna, enhanced_df, result)

    tab1, tab2, tab3 = st.tabs(["K-Line", "Equity Curve", "Quick Preview"])

    with tab1:
        st.plotly_chart(charts["kline"], use_container_width=True)

    with tab2:
        st.plotly_chart(charts["equity"], use_container_width=True)

    with tab3:
        st.plotly_chart(charts["quick_preview"], use_container_width=True)

except Exception as e:
    st.warning(f"Chart generation failed: {e}")

# --- Evolution History ---
history = get_history(DB_PATH, selected_task_id)
if history:
    st.subheader("Evolution History")
    from MyQuant.core.visualization.chart_builder import build_evolution_dashboard
    dashboard = build_evolution_dashboard(history, task.get("target_score", 80.0))
    st.plotly_chart(dashboard["generation"], use_container_width=True)

# --- DNA JSON ---
with st.expander("Raw DNA JSON"):
    render_dna_json(champion_dna)

# --- Export ---
st.divider()
report_data = {
    "task_id": selected_task_id,
    "symbol": symbol,
    "timeframe": timeframe,
    "template": template,
    "stop_reason": task.get("stop_reason"),
    "champion_dna": champion_dna.to_dict(),
    "metrics": metrics,
    "score": score_detail,
    "history_summary": [
        {"generation": h["generation"], "best_score": h["best_score"], "avg_score": h["avg_score"]}
        for h in history
    ],
}

st.download_button(
    label="Download Report (JSON)",
    data=json.dumps(report_data, indent=2, ensure_ascii=False),
    file_name=f"report_{selected_task_id}.json",
    mime="application/json",
)
