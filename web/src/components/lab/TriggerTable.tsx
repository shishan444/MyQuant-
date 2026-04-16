import { useState, useMemo } from "react";
import { ChevronUp, ChevronDown, ChevronsUpDown, MapPin, Eye, Download } from "lucide-react";
import { cn, formatCurrency, formatDateTime } from "@/lib/utils";
import type { TriggerRecord } from "@/types/api";

interface TriggerTableProps {
  triggers: TriggerRecord[];
  onLocate: (trigger: TriggerRecord) => void;
  onViewDetail: (trigger: TriggerRecord) => void;
  pair?: string;
  timeframe?: string;
}

type SortField = "time" | "trigger_price" | "change_pct";
type SortOrder = "asc" | "desc" | null;

const PAGE_SIZES = [10, 20, 50];

export function TriggerTable({ triggers, onLocate, onViewDetail, pair, timeframe }: TriggerTableProps) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
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

  const totalPages = Math.ceil(sorted.length / pageSize);
  const paged = sorted.slice((page - 1) * pageSize, page * pageSize);

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

  const handleExportCsv = () => {
    const header = "#,时间,触发价格,幅度,结果";
    const rows = sorted.map((t) =>
      `${t.id},${t.time},${t.trigger_price},${t.change_pct},${t.matched ? "符合" : "不符合"}`
    );
    const csv = [header, ...rows].join("\n");
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `验证结果_${pair ?? "data"}_${timeframe ?? "tf"}_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-semibold text-text-secondary">
          触发记录 -- 共 {triggers.length} 次
        </h4>
        <button
          type="button"
          onClick={handleExportCsv}
          className="flex items-center gap-1 text-xs text-text-muted transition-colors hover:text-accent-gold"
        >
          <Download className="h-3.5 w-3.5" />
          导出CSV
        </button>
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
          <div className="flex items-center gap-2">
            <span>
              显示 {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, triggers.length)} /
              共{triggers.length}条
            </span>
            <select
              value={pageSize}
              onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
              className="h-6 rounded border border-border-default bg-bg-surface px-1 text-xs text-text-primary outline-none"
            >
              {PAGE_SIZES.map((s) => (
                <option key={s} value={s}>{s}条/页</option>
              ))}
            </select>
          </div>
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
