import { cn } from "@/lib/utils";

// ─────────────────────────────────────────────────────────────────────────────
// RISK BADGE
// ─────────────────────────────────────────────────────────────────────────────

type RiskLevel = "low" | "medium" | "high" | "critical";

const RISK_STYLES: Record<RiskLevel, string> = {
  low:      "bg-green-100 dark:bg-green-950 text-green-700 dark:text-green-300",
  medium:   "bg-yellow-100 dark:bg-yellow-950 text-yellow-700 dark:text-yellow-300",
  high:     "bg-orange-100 dark:bg-orange-950 text-orange-700 dark:text-orange-300",
  critical: "bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-300",
};

const RISK_LABELS: Record<RiskLevel, string> = {
  low:      "Low risk",
  medium:   "Medium risk",
  high:     "High risk",
  critical: "Critical",
};

interface RiskBadgeProps {
  level: RiskLevel;
  score?: number | null;
  className?: string;
}

export function RiskBadge({ level, score, className }: RiskBadgeProps) {
  const style = RISK_STYLES[level] ?? RISK_STYLES.low;
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold",
        style,
        className
      )}
    >
      {RISK_LABELS[level] ?? level}
      {score != null && ` · ${score}`}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// STATUS BADGE
// ─────────────────────────────────────────────────────────────────────────────

const STATUS_STYLES: Record<string, string> = {
  pending:       "bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400",
  parsing:       "bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300",
  parsed:        "bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300",
  verifying:     "bg-purple-100 dark:bg-purple-950 text-purple-700 dark:text-purple-300",
  running:       "bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300",
  completed:     "bg-green-100 dark:bg-green-950 text-green-700 dark:text-green-300",
  failed:        "bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-300",
  cancelled:     "bg-zinc-100 dark:bg-zinc-800 text-zinc-500",
  manual_review: "bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300",
  email_sent:    "bg-cyan-100 dark:bg-cyan-950 text-cyan-700 dark:text-cyan-300",
  verified:      "bg-green-100 dark:bg-green-950 text-green-700 dark:text-green-300",
  unverified:    "bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-300",
};

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.pending;
  const label = status.replace(/_/g, " ");
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium capitalize",
        style,
        className
      )}
    >
      {label}
    </span>
  );
}
