/**
 * Tests for TradingChart component and tradesToSignals logic.
 * Covers: signal conversion, loading state, empty trades.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { PaperTrade } from "@/services/trading";

// Mock hooks and child components
vi.mock("@/hooks/useChartIndicators", () => ({
  useChartIndicators: vi.fn(),
}));

vi.mock("@/components/charts/KlineChart", () => ({
  KlineChart: vi.fn(({ signals }) => (
    <div data-testid="kline-chart">
      <span data-testid="signal-count">{signals?.length ?? 0}</span>
    </div>
  )),
}));

import { TradingChart } from "@/components/trading/TradingChart";
import { useChartIndicators } from "@/hooks/useChartIndicators";

const mockUseChartIndicators = vi.mocked(useChartIndicators);

function makeTrade(overrides: Partial<PaperTrade> = {}): PaperTrade {
  return {
    id: 1,
    task_id: "t1",
    bar_time: "2025-01-05T08:00:00Z",
    side: "long",
    action: "open",
    price: 100000,
    quantity: 0.1,
    pnl: null,
    fee_paid: 10,
    reason: null,
    ...overrides,
  };
}

describe("TradingChart", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // --- tradesToSignals: open -> buy ---
  it("converts open trades to buy signals", () => {
    mockUseChartIndicators.mockReturnValue({
      candleData: [{ timestamp: "2025-01-05T08:00:00Z", open: 100, high: 110, low: 95, close: 105, volume: 1000 }],
      volumeData: [],
      isLoadingOhlcv: false,
    } as any);

    const trades = [makeTrade({ action: "open", bar_time: "2025-01-05T08:00:00Z" })];
    render(<TradingChart symbol="BTCUSDT" timeframe="4h" trades={trades} />);

    expect(screen.getByTestId("signal-count").textContent).toBe("1");
  });

  // --- tradesToSignals: close -> sell ---
  it("converts close trades to sell signals", () => {
    mockUseChartIndicators.mockReturnValue({
      candleData: [{ timestamp: "2025-01-05T08:00:00Z", open: 100, high: 110, low: 95, close: 105, volume: 1000 }],
      volumeData: [],
      isLoadingOhlcv: false,
    } as any);

    const trades = [makeTrade({ action: "close", bar_time: "2025-01-10T12:00:00Z" })];
    render(<TradingChart symbol="BTCUSDT" timeframe="4h" trades={trades} />);

    expect(screen.getByTestId("signal-count").textContent).toBe("1");
  });

  // --- tradesToSignals: filters out non-open/close ---
  it("filters out trades with action other than open/close", () => {
    mockUseChartIndicators.mockReturnValue({
      candleData: [{ timestamp: "2025-01-05T08:00:00Z", open: 100, high: 110, low: 95, close: 105, volume: 1000 }],
      volumeData: [],
      isLoadingOhlcv: false,
    } as any);

    const trades = [
      makeTrade({ action: "add", bar_time: "2025-01-05T08:00:00Z" }),
      makeTrade({ action: "reduce", bar_time: "2025-01-06T08:00:00Z" }),
    ];
    render(<TradingChart symbol="BTCUSDT" timeframe="4h" trades={trades} />);

    expect(screen.getByTestId("signal-count").textContent).toBe("0");
  });

  // --- Empty trades ---
  it("handles empty trades array", () => {
    mockUseChartIndicators.mockReturnValue({
      candleData: [{ timestamp: "2025-01-05T08:00:00Z", open: 100, high: 110, low: 95, close: 105, volume: 1000 }],
      volumeData: [],
      isLoadingOhlcv: false,
    } as any);

    render(<TradingChart symbol="BTCUSDT" timeframe="4h" trades={[]} />);
    expect(screen.getByTestId("signal-count").textContent).toBe("0");
  });

  // --- Mixed trades ---
  it("correctly maps mixed open and close trades", () => {
    mockUseChartIndicators.mockReturnValue({
      candleData: [{ timestamp: "2025-01-05T08:00:00Z", open: 100, high: 110, low: 95, close: 105, volume: 1000 }],
      volumeData: [],
      isLoadingOhlcv: false,
    } as any);

    const trades = [
      makeTrade({ id: 1, action: "open", bar_time: "2025-01-05T08:00:00Z" }),
      makeTrade({ id: 2, action: "close", bar_time: "2025-01-10T12:00:00Z" }),
      makeTrade({ id: 3, action: "open", bar_time: "2025-01-15T08:00:00Z" }),
      makeTrade({ id: 4, action: "close", bar_time: "2025-01-20T12:00:00Z" }),
    ];
    render(<TradingChart symbol="BTCUSDT" timeframe="4h" trades={trades} />);

    expect(screen.getByTestId("signal-count").textContent).toBe("4");
  });

  // --- Loading state ---
  it("shows loading state when ohlcv is loading", () => {
    mockUseChartIndicators.mockReturnValue({
      candleData: null,
      volumeData: null,
      isLoadingOhlcv: true,
    } as any);

    render(<TradingChart symbol="BTCUSDT" timeframe="4h" trades={[]} />);
    expect(screen.getByText("Loading chart...")).toBeInTheDocument();
  });

  // --- Empty candle data ---
  it("shows loading state when candle data is empty", () => {
    mockUseChartIndicators.mockReturnValue({
      candleData: [],
      volumeData: [],
      isLoadingOhlcv: false,
    } as any);

    render(<TradingChart symbol="BTCUSDT" timeframe="4h" trades={[]} />);
    expect(screen.getByText("Loading chart...")).toBeInTheDocument();
  });
});
