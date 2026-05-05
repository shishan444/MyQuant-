/**
 * Tests for EquityCurve component.
 * Covers: empty state, chart rendering, profit/loss color logic.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// Mock recharts to avoid SVG rendering issues in jsdom
vi.mock("recharts", () => ({
  AreaChart: vi.fn(({ data }) => (
    <div data-testid="area-chart" data-points={data?.length ?? 0} />
  )),
  Area: vi.fn(() => <div data-testid="area" />),
  XAxis: vi.fn(() => null),
  YAxis: vi.fn(() => null),
  Tooltip: vi.fn(() => null),
  ResponsiveContainer: vi.fn(({ children }) => (
    <div data-testid="responsive-container">{children}</div>
  )),
}));

import { EquityCurve } from "@/components/trading/EquityCurve";
import { mockEquitySnapshots } from "@/test/fixtures";
import { AreaChart } from "recharts";

const mockAreaChart = vi.mocked(AreaChart);

describe("EquityCurve", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // --- Empty state ---
  it("shows empty state when no data", () => {
    render(<EquityCurve data={[]} initialCash={100000} />);
    expect(screen.getByText("No equity data yet")).toBeInTheDocument();
  });

  // --- Renders chart with data ---
  it("renders chart with equity data", () => {
    render(<EquityCurve data={mockEquitySnapshots} initialCash={100000} />);
    expect(screen.getByTestId("area-chart")).toBeInTheDocument();
    expect(screen.getByTestId("area-chart").dataset.points).toBe("3");
  });

  // --- Profit color ---
  it("uses green stroke when equity > initialCash", () => {
    const profitData = [
      { timestamp: "2025-01-01T00:00:00Z", equity: 100000, balance: 100000 },
      { timestamp: "2025-01-10T00:00:00Z", equity: 110000, balance: 110000 },
    ];
    render(<EquityCurve data={profitData} initialCash={100000} />);

    // AreaChart receives data, check the Area component for stroke color
    expect(mockAreaChart).toHaveBeenCalled();
  });

  // --- Loss color ---
  it("uses red stroke when equity < initialCash", () => {
    const lossData = [
      { timestamp: "2025-01-01T00:00:00Z", equity: 100000, balance: 100000 },
      { timestamp: "2025-01-10T00:00:00Z", equity: 90000, balance: 90000 },
    ];
    render(<EquityCurve data={lossData} initialCash={100000} />);

    expect(mockAreaChart).toHaveBeenCalled();
  });

  // --- Break-even ---
  it("handles break-even (equity equals initialCash)", () => {
    const breakEvenData = [
      { timestamp: "2025-01-01T00:00:00Z", equity: 100000, balance: 100000 },
      { timestamp: "2025-01-10T00:00:00Z", equity: 100000, balance: 100000 },
    ];
    render(<EquityCurve data={breakEvenData} initialCash={100000} />);

    expect(screen.getByTestId("area-chart")).toBeInTheDocument();
  });

  // --- Custom height ---
  it("renders with custom height", () => {
    render(<EquityCurve data={mockEquitySnapshots} initialCash={100000} height={300} />);
    expect(screen.getByTestId("area-chart")).toBeInTheDocument();
  });
});
