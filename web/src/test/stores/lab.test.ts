/**
 * Tests for stores/lab.ts: Zustand store for strategy lab configuration.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { useLabStore } from "@/stores/lab";
import type { IndicatorConfig } from "@/types/strategy";

const sampleIndicator: IndicatorConfig = {
  id: "ind-1",
  name: "RSI",
  params: { period: 14 },
};

describe("useLabStore", () => {
  beforeEach(() => {
    useLabStore.getState().resetConfig();
  });

  it("has correct default config", () => {
    const { config } = useLabStore.getState();
    expect(config.symbol).toBe("BTCUSDT");
    expect(config.timeframe).toBe("1h");
    expect(config.scoreTemplate).toBe("profit_first");
    expect(config.initCash).toBe(100000);
    expect(config.indicators).toEqual([]);
  });

  it("setConfig updates individual fields", () => {
    useLabStore.getState().setConfig({ symbol: "ETHUSDT" });
    expect(useLabStore.getState().config.symbol).toBe("ETHUSDT");
    // Other fields unchanged
    expect(useLabStore.getState().config.timeframe).toBe("1h");
  });

  it("setConfig merges multiple fields", () => {
    useLabStore.getState().setConfig({
      symbol: "ETHUSDT",
      timeframe: "4h",
      initCash: 50000,
    });
    const { config } = useLabStore.getState();
    expect(config.symbol).toBe("ETHUSDT");
    expect(config.timeframe).toBe("4h");
    expect(config.initCash).toBe(50000);
  });

  it("addIndicator appends to list", () => {
    useLabStore.getState().addIndicator(sampleIndicator);
    expect(useLabStore.getState().config.indicators).toHaveLength(1);
    expect(useLabStore.getState().config.indicators[0].name).toBe("RSI");
  });

  it("removeIndicator removes by id", () => {
    useLabStore.getState().addIndicator(sampleIndicator);
    useLabStore.getState().removeIndicator("ind-1");
    expect(useLabStore.getState().config.indicators).toHaveLength(0);
  });

  it("removeIndicator does nothing for non-existent id", () => {
    useLabStore.getState().addIndicator(sampleIndicator);
    useLabStore.getState().removeIndicator("nonexistent");
    expect(useLabStore.getState().config.indicators).toHaveLength(1);
  });

  it("updateIndicator modifies specific indicator", () => {
    useLabStore.getState().addIndicator(sampleIndicator);
    useLabStore.getState().updateIndicator("ind-1", { params: { period: 28 } });
    expect(useLabStore.getState().config.indicators[0].params.period).toBe(28);
  });

  it("resetConfig restores defaults", () => {
    useLabStore.getState().setConfig({ symbol: "ETHUSDT" });
    useLabStore.getState().addIndicator(sampleIndicator);
    useLabStore.getState().resetConfig();
    const { config } = useLabStore.getState();
    expect(config.symbol).toBe("BTCUSDT");
    expect(config.indicators).toEqual([]);
  });
});
