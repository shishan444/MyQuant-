import { create } from "zustand";
import type { IndicatorConfig, LabConfig } from "@/types/strategy";

interface LabState {
  config: LabConfig;
  setConfig: (updates: Partial<LabConfig>) => void;
  addIndicator: (indicator: IndicatorConfig) => void;
  removeIndicator: (id: string) => void;
  updateIndicator: (id: string, updates: Partial<IndicatorConfig>) => void;
  resetConfig: () => void;
}

const defaultConfig: LabConfig = {
  datasetId: "",
  symbol: "BTCUSDT",
  timeframe: "1h",
  indicators: [],
  scoreTemplate: "profit_first",
  initCash: 100000,
  fee: 0.001,
  slippage: 0.0005,
};

export const useLabStore = create<LabState>()((set) => ({
  config: { ...defaultConfig },
  setConfig: (updates) =>
    set((s) => ({ config: { ...s.config, ...updates } })),
  addIndicator: (indicator) =>
    set((s) => ({
      config: {
        ...s.config,
        indicators: [...s.config.indicators, indicator],
      },
    })),
  removeIndicator: (id) =>
    set((s) => ({
      config: {
        ...s.config,
        indicators: s.config.indicators.filter((i) => i.id !== id),
      },
    })),
  updateIndicator: (id, updates) =>
    set((s) => ({
      config: {
        ...s.config,
        indicators: s.config.indicators.map((i) =>
          i.id === id ? { ...i, ...updates } : i
        ),
      },
    })),
  resetConfig: () => set({ config: { ...defaultConfig } }),
}));
