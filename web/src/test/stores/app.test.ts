/**
 * Tests for stores/app.ts: Zustand global app store.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { useAppStore } from "@/stores/app";

describe("useAppStore", () => {
  beforeEach(() => {
    // Reset to default state
    useAppStore.setState({ sidebarCollapsed: false });
  });

  it("has correct default state", () => {
    const { sidebarCollapsed } = useAppStore.getState();
    expect(sidebarCollapsed).toBe(false);
  });

  it("toggleSidebar flips boolean", () => {
    expect(useAppStore.getState().sidebarCollapsed).toBe(false);
    useAppStore.getState().toggleSidebar();
    expect(useAppStore.getState().sidebarCollapsed).toBe(true);
    useAppStore.getState().toggleSidebar();
    expect(useAppStore.getState().sidebarCollapsed).toBe(false);
  });

  it("setSidebarCollapsed sets explicit value", () => {
    useAppStore.getState().setSidebarCollapsed(true);
    expect(useAppStore.getState().sidebarCollapsed).toBe(true);
    useAppStore.getState().setSidebarCollapsed(false);
    expect(useAppStore.getState().sidebarCollapsed).toBe(false);
  });
});
