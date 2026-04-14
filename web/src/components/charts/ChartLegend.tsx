interface ChartLegendItem {
  id: string;
  label: string;
  color: string;
  visible: boolean;
}

interface ChartLegendProps {
  items: ChartLegendItem[];
  onToggle: (id: string) => void;
  extra?: React.ReactNode;
}

/**
 * Horizontal legend bar for toggling chart series visibility.
 * Each item shows a colored dot + label; clicking toggles visibility.
 * Hidden items are rendered at reduced opacity.
 */
function ChartLegend({ items, onToggle, extra }: ChartLegendProps) {
  return (
    <div className="flex items-center gap-4 px-2 py-1">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onToggle(item.id)}
          className="flex items-center gap-1.5 text-xs transition-opacity"
          style={{ opacity: item.visible ? 1 : 0.4 }}
          aria-pressed={item.visible}
          aria-label={`Toggle ${item.label}`}
        >
          <span
            className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
            style={{ backgroundColor: item.color }}
          />
          <span className="whitespace-nowrap text-slate-300">{item.label}</span>
        </button>
      ))}
      {extra && <div className="ml-auto flex items-center">{extra}</div>}
    </div>
  );
}

export { ChartLegend };
export type { ChartLegendProps, ChartLegendItem };
