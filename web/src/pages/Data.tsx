import { useState, useCallback, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Upload,
  Search,
  Eye,
  Trash2,
  X,
  FileUp,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Database,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { getDatasets, getDatasetPreview, deleteDataset, detectCsv, importCsv } from '@/api/data';
import type { Dataset, DatasetPreview, ImportStrategy } from '@/types';

// ============================================================
// Dataset Card Component
// ============================================================

function DatasetCard({
  dataset,
  onPreview,
  onDelete,
  isDeleting,
}: {
  dataset: Dataset;
  onPreview: (dataset: Dataset) => void;
  onDelete: (id: string) => void;
  isDeleting: boolean;
}) {
  const symbolColors: Record<string, string> = {
    BTC: 'var(--color-warn)',
    ETH: 'var(--color-purple)',
  };
  const color = symbolColors[dataset.symbol] ?? 'var(--color-blue)';

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-4 hover:border-[var(--color-blue)]/40 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold text-xs"
            style={{ backgroundColor: color }}
          >
            {dataset.symbol.slice(0, 3)}
          </div>
          <div>
            <div className="text-[var(--text-primary)] font-medium text-sm">
              {dataset.symbol} / {dataset.interval}
            </div>
            <div className="text-[var(--text-secondary)] text-xs">
              {dataset.format.toUpperCase()} format
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onPreview(dataset)}
            title="Preview data"
          >
            <Eye className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onDelete(dataset.id)}
            disabled={isDeleting}
            title="Delete dataset"
          >
            {isDeleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4 text-[var(--color-loss)]" />}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3 text-xs">
        <div>
          <div className="text-[var(--text-disabled)] mb-0.5">Start</div>
          <div className="text-[var(--text-secondary)]">{dataset.start_time.slice(0, 10)}</div>
        </div>
        <div>
          <div className="text-[var(--text-disabled)] mb-0.5">End</div>
          <div className="text-[var(--text-secondary)]">{dataset.end_time.slice(0, 10)}</div>
        </div>
        <div>
          <div className="text-[var(--text-disabled)] mb-0.5">Rows</div>
          <div className="text-[var(--text-secondary)]">{dataset.row_count.toLocaleString()}</div>
        </div>
        <div>
          <div className="text-[var(--text-disabled)] mb-0.5">Size</div>
          <div className="text-[var(--text-secondary)]">{dataset.file_size_display}</div>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// Preview Modal Component
// ============================================================

function PreviewModal({
  dataset,
  onClose,
}: {
  dataset: Dataset;
  onClose: () => void;
}) {
  const { data: preview, isLoading, error } = useQuery<DatasetPreview>({
    queryKey: ['dataset-preview', dataset.id],
    queryFn: () => getDatasetPreview(dataset.id),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg w-full max-w-3xl max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
          <div>
            <h3 className="text-[var(--text-primary)] font-medium">
              {dataset.symbol} / {dataset.interval} - Preview
            </h3>
            {preview && (
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                Showing {preview.rows.length} of {preview.total_rows.toLocaleString()} rows
              </p>
            )}
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>

        <div className="flex-1 overflow-auto p-4">
          {isLoading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-[var(--color-blue)]" />
              <span className="ml-2 text-[var(--text-secondary)]">Loading preview...</span>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 text-[var(--color-loss)] p-4 bg-[var(--color-loss)]/10 rounded-md">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <span className="text-sm">{error instanceof Error ? error.message : 'Failed to load preview'}</span>
            </div>
          )}

          {preview && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)]">
                    {preview.columns.map((col) => (
                      <th
                        key={col}
                        className="text-left text-[var(--text-secondary)] font-medium py-2 px-3 whitespace-nowrap"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row, i) => (
                    <tr key={i} className="border-b border-[var(--border)]/50">
                      {preview.columns.map((col) => (
                        <td key={col} className="py-2 px-3 text-[var(--text-primary)] whitespace-nowrap">
                          {String(row[col] ?? '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================
// CSV Import Modal Component
// ============================================================

function ImportModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [strategy, setStrategy] = useState<ImportStrategy>('new');

  const detectMutation = useMutation({
    mutationFn: detectCsv,
  });

  const importMutation = useMutation({
    mutationFn: ({ file, strategy: importStrategy }: { file: File; strategy: ImportStrategy }) =>
      importCsv(file, importStrategy),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
      onClose();
    },
  });

  const handleFileSelect = useCallback(
    async (selectedFile: File) => {
      if (!selectedFile.name.endsWith('.csv')) {
        return;
      }
      setFile(selectedFile);
      detectMutation.mutate(selectedFile);
    },
    [detectMutation],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile) {
        handleFileSelect(droppedFile);
      }
    },
    [handleFileSelect],
  );

  const handleImport = () => {
    if (!file) return;
    importMutation.mutate({ file, strategy });
  };

  const detectResult = detectMutation.data;
  const detectError = detectMutation.error;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg w-full max-w-2xl max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
          <h3 className="text-[var(--text-primary)] font-medium">Import CSV Data</h3>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Drop Zone */}
          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
              isDragging
                ? 'border-[var(--color-blue)] bg-[var(--color-blue)]/5'
                : 'border-[var(--border)] hover:border-[var(--color-blue)]/50'
            }`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <FileUp className="w-10 h-10 mx-auto text-[var(--text-disabled)] mb-3" />
            {file ? (
              <div>
                <p className="text-[var(--text-primary)] text-sm font-medium">{file.name}</p>
                <p className="text-[var(--text-secondary)] text-xs mt-1">
                  {(file.size / 1024).toFixed(1)} KB
                </p>
              </div>
            ) : (
              <div>
                <p className="text-[var(--text-secondary)] text-sm">
                  Drag and drop a CSV file here, or
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-2"
                  onClick={() => fileInputRef.current?.click()}
                >
                  Browse Files
                </Button>
              </div>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => {
                const selected = e.target.files?.[0];
                if (selected) handleFileSelect(selected);
              }}
            />
          </div>

          {/* Detect Error */}
          {detectError && (
            <div className="flex items-center gap-2 text-[var(--color-loss)] p-3 bg-[var(--color-loss)]/10 rounded-md text-sm">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{detectError instanceof Error ? detectError.message : 'Detection failed'}</span>
            </div>
          )}

          {/* Detect Loading */}
          {detectMutation.isPending && (
            <div className="flex items-center justify-center py-4 gap-2 text-[var(--text-secondary)] text-sm">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Analyzing CSV file...</span>
            </div>
          )}

          {/* Detection Result */}
          {detectResult && (
            <>
              <div className="bg-[var(--bg-hover)] rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <CheckCircle2 className="w-4 h-4 text-[var(--color-profit)]" />
                  <span className="text-sm text-[var(--text-primary)] font-medium">
                    File Detected Successfully
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-[var(--text-disabled)]">Symbol:</span>{' '}
                    <span className="text-[var(--text-primary)]">{detectResult.symbol}</span>
                  </div>
                  <div>
                    <span className="text-[var(--text-disabled)]">Interval:</span>{' '}
                    <span className="text-[var(--text-primary)]">{detectResult.interval}</span>
                  </div>
                  <div>
                    <span className="text-[var(--text-disabled)]">Format:</span>{' '}
                    <span className="text-[var(--text-primary)]">{detectResult.format}</span>
                  </div>
                  <div>
                    <span className="text-[var(--text-disabled)]">Timestamp:</span>{' '}
                    <span className="text-[var(--text-primary)]">{detectResult.timestamp_precision}</span>
                  </div>
                </div>
              </div>

              {/* Data Preview Table */}
              {detectResult.preview_rows.length > 0 && (
                <div>
                  <h4 className="text-sm text-[var(--text-secondary)] mb-2">Data Preview (first 5 rows)</h4>
                  <div className="overflow-x-auto border border-[var(--border)] rounded-md">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="bg-[var(--bg-hover)]">
                          {detectResult.columns.map((col) => (
                            <th
                              key={col}
                              className="text-left text-[var(--text-secondary)] font-medium py-1.5 px-2 whitespace-nowrap"
                            >
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {detectResult.preview_rows.map((row, i) => (
                          <tr key={i} className="border-t border-[var(--border)]/50">
                            {detectResult.columns.map((col) => (
                              <td key={col} className="py-1.5 px-2 text-[var(--text-primary)] whitespace-nowrap">
                                {String(row[col] ?? '')}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Import Strategy */}
              <div>
                <h4 className="text-sm text-[var(--text-secondary)] mb-2">Import Strategy</h4>
                <div className="flex gap-3">
                  {([
                    { value: 'new' as const, label: 'New', desc: 'Create new dataset' },
                    { value: 'merge' as const, label: 'Merge', desc: 'Append to existing' },
                    { value: 'replace' as const, label: 'Replace', desc: 'Overwrite existing' },
                  ]).map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => setStrategy(opt.value)}
                      className={`flex-1 p-3 rounded-md border text-left transition-colors ${
                        strategy === opt.value
                          ? 'border-[var(--color-blue)] bg-[var(--color-blue)]/10'
                          : 'border-[var(--border)] hover:border-[var(--border)]'
                      }`}
                    >
                      <div className="text-sm text-[var(--text-primary)] font-medium">
                        {opt.label}
                      </div>
                      <div className="text-xs text-[var(--text-secondary)] mt-0.5">
                        {opt.desc}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-[var(--border)]">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={handleImport}
            disabled={!detectResult || importMutation.isPending}
          >
            {importMutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Importing...
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                Import
              </>
            )}
          </Button>
        </div>

        {/* Import Error */}
        {importMutation.error && (
          <div className="px-4 py-2 border-t border-[var(--border)]">
            <div className="flex items-center gap-2 text-[var(--color-loss)] text-sm">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>
                {importMutation.error instanceof Error
                  ? importMutation.error.message
                  : 'Import failed'}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================
// Data Page (Main)
// ============================================================

export function Data() {
  const queryClient = useQueryClient();
  const [showImport, setShowImport] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [previewDataset, setPreviewDataset] = useState<Dataset | null>(null);

  const {
    data: datasets = [],
    isLoading,
    error,
  } = useQuery<Dataset[]>({
    queryKey: ['datasets'],
    queryFn: getDatasets,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteDataset,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
    },
  });

  const filteredDatasets = datasets.filter(
    (ds) =>
      ds.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ds.interval.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  return (
    <div className="space-y-4">
      {/* Top Bar */}
      <div className="flex items-center justify-between">
        <div className="relative w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-disabled)]" />
          <input
            type="text"
            placeholder="Search by symbol or interval..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-9 pl-9 pr-3 bg-[var(--bg-card)] border border-[var(--border)] rounded-md text-sm text-[var(--text-primary)] placeholder:text-[var(--text-disabled)] focus:outline-none focus:border-[var(--color-blue)]"
          />
        </div>
        <Button onClick={() => setShowImport(true)}>
          <Upload className="w-4 h-4" />
          Import CSV
        </Button>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="flex items-center justify-center py-16 gap-2 text-[var(--text-secondary)]">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Loading datasets...</span>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="flex items-center gap-2 text-[var(--color-loss)] p-4 bg-[var(--color-loss)]/10 rounded-md">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <span className="text-sm">
            {error instanceof Error ? error.message : 'Failed to load datasets'}
          </span>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && filteredDatasets.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16">
          <Database className="w-12 h-12 text-[var(--text-disabled)] mb-3" />
          <p className="text-[var(--text-secondary)] text-sm mb-1">
            {searchQuery ? 'No matching datasets found' : 'No datasets yet'}
          </p>
          {!searchQuery && (
            <p className="text-[var(--text-disabled)] text-xs">
              Import a CSV file to get started
            </p>
          )}
        </div>
      )}

      {/* Dataset Grid */}
      {!isLoading && filteredDatasets.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filteredDatasets.map((dataset) => (
            <DatasetCard
              key={dataset.id}
              dataset={dataset}
              onPreview={setPreviewDataset}
              onDelete={(id) => deleteMutation.mutate(id)}
              isDeleting={deleteMutation.isPending}
            />
          ))}
        </div>
      )}

      {/* Preview Modal */}
      {previewDataset && (
        <PreviewModal
          dataset={previewDataset}
          onClose={() => setPreviewDataset(null)}
        />
      )}

      {/* Import Modal */}
      {showImport && <ImportModal onClose={() => setShowImport(false)} />}
    </div>
  );
}
