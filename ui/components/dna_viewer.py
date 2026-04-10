"""DNA viewer component for Streamlit: renders strategy DNA details."""

from __future__ import annotations

from typing import Optional

import streamlit as st

from MyQuant.core.strategy.dna import StrategyDNA, SignalRole


def render_dna_card(dna: StrategyDNA, container=None) -> None:
    """Render an expandable card showing DNA structure.

    Args:
        dna: Strategy DNA to display.
        container: Optional Streamlit container (defaults to st).
    """
    ctx = container or st

    with ctx.expander("Strategy DNA", expanded=False):
        # Signal genes
        st.markdown("**Signal Genes**")
        for i, gene in enumerate(dna.signal_genes):
            role_label = {
                SignalRole.ENTRY_TRIGGER: "Entry Trigger",
                SignalRole.ENTRY_GUARD: "Entry Guard",
                SignalRole.EXIT_TRIGGER: "Exit Trigger",
                SignalRole.EXIT_GUARD: "Exit Guard",
            }.get(gene.role, gene.role.value)

            condition_str = _format_condition(gene.condition)
            st.markdown(
                f"  {i+1}. **{gene.indicator}** ({gene.params}) "
                f"| Role: {role_label} | {condition_str}"
            )

        # Logic genes
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Entry Logic", dna.logic_genes.entry_logic)
        with col2:
            st.metric("Exit Logic", dna.logic_genes.exit_logic)

        # Risk genes
        st.markdown("**Risk Management**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Stop Loss", f"{dna.risk_genes.stop_loss:.1%}")
        with col2:
            tp = dna.risk_genes.take_profit
            st.metric("Take Profit", f"{tp:.1%}" if tp else "None")
        with col3:
            st.metric("Position Size", f"{dna.risk_genes.position_size:.0%}")


def render_dna_json(dna: StrategyDNA) -> None:
    """Render raw DNA JSON in a code block."""
    st.code(dna.to_json(), language="json")


def _format_condition(condition: dict) -> str:
    """Format a condition dict to a human-readable string."""
    cond_type = condition.get("type", "?")
    threshold = condition.get("threshold")
    if threshold is not None:
        return f"{cond_type} {threshold}"
    return cond_type
