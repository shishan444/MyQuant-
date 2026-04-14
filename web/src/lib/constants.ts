/**
 * Shared constants used across evolution, lab, and strategy modules.
 */

// ---------------------------------------------------------------------------
// Symbols
// ---------------------------------------------------------------------------

export const SYMBOL_OPTIONS = [
  { value: "BTCUSDT", label: "BTC/USDT" },
  { value: "ETHUSDT", label: "ETH/USDT" },
  { value: "BNBUSDT", label: "BNB/USDT" },
  { value: "SOLUSDT", label: "SOL/USDT" },
] as const;

// ---------------------------------------------------------------------------
// Timeframes
// ---------------------------------------------------------------------------

export const TIMEFRAME_POOL_OPTIONS = ["1d", "4h", "1h", "15m"] as const;

export const TIMEFRAME_LABELS: Record<string, string> = {
  "1d": "1D",
  "4h": "4H",
  "1h": "1H",
  "15m": "15M",
};

// Full options for selects (Chinese labels, broader set)
export const TIMEFRAME_SELECT_OPTIONS = [
  { value: "15m", label: "15分钟" },
  { value: "1h", label: "1小时" },
  { value: "4h", label: "4小时" },
  { value: "1d", label: "1天" },
  { value: "1w", label: "1周" },
] as const;

// Short labels for evolution forms
export const TIMEFRAME_FORM_OPTIONS = [
  { value: "1d", label: "1D" },
  { value: "4h", label: "4H" },
  { value: "1h", label: "1H" },
  { value: "15m", label: "15M" },
] as const;

// ---------------------------------------------------------------------------
// Indicators
// ---------------------------------------------------------------------------

export const INDICATOR_GROUPS = [
  {
    label: "趋势",
    items: ["EMA", "SMA", "WMA", "DEMA", "TEMA", "VWAP"],
  },
  {
    label: "动量",
    items: ["RSI", "MACD", "Stochastic", "CCI", "ROC", "Williams %R"],
  },
  {
    label: "波动",
    items: ["BB", "ATR", "Keltner", "Donchian"],
  },
  {
    label: "成交量",
    items: ["OBV", "CMF", "MFI"],
  },
  {
    label: "趋势强度",
    items: ["ADX", "PSAR"],
  },
];

export const INDICATOR_FLAT_LIST = [
  "EMA",
  "SMA",
  "RSI",
  "MACD",
  "BB",
  "ATR",
  "ADX",
  "Stochastic",
  "CCI",
  "OBV",
];

// ---------------------------------------------------------------------------
// Condition types
// ---------------------------------------------------------------------------

export const CONDITION_TYPE_LABELS: Record<string, string> = {
  lt: "<",
  gt: ">",
  le: "<=",
  ge: ">=",
  cross_above: "金叉",
  cross_below: "死叉",
  price_above: "价格在上方",
  price_below: "价格在下方",
};

export const CONDITION_TYPE_SYMBOLS: Record<string, string> = {
  lt: "<",
  gt: ">",
  le: "<=",
  ge: ">=",
  cross_above: "cross_above",
  cross_below: "cross_below",
  price_above: "price_above",
  price_below: "price_below",
};

export const CONDITION_OPTIONS = [
  { value: "lt", label: "<" },
  { value: "gt", label: ">" },
  { value: "le", label: "<=" },
  { value: "ge", label: ">=" },
  { value: "cross_above", label: "金叉" },
  { value: "cross_below", label: "死叉" },
  { value: "price_above", label: "价格在上方" },
  { value: "price_below", label: "价格在下方" },
];

// ---------------------------------------------------------------------------
// Score templates
// ---------------------------------------------------------------------------

export const SCORE_TEMPLATE_LABELS: Record<string, string> = {
  profit_first: "收益优先",
  steady: "稳健优先",
  risk_first: "风控优先",
};

export const OPTIMIZE_TARGETS = [
  { value: "profit_first", label: "最大化收益" },
  { value: "steady", label: "稳健优先" },
  { value: "risk_first", label: "风控优先" },
] as const;

// ---------------------------------------------------------------------------
// Task status
// ---------------------------------------------------------------------------

import type { EvolutionTaskStatus } from "@/types/api";

export const STATUS_LABELS: Record<EvolutionTaskStatus, string> = {
  pending: "等待中",
  running: "探索中",
  paused: "已暂停",
  stopped: "已停止",
  completed: "已完成",
};

export function isActiveStatus(status: EvolutionTaskStatus): boolean {
  return status === "running" || status === "pending";
}
