import type { DNA } from "@/types/api";

const INDICATOR_TYPE_MAP: Record<string, string> = {
  EMA: "趋势", SMA: "趋势", WMA: "趋势", DEMA: "趋势", TEMA: "趋势",
  RSI: "动量", MACD: "动量", CCI: "动量", STOCH: "动量", WILLR: "动量",
  BB: "波动", ATR: "波动", KC: "波动",
  ADX: "趋势", ICHIMOKU: "趋势",
  MFI: "量价", OBV: "量价", VWAP: "量价",
  SAR: "趋势", TRIX: "动量", ROC: "动量",
};

const DIRECTION_LABEL: Record<string, string> = {
  long: "做多",
  short: "做空",
  mixed: "混合",
};

export function getStrategyType(dna: DNA | null | undefined): string {
  if (!dna) return "未知";
  const genes = dna.layers?.[0]?.signal_genes ?? dna.signal_genes;
  const trigger = genes.find((g) => g.role === "entry_trigger");
  const indicator = trigger?.indicator ?? genes[0]?.indicator ?? "";
  return INDICATOR_TYPE_MAP[indicator] ?? "混合";
}

export function getStrategyName(dna: DNA | null | undefined): string {
  if (!dna) return "未命名策略";
  const genes = dna.layers?.[0]?.signal_genes ?? dna.signal_genes;
  const trigger = genes.find((g) => g.role === "entry_trigger");
  const indicator = trigger?.indicator ?? genes[0]?.indicator ?? "MIX";
  const typeLabel = INDICATOR_TYPE_MAP[indicator] ?? "混合";
  const dirLabel = DIRECTION_LABEL[dna.risk_genes.direction] ?? "做多";
  const tf = dna.execution_genes.timeframe.toUpperCase();
  return `${indicator}${typeLabel} ${dirLabel} ${tf}`;
}
