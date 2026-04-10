"""Page 2: Evolution Monitor - real-time progress of running evolution."""

import sys
from pathlib import Path

_parent = str(Path(__file__).resolve().parents[3])
if _parent not in sys.path:
    sys.path.insert(0, _parent)

import os
import signal as signal_module

import streamlit as st

from MyQuant.core.persistence.db import (
    get_history, get_running_task, get_task, init_db,
)
from MyQuant.core.visualization.chart_builder import build_evolution_dashboard

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "evolution.db"


st.title("Evolution Monitor")

init_db(DB_PATH)

# --- Get active task ---
task_id = st.session_state.get("evolution_task_id")
if not task_id:
    # Try to find a running task
    running = get_running_task(DB_PATH)
    if running:
        task_id = running["task_id"]
        st.session_state["evolution_task_id"] = task_id

if not task_id:
    st.info("No evolution task is currently running. Start one from Strategy Input.")
    if st.button("Go to Strategy Input"):
        st.switch_page("MyQuant/ui/pages/1_strategy_input.py")
    st.stop()

task = get_task(DB_PATH, task_id)
if not task:
    st.error(f"Task {task_id} not found.")
    st.stop()

# --- Status Panel ---
st.subheader(f"Task: {task_id}")
status = task.get("status", "unknown")

is_running = status == "running"

status_color = "green" if status == "completed" else ("orange" if is_running else "red")
st.markdown(f"Status: **:{status_color}[{status}]**")

col1, col2, col3, col4 = st.columns(4)

history = get_history(DB_PATH, task_id)
latest_gen = len(history)
best_score = history[-1]["best_score"] if history else 0.0
avg_score = history[-1]["avg_score"] if history else 0.0
target = task.get("target_score", 80.0)

with col1:
    st.metric("Generation", latest_gen)
with col2:
    st.metric("Best Score", f"{best_score:.1f}")
with col3:
    st.metric("Avg Score", f"{avg_score:.1f}")
with col4:
    st.metric("Target", f"{target:.1f}")

# --- Auto-refresh fragment ---
@st.fragment(run_every="5s" if is_running else None)
def render_live_chart():
    """Render the generation chart with auto-refresh when running."""
    hist = get_history(DB_PATH, task_id)
    if hist:
        dashboard = build_evolution_dashboard(hist, target)
        st.plotly_chart(dashboard["generation"], use_container_width=True)

    # Re-check status
    t = get_task(DB_PATH, task_id)
    if t and t["status"] == "completed":
        st.success("Evolution completed!")
        if st.button("View Result Report"):
            st.session_state["report_task_id"] = task_id
            st.switch_page("MyQuant/ui/pages/3_result_report.py")

render_live_chart()

# --- Controls ---
st.divider()
col1, col2 = st.columns(2)

with col1:
    pid = st.session_state.get("evolution_pid")
    if pid and is_running:
        if st.button("Stop Evolution", type="secondary"):
            try:
                os.kill(pid, signal_module.SIGTERM)
                st.warning(f"Sent SIGTERM to process {pid}")
            except ProcessLookupError:
                st.info("Process already terminated.")
            except PermissionError:
                st.error("Permission denied to kill process.")

with col2:
    if st.button("Refresh Now"):
        st.rerun()

# --- Mutation Log ---
if history:
    with st.expander("Generation Details", expanded=False):
        for h in reversed(history[-20:]):
            st.markdown(
                f"Gen {h['generation']}: "
                f"Best={h['best_score']:.1f}, "
                f"Avg={h['avg_score']:.1f}"
            )
