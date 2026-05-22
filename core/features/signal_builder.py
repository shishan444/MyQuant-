"""Signal builder: extract indicator requirements from DNA and build entry/exit signals.

Higher-level interface than executor.py - takes raw DNA and enhanced DataFrame,
resolves indicator columns, and returns boolean signal Series.

DEPRECATED: This module is dead code. Production code uses executor.py's
_get_indicator_column() instead. Only test files reference this module.
"""

from __future__ import annotations

import warnings

from typing import Any, Dict, List, Tuple

import pandas as pd

from core.strategy.dna import StrategyDNA, SignalRole
from core.strategy.executor import evaluate_condition, combine_signals, SignalSet
from core.features.registry import INDICATOR_REGISTRY, resolve_indicator_column


def extract_indicator_requirements(dna: StrategyDNA) -> List[Tuple[str, Dict[str, Any]]]:
    """Extract unique indicator name + param combinations from DNA.

    Returns:
        List of (indicator_name, params) tuples, deduplicated.
    """
    seen = set()
    result = []
    for gene in dna.signal_genes:
        key = (gene.indicator, tuple(sorted(gene.params.items())))
        if key not in seen:
            seen.add(key)
            result.append((gene.indicator, gene.params))
    return result


def _resolve_column(df: pd.DataFrame, indicator: str, params: Dict[str, Any],
                    field_name: str | None = None) -> pd.Series | None:
    """Find the right DataFrame column for an indicator gene.

    Returns None if column not found.
    """
    reg = INDICATOR_REGISTRY.get(indicator)
    if reg is not None:
        col = resolve_indicator_column(
            indicator, params, field_name or "", reg.naming
        )
    else:
        # Generic fallback for unknown indicators
        matches = [c for c in df.columns if c.lower().startswith(indicator.lower())]
        if matches:
            col = matches[0]
        else:
            return None

    if col in df.columns:
        return df[col]

    # Prefix fallback
    matches = [c for c in df.columns if col in c]
    if matches:
        return df[matches[0]]

    return None


def build_signals(
    dna: StrategyDNA,
    enhanced_df: pd.DataFrame,
) -> Tuple[pd.Series, pd.Series]:
    """Build entry/exit boolean Series from StrategyDNA using enhanced DataFrame.

    Similar to executor.dna_to_signals but with more robust column resolution.
    Missing indicator columns are silently skipped.
    Returns (entries, exits) for backward compatibility.
    """
    sig_set = build_signal_set(dna, enhanced_df)
    return sig_set.entries, sig_set.exits


def build_signal_set(
    dna: StrategyDNA,
    enhanced_df: pd.DataFrame,
) -> SignalSet:
    """Build full SignalSet with adds/reduces from StrategyDNA."""
    close = enhanced_df["close"]

    entry_triggers, entry_guards = [], []
    exit_triggers, exit_guards = [], []
    add_triggers, add_guards = [], []
    reduce_triggers, reduce_guards = [], []

    for gene in dna.signal_genes:
        col_series = _resolve_column(enhanced_df, gene.indicator, gene.params, gene.field_name)
        if col_series is None:
            continue

        signal = evaluate_condition(col_series, close, gene.condition)
        signal = signal.fillna(False)

        if gene.role == SignalRole.ENTRY_TRIGGER:
            entry_triggers.append(signal)
        elif gene.role == SignalRole.ENTRY_GUARD:
            entry_guards.append(signal)
        elif gene.role == SignalRole.EXIT_TRIGGER:
            exit_triggers.append(signal)
        elif gene.role == SignalRole.EXIT_GUARD:
            exit_guards.append(signal)
        elif gene.role == SignalRole.ADD_TRIGGER:
            add_triggers.append(signal)
        elif gene.role == SignalRole.ADD_GUARD:
            add_guards.append(signal)
        elif gene.role == SignalRole.REDUCE_TRIGGER:
            reduce_triggers.append(signal)
        elif gene.role == SignalRole.REDUCE_GUARD:
            reduce_guards.append(signal)

    # Combine
    all_entry = entry_triggers + entry_guards
    if not all_entry:
        entries = pd.Series(False, index=enhanced_df.index)
    else:
        entries = combine_signals(all_entry, dna.logic_genes.entry_logic)

    all_exit = exit_triggers + exit_guards
    if not all_exit:
        exits = pd.Series(False, index=enhanced_df.index)
    else:
        exits = combine_signals(all_exit, dna.logic_genes.exit_logic)

    add_logic = getattr(dna.logic_genes, 'add_logic', 'AND') or 'AND'
    reduce_logic = getattr(dna.logic_genes, 'reduce_logic', 'AND') or 'AND'

    all_add = add_triggers + add_guards
    adds = combine_signals(all_add, add_logic) if all_add else pd.Series(False, index=enhanced_df.index)

    all_reduce = reduce_triggers + reduce_guards
    reduces = combine_signals(all_reduce, reduce_logic) if all_reduce else pd.Series(False, index=enhanced_df.index)

    # Prevent simultaneous entry+exit (favor exit)
    both = entries & exits
    entries = entries & ~both

    return SignalSet(
        entries=entries,
        exits=exits,
        adds=adds,
        reduces=reduces,
    )
