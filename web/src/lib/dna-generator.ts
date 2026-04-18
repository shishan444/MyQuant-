/**
 * Generate a minimal DNA from WHEN/THEN validation conditions.
 *
 * This is a lossy mapping: Lab conditions become entry/exit signal genes,
 * while full strategy DNA supports guards, logic, risk genes etc.
 * The generated DNA is sufficient for saving and basic backtesting.
 */
import type { ConditionInput, DNA } from "@/types/api";

const CONDITION_TYPE_MAP: Record<string, string> = {
  gt: "gt",
  lt: "lt",
  ge: "ge",
  le: "le",
  touch: "price_above",
  cross_above: "cross_above",
  cross_below: "cross_below",
  spike: "gt",
  shrink: "lt",
  breakout: "cross_above",
  breakdown: "cross_below",
  rise: "gt",
  drop: "lt",
};

function mapCondition(
  cond: ConditionInput,
  role: "entry_trigger" | "exit_trigger"
): unknown {
  const indicator = cond.subject || "close";
  const condType = CONDITION_TYPE_MAP[cond.action] || "gt";
  const target = cond.target || "0";

  let params: Record<string, number> = {};
  // Try to extract period from common indicator patterns
  if (indicator.toLowerCase() === "rsi") {
    params = { period: 14 };
  } else if (indicator.toLowerCase() === "ema") {
    params = { period: 20 };
  } else if (indicator.toLowerCase() === "macd") {
    params = { fast: 12, slow: 26, signal: 9 };
  }

  // Build condition dict
  let condition: Record<string, unknown>;
  if (condType === "price_above" || condType === "price_below") {
    condition = { type: condType };
  } else {
    const threshold = parseFloat(target);
    condition = isNaN(threshold)
      ? { type: condType, target }
      : { type: condType, threshold };
  }

  return {
    indicator: indicator.toUpperCase(),
    params,
    role,
    field_name: null,
    condition,
  };
}

export function generateDnaFromValidation(
  when: ConditionInput[],
  then: ConditionInput[],
  pair: string,
  timeframe: string
): DNA {
  // Map WHEN conditions to entry triggers
  const signal_genes = [
    ...when
      .filter((c) => c.subject)
      .map((c) => mapCondition(c, "entry_trigger")),
    // Map THEN conditions to exit triggers
    ...then
      .filter((c) => c.subject)
      .map((c) => mapCondition(c, "exit_trigger")),
  ];

  return {
    signal_genes: signal_genes as DNA["signal_genes"],
    logic_genes: {
      entry_logic: "AND",
      exit_logic: "AND",
    },
    execution_genes: {
      timeframe: timeframe,
      symbol: pair,
    },
    risk_genes: {
      stop_loss: 0.05,
      take_profit: 0.1,
      position_size: 0.3,
      leverage: 1,
      direction: "long",
    },
    strategy_id: crypto.randomUUID(),
    generation: 0,
    parent_ids: [],
    mutation_ops: [],
  };
}
