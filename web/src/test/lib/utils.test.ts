/**
 * Unit tests for lib/utils.ts: formatting and utility functions.
 */
import { describe, it, expect } from "vitest";
import {
  formatPercent,
  formatCurrency,
  formatNumber,
  formatPercentValue,
  formatDuration,
  formatDateTime,
  cn,
} from "@/lib/utils";

describe("formatPercent", () => {
  it("positive value shows + sign", () => {
    expect(formatPercent(0.255)).toBe("+25.5%");
  });

  it("negative value shows - sign", () => {
    expect(formatPercent(-0.083)).toBe("-8.3%");
  });

  it("zero shows + sign", () => {
    expect(formatPercent(0)).toBe("+0.0%");
  });

  it("formats to 1 decimal place", () => {
    expect(formatPercent(0.12345)).toBe("+12.3%");
  });
});

describe("formatCurrency", () => {
  it("formats integer USD", () => {
    expect(formatCurrency(100000)).toBe("$100,000");
  });

  it("formats zero", () => {
    expect(formatCurrency(0)).toBe("$0");
  });
});

describe("formatNumber", () => {
  it("defaults to 2 decimals", () => {
    expect(formatNumber(3.14159)).toBe("3.14");
  });

  it("respects custom decimals", () => {
    expect(formatNumber(3.14159, 4)).toBe("3.1416");
  });
});

describe("formatPercentValue", () => {
  it("positive shows + sign", () => {
    expect(formatPercentValue(25.5)).toBe("+25.5%");
  });

  it("negative shows - sign", () => {
    expect(formatPercentValue(-8.3)).toBe("-8.3%");
  });
});

describe("formatDuration", () => {
  it("formats seconds", () => {
    const start = "2024-01-01T00:00:00Z";
    const end = "2024-01-01T00:00:30Z";
    expect(formatDuration(start, end)).toBe("30秒");
  });

  it("formats minutes", () => {
    const start = "2024-01-01T00:00:00Z";
    const end = "2024-01-01T00:05:00Z";
    expect(formatDuration(start, end)).toBe("5分钟");
  });

  it("formats hours", () => {
    const start = "2024-01-01T00:00:00Z";
    const end = "2024-01-01T03:00:00Z";
    expect(formatDuration(start, end)).toBe("3.0小时");
  });

  it("invalid input handles gracefully", () => {
    const result = formatDuration("invalid", "invalid");
    // Invalid dates produce NaN in getTime(), which falls through to hours
    expect(typeof result).toBe("string");
  });
});

describe("formatDateTime", () => {
  it("formats ISO string", () => {
    const result = formatDateTime("2024-06-15T14:30:00Z");
    // Result depends on locale, just verify it's a non-empty string
    expect(result.length).toBeGreaterThan(0);
  });

  it("invalid input returns fallback string", () => {
    const result = formatDateTime("not-a-date");
    // Invalid date -> toLocaleString returns "Invalid Date"
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });
});

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("handles conditional classes", () => {
    expect(cn("foo", false && "bar", "baz")).toBe("foo baz");
  });
});
