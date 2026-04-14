import { useState, useRef, useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Database,
  Upload,
  Search,
  Eye,
  Trash2,
  TrendingUp,
  FileUp,
  Loader2,
  X,
  FileSpreadsheet,
  CheckCircle2,
} from "lucide-react";
import { GlassCard } from "@/components/GlassCard";
import { PageTransition } from "@/components/PageTransition";
import { EmptyState } from "@/components/EmptyState";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useImportCsv, useImportCsvBatch, useDeleteDataset } from "@/hooks/useDatasets";
import { cn, formatNumber } from "@/lib/utils";
import { api } from "@/services/api";
import type { Dataset } from "@/types/api";

// ---------------------------------------------------------------------------
// Filename parsing (mirrors backend parse_filename logic)
// ---------------------------------------------------------------------------
const FILENAME_RE = /^([A-Z]{3,10}USDT)-(\d+[mhdw])-/i;

function parseCsvFilename(name: string): { symbol: string; interval: string } | null {
  const m = FILENAME_RE.exec(name);
  if (m) return { symbol: m[1].toUpperCase(), interval: m[2] };
  return null;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ---------------------------------------------------------------------------
// Quality indicator bar below each table row
// ---------------------------------------------------------------------------
function QualityBar({ status }: { status: Dataset["quality_status"] }) {
  const cfg: Record<
    Dataset["quality_status"],
    { value: number; color: string; label: string }
  > = {
    complete: { value: 100, color: "bg-green-500", label: "数据质量: 完整" },
    warning: { value: 90, color: "bg-yellow-500", label: "有缺口 <5%" },
    error: { value: 60, color: "bg-red-500", label: "缺口 >5%" },
    unknown: { value: 0, color: "bg-gray-500", label: "未知" },
  };

  const { value, color, label } = cfg[status] ?? cfg.unknown;

  return (
    <div className="flex items-center gap-2 pt-1">
      <Progress
        value={value}
        className={cn("h-1.5 flex-1", "[&>[data-slot=progress-indicator]]:" + color)}
      />
      <span className="text-[11px] text-text-muted">{label}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Skeleton loader for the table
// ---------------------------------------------------------------------------
function TableSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full rounded-lg" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Upload Dialog (extracted to avoid duplication)
// ---------------------------------------------------------------------------
function UploadDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [symbol, setSymbol] = useState("");
  const [interval, setInterval] = useState("1h");
  const [mode, setMode] = useState("merge");

  const importCsv = useImportCsv();
  const importCsvBatch = useImportCsvBatch();

  const detectedInfo = useMemo(() => {
    if (selectedFiles.length === 0) return null;
    const first = parseCsvFilename(selectedFiles[0].name);
    if (!first) return null;
    const allMatch = selectedFiles.every(
      (f) => parseCsvFilename(f.name)?.symbol === first.symbol &&
             parseCsvFilename(f.name)?.interval === first.interval
    );
    return allMatch ? first : null;
  }, [selectedFiles]);

  const autoSymbol = detectedInfo?.symbol ?? "";
  const autoInterval = detectedInfo?.interval ?? "";
  const effectiveSymbol = autoSymbol || symbol.trim().toUpperCase();
  const effectiveInterval = autoInterval || interval;

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const fileList = e.target.files;
      if (!fileList) return;
      setSelectedFiles((prev) => {
        const existing = new Set(prev.map((f) => f.name));
        const newFiles = Array.from(fileList).filter((f) => !existing.has(f.name));
        return [...prev, ...newFiles];
      });
      e.target.value = "";
    },
    []
  );

  const removeFile = useCallback((index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleUpload = useCallback(async () => {
    if (selectedFiles.length === 0 || !effectiveSymbol) return;

    const formData = new FormData();
    if (selectedFiles.length === 1) {
      formData.append("file", selectedFiles[0]);
    } else {
      selectedFiles.forEach((f) => formData.append("files", f));
    }
    formData.append("symbol", effectiveSymbol);
    formData.append("interval", effectiveInterval);
    formData.append("mode", mode);

    try {
      if (selectedFiles.length === 1) {
        await importCsv.mutateAsync(formData);
      } else {
        await importCsvBatch.mutateAsync(formData);
      }
      onOpenChange(false);
      setSelectedFiles([]);
      setSymbol("");
      setInterval("1h");
      setMode("merge");
    } catch {
      // error handled by mutation onError
    }
  }, [selectedFiles, effectiveSymbol, effectiveInterval, mode, importCsv, importCsvBatch, onOpenChange]);

  const isPending = importCsv.isPending || importCsvBatch.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>上传 CSV 文件</DialogTitle>
          <DialogDescription>
            支持多文件上传，自动从文件名识别 Symbol 和周期（如 BTCUSDT-30m-2026-03.csv）
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 py-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            multiple
            className="hidden"
            onChange={handleFileChange}
          />

          <Button
            variant="outline"
            className="w-full justify-start gap-2 h-auto py-3"
            onClick={() => fileInputRef.current?.click()}
          >
            <FileUp className="h-4 w-4 shrink-0" />
            <span className="text-text-secondary">
              点击选择 CSV 文件（支持多选）
            </span>
          </Button>

          {selectedFiles.length > 0 && (
            <div className="flex flex-col gap-1.5 max-h-48 overflow-y-auto">
              {selectedFiles.map((file, idx) => {
                const parsed = parseCsvFilename(file.name);
                return (
                  <div
                    key={`${file.name}-${idx}`}
                    className="flex items-center gap-2 rounded-md bg-bg-elevated px-3 py-2 text-xs"
                  >
                    <FileSpreadsheet className="h-3.5 w-3.5 shrink-0 text-accent-gold" />
                    <span className="flex-1 truncate text-text-primary">
                      {file.name}
                    </span>
                    <span className="text-text-muted shrink-0">
                      {formatFileSize(file.size)}
                    </span>
                    {parsed && (
                      <span className="shrink-0 text-profit text-[10px]">
                        <CheckCircle2 className="h-3 w-3 inline mr-0.5" />
                        {parsed.symbol} {parsed.interval}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => removeFile(idx)}
                      className="shrink-0 text-text-muted hover:text-loss transition-colors"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                );
              })}
              <span className="text-[11px] text-text-muted">
                共 {selectedFiles.length} 个文件，{formatFileSize(selectedFiles.reduce((s, f) => s + f.size, 0))}
              </span>
            </div>
          )}

          {detectedInfo && (
            <div className="flex items-center gap-2 rounded-md bg-profit/10 px-3 py-2 text-xs text-profit">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span>
                已自动识别: {detectedInfo.symbol} / {detectedInfo.interval}
              </span>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-text-secondary">
                Symbol
              </label>
              <Input
                placeholder="BTCUSDT"
                value={autoSymbol || symbol}
                onChange={(e) => setSymbol(e.target.value)}
                disabled={!!autoSymbol}
                className={cn(!!autoSymbol && "opacity-60")}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-text-secondary">
                周期
              </label>
              <Select
                value={autoInterval || interval}
                onValueChange={setInterval}
                disabled={!!autoInterval}
              >
                <SelectTrigger className={cn(!!autoInterval && "opacity-60")}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="15m">15m</SelectItem>
                  <SelectItem value="30m">30m</SelectItem>
                  <SelectItem value="1h">1h</SelectItem>
                  <SelectItem value="4h">4h</SelectItem>
                  <SelectItem value="1d">1d</SelectItem>
                  <SelectItem value="3d">3d</SelectItem>
                  <SelectItem value="1w">1w</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-text-secondary">
              导入模式
            </label>
            <Select value={mode} onValueChange={setMode}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="merge">合并 (merge)</SelectItem>
                <SelectItem value="replace">替换 (replace)</SelectItem>
                <SelectItem value="new">新建 (new)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isPending}
          >
            取消
          </Button>
          <Button
            onClick={handleUpload}
            disabled={selectedFiles.length === 0 || !effectiveSymbol || isPending}
          >
            {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            上传 {selectedFiles.length > 1 ? `(${selectedFiles.length} 个文件)` : ""}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export function DataManagement() {
  // Search ------------------------------------------------------------------
  const [search, setSearch] = useState("");
  const normalizedSearch = search.trim().toLowerCase();

  // Upload dialog -----------------------------------------------------------
  const [uploadOpen, setUploadOpen] = useState(false);

  // Delete confirm ----------------------------------------------------------
  const [deleteTarget, setDeleteTarget] = useState<Dataset | null>(null);
  const deleteDataset = useDeleteDataset();

  // Data --------------------------------------------------------------------
  const { data, isLoading } = useQuery({
    queryKey: ["datasets"],
    queryFn: () => api.get("/api/data/datasets").then((r) => r.data),
  });

  const allDatasets: Dataset[] = data?.datasets ?? data?.items ?? [];

  const datasets = normalizedSearch
    ? allDatasets.filter(
        (d) =>
          d.symbol.toLowerCase().includes(normalizedSearch) ||
          d.interval.toLowerCase().includes(normalizedSearch)
      )
    : allDatasets;

  // Handlers ----------------------------------------------------------------
  const handleDelete = useCallback(async () => {
    if (!deleteTarget) return;
    try {
      await deleteDataset.mutateAsync(deleteTarget.dataset_id);
      setDeleteTarget(null);
    } catch {
      // error handled by mutation onError
    }
  }, [deleteTarget, deleteDataset]);

  // Empty state -------------------------------------------------------------
  if (!isLoading && allDatasets.length === 0) {
    return (
      <PageTransition>
        <EmptyState
          icon={Database}
          title="还没有导入任何数据集"
          description="导入 CSV 文件或从 Binance 导入历史数据，开始量化分析"
          actions={[
            {
              label: "导入 CSV 文件",
              onClick: () => setUploadOpen(true),
            },
          ]}
        />
        <UploadDialog open={uploadOpen} onOpenChange={setUploadOpen} />
      </PageTransition>
    );
  }

  return (
    <PageTransition>
      <div className="flex flex-col gap-4">
        {/* Toolbar */}
        <GlassCard className="p-4" hover={false}>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              size="sm"
              className="gap-1.5 bg-accent-gold text-black hover:bg-accent-gold/90"
              onClick={() => setUploadOpen(true)}
            >
              <Upload className="h-3.5 w-3.5" />
              上传 CSV 文件
            </Button>
            <Button size="sm" variant="outline" className="gap-1.5">
              <FileUp className="h-3.5 w-3.5" />
              从 Binance 导入
            </Button>
            <div className="relative ml-auto">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" />
              <Input
                placeholder="搜索币种..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-8 w-56 pl-8 text-xs"
              />
            </div>
          </div>
        </GlassCard>

        {/* Dataset Table */}
        <GlassCard className="p-0 overflow-hidden" hover={false}>
          {isLoading ? (
            <div className="p-4">
              <TableSkeleton />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>币种</TableHead>
                  <TableHead>名称</TableHead>
                  <TableHead>周期</TableHead>
                  <TableHead>日期范围</TableHead>
                  <TableHead className="text-right">K线数量</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {datasets.map((ds) => (
                  <DatasetRow
                    key={ds.dataset_id}
                    dataset={ds}
                    onPreview={() => {
                      void ds;
                    }}
                    onOpenInLab={() => {
                      void ds;
                    }}
                    onDelete={() => setDeleteTarget(ds)}
                  />
                ))}
                {datasets.length === 0 && (
                  <TableRow>
                    <TableCell
                      colSpan={6}
                      className="h-24 text-center text-text-muted"
                    >
                      没有匹配的数据集
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </GlassCard>

        {/* Footer hint */}
        <p className="text-xs text-text-muted text-center">
          建议至少准备6个月历史数据用于回测，支持 Binance Data Vision CSV
        </p>

        {/* Upload Dialog */}
        <UploadDialog open={uploadOpen} onOpenChange={setUploadOpen} />

        {/* Delete Confirm Dialog */}
        <ConfirmDialog
          open={!!deleteTarget}
          onOpenChange={(open) => {
            if (!open) setDeleteTarget(null);
          }}
          title="删除数据集"
          description={`确定要删除 ${deleteTarget?.symbol ?? ""} (${deleteTarget?.interval ?? ""}) 数据集吗？此操作不可撤销。`}
          confirmLabel="删除"
          variant="destructive"
          onConfirm={handleDelete}
          loading={deleteDataset.isPending}
        />
      </div>
    </PageTransition>
  );
}

// ---------------------------------------------------------------------------
// Single dataset row
// ---------------------------------------------------------------------------
interface DatasetRowProps {
  dataset: Dataset;
  onPreview: () => void;
  onOpenInLab: () => void;
  onDelete: () => void;
}

function DatasetRow({ dataset: ds, onPreview, onOpenInLab, onDelete }: DatasetRowProps) {
  const dateRange =
    ds.time_start && ds.time_end
      ? `${ds.time_start.slice(0, 10)} ~ ${ds.time_end.slice(0, 10)}`
      : "-";

  return (
    <>
      <TableRow className="group">
        <TableCell className="font-medium text-text-primary">
          {ds.symbol}
        </TableCell>
        <TableCell className="text-text-secondary">{ds.symbol}</TableCell>
        <TableCell>
          <span className="inline-flex items-center rounded-md bg-accent/10 px-1.5 py-0.5 text-xs text-text-secondary">
            {ds.interval}
          </span>
        </TableCell>
        <TableCell className="text-text-secondary text-xs font-num">
          {dateRange}
        </TableCell>
        <TableCell className="text-right font-num text-text-secondary">
          {formatNumber(ds.row_count, 0)}
        </TableCell>
        <TableCell className="text-right">
          <div className="flex items-center justify-end gap-1 opacity-0 transition-opacity group-hover:opacity-100">
            <Button
              size="icon-xs"
              variant="ghost"
              onClick={onPreview}
              title="预览"
            >
              <Eye className="h-3.5 w-3.5" />
            </Button>
            <Button
              size="icon-xs"
              variant="ghost"
              onClick={onOpenInLab}
              title="在实验室打开"
            >
              <TrendingUp className="h-3.5 w-3.5" />
            </Button>
            <Button
              size="icon-xs"
              variant="ghost"
              onClick={onDelete}
              title="删除"
            >
              <Trash2 className="h-3.5 w-3.5 text-red-400" />
            </Button>
          </div>
        </TableCell>
      </TableRow>
      <TableRow>
        <TableCell colSpan={6} className="border-0 py-0 px-4 pb-2">
          <QualityBar status={ds.quality_status} />
        </TableCell>
      </TableRow>
    </>
  );
}
