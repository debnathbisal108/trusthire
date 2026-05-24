"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { apiClient } from "@/lib/api-client";
import { AlertTriangle, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

const SEVERITY_STYLES: Record<string, string> = {
  critical: "bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-300",
  high:     "bg-orange-100 dark:bg-orange-950 text-orange-700 dark:text-orange-300",
  medium:   "bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300",
  low:      "bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400",
};

export default function FraudAlerts() {
  // We query candidates and show those with unreviewed fraud flags
  // In production you'd have a dedicated /fraud-flags?reviewed=false endpoint
  const { data: candidates, isLoading } = useQuery({
    queryKey: ["candidates", { limit: 20 }],
    queryFn: () => apiClient.candidates.list({ limit: 20 }),
  });

  const flaggedCandidates = candidates?.data.filter((c) => c.fraud_flag_count > 0) ?? [];

  return (
    <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800">
      <div className="flex items-center gap-2 px-5 py-4 border-b border-zinc-100 dark:border-zinc-800">
        <AlertTriangle className="w-4 h-4 text-amber-500" />
        <h2 className="font-semibold text-zinc-900 dark:text-white">Fraud alerts</h2>
        {flaggedCandidates.length > 0 && (
          <span className="ml-auto text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300">
            {flaggedCandidates.length}
          </span>
        )}
      </div>

      {isLoading && (
        <div className="p-5 space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-12 bg-zinc-100 dark:bg-zinc-800 animate-pulse rounded-lg" />
          ))}
        </div>
      )}

      {!isLoading && flaggedCandidates.length === 0 && (
        <div className="px-5 py-10 text-center">
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            No fraud alerts to review. 🎉
          </p>
        </div>
      )}

      {flaggedCandidates.length > 0 && (
        <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
          {flaggedCandidates.slice(0, 8).map((c) => (
            <Link
              key={c.id}
              href={`/candidates/${c.id}`}
              className="flex items-center gap-3 px-5 py-3 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-zinc-900 dark:text-white truncate">
                  {c.full_name}
                </p>
                <p className="text-xs text-zinc-400 mt-0.5">
                  {c.fraud_flag_count} flag{c.fraud_flag_count !== 1 ? "s" : ""} pending review
                </p>
              </div>
              <ChevronRight className="w-4 h-4 text-zinc-400 flex-shrink-0" />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
