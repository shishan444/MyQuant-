import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { LegendGroup } from "@/types/chart";

interface ChartEmbeddedLegendProps {
  groups: LegendGroup[];
  onToggle: (groupId: string, itemId: string) => void;
  values?: Record<string, string>;
}

export function ChartEmbeddedLegend({ groups, onToggle, values }: ChartEmbeddedLegendProps) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const toggleCollapse = (groupId: string) => {
    setCollapsed((prev) => ({ ...prev, [groupId]: !prev[groupId] }));
  };

  const visibleGroups = groups.filter((g) => g.items.length > 0);
  if (visibleGroups.length === 0) return null;

  return (
    <div className="pointer-events-auto absolute left-2 top-2 z-10 rounded-md bg-black/60 p-1.5 font-mono text-[10px]">
      {visibleGroups.map((group) => (
        <div key={group.id} className="mb-0.5 last:mb-0">
          <button
            type="button"
            onClick={() => toggleCollapse(group.id)}
            className="flex items-center gap-1 text-text-muted hover:text-text-secondary"
          >
            {collapsed[group.id] ? (
              <ChevronRight className="h-2.5 w-2.5" />
            ) : (
              <ChevronDown className="h-2.5 w-2.5" />
            )}
            <span className="font-semibold">{group.label}</span>
          </button>
          {!collapsed[group.id] && (
            <div className="ml-1">
              {group.items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onToggle(group.id, item.id)}
                  className={cn(
                    "flex w-full items-center gap-1.5 py-0.5 text-left transition-opacity",
                    item.visible ? "opacity-100" : "opacity-40",
                  )}
                >
                  <span
                    className="inline-block h-2 w-2 shrink-0 rounded-full"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="text-slate-300">{item.label}</span>
                  {values?.[item.id] && (
                    <span className="ml-auto text-slate-400">{values[item.id]}</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
