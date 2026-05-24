"use client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL + "/api/v1";

// ─────────────────────────────────────────────────────────────────────────────
// ERROR
// ─────────────────────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// BASE FETCH
// ─────────────────────────────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  // Get token from next-auth session
  let token: string | undefined;
  try {
    const { getSession } = await import("next-auth/react");
    const session = await getSession();
    token = (session as any)?.accessToken as string | undefined;
    // Fallback: NextAuth JWT stored in cookie — attach as Bearer if present
  } catch {}

  const headers: Record<string, string> = {
    ...(options.body && !(options.body instanceof FormData)
      ? { "Content-Type": "application/json" }
      : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers as Record<string, string> | undefined),
  };

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    let errBody: any = {};
    try { errBody = await res.json(); } catch {}
    throw new ApiError(
      res.status,
      errBody.error || errBody.detail || `HTTP ${res.status}`,
      errBody.code
    );
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// ─────────────────────────────────────────────────────────────────────────────
// TYPES (subset — extend as needed)
// ─────────────────────────────────────────────────────────────────────────────

export interface Candidate {
  id: string;
  full_name: string;
  status: string;
  risk_score?: number;
  risk_level?: string;
  linkedin_url?: string;
  employment_records: EmploymentRecord[];
  education_records: EducationRecord[];
  fraud_flags: FraudFlag[];
  risk_scores: RiskScore[];
  created_at: string;
  updated_at: string;
}

export interface CandidateListItem {
  id: string;
  full_name: string;
  status: string;
  risk_score?: number;
  risk_level?: string;
  fraud_flag_count: number;
  created_at: string;
}

export interface CandidateListResponse {
  data: CandidateListItem[];
  meta: { page: number; limit: number; total: number; total_pages: number };
}

export interface EmploymentRecord {
  id: string;
  company_name: string;
  job_title?: string;
  start_date?: string;
  end_date?: string;
  location?: string;
  verification_status: string;
  confidence_score?: number;
  hr_email?: string;
  notes?: string;
  is_suspicious: boolean;
}

export interface EducationRecord {
  id: string;
  institution_name: string;
  degree?: string;
  field_of_study?: string;
  graduation_year?: number;
  verification_status: string;
  confidence_score?: number;
}

export interface FraudFlag {
  id: string;
  flag_type: string;
  severity: string;
  description: string;
  ai_reasoning?: string;
  requires_review: boolean;
  reviewed_at?: string;
  review_outcome?: string;
  created_at: string;
}

export interface RiskScore {
  id: string;
  overall_score: number;
  risk_level: string;
  score_breakdown: Record<string, any>;
  confidence: number;
  ai_reasoning?: string;
  calculated_at: string;
}

export interface Verification {
  id: string;
  candidate_id: string;
  status: string;
  config: Record<string, any>;
  celery_task_id?: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

export interface Consent {
  id: string;
  consent_type: string;
  status: string;
  granted_at?: string;
  revoked_at?: string;
  expires_at?: string;
  version: string;
  created_at: string;
}

export interface Notification {
  id: string;
  type: string;
  title?: string;
  message?: string;
  data: Record<string, any>;
  is_read: boolean;
  created_at: string;
}

export interface UsageStats {
  total_candidates: number;
  running_verifications: number;
  completed_today: number;
  unreviewed_fraud_flags: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// API CLIENT
// ─────────────────────────────────────────────────────────────────────────────

export const apiClient = {
  // CANDIDATES
  candidates: {
    list: (params: Record<string, any> = {}): Promise<CandidateListResponse> => {
      const qs = new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v != null))
      ).toString();
      return apiFetch(`/candidates${qs ? "?" + qs : ""}`);
    },
    get: (id: string): Promise<Candidate> => apiFetch(`/candidates/${id}`),
    create: (formData: FormData): Promise<Candidate> =>
      apiFetch("/candidates", { method: "POST", body: formData }),
    delete: (id: string): Promise<{ message: string }> =>
      apiFetch(`/candidates/${id}`, { method: "DELETE" }),
    getDocumentUrl: (candidateId: string, docId: string): Promise<{ url: string }> =>
      apiFetch(`/candidates/${candidateId}/documents/${docId}/url`),
    gdprErase: (id: string): Promise<{ message: string }> =>
      apiFetch(`/candidates/${id}/gdpr/erase`, { method: "DELETE" }),
  },

  // VERIFICATIONS
  verifications: {
    create: (candidateId: string, config: Record<string, any> = {}): Promise<Verification> =>
      apiFetch("/verifications", {
        method: "POST",
        body: JSON.stringify({ candidate_id: candidateId, config }),
      }),
    get: (id: string): Promise<Verification> => apiFetch(`/verifications/${id}`),
    cancel: (id: string): Promise<{ message: string }> =>
      apiFetch(`/verifications/${id}/cancel`, { method: "POST" }),
    retry: (id: string): Promise<Verification> =>
      apiFetch(`/verifications/${id}/retry`, { method: "POST" }),
  },

  // CONSENT
  consent: {
    list: (candidateId: string): Promise<Consent[]> =>
      apiFetch(`/candidates/${candidateId}/consent`),
    grant: (candidateId: string, consentType: string): Promise<Consent> =>
      apiFetch(`/candidates/${candidateId}/consent`, {
        method: "POST",
        body: JSON.stringify({ consent_type: consentType }),
      }),
    revoke: (candidateId: string, consentType: string): Promise<{ message: string }> =>
      apiFetch(`/candidates/${candidateId}/consent/${consentType}`, { method: "DELETE" }),
  },

  // FRAUD FLAGS
  fraud: {
    list: (candidateId: string): Promise<FraudFlag[]> =>
      apiFetch(`/fraud-flags/candidates/${candidateId}`),
    review: (flagId: string, outcome: string, notes?: string): Promise<FraudFlag> =>
      apiFetch(`/fraud-flags/${flagId}/review`, {
        method: "PATCH",
        body: JSON.stringify({ outcome, notes }),
      }),
  },

  // RISK SCORE
  riskScore: {
    get: (candidateId: string): Promise<RiskScore> =>
      apiFetch(`/candidates/${candidateId}/risk-score`),
  },

  // REPORTS
  reports: {
    getPdfUrl: (candidateId: string): Promise<{ url: string; expires_in_minutes: number }> =>
      apiFetch(`/candidates/${candidateId}/report/pdf`),
  },

  // NOTIFICATIONS
  notifications: {
    list: (): Promise<Notification[]> => apiFetch("/notifications"),
    markRead: (id: string): Promise<{ message: string }> =>
      apiFetch(`/notifications/${id}/read`, { method: "PATCH" }),
    markAllRead: (): Promise<{ message: string }> =>
      apiFetch("/notifications/read-all", { method: "POST" }),
  },

  // ADMIN / STATS
  admin: {
    usage: (): Promise<UsageStats> => apiFetch("/admin/usage"),
    health: (): Promise<{ status: string }> => apiFetch("/admin/health"),
  },

  // COMPLIANCE
  compliance: {
    auditLogs: (params: Record<string, any> = {}): Promise<any[]> => {
      const qs = new URLSearchParams(params).toString();
      return apiFetch(`/compliance/audit-logs${qs ? "?" + qs : ""}`);
    },
  },
};
