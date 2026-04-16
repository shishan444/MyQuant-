import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ConditionInput } from "@/types/api";
import { SubjectDropdown, getSubjectLabel } from "./SubjectDropdown";
import { ActionDropdown, getActionLabel } from "./ActionDropdown";
import { TargetInput, getTargetLabel } from "./TargetInput";
import { TimeframeLabel } from "./TimeframeLabel";
import { TimeframeSelector } from "./TimeframeSelector";

interface ConditionPillProps {
  condition: ConditionInput;
  onChange: (updated: ConditionInput) => void;
  onDelete: () => void;
  isThen?: boolean;
  baseTimeframe: string;
  referencedTimeframes?: string[];
}

export function ConditionPill({
  condition,
  onChange,
  onDelete,
  isThen = false,
  baseTimeframe,
  referencedTimeframes = [],
}: ConditionPillProps) {
  const [editing, setEditing] = useState(false);
  const [hovered, setHovered] = useState(false);

  // Auto-enter edit mode if condition is incomplete
  useEffect(() => {
    if (!condition.subject || !condition.action) {
      setEditing(true);
    }
  }, [condition.subject, condition.action]);

  const isComplete = condition.subject && condition.action;

  const handleSubjectChange = (v: string) => {
    onChange({ ...condition, subject: v, action: "", target: "" });
  };

  const handleActionChange = (v: string) => {
    onChange({ ...condition, action: v });
  };

  const handleTargetChange = (v: string) => {
    const updated = { ...condition, target: v };
    onChange(updated);
    if (editing && isComplete && v) {
      setEditing(false);
    }
  };

  const handleTimeframeChange = (v: string) => {
    onChange({ ...condition, timeframe: v });
  };

  const effectiveTimeframe = condition.timeframe || baseTimeframe;

  if (editing) {
    return (
      <div
        className={cn(
          "inline-flex min-w-[320px] items-center gap-2 rounded-full border px-3 py-1.5",
          "border-accent-gold bg-bg-surface/80",
        )}
      >
        <TimeframeSelector
          value={condition.timeframe || ""}
          onChange={handleTimeframeChange}
          baseTimeframe={baseTimeframe}
        />
        <SubjectDropdown value={condition.subject} onChange={handleSubjectChange} />
        {condition.subject && (
          <ActionDropdown
            value={condition.action}
            onChange={handleActionChange}
            subject={condition.subject}
            isThen={isThen}
          />
        )}
        {condition.subject && condition.action && (
          <TargetInput
            value={condition.target}
            onChange={handleTargetChange}
            action={condition.action}
            subject={condition.subject}
            baseTimeframe={baseTimeframe}
            referencedTimeframes={referencedTimeframes}
          />
        )}
        {isThen && (
          <div className="flex items-center gap-1 text-xs text-text-muted">
            <span>在</span>
            <input
              type="number"
              value={condition.window ?? 8}
              onChange={(e) =>
                onChange({ ...condition, window: Number(e.target.value) || 8 })
              }
              className="h-6 w-10 rounded border border-border-default bg-bg-surface px-1 text-xs text-text-primary text-center outline-none focus:border-accent-gold"
              min={1}
              max={100}
            />
            <span>根K线内</span>
          </div>
        )}
        <button
          type="button"
          onClick={onDelete}
          className="ml-1 rounded-full p-0.5 text-text-muted transition-colors hover:bg-loss/10 hover:text-loss"
        >
          <X className="h-3 w-3" />
        </button>
      </div>
    );
  }

  // Display mode
  const subjectLabel = getSubjectLabel(condition.subject);
  const actionLabel = getActionLabel(condition.action);
  const targetLabel = getTargetLabel(condition.target);

  const thenSuffix = isThen && condition.window
    ? ` * 在${condition.window}根K线内`
    : "";

  return (
    <div
      className={cn(
        "group inline-flex cursor-pointer items-center gap-0 rounded-full border px-3 py-1.5",
        "border-border-default bg-bg-surface transition-colors",
        "hover:border-accent-gold/50",
      )}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => setEditing(true)}
    >
      <span className="mr-1.5">
        <TimeframeLabel timeframe={effectiveTimeframe} />
      </span>
      <span className="text-xs text-text-primary">
        {subjectLabel}
        <span className="mx-1 text-text-muted">*</span>
        {actionLabel}
        <span className="mx-1 text-text-muted">*</span>
        {targetLabel}
        {thenSuffix && (
          <span className="text-text-muted">{thenSuffix}</span>
        )}
      </span>
      {hovered && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="ml-1.5 rounded-full p-0.5 text-text-muted transition-colors hover:bg-loss/10 hover:text-loss"
        >
          <X className="h-3 w-3" />
        </button>
      )}
    </div>
  );
}
