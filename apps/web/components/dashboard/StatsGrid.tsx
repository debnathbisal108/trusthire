"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { Users, Loader2, CheckCircle, AlertTriangle, Activity } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: number | string;
  icon: React.ElementType;
  iconColor: string;
  iconBg: string;
  loading?: boolean;
}

function StatCard({ label, value, icon: Icon, iconColor, iconBg, loading }: StatCardProps) {
  return (
    <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">{label}</p>
          {loading ? (
            <div className="h-8 w-16 bg-zinc-100 dark:bg-zinc-800 animate-pulse rounded mt-1" />
          ) : (
            <p className="text-2xl font-bold text-zinc-900 dark:text-white mt-1">{value}</p>
          )}
        </div>
        <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center", iconBg)}>
          <Icon className={cn("w-5 h-5", iconColor)} />
        </div>
      </div>
    </div>
  );
}

export default function StatsGrid() {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-usage"],
    queryFn: () => apiClient.admin.usage(),
    refetchInterval: 60_000,
  });

  const stats = [
    {
      label: "Total candidates",
      value: data?.total_candidates ?? 0,
      icon: Users,
      iconColor: "text-blue-600",
      iconBg: "bg-blue-50 dark:bg-blue-950",
    },
    {
      label: "Verifications running",
      value: data?.running_verifications ?? 0,
      icon: Activity,
      iconColor: "text-indigo-600",
      iconBg: "bg-indigo-50 dark:bg-indigo-950",
    },
    {
      label: "Completed today",
      value: data?.completed_today ?? 0,
      icon: CheckCircle,
      iconColor: "text-green-600",
      iconBg: "bg-green-50 dark:bg-green-950",
    },
    {
      label: "Fraud alerts",
      value: data?.unreviewed_fraud_flags ?? 0,
      icon: AlertTriangle,
      iconColor: (data?.unreviewed_fraud_flags ?? 0) > 0 ? "text-amber-600" : "text-zinc-400",
      iconBg:
        (data?.unreviewed_fraud_flags ?? 0) > 0
          ? "bg-amber-50 dark:bg-amber-950"
          : "bg-zinc-50 dark:bg-zinc-800",
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map((s) => (
        <StatCard key={s.label} {...s} loading={isLoading} />
      ))}
    </div>
  );
}
