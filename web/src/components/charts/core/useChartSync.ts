import { useEffect, useRef } from "react";
import type { IChartApi } from "lightweight-charts";

/**
 * Synchronizes the visible time range between two charts (e.g. main K-line
 * chart and RSI sub-chart) so that scrolling/zooming on one updates the other.
 *
 * A `syncing` ref prevents infinite loops caused by mutual subscription
 * callbacks.
 *
 * @param mainChart - The primary chart (K-line / candlestick).
 * @param subChart  - The secondary chart (RSI / volume / etc.).
 */
export function useChartSync(
  mainChart: IChartApi | null,
  subChart: IChartApi | null,
): void {
  const syncing = useRef(false);

  useEffect(() => {
    if (!mainChart || !subChart) return;

    const mainTimeScale = mainChart.timeScale();
    const subTimeScale = subChart.timeScale();

    const onMainRangeChange = () => {
      if (syncing.current) return;
      syncing.current = true;
      const range = mainTimeScale.getVisibleLogicalRange();
      if (range) {
        subTimeScale.setVisibleLogicalRange(range);
      }
      syncing.current = false;
    };

    const onSubRangeChange = () => {
      if (syncing.current) return;
      syncing.current = true;
      const range = subTimeScale.getVisibleLogicalRange();
      if (range) {
        mainTimeScale.setVisibleLogicalRange(range);
      }
      syncing.current = false;
    };

    mainTimeScale.subscribeVisibleLogicalRangeChange(onMainRangeChange);
    subTimeScale.subscribeVisibleLogicalRangeChange(onSubRangeChange);

    return () => {
      mainTimeScale.unsubscribeVisibleLogicalRangeChange(onMainRangeChange);
      subTimeScale.unsubscribeVisibleLogicalRangeChange(onSubRangeChange);
    };
  }, [mainChart, subChart]);
}
