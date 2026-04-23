/**
 * Discovery API service: pattern discovery, similar cases, price prediction.
 */

const API_BASE = "/api/discovery";

export interface DiscoveryRule {
  conditions: Array<{
    feature: string;
    operator: string;
    threshold: number;
  }>;
  direction: string;
  confidence: number;
  samples: number;
  lift: number;
}

export interface DiscoveryResponse {
  rules: DiscoveryRule[];
  accuracy: number;
  cv_scores: number[];
  feature_importance: Record<string, number>;
  tree_depth: number;
  n_samples: number;
  error?: string;
}

export interface SimilarCase {
  index: number;
  timestamp: string;
  close_price: number;
  future_return_pct: number;
  future_high_pct: number;
  future_low_pct: number;
  distance: number;
}

export interface SimilarResponse {
  cases: SimilarCase[];
  error?: string;
}

export interface PredictResponse {
  predicted_direction: string;
  avg_return: number;
  median_return: number;
  positive_pct: number;
  price_range_low: number;
  price_range_high: number;
  confidence: number;
  accuracy: number;
  n_cases: number;
  error?: string;
}

export async function discoverPatterns(params: {
  symbol: string;
  timeframe: string;
  horizon?: number;
  maxDepth?: number;
  dataStart?: string;
  dataEnd?: string;
}): Promise<DiscoveryResponse> {
  const res = await fetch(`${API_BASE}/patterns`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      symbol: params.symbol,
      timeframe: params.timeframe,
      horizon: params.horizon ?? 12,
      max_depth: params.maxDepth ?? 5,
      data_start: params.dataStart || undefined,
      data_end: params.dataEnd || undefined,
    }),
  });
  return res.json();
}

export async function findSimilar(params: {
  symbol: string;
  timeframe: string;
  horizon?: number;
  nNeighbors?: number;
  dataStart?: string;
  dataEnd?: string;
}): Promise<SimilarResponse> {
  const res = await fetch(`${API_BASE}/similar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      symbol: params.symbol,
      timeframe: params.timeframe,
      horizon: params.horizon ?? 12,
      n_neighbors: params.nNeighbors ?? 50,
      data_start: params.dataStart || undefined,
      data_end: params.dataEnd || undefined,
    }),
  });
  return res.json();
}

export async function predictRange(params: {
  symbol: string;
  timeframe: string;
  horizon?: number;
  nNeighbors?: number;
  dataStart?: string;
  dataEnd?: string;
}): Promise<PredictResponse> {
  const res = await fetch(`${API_BASE}/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      symbol: params.symbol,
      timeframe: params.timeframe,
      horizon: params.horizon ?? 12,
      n_neighbors: params.nNeighbors ?? 50,
      data_start: params.dataStart || undefined,
      data_end: params.dataEnd || undefined,
    }),
  });
  return res.json();
}
