"use client";

import { use, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { RiskBadge, StatusBadge } from "@/components/candidates/RiskBadge";
import { formatDistanceToNow, format } from "date-fns";
import {
  ArrowLeft, FileText, Phone, Mail, Shield, AlertTriangle,
  CheckCircle, XCircle, Clock, Download, Play, ChevronDown,
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

const TABS = ["overview", "employment", "education", "fraud", "consent"] as const;
type Tab = (typeof TABS)[number];

export default function CandidateDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [tab, setTab] = useState<Tab>("overview");
  const qc = useQueryClient();

  const { data: candidate, isLoading } = useQuery({
    queryKey: ["candidate", id],
    queryFn: () => apiClient.candidates.get(id),
  });

  const startVerification = useMutation({
    mutationFn: () =>
      apiClient.verifications.create(id, {
        check_employment: true,
        check_education: true,
        allow_emails: true,
        allow_voice_calls: false,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["candidate", id] });
      alert("Verification started! Check the overview tab for progress.");
    },
    onError: (err: any) => {
      alert(err.message ?? "Failed to start verification");
    },
  });

  const downloadReport = async () => {
    try {
      const { url } = await apiClient.reports.getPdfUrl(id);
      window.open(url, "_blank");
    } catch (err: any) {
      alert(err.message ?? "Failed to generate report");
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto space-y-4">
        <div className="h-8 w-48 bg-zinc-100 dark:bg-zinc-800 animate-pulse rounded" />
        <div className="h-32 bg-zinc-100 dark:bg-zinc-800 animate-pulse rounded-xl" />
      </div>
    );
  }

  if (!candidate) {
    return (
      <div className="max-w-5xl mx-auto text-center py-20">
        <p className="text-zinc-500">Candidate not found.</p>
        <Link href="/candidates" className="mt-2 text-blue-600 hover:underline text-sm">
          ← Back to candidates
        </Link>
      </div>
    );
  }

  const latestRisk = candidate.risk_scores?.[0];

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Back */}
      <Link
        href="/candidates"
        className="inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-900 dark:hover:text-white transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" /> Back to candidates
      </Link>

      {/* Hero card */}
      <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6">
        <div className="flex flex-col sm:flex-row sm:items-start gap-4 justify-between">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-blue-100 dark:bg-blue-900 flex items-center justify-center text-xl font-bold text-blue-700 dark:text-blue-300">
              {candidate.full_name[0]?.toUpperCase()}
            </div>
            <div>
              <h1 className="text-xl font-bold text-zinc-900 dark:text-white">
                {candidate.full_name}
              </h1>
              <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                <StatusBadge status={candidate.status} />
                {candidate.risk_level && (
                  <RiskBadge level={candidate.risk_level as any} score={candidate.risk_score} />
                )}
                {candidate.linkedin_url && (
                  <a
                    href={candidate.linkedin_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-blue-600 hover:underline"
                  >
                    LinkedIn ↗
                  </a>
                )}
              </div>
              <p className="text-xs text-zinc-400 mt-1">
                Added {formatDistanceToNow(new Date(candidate.created_at), { addSuffix: true })}
              </p>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex gap-2 flex-wrap">
            {candidate.status === "parsed" && (
              <button
                onClick={() => startVerification.mutate()}
                disabled={startVerification.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-60 transition-colors"
              >
                <Play className="w-4 h-4" />
                {startVerification.isPending ? "Starting…" : "Start verification"}
              </button>
            )}
            {candidate.status === "completed" && (
              <button
                onClick={downloadReport}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 transition-colors"
              >
                <Download className="w-4 h-4" />
                Download report
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-zinc-200 dark:border-zinc-800">
        <nav className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                "px-4 py-2.5 text-sm font-medium capitalize border-b-2 -mb-px transition-colors",
                tab === t
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-zinc-500 hover:text-zinc-900 dark:hover:text-white"
              )}
            >
              {t}
              {t === "fraud" && candidate.fraud_flags.length > 0 && (
                <span className="ml-1.5 text-xs bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300 px-1.5 py-0.5 rounded-full">
                  {candidate.fraud_flags.length}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {tab === "overview" && <OverviewTab candidate={candidate} risk={latestRisk} />}
      {tab === "employment" && <EmploymentTab records={candidate.employment_records} candidateId={id} />}
      {tab === "education" && <EducationTab records={candidate.education_records} />}
      {tab === "fraud" && <FraudTab flags={candidate.fraud_flags} candidateId={id} />}
      {tab === "consent" && <ConsentTab candidateId={id} />}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// OVERVIEW TAB
// ─────────────────────────────────────────────────────────────────────────────

function OverviewTab({ candidate, risk }: { candidate: any; risk: any }) {
  if (!risk) {
    return (
      <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 text-center text-zinc-500">
        No risk score yet. Start a verification to generate one.
      </div>
    );
  }

  const scoreEntries = Object.entries(risk.score_breakdown ?? {}) as [string, any][];

  return (
    <div className="space-y-4">
      {/* Risk summary */}
      <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-zinc-900 dark:text-white">Risk assessment</h3>
          <RiskBadge level={risk.risk_level} score={risk.overall_score} />
        </div>

        {/* Score breakdown grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-4">
          {scoreEntries.map(([key, val]) => (
            <div
              key={key}
              className="text-center p-3 rounded-lg bg-zinc-50 dark:bg-zinc-800"
            >
              <p className="text-2xl font-bold text-zinc-900 dark:text-white">{val.score}</p>
              <p className="text-xs text-zinc-500 mt-0.5 capitalize">{key.replace(/_/g, " ")}</p>
            </div>
          ))}
        </div>

        {/* AI reasoning */}
        {risk.ai_reasoning && (
          <div className="bg-zinc-50 dark:bg-zinc-800 rounded-lg p-4 text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">
            {risk.ai_reasoning}
          </div>
        )}

        <p className="text-xs text-zinc-400 mt-3">
          Confidence: {Math.round((risk.confidence ?? 0) * 100)}% ·
          Calculated {formatDistanceToNow(new Date(risk.calculated_at), { addSuffix: true })}
        </p>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// EMPLOYMENT TAB
// ─────────────────────────────────────────────────────────────────────────────

function EmploymentTab({ records, candidateId }: { records: any[]; candidateId: string }) {
  if (records.length === 0) {
    return (
      <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-8 text-center text-zinc-500 text-sm">
        No employment records extracted yet. The resume may still be parsing.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {records.map((emp) => (
        <div
          key={emp.id}
          className={cn(
            "bg-white dark:bg-zinc-900 rounded-xl border p-5",
            emp.is_suspicious
              ? "border-amber-300 dark:border-amber-800"
              : "border-zinc-200 dark:border-zinc-800"
          )}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <p className="font-semibold text-zinc-900 dark:text-white">
                {emp.job_title ?? "Role not specified"} — {emp.company_name}
              </p>
              <p className="text-sm text-zinc-500 mt-0.5">
                {emp.start_date ?? "?"} → {emp.end_date ?? "Present"}
                {emp.location && ` · ${emp.location}`}
              </p>
              {emp.hr_email && (
                <p className="text-xs text-zinc-400 mt-1">HR: {emp.hr_email}</p>
              )}
              {emp.notes && (
                <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-2 bg-zinc-50 dark:bg-zinc-800 rounded-lg p-3">
                  {emp.notes}
                </p>
              )}
            </div>
            <div className="flex flex-col items-end gap-2">
              <StatusBadge status={emp.verification_status} />
              {emp.confidence_score != null && (
                <span className="text-xs text-zinc-400">{emp.confidence_score}% confidence</span>
              )}
              {emp.is_suspicious && (
                <span className="flex items-center gap-1 text-xs text-amber-600">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  Suspicious
                </span>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// EDUCATION TAB
// ─────────────────────────────────────────────────────────────────────────────

function EducationTab({ records }: { records: any[] }) {
  if (records.length === 0) {
    return (
      <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-8 text-center text-zinc-500 text-sm">
        No education records extracted yet.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {records.map((edu) => (
        <div
          key={edu.id}
          className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-5"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="font-semibold text-zinc-900 dark:text-white">
                {edu.degree ?? "Qualification"}
                {edu.field_of_study ? ` in ${edu.field_of_study}` : ""}
              </p>
              <p className="text-sm text-zinc-500 mt-0.5">
                {edu.institution_name} · {edu.graduation_year ?? "Year unknown"}
              </p>
              {edu.institution_country && (
                <p className="text-xs text-zinc-400 mt-0.5">{edu.institution_country}</p>
              )}
            </div>
            <StatusBadge status={edu.verification_status} />
          </div>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// FRAUD TAB
// ─────────────────────────────────────────────────────────────────────────────

const SEVERITY_ICON: Record<string, React.ElementType> = {
  critical: XCircle,
  high:     AlertTriangle,
  medium:   AlertTriangle,
  low:      Clock,
};

function FraudTab({ flags, candidateId }: { flags: any[]; candidateId: string }) {
  const qc = useQueryClient();

  const reviewFlag = useMutation({
    mutationFn: ({ flagId, outcome }: { flagId: string; outcome: string }) =>
      apiClient.fraud.review(flagId, outcome),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["candidate", candidateId] }),
  });

  if (flags.length === 0) {
    return (
      <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-8 text-center">
        <CheckCircle className="w-8 h-8 text-green-500 mx-auto mb-2" />
        <p className="text-sm text-zinc-500">No fraud indicators detected.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="text-xs text-zinc-500 bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 rounded-lg px-4 py-3">
        ⚠️ All fraud indicators require manual review before any hiring decision is made.
        These are potential signals, not determinations.
      </div>
      {flags.map((flag) => {
        type Severity = "critical" | "high" | "medium" | "low";
        
        const severity = (flag.severity ?? "low") as Severity;
        
        const severityColors: Record<Severity, string> = {
          critical: "text-red-600",
          high: "text-orange-600",
          medium: "text-amber-600",
          low: "text-blue-600",
        };
        
        const Icon = SEVERITY_ICON[severity] ?? AlertTriangle;
        
        const severityColor =
          severityColors[severity] ?? severityColors.low;
        return (
          <div
            key={flag.id}
            className={cn(
              "bg-white dark:bg-zinc-900 rounded-xl border p-5",
              flag.severity === "critical" || flag.severity === "high"
                ? "border-red-200 dark:border-red-900"
                : "border-zinc-200 dark:border-zinc-800"
            )}
          >
            <div className="flex items-start gap-3">
              <Icon className={cn("w-5 h-5 mt-0.5 flex-shrink-0", severityColor)} />
              <div className="flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="font-medium text-zinc-900 dark:text-white capitalize">
                    {flag.flag_type.replace(/_/g, " ")}
                  </p>
                  <span className={cn("text-xs font-semibold capitalize", severityColor)}>
                    {flag.severity}
                  </span>
                  {flag.review_outcome && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 capitalize">
                      {flag.review_outcome}
                    </span>
                  )}
                </div>
                <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">{flag.description}</p>
                {flag.ai_reasoning && (
                  <p className="text-xs text-zinc-400 mt-1 italic">{flag.ai_reasoning}</p>
                )}
                {flag.requires_review && !flag.reviewed_at && (
                  <div className="flex gap-2 mt-3">
                    <button
                      onClick={() => reviewFlag.mutate({ flagId: flag.id, outcome: "dismissed" })}
                      disabled={reviewFlag.isPending}
                      className="px-3 py-1.5 text-xs font-medium bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 rounded-lg hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors"
                    >
                      Dismiss
                    </button>
                    <button
                      onClick={() => reviewFlag.mutate({ flagId: flag.id, outcome: "confirmed" })}
                      disabled={reviewFlag.isPending}
                      className="px-3 py-1.5 text-xs font-medium bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-300 rounded-lg hover:bg-red-200 dark:hover:bg-red-900 transition-colors"
                    >
                      Confirm flag
                    </button>
                    <button
                      onClick={() => reviewFlag.mutate({ flagId: flag.id, outcome: "escalated" })}
                      disabled={reviewFlag.isPending}
                      className="px-3 py-1.5 text-xs font-medium bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300 rounded-lg hover:bg-amber-200 dark:hover:bg-amber-900 transition-colors"
                    >
                      Escalate
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// CONSENT TAB
// ─────────────────────────────────────────────────────────────────────────────

const CONSENT_TYPES = [
  "data_processing",
  "employment_verification",
  "education_verification",
  "voice_call_consent",
  "email_contact",
  "criminal_check",
];

function ConsentTab({ candidateId }: { candidateId: string }) {
  const qc = useQueryClient();

  const { data: consents, isLoading } = useQuery({
    queryKey: ["consents", candidateId],
    queryFn: () => apiClient.consent.list(candidateId),
  });

  const grantConsent = useMutation({
    mutationFn: (type: string) => apiClient.consent.grant(candidateId, type),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["consents", candidateId] }),
  });

  const revokeConsent = useMutation({
    mutationFn: (type: string) => apiClient.consent.revoke(candidateId, type),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["consents", candidateId] }),
  });

  const activeTypes = new Set(
    consents?.filter((c) => c.status === "granted").map((c) => c.consent_type) ?? []
  );

  return (
    <div className="space-y-3">
      <div className="text-xs text-zinc-500 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg px-4 py-3">
        GDPR / DPDP Act 2023 — All consents must be explicitly granted before verification begins.
        Revocation stops all processing immediately.
      </div>

      {isLoading && (
        <div className="space-y-2">
          {CONSENT_TYPES.map((t) => (
            <div key={t} className="h-16 bg-zinc-100 dark:bg-zinc-800 animate-pulse rounded-xl" />
          ))}
        </div>
      )}

      {!isLoading &&
        CONSENT_TYPES.map((type) => {
          const isGranted = activeTypes.has(type);
          const record = consents?.find((c) => c.consent_type === type && c.status === "granted");
          return (
            <div
              key={type}
              className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-4 flex items-center justify-between gap-4"
            >
              <div className="flex items-center gap-3">
                {isGranted ? (
                  <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0" />
                ) : (
                  <XCircle className="w-5 h-5 text-zinc-300 dark:text-zinc-600 flex-shrink-0" />
                )}
                <div>
                  <p className="text-sm font-medium text-zinc-900 dark:text-white capitalize">
                    {type.replace(/_/g, " ")}
                  </p>
                  {record && (
                    <p className="text-xs text-zinc-400">
                      Granted {formatDistanceToNow(new Date(record.granted_at!), { addSuffix: true })}
                    </p>
                  )}
                </div>
              </div>
              {isGranted ? (
                <button
                  onClick={() => revokeConsent.mutate(type)}
                  disabled={revokeConsent.isPending}
                  className="px-3 py-1.5 text-xs font-medium text-red-600 border border-red-200 dark:border-red-800 rounded-lg hover:bg-red-50 dark:hover:bg-red-950 transition-colors"
                >
                  Revoke
                </button>
              ) : (
                <button
                  onClick={() => grantConsent.mutate(type)}
                  disabled={grantConsent.isPending}
                  className="px-3 py-1.5 text-xs font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Grant
                </button>
              )}
            </div>
          );
        })}
    </div>
  );
}
