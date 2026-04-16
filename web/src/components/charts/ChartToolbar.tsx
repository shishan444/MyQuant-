import { ZoomIn, ZoomOut, Maximize2, RotateCcw } from "lucide-react";

interface ChartToolbarProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  onFullscreen: () => void;
}

export function ChartToolbar({ onZoomIn, onZoomOut, onReset, onFullscreen }: ChartToolbarProps) {
  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        onClick={onZoomIn}
        className="h-7 w-7 rounded p-1 text-text-muted transition-colors hover:bg-white/5 hover:text-text-secondary"
        title="放大"
      >
        <ZoomIn className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={onZoomOut}
        className="h-7 w-7 rounded p-1 text-text-muted transition-colors hover:bg-white/5 hover:text-text-secondary"
        title="缩小"
      >
        <ZoomOut className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={onReset}
        className="h-7 w-7 rounded p-1 text-text-muted transition-colors hover:bg-white/5 hover:text-text-secondary"
        title="重置视图"
      >
        <RotateCcw className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={onFullscreen}
        className="h-7 w-7 rounded p-1 text-text-muted transition-colors hover:bg-white/5 hover:text-text-secondary"
        title="全屏"
      >
        <Maximize2 className="h-4 w-4" />
      </button>
    </div>
  );
}
