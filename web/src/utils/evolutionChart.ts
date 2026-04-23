/**
 * Data transformation utilities for the evolution score trend chart.
 *
 * Separates parsing, population-boundary detection, champion tracking,
 * and stagnation counting from the rendering component.
 */

import type { EvolutionHistoryRecord } from "@/types/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChartDataPoint {
  generation: number;
  bestScore: number;
  avgScore: number;
  cumulativeBest: number;
  prevBestScore?: number;
  isChampionChange?: boolean;
  stagnationCount: number;
  avgTrades?: number;
  diversity?: number;
  population: number;
  isPopulationBoundary: boolean;
}

export interface ParsedDiagnostics {
  avgTrades?: number;
  diversity?: number;
  population?: number;
}

export interface ChartTransformResult {
  data: ChartDataPoint[];
  championChanges: ChartDataPoint[];
  boundaries: number[];
  stats: {
    maxStagnation: number;
    totalChampionChanges: number;
    populationCount: number;
  };
}

// ---------------------------------------------------------------------------
// Parsing
// ---------------------------------------------------------------------------

/** Parse the pipe-delimited top3_summary string from the backend. */
export function parseDiagnostics(top3Summary?: string): ParsedDiagnostics {
  if (!top3Summary) return {};
  try {
    // Format: "best=85.2|pop=2|diag={...}"
    const parts = top3Summary.split("|");
    let population: number | undefined;
    let raw: Record<string, unknown> | undefined;

    for (const part of parts) {
      if (part.startsWith("pop=")) {
        population = parseInt(part.slice(4), 10);
        if (isNaN(population)) population = undefined;
      } else if (part.startsWith("diag=")) {
        raw = JSON.parse(part.slice(5)) as Record<string, unknown>;
      }
    }

    if (!raw) return population !== undefined ? { population } : {};

    const avgTrades =
      typeof raw.avg_trades === "number" ? raw.avg_trades : undefined;
    const rawDiv = raw.diversity;
    const diversity =
      typeof rawDiv === "number"
        ? rawDiv
        : typeof rawDiv === "object" && rawDiv !== null
          ? (rawDiv as Record<string, unknown>).genotype as number
          : undefined;

    return { avgTrades, diversity, population };
  } catch {
    return {};
  }
}

// ---------------------------------------------------------------------------
// Transformation
// ---------------------------------------------------------------------------

/** Transform raw evolution history records into chart-ready data. */
export function transformChartData(
  records: EvolutionHistoryRecord[]
): ChartTransformResult {
  if (records.length === 0) {
    return { data: [], championChanges: [], boundaries: [], stats: { maxStagnation: 0, totalChampionChanges: 0, populationCount: 0 } };
  }

  // Pass 1: Map raw records to chart data points
  const chartData: ChartDataPoint[] = records.map((r) => {
    const diag = parseDiagnostics(r.top3_summary);
    return {
      generation: r.generation,
      bestScore: r.best_score,
      avgScore: r.avg_score,
      cumulativeBest: r.best_score, // placeholder, computed in pass 2
      prevBestScore: undefined,
      isChampionChange: false,
      stagnationCount: 0,
      avgTrades: diag.avgTrades,
      diversity: diag.diversity,
      population: diag.population ?? 1,
      isPopulationBoundary: false,
    };
  });

  // Pass 2: Detect population boundaries
  const boundaries: number[] = [];
  for (let i = 1; i < chartData.length; i++) {
    if (chartData[i].population !== chartData[i - 1].population) {
      chartData[i].isPopulationBoundary = true;
      boundaries.push(chartData[i].generation);
    }
  }
  const populationCount = new Set(chartData.map((d) => d.population)).size;

  // Pass 3: Compute cumulative best (global, never decreases)
  let cumBest = -Infinity;
  for (const point of chartData) {
    cumBest = Math.max(cumBest, point.bestScore);
    point.cumulativeBest = cumBest;
  }

  // Pass 4: Champion changes + per-generation delta
  // runningMax tracks the global all-time best (only increases) for champion detection.
  // prevGenScore tracks the previous generation's score for delta display.
  let runningMax = -Infinity;
  let prevGenScore: number | undefined;
  const changes: ChartDataPoint[] = [];
  for (const point of chartData) {
    if (point.isPopulationBoundary) {
      point.prevBestScore = undefined;
    } else {
      point.prevBestScore = prevGenScore;
    }

    if (point.bestScore > runningMax) {
      point.isChampionChange = true;
      changes.push(point);
      runningMax = point.bestScore;
    }
    prevGenScore = point.bestScore;
  }

  // Pass 5: Stagnation count (resets at population boundaries)
  let stagnationCounter = 0;
  let runningBest = -Infinity;
  let maxStagnation = 0;
  for (const point of chartData) {
    if (point.isPopulationBoundary) {
      stagnationCounter = 0;
      runningBest = -Infinity;
    }
    if (point.bestScore > runningBest) {
      stagnationCounter = 0;
      runningBest = point.bestScore;
    } else {
      stagnationCounter++;
    }
    point.stagnationCount = stagnationCounter;
    maxStagnation = Math.max(maxStagnation, stagnationCounter);
  }

  return {
    data: chartData,
    championChanges: changes,
    boundaries,
    stats: {
      maxStagnation,
      totalChampionChanges: changes.length,
      populationCount,
    },
  };
}
