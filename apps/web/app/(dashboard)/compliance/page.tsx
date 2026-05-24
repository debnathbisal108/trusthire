"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { format } from "date-fns";
import { Shield, ScrollText, Clock, CheckCircle } from "lucide-react";
import { cn } from "@/lib/utils";

type ComplianceTab = "audit" | "overview";

export default function CompliancePage() {
  const [tab, setTab] = useState<ComplianceTab>("overview");
  const [page, setPage] = useState(1);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">
          Compliance center
        </h1>
        <p className="text-zinc-500 dark:text-zinc-400 text-sm mt-1">
          GDPR / DPDP Act compliance tools, audit logs, and consent management.
        </p>
      </div>

      {/* Legal notice */}
      <div className="bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 rounded-xl px-5 py-4 text-sm text-amber-800 dark:text-amber-300">
        <strong>Legal reminder:</strong> All background verification decisions must be reviewed
        by a qualified compliance officer. TrustHire AI does not make automated adverse
        employment decisions. Public record matches are potential matches only.
      </div>

      {/* Tabs */}
      <div className="border-b border-zinc-200 dark:border-zinc-800">
        <nav className="flex gap-1">
          {[
            { id: "overview", label: "Overview", icon: Shield },
            { id: "audit",    label: "Audit log",  icon: ScrollText },
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id as ComplianceTab)}
              className={cn(
                "flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors",
                tab === id
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-zinc-500 hover:text-zinc-900 dark:hover:text-white"
              )}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </nav>
      </div>

      {tab === "overview" && <ComplianceOverview />}
      {tab === "audit"    && <AuditLogTab page={page} setPage={setPage} />}
    </div>
  );
}

// ─── Compliance overview ────────────────────────────────────────────────────

function ComplianceOverview() {
  const { data: stats } = useQuery({
    queryKey: ["admin-usage"],
    queryFn: () => apiClient.admin.usage(),
  });

  const items = [
    {
      label: "Data processing consents",
      description: "Explicit consents recorded under GDPR Art. 6(1)(a)",
      icon: CheckCircle,
      color: "text-green-600",
      bg: "bg-green-50 dark:bg-green-950",
    },
    {
      label: "Audit log entries",
      description: "Immutable records of all system actions",
      icon: ScrollText,
      color: "text-blue-600",
      bg: "bg-blue-50 dark:bg-blue-950",
    },
    {
      label: "Fraud flags pending review",
      value: stats?.unreviewed_fraud_flags,
      description: "Require manual compliance officer review",
      icon: Clock,
      color: (stats?.unreviewed_fraud_flags ?? 0) > 0 ? "text-amber-600" : "text-zinc-400",
      bg: (stats?.unreviewed_fraud_flags ?? 0) > 0
        ? "bg-amber-50 dark:bg-amber-950"
        : "bg-zinc-50 dark:bg-zinc-800",
    },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {items.map((item) => (
          <div
            key={item.label}
            className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-5"
          >
            <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center mb-3", item.bg)}>
              <item.icon className={cn("w-5 h-5", item.color)} />
            </div>
            <p className="font-semibold text-zinc-900 dark:text-white text-sm">
              {item.label}
            </p>
            {item.value !== undefined && (
              <p className="text-2xl font-bold text-zinc-900 dark:text-white mt-1">{item.value}</p>
            )}
            <p className="text-xs text-zinc-500 mt-1">{item.description}</p>
          </div>
        ))}
      </div>

      {/* Data retention policy */}
      <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 space-y-4">
        <h3 className="font-semibold text-zinc-900 dark:text-white">Data retention policy</h3>
        <div className="space-y-3 text-sm text-zinc-600 dark:text-zinc-400">
          <div className="flex justify-between py-2 border-b border-zinc-100 dark:border-zinc-800">
            <span>Candidate personal data</span>
            <span className="font-medium text-zinc-900 dark:text-white">365 days from consent</span>
          </div>
          <div className="flex justify-between py-2 border-b border-zinc-100 dark:border-zinc-800">
            <span>Call recordings</span>
            <span className="font-medium text-zinc-900 dark:text-white">90 days</span>
          </div>
          <div className="flex justify-between py-2 border-b border-zinc-100 dark:border-zinc-800">
            <span>Audit logs</span>
            <span className="font-medium text-zinc-900 dark:text-white">7 years (legal requirement)</span>
          </div>
          <div className="flex justify-between py-2">
            <span>Verification reports</span>
            <span className="font-medium text-zinc-900 dark:text-white">365 days</span>
          </div>
        </div>
        <p className="text-xs text-zinc-400">
          Data deletion requests (GDPR Art. 17) are processed via the candidate detail page.
          Audit logs are retained but anonymised upon erasure requests.
        </p>
      </div>
    </div>
  );
}

// ─── Audit log tab ───────────────────────────────────────────────────────────

function AuditLogTab({
  page,
  setPage,
}: {
  page: number;
  setPage: (p: number) => void;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["audit-logs", page],
    queryFn: () => apiClient.compliance.auditLogs({ page, limit: 50 }),
    placeholderData: (prev) => prev,
  });

  const entries = Array.isArray(data) ? data : [];

  const ACTION_COLORS: Record<string, string> = {
    "candidate.create":        "bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300",
    "candidate.delete":        "bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-300",
    "verification.start":      "bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300",
    "verification.completed":  "bg-green-100 dark:bg-green-950 text-green-700 dark:text-green-300",
    "verification.cancel":     "bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400",
    "consent.granted":         "bg-green-100 dark:bg-green-950 text-green-700 dark:text-green-300",
    "consent.revoked":         "bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300",
    "gdpr.erasure_completed":  "bg-purple-100 dark:bg-purple-950 text-purple-700 dark:text-purple-300",
    "fraud_flag.reviewed":     "bg-orange-100 dark:bg-orange-950 text-orange-700 dark:text-orange-300",
    "report.downloaded":       "bg-cyan-100 dark:bg-cyan-950 text-cyan-700 dark:text-cyan-300",
  };

  return (
    <div className="space-y-4">
      <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
        <div className="px-5 py-4 border-b border-zinc-100 dark:border-zinc-800">
          <h3 className="font-semibold text-zinc-900 dark:text-white">Audit log</h3>
          <p className="text-xs text-zinc-500 mt-0.5">
            Immutable record of all actions. Page {page}.
          </p>
        </div>

        {isLoading && (
          <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="px-5 py-4 flex items-center gap-4">
                <div className="h-5 w-48 bg-zinc-100 dark:bg-zinc-800 animate-pulse rounded" />
                <div className="h-5 w-32 bg-zinc-100 dark:bg-zinc-800 animate-pulse rounded" />
              </div>
            ))}
          </div>
        )}

        {!isLoading && entries.length === 0 && (
          <div className="px-5 py-12 text-center text-sm text-zinc-500">
            No audit log entries yet.
          </div>
        )}

        {entries.length > 0 && (
          <div className="divide-y divide-zinc-100 dark:divide-zinc-800 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-zinc-50 dark:bg-zinc-800/50">
                  <th className="text-left px-5 py-2.5 text-xs font-semibold text-zinc-500">Action</th>
                  <th className="text-left px-5 py-2.5 text-xs font-semibold text-zinc-500">Entity</th>
                  <th className="text-left px-5 py-2.5 text-xs font-semibold text-zinc-500">IP</th>
                  <th className="text-left px-5 py-2.5 text-xs font-semibold text-zinc-500">When</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((log: any) => (
                  <tr
                    key={log.id}
                    className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors"
                  >
                    <td className="px-5 py-3">
                      <span
                        className={cn(
                          "inline-block px-2 py-0.5 rounded-full text-xs font-medium",
                          ACTION_COLORS[log.action] ??
                            "bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400"
                        )}
                      >
                        {log.action}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-zinc-500 text-xs font-mono">
                      {log.entity_type && (
                        <span>{log.entity_type}</span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-zinc-400 text-xs font-mono">
                      {log.ip_address ?? "—"}
                    </td>
                    <td className="px-5 py-3 text-zinc-400 text-xs">
                      {format(new Date(log.created_at), "MMM d, HH:mm:ss")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-zinc-100 dark:border-zinc-800">
          <p className="text-xs text-zinc-500">Page {page}</p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page <= 1}
              className="px-3 py-1.5 text-xs border border-zinc-200 dark:border-zinc-700 rounded-lg disabled:opacity-40 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
            >
              Previous
            </button>
            <button
              onClick={() => setPage(page + 1)}
              disabled={entries.length < 50}
              className="px-3 py-1.5 text-xs border border-zinc-200 dark:border-zinc-700 rounded-lg disabled:opacity-40 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
