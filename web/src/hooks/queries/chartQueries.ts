import { queryOptions } from "@tanstack/react-query";
import { getOhlcvBySymbol, getChartIndicators } from "@/services/datasets";

// ---------------------------------------------------------------------------
// Query Keys
// ---------------------------------------------------------------------------

export const chartKeys = {
  ohlcv: (
    symbol: string,
    timeframe: string,
    dateRange?: { start?: string; end?: string },
  ) => ["ohlcv", symbol, timeframe, dateRange] as const,

  indicators: (
    symbol: string,
    timeframe: string,
    params: {
      start?: string;
      end?: string;
      subChartType: string;
      emaPeriods: string;
      bollEnabled: boolean;
      bollPeriod: number;
      bollStd: number;
      rsiEnabled: boolean;
      rsiPeriod: number;
      macdEnabled: boolean;
      kdjEnabled: boolean;
    },
  ) => ["chart-indicators", symbol, timeframe, params] as const,
};

// ---------------------------------------------------------------------------
// Query Options
// ---------------------------------------------------------------------------

export function ohlcvOptions(
  symbol: string,
  timeframe: string,
  dateRange?: { start?: string; end?: string },
) {
  return queryOptions({
    queryKey: chartKeys.ohlcv(symbol, timeframe, dateRange),
    queryFn: () =>
      getOhlcvBySymbol(symbol, timeframe, {
        start: dateRange?.start || undefined,
        end: dateRange?.end || undefined,
        limit: 10000,
      }),
    enabled: !!symbol && !!timeframe,
    staleTime: 60_000,
  });
}

export interface ChartIndicatorParams {
  start?: string;
  end?: string;
  emaPeriods: string;
  bollEnabled: boolean;
  bollPeriod: number;
  bollStd: number;
  rsiEnabled: boolean;
  rsiPeriod: number;
  macdEnabled: boolean;
  kdjEnabled: boolean;
}

export function chartIndicatorOptions(
  symbol: string,
  timeframe: string,
  subChartType: string,
  params: ChartIndicatorParams,
  options?: { enabled?: boolean },
) {
  return queryOptions({
    queryKey: chartKeys.indicators(symbol, timeframe, {
      ...params,
      start: params.start,
      end: params.end,
      subChartType,
    }),
    queryFn: () =>
      getChartIndicators(symbol, timeframe, {
        start: params.start || undefined,
        end: params.end || undefined,
        ema_periods: params.emaPeriods || undefined,
        boll_enabled: params.bollEnabled,
        boll_period: params.bollPeriod,
        boll_std: params.bollStd,
        rsi_enabled: params.rsiEnabled,
        rsi_period: params.rsiPeriod,
        macd_enabled: params.macdEnabled,
        kdj_enabled: params.kdjEnabled,
        limit: 10000,
      }),
    enabled: options?.enabled ?? true,
    staleTime: 60_000,
  });
}
