import { Sparkles, FileText } from "lucide-react";
import { cn } from "@/lib/utils";

export type ExploreMode = "auto" | "seed";

interface SegmentedControlProps {
  value: ExploreMode;
  onChange: (mode: ExploreMode) => void;
}

const SEGMENTS: Array<{
  value: ExploreMode;
  icon: typeof Sparkles;
  label: string;
  description: string;
}> = [
  {
    value: "auto",
    icon: Sparkles,
    label: "自动探索",
    description: "系统自动搜索策略空间",
  },
  {
    value: "seed",
    icon: FileText,
    label: "种子探索",
    description: "基于你的想法探索",
  },
];

export function SegmentedControl({ value, onChange }: SegmentedControlProps) {
  return (
    <div className="inline-flex items-center gap-0 rounded-[10px] border border-slate-700/50 p-0.5">
      {SEGMENTS.map((seg) => {
        const Icon = seg.icon;
        const active = value === seg.value;
        return (
          <button
            key={seg.value}
            type="button"
            onClick={() => onChange(seg.value)}
            className={cn(
              "flex items-center gap-2 rounded-lg px-4 py-2.5 transition-all duration-200 ease-out",
              active
                ? "border border-amber-400/50 bg-amber-400/10 text-slate-100 shadow-[0_0_12px_rgba(234,179,8,0.06)]"
                : "border border-transparent text-slate-400 hover:bg-white/[0.03] hover:text-slate-300"
            )}
          >
            <Icon className="h-4 w-4 shrink-0" />
            <div className="flex flex-col items-start">
              <span className="text-[13px] font-medium leading-tight">
                {seg.label}
              </span>
              <span className="text-[11px] font-normal leading-tight text-slate-500">
                {seg.description}
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
