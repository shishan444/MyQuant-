"""MyQuant - BTC/ETH Quantitative Trading Strategy Evolution Tool."""

import sys
from pathlib import Path

# Ensure the parent directory is in sys.path so `from MyQuant.xxx` resolves
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

import streamlit as st

from MyQuant.ui.components.filter_controls import render_sidebar_controls


def main():
    st.set_page_config(
        page_title="MyQuant",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    sidebar_config = render_sidebar_controls()
    for key, value in sidebar_config.items():
        st.session_state[key] = value

    pg = st.navigation([
        st.Page("ui/pages/1_strategy_input.py", title="Strategy Input", icon="🎯"),
        st.Page("ui/pages/2_evolution_monitor.py", title="Evolution Monitor", icon="🔄"),
        st.Page("ui/pages/3_result_report.py", title="Result Report", icon="📊"),
    ])
    pg.run()


if __name__ == "__main__":
    main()
