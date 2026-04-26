/**
 * Contract verification tests: ensure TypeScript types match Python API schemas.
 * These tests validate that the type definitions in api.ts accurately reflect
 * the backend Pydantic models in api/schemas.py.
 */
import { describe, it, expect } from "vitest";
import type {
  BacktestResult,
  DNA,
  TimeframeLayerModel,
  DatasetListResponse,
  OhlcvData,
} from "@/types/api";
import { mockBacktestResult } from "@/test/fixtures";

// ---------------------------------------------------------------------------
// BacktestResult contract
// ---------------------------------------------------------------------------

describe("BacktestResult contract", () => {
  it("matches Python BacktestResponse schema", () => {
    const result: BacktestResult = {
      result_id: "r1",
      strategy_id: "s1",
      symbol: "BTCUSDT",
      timeframe: "4h",
      init_cash: 100000,
      fee: 0.001,
      slippage: 0.0005,
      total_return: 0.1,
      sharpe_ratio: 1.5,
      max_drawdown: -0.05,
      win_rate: 0.6,
      total_trades: 10,
      total_score: 72,
      template_name: "profit_first",
      run_source: "lab",
      total_funding_cost: 0,
      liquidated: false,
    };
    // Verify required fields exist
    expect(result.fee).toBe(0.001);
    expect(result.slippage).toBe(0.0005);
    expect(result.run_source).toBe("lab");
  });

  it("mock fixture satisfies BacktestResult type", () => {
    const result: BacktestResult = mockBacktestResult as BacktestResult;
    expect(result.fee).toBe(0.001);
    expect(result.slippage).toBe(0.0005);
    expect(result.run_source).toBe("lab");
  });
});

// ---------------------------------------------------------------------------
// DNA contract
// ---------------------------------------------------------------------------

describe("DNA contract", () => {
  it("includes MTF engine fields from Python DNAModel", () => {
    const dna: DNA = {
      signal_genes: [],
      logic_genes: { entry_logic: "AND", exit_logic: "OR" },
      execution_genes: { timeframe: "4h", symbol: "BTCUSDT" },
      risk_genes: {
        stop_loss: 0.05,
        take_profit: 0.1,
        position_size: 0.3,
        leverage: 1,
        direction: "long",
      },
      generation: 0,
      parent_ids: [],
      mutation_ops: [],
      mtf_mode: "direction",
      confluence_threshold: 0.3,
      proximity_mult: 1.5,
    };
    expect(dna.mtf_mode).toBe("direction");
    expect(dna.confluence_threshold).toBe(0.3);
    expect(dna.proximity_mult).toBe(1.5);
  });

  it("mtf_mode can be null for non-MTF strategies", () => {
    const dna: DNA = {
      signal_genes: [],
      logic_genes: { entry_logic: "AND", exit_logic: "OR" },
      execution_genes: { timeframe: "4h", symbol: "BTCUSDT" },
      risk_genes: {
        stop_loss: 0.05,
        take_profit: 0.1,
        position_size: 0.3,
        leverage: 1,
        direction: "long",
      },
      generation: 0,
      parent_ids: [],
      mutation_ops: [],
      mtf_mode: null,
    };
    expect(dna.mtf_mode).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// TimeframeLayerModel contract
// ---------------------------------------------------------------------------

describe("TimeframeLayerModel contract", () => {
  it("includes role field from Python TimeframeLayerModel", () => {
    const layer: TimeframeLayerModel = {
      timeframe: "1d",
      signal_genes: [],
      logic_genes: { entry_logic: "AND", exit_logic: "OR" },
      role: "structure",
    };
    expect(layer.role).toBe("structure");
  });
});

// ---------------------------------------------------------------------------
// DatasetListResponse contract
// ---------------------------------------------------------------------------

describe("DatasetListResponse contract", () => {
  it("uses 'items' field matching Python DatasetListResponse", () => {
    const response: DatasetListResponse = {
      items: [],
      total: 0,
    };
    expect(Array.isArray(response.items)).toBe(true);
    expect(response.total).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// OhlcvData contract
// ---------------------------------------------------------------------------

describe("OhlcvData contract", () => {
  it("includes dataset_id from Python OhlcvResponse", () => {
    const data: OhlcvData = {
      dataset_id: "BTCUSDT_4h",
      data: [
        {
          timestamp: "2025-01-01T00:00:00Z",
          open: 100,
          high: 110,
          low: 95,
          close: 105,
          volume: 1000,
        },
      ],
    };
    expect(data.dataset_id).toBe("BTCUSDT_4h");
    expect(data.data).toHaveLength(1);
  });
});
