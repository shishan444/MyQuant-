/**
 * Tests for Strategies page component.
 * Covers: loading state, empty state, strategy list rendering, filter/search.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

// Mock API services
vi.mock("@/services/strategies", () => ({
  getStrategies: vi.fn(),
  getStrategy: vi.fn(),
  createStrategy: vi.fn(),
  deleteStrategy: vi.fn(),
  updateStrategy: vi.fn(),
  runBacktest: vi.fn(),
  compareStrategies: vi.fn(),
}));

// Mock hooks - keep useStrategies real (delegates to mocked API), mock mutations
vi.mock("@/hooks/useStrategies", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/hooks/useStrategies")>();
  return {
    ...actual,
    useDeleteStrategy: vi.fn(),
    useUpdateStrategy: vi.fn(),
  };
});

vi.mock("react-router", () => ({
  useNavigate: vi.fn(() => vi.fn()),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

// Mock framer-motion
vi.mock("framer-motion", () => ({
  motion: new Proxy({}, {
    get: (_, tag) => {
      return ({ children, ...props }: any) => {
        const Tag = typeof tag === "string" ? tag : "div";
        const htmlProps: any = {};
        for (const [k, v] of Object.entries(props)) {
          if (typeof v !== "object" || k === "className" || k === "style" || k === "onClick" || k === "aria-label") {
            htmlProps[k] = v;
          }
        }
        return <Tag {...htmlProps}>{children}</Tag>;
      };
    },
  }),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

import { Strategies } from "@/pages/Strategies";
import { useDeleteStrategy } from "@/hooks/useStrategies";
import { getStrategies } from "@/services/strategies";
import type { Strategy } from "@/types/api";

const mockGetStrategies = vi.mocked(getStrategies);
const mockUseDeleteStrategy = vi.mocked(useDeleteStrategy);

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

function makeStrategy(overrides: Partial<Strategy> = {}): Strategy {
  return {
    strategy_id: "s1",
    name: "Test Strategy",
    symbol: "BTCUSDT",
    timeframe: "4h",
    source: "lab",
    dna: { signal_genes: [], logic_genes: { entry_logic: "AND", exit_logic: "OR" }, execution_genes: { timeframe: "4h", symbol: "BTCUSDT", leverage: 1, direction: "long" }, risk_genes: { stop_loss: 0.05, take_profit: 0.1, position_size: 0.3 } },
    metrics: {
      annual_return: 0.25,
      sharpe_ratio: 1.5,
      max_drawdown: -0.08,
      win_rate: 0.6,
      total_trades: 50,
      total_return: 0.25,
    },
    tags: "",
    notes: "",
    created_at: "2025-01-15T00:00:00Z",
    updated_at: "2025-01-15T00:00:00Z",
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockUseDeleteStrategy.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as any);
});

describe("Strategies page", () => {
  // --- Loading state ---
  it("shows loading skeleton when loading", () => {
    // Don't resolve the API call -> stays in loading state
    mockGetStrategies.mockReturnValue(new Promise(() => {}));

    render(<Strategies />, { wrapper: createWrapper() });
    const pulses = document.querySelectorAll(".animate-pulse");
    expect(pulses.length).toBeGreaterThan(0);
  });

  // --- Error state ---
  it("shows error state with retry when loading fails", async () => {
    mockGetStrategies.mockRejectedValue(new Error("服务器错误"));

    render(<Strategies />, { wrapper: createWrapper() });
    await screen.findByText("加载失败");
    expect(screen.getByText("服务器错误")).toBeInTheDocument();
    expect(screen.getByText("重试")).toBeInTheDocument();
  });

  // --- Empty state ---
  it("shows empty state when no strategies", async () => {
    mockGetStrategies.mockResolvedValue({ items: [], total: 0 });

    render(<Strategies />, { wrapper: createWrapper() });
    // Wait for React Query to resolve
    await screen.findByText("策略库为空");
    expect(screen.getByText("前往实验室")).toBeInTheDocument();
  });

  // --- Strategy list ---
  it("renders strategy list with names", async () => {
    const strategies = [
      makeStrategy({ strategy_id: "s1", name: "Alpha Strategy" }),
      makeStrategy({ strategy_id: "s2", name: "Beta Strategy" }),
    ];
    mockGetStrategies.mockResolvedValue({ items: strategies, total: 2 });

    render(<Strategies />, { wrapper: createWrapper() });
    await screen.findByText("Alpha Strategy");
    expect(screen.getByText("Beta Strategy")).toBeInTheDocument();
  });

  // --- Strategy count ---
  it("shows strategy count", async () => {
    const strategies = [
      makeStrategy({ strategy_id: "s1", name: "First Strategy" }),
      makeStrategy({ strategy_id: "s2", name: "Second Strategy" }),
    ];
    mockGetStrategies.mockResolvedValue({ items: strategies, total: 2 });

    render(<Strategies />, { wrapper: createWrapper() });
    await screen.findByText("已保存策略");
    // Count badge shows number of strategies
    expect(screen.getByText("已保存策略").nextElementSibling?.textContent).toBe("2");
  });

  // --- Filter: no match ---
  it("shows no match text when filter excludes all", async () => {
    mockGetStrategies.mockResolvedValue({ items: [makeStrategy({ strategy_id: "s1", name: "Alpha", source: "lab" })], total: 1 });

    render(<Strategies />, { wrapper: createWrapper() });
    await screen.findByText("Alpha");

    const searchInput = screen.getByPlaceholderText("搜索策略...");
    fireEvent.change(searchInput, { target: { value: "nonexistent" } });

    expect(screen.getByText("未找到匹配的策略")).toBeInTheDocument();
  });

  // --- Search by name ---
  it("filters strategies by search query", async () => {
    const strategies = [
      makeStrategy({ strategy_id: "s1", name: "Alpha Strategy" }),
      makeStrategy({ strategy_id: "s2", name: "Beta Strategy" }),
    ];
    mockGetStrategies.mockResolvedValue({ items: strategies, total: 2 });

    render(<Strategies />, { wrapper: createWrapper() });
    await screen.findByText("Alpha Strategy");

    const searchInput = screen.getByPlaceholderText("搜索策略...");
    fireEvent.change(searchInput, { target: { value: "alpha" } });

    expect(screen.getByText("Alpha Strategy")).toBeInTheDocument();
    expect(screen.queryByText("Beta Strategy")).not.toBeInTheDocument();
  });

  // --- Source badge ---
  it("renders source badge for strategies", async () => {
    mockGetStrategies.mockResolvedValue({ items: [makeStrategy({ strategy_id: "s1", source: "evolution" })], total: 1 });

    render(<Strategies />, { wrapper: createWrapper() });
    await screen.findByText("进化");
  });

  // --- Symbol/timeframe ---
  it("renders symbol and timeframe", async () => {
    mockGetStrategies.mockResolvedValue({ items: [makeStrategy({ strategy_id: "s1", symbol: "ETHUSDT", timeframe: "1h" })], total: 1 });

    render(<Strategies />, { wrapper: createWrapper() });
    await screen.findByText("Test Strategy");
    const content = document.body.textContent ?? "";
    expect(content).toContain("ETHUSDT");
    expect(content).toContain("1h");
  });

  // --- Delete mutation hook called ---
  it("calls useDeleteStrategy", async () => {
    mockGetStrategies.mockResolvedValue({ items: [makeStrategy()], total: 1 });

    render(<Strategies />, { wrapper: createWrapper() });
    await screen.findByText("Test Strategy");
    expect(mockUseDeleteStrategy).toHaveBeenCalled();
  });

  // --- Qualified badge ---
  it("renders qualified badge for qualified strategy", async () => {
    mockGetStrategies.mockResolvedValue({
      items: [makeStrategy({ strategy_id: "s1", name: "Good Strat", qualified: true, best_fitness: 1.5 })],
      total: 1,
    });

    render(<Strategies />, { wrapper: createWrapper() });
    await screen.findByText("Good Strat");
    const badges = screen.getAllByText("达标");
    expect(badges.length).toBeGreaterThanOrEqual(1);
  });

  // --- Checkbox rendering ---
  it("renders checkboxes in table rows", async () => {
    mockGetStrategies.mockResolvedValue({
      items: [
        makeStrategy({ strategy_id: "s1", name: "Alpha" }),
        makeStrategy({ strategy_id: "s2", name: "Beta" }),
      ],
      total: 2,
    });

    render(<Strategies />, { wrapper: createWrapper() });
    await screen.findByText("Alpha");
    const checkboxes = document.querySelectorAll('input[type="checkbox"]');
    // 1 header + 2 rows = 3 checkboxes
    expect(checkboxes.length).toBe(3);
  });

  // --- Qualified filter ---
  it("shows qualified filter select", async () => {
    mockGetStrategies.mockResolvedValue({ items: [makeStrategy()], total: 1 });

    render(<Strategies />, { wrapper: createWrapper() });
    await screen.findByText("Test Strategy");
    // The qualified filter select is rendered
    const selects = document.querySelectorAll("button[role='combobox']");
    expect(selects.length).toBeGreaterThanOrEqual(2); // source + qualified
  });

  // --- Expand panel on row click ---
  it("shows expand panel with strategy info when row name is clicked", async () => {
    mockGetStrategies.mockResolvedValue({
      items: [makeStrategy({ strategy_id: "s1", name: "Expandable" })],
      total: 1,
    });

    render(<Strategies />, { wrapper: createWrapper() });
    const nameEl = await screen.findByText("Expandable");
    fireEvent.click(nameEl);
    // Expand panel should show strategy info labels
    await screen.findByText("策略信息");
    expect(screen.getByText("策略结构")).toBeInTheDocument();
  });

  // --- Batch toolbar appears on selection ---
  it("shows batch toolbar when strategies are selected", async () => {
    mockGetStrategies.mockResolvedValue({
      items: [
        makeStrategy({ strategy_id: "s1", name: "Alpha" }),
        makeStrategy({ strategy_id: "s2", name: "Beta" }),
      ],
      total: 2,
    });

    render(<Strategies />, { wrapper: createWrapper() });
    await screen.findByText("Alpha");

    const checkboxes = document.querySelectorAll('input[type="checkbox"]');
    fireEvent.click(checkboxes[1]); // Select first strategy row

    expect(screen.getByText(/已选 1 项/)).toBeInTheDocument();
    expect(screen.getByText("批量删除")).toBeInTheDocument();
  });
});
