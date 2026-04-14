export interface IndicatorConfig {
  id: string;
  type: string;
  params: Record<string, number>;
  visible: boolean;
}

export interface LabConfig {
  datasetId: string;
  symbol: string;
  timeframe: string;
  indicators: IndicatorConfig[];
  scoreTemplate: string;
  initCash: number;
  fee: number;
  slippage: number;
}

export type ScoreTemplate = "profit_first" | "steady" | "risk_first" | "custom";

export const INDICATOR_OPTIONS = [
  "EMA",
  "SMA",
  "RSI",
  "MACD",
  "BB",
  "ATR",
  "Stochastic",
  "CCI",
  "ADX",
  "OBV",
] as const;

export const TIMEFRAME_OPTIONS = [
  { value: "1m", label: "1 分钟" },
  { value: "5m", label: "5 分钟" },
  { value: "15m", label: "15 分钟" },
  { value: "1h", label: "1 小时" },
  { value: "4h", label: "4 小时" },
  { value: "1d", label: "1 天" },
] as const;
