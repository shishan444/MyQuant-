export interface OhlcvDataPoint {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ChartThemeConfig {
  background: string;
  grid: string;
  candle: { up: string; down: string };
  lines: { primary: string; secondary: string; tertiary: string };
}

export interface LegendItem {
  id: string;
  label: string;
  color: string;
  visible: boolean;
}

export interface EquitySeries {
  name: string;
  color: string;
  data: Array<{ time: string; value: number }>;
}
