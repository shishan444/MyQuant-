import { useEffect, useRef } from "react";
import type { Time, UTCTimestamp } from "lightweight-charts";

interface EquityCurveChartProps {
  data: Array<{ timestamp: string; value: number }>;
  height?: number;
}

function toTime(ts: string): Time {
  const withT = ts.includes("T") ? ts : ts.replace(" ", "T");
  const date = new Date(withT);
  if (isNaN(date.getTime())) {
    return ts.slice(0, 10) as Time;
  }
  return Math.floor(date.getTime() / 1000) as UTCTimestamp;
}

export function EquityCurveChart({ data, height = 180 }: EquityCurveChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || data.length < 2) return;

    let chart: import("lightweight-charts").IChartApi | null = null;

    import("lightweight-charts").then(({ createChart, LineSeries, ColorType }) => {
      if (!containerRef.current) return;

      const { width } = containerRef.current.getBoundingClientRect();
      chart = createChart(containerRef.current, {
        width,
        height,
        layout: {
          background: { type: ColorType.Solid, color: "transparent" },
          textColor: "#94a3b8",
          fontSize: 10,
        },
        grid: {
          vertLines: { color: "rgba(51,65,85,0.2)" },
          horzLines: { color: "rgba(51,65,85,0.2)" },
        },
        rightPriceScale: { borderColor: "rgba(51,65,85,0.3)" },
        timeScale: { borderColor: "rgba(51,65,85,0.3)", timeVisible: true },
        crosshair: { mode: 0 },
      });

      const lineSeries = chart.addSeries(LineSeries, {
        color: "#f59e0b",
        lineWidth: 1.5,
        priceLineVisible: false,
        lastValueVisible: true,
      });

      const sortedData = [...data]
        .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
        .map((d) => ({
          time: toTime(d.timestamp),
          value: d.value,
        }));

      lineSeries.setData(sortedData);
      chart.timeScale().fitContent();
    });

    return () => {
      chart?.remove();
    };
  }, [data, height]);

  return <div ref={containerRef} />;
}
