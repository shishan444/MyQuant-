import { useState, useMemo } from "react";
import { ChevronUp, ChevronDown, ChevronsUpDown, MapPin, Eye } from "lucide-react";
import { cn, formatCurrency, formatDateTime } from "@/lib/utils";
import type { TriggerRecord } from "@/types/api";

interface TriggerTableProps {
  triggers: TriggerRecord[];
  onLocate: (trigger: TriggerRecord) => void;
  onViewDetail: (trigger: TriggerRecord) => void;
}

type SortField = "time" | "trigger_price" | "change_pct";
type SortOrder = "asc" | "desc" | null;

const PAGE_SIZE = 20;

export function TriggerTable({ triggers, onLocate, onViewDetail }: TriggerTableProps) {
  const [page, setPage] = useState(1);
  const [sortField, setSortField] = useState<SortField>("time");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [hoveredId, setHoveredId] = useState<number | null>(null);

  const sorted = useMemo(() => {
    if (!sortField || !sortOrder) return triggers;
    return [...triggers].sort((a, b) => {
      let cmp = 0;
      if (sortField === "time") {
        cmp = a.time.localeCompare(b.time);
      } else if (sortField === "trigger_price") {
        cmp = a.trigger_price - b.trigger_price;
      } else if (sortField === "change_pct") {
        cmp = a.change_pct - b.change_pct;
      }
      return sortOrder === "desc" ? -cmp : cmp;
    });
  }, [triggers, sortField, sortOrder]);

  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);
  const paged = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      if (sortOrder === "desc") setSortOrder("asc");
      else if (sortOrder === "asc") {
        setSortField("time");
        setSortOrder("desc");
      }
    } else {
      setSortField(field);
      setSortOrder("desc");
    }
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <ChevronsUpDown className="h-3 w-3 text-text-muted/40" />;
    if (sortOrder === "desc") return <ChevronDown className="h-3 w-3 text-accent-gold" />;
    return <ChevronUp className="h-3 w-3 text-accent-gold" />;
  };

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-semibold text-text-secondary">
          触发记录 -- 共 {triggers.length} 次
        </h4>
      </div>

      <div className="overflow-hidden rounded-lg border border-border-default">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border-default bg-white/[0.02]">
              <th className="px-3 py-2 text-left font-semibold text-text-muted">#</th>
              <th
                className="cursor-pointer px-3 py-2 text-left font-semibold text-text-muted"
                onClick={() => handleSort("time")}
              >
                <span className="inline-flex items-center gap-1">
                  时间 <SortIcon field="time" />
                </span>
              </th>
              <th
                className="cursor-pointer px-3 py-2 text-right font-semibold text-text-muted"
                onClick={() => handleSort("trigger_price")}
              >
                <span className="inline-flex items-center gap-1">
                  触发价格 <SortIcon field="trigger_price" />
                </span>
              </th>
              <th
                className="cursor-pointer px-3 py-2 text-right font-semibold text-text-muted"
                onClick={() => handleSort("change_pct")}
              >
                <span className="inline-flex items-center gap-1">
                  幅度 <SortIcon field="change_pct" />
                </span>
              </th>
              <th className="px-3 py-2 text-center font-semibold text-text-muted">结果</th>
              <th className="px-3 py-2 text-right font-semibold text-text-muted">操作</th>
            </tr>
          </thead>
          <tbody>
            {paged.map((trigger) => (
              <tr
                key={trigger.id}
                className={cn(
                  "border-b border-border-default transition-colors",
                  hoveredId === trigger.id && "bg-accent-gold/[0.03]",
                )}
                onMouseEnter={() => setHoveredId(trigger.id)}
                onMouseLeave={() => setHoveredId(null)}
              >
                <td className="px-3 py-2 font-num text-accent-gold">{trigger.id}</td>
                <td className="px-3 py-2 font-num text-text-primary">
                  {formatDateTime(trigger.time)}
                </td>
                <td className="px-3 py-2 text-right font-num text-text-primary">
                  {formatCurrency(trigger.trigger_price)}
                </td>
                <td
                  className={cn(
                    "px-3 py-2 text-right font-num font-semibold",
                    trigger.change_pct >= 0 ? "text-profit" : "text-loss",
                  )}
                >
                  {trigger.change_pct >= 0 ? "+" : ""}
                  {trigger.change_pct}%
                </td>
                <td className="px-3 py-2 text-center">
                  <span
                    className={cn(
                      "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold",
                      trigger.matched
                        ? "bg-profit/10 text-profit"
                        : "bg-loss/10 text-loss",
                    )}
                  >
                    {trigger.matched ? "符合" : "不符合"}
                  </span>
                </td>
                <td className="px-3 py-2 text-right">
                  <div
                    className={cn(
                      "inline-flex items-center gap-1 transition-opacity",
                      hoveredId === trigger.id ? "opacity-100" : "opacity-0",
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => onLocate(trigger)}
                      className="rounded p-1 text-text-muted transition-colors hover:bg-white/5 hover:text-accent-gold"
                      title="定位到K线图"
                    >
                      <MapPin className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => onViewDetail(trigger)}
                      className="rounded p-1 text-text-muted transition-colors hover:bg-white/5 hover:text-accent-gold"
                      title="查看详情"
                    >
                      <Eye className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-3 flex items-center justify-between text-xs text-text-muted">
          <span>
            显示 {(page - 1) * PAGE_SIZE + 1}-{Math.min(page * PAGE_SIZE, triggers.length)} /
            共{triggers.length}条
          </span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
              className="rounded px-2 py-1 transition-colors hover:bg-white/5 disabled:opacity-30"
            >
              &lt;
            </button>
            {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
              const p = i + 1;
              return (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPage(p)}
                  className={cn(
                    "rounded px-2 py-1 transition-colors",
                    page === p ? "bg-accent-gold/10 text-accent-gold" : "hover:bg-white/5",
                  )}
                >
                  {p}
                </button>
              );
            })}
            {totalPages > 5 && <span>...</span>}
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
              className="rounded px-2 py-1 transition-colors hover:bg-white/5 disabled:opacity-30"
            >
              &gt;
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
