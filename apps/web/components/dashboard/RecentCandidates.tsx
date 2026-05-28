"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { apiClient } from "@/lib/api-client";
import { RiskBadge } from "@/components/candidates/RiskBadge";
// import { StatusBadge } from "@/components/candidates/StatusBadge";
import { formatDistanceToNow } from "date-fns";
import { ArrowRight, AlertTriangle } from "lucide-react";

export default function RecentCandidates() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["candidates", { limit: 8 }],
    queryFn: () => apiClient.candidates.list({ limit: 8 }),
  });

  return (
    <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800">
      <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-100 dark:border-zinc-800">
        <h2 className="font-semibold text-zinc-900 dark:text-white">Recent candidates</h2>
        <Link
          href="/candidates"
          className="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-1"
        >
          View all <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>

      {isLoading && (
        <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="px-5 py-4 flex items-center gap-4">
              <div className="w-8 h-8 rounded-full bg-zinc-100 dark:bg-zinc-800 animate-pulse" />
              <div className="flex-1 space-y-1.5">
                <div className="h-4 w-36 bg-zinc-100 dark:bg-zinc-800 animate-pulse rounded" />
                <div className="h-3 w-24 bg-zinc-100 dark:bg-zinc-800 animate-pulse rounded" />
              </div>
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="px-5 py-8 text-center text-sm text-zinc-500">
          Failed to load candidates. Check your API connection.
        </div>
      )}

      {data && data.data.length === 0 && (
        <div className="px-5 py-12 text-center">
          <p className="text-sm text-zinc-500 dark:text-zinc-400">No candidates yet.</p>
          <Link
            href="/candidates/new"
            className="mt-2 inline-block text-sm text-blue-600 hover:underline"
          >
            Add your first candidate →
          </Link>
        </div>
      )}

      {data && data.data.length > 0 && (
        <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
          {data.data.map((c) => (
            <Link
              key={c.id}
              href={`/candidates/${c.id}`}
              className="flex items-center gap-4 px-5 py-3.5 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors"
            >
              {/* Avatar */}
              <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center text-xs font-semibold text-blue-700 dark:text-blue-300 flex-shrink-0">
                {c.full_name[0]?.toUpperCase() ?? "?"}
              </div>

              {/* Name + time */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-zinc-900 dark:text-white truncate">
                  {c.full_name}
                </p>
                <p className="text-xs text-zinc-400">
                  {formatDistanceToNow(new Date(c.created_at), { addSuffix: true })}
                </p>
              </div>

              {/* Fraud flag indicator */}
              {c.fraud_flag_count > 0 && (
                <span className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  {c.fraud_flag_count}
                </span>
              )}

              {/* Badges */}
              <div className="flex items-center gap-2">
                <StatusBadge status={c.status} />
                {c.risk_level && (
                  <RiskBadge level={c.risk_level as any} score={c.risk_score} />
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
