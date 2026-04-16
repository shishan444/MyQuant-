import { cn } from "@/lib/utils";
import { MTF_TIMEFRAME_COLORS } from "@/lib/constants";

interface TimeframeLabelProps {
  timeframe: string;
}

export function TimeframeLabel({ timeframe }: TimeframeLabelProps) {
  const color = MTF_TIMEFRAME_COLORS[timeframe] ?? "#6B7280";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold",
        "bg-white/5",
      )}
      style={{ color, border: `1px solid ${color}33` }}
    >
      {timeframe.toUpperCase()}
    </span>
  );
}
