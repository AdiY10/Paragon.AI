import type { ReactNode } from "react";
import { AlertTriangle, CircleCheck, Clock } from "lucide-react";

export type BadgeTone = "neutral" | "accent" | "high" | "watch";

/** Small label. High/Watch tones are reserved for attention levels; reliability and stale badges are neutral. */
export function Badge({ tone = "neutral", icon, children }: { tone?: BadgeTone; icon?: ReactNode; children: ReactNode }) {
  return (
    <span className={`ui-badge ui-badge-${tone}`}>
      {icon}
      {children}
    </span>
  );
}

export type Attention = "High" | "Watch" | "Clear";

/** Attention level with icon + word: colour is never the only signal. */
export function AttentionBadge({ level }: { level: Attention | null | undefined }) {
  const value = level ?? "Clear";
  if (value === "High")
    return (
      <Badge tone="high" icon={<AlertTriangle size={12} aria-hidden="true" />}>
        High
      </Badge>
    );
  if (value === "Watch")
    return (
      <Badge tone="watch" icon={<Clock size={12} aria-hidden="true" />}>
        Watch
      </Badge>
    );
  return (
    <Badge tone="neutral" icon={<CircleCheck size={12} aria-hidden="true" />}>
      Clear
    </Badge>
  );
}
