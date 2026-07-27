import { apiRequest } from './client';

export type AdminMe = {
  subject: string;
  email: string;
  csrfToken: string;
};

export type ReviewItem = {
  id: string;
  candidateType: string;
  candidateId: string | null;
  candidateSnapshot: Record<string, unknown>;
  reason: string;
  priority: number;
  state: string;
  assignedAdminId: string | null;
  listingId: string | null;
  version: number;
  resolution: Record<string, unknown> | null;
  resolvedAt: string | null;
  createdAt: string;
  updatedAt: string;
};

export type AIReviewRecommendation = 'approve' | 'reject' | 'needs_more_info';

export type AIReviewConcern = {
  severity: 'high' | 'medium' | 'low';
  message: string;
};

/** Automated pre-review attached to a submission's candidateSnapshot.aiReview. */
export type AIReviewSnapshot = {
  recommendation: AIReviewRecommendation;
  confidence: number;
  summary: string;
  concerns: AIReviewConcern[];
  suggestedFields: Record<string, unknown>;
  engine: string;
  model: string | null;
  generatedAt: string;
  version: string;
};

/** Deterministic verification summary attached alongside the AI review. */
export type VerificationSnapshot = {
  status: string;
  score: number;
  reasons: string[];
  publishable: boolean;
};

export type AIUsageCall = {
  operation: string;
  provider: string;
  model: string;
  serviceTier: string;
  promptTokens: number;
  cachedPromptTokens: number;
  completionTokens: number;
  totalTokens: number;
  estimatedCostUsd: number | null;
};

export type AIUsageSnapshot = {
  currency: 'USD';
  estimated: boolean;
  pricingVersion: string;
  pricingComplete: boolean;
  promptTokens: number;
  cachedPromptTokens: number;
  completionTokens: number;
  totalTokens: number;
  estimatedCostUsd: number | null;
  calls: AIUsageCall[];
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

/** Safely read the AI review block from an untyped snapshot. */
export function readAIReview(snapshot: Record<string, unknown>): AIReviewSnapshot | null {
  const raw = asRecord(snapshot.aiReview);
  if (!raw) return null;
  const rec = String(raw.recommendation ?? 'needs_more_info') as AIReviewRecommendation;
  const concerns = Array.isArray(raw.concerns)
    ? raw.concerns.flatMap((c) => {
        const r = asRecord(c);
        if (!r || typeof r.message !== 'string') return [];
        const severity = (['high', 'medium', 'low'].includes(String(r.severity))
          ? r.severity
          : 'low') as AIReviewConcern['severity'];
        return [{ severity, message: r.message }];
      })
    : [];
  return {
    recommendation: (['approve', 'reject', 'needs_more_info'].includes(rec)
      ? rec
      : 'needs_more_info') as AIReviewRecommendation,
    confidence: Number(raw.confidence ?? 0),
    summary: typeof raw.summary === 'string' ? raw.summary : '',
    concerns,
    suggestedFields: asRecord(raw.suggestedFields) ?? {},
    engine: typeof raw.engine === 'string' ? raw.engine : 'heuristic',
    model: typeof raw.model === 'string' ? raw.model : null,
    generatedAt: typeof raw.generatedAt === 'string' ? raw.generatedAt : '',
    version: typeof raw.version === 'string' ? raw.version : '',
  };
}

/** Safely read the verification block from an untyped snapshot. */
export function readVerification(snapshot: Record<string, unknown>): VerificationSnapshot | null {
  const raw = asRecord(snapshot.verification);
  if (!raw) return null;
  return {
    status: String(raw.status ?? 'needs_review'),
    score: Number(raw.score ?? 0),
    reasons: Array.isArray(raw.reasons) ? raw.reasons.map(String) : [],
    publishable: Boolean(raw.publishable),
  };
}

/** Read token usage and estimated model cost recorded by the worker. */
export function readAIUsage(snapshot: Record<string, unknown>): AIUsageSnapshot | null {
  const raw = asRecord(snapshot.aiUsage);
  if (!raw) return null;
  const calls = Array.isArray(raw.calls)
    ? raw.calls.flatMap((value) => {
        const call = asRecord(value);
        if (!call) return [];
        const cost = call.estimatedCostUsd;
        return [{
          operation: String(call.operation ?? 'unknown'),
          provider: String(call.provider ?? 'openai'),
          model: String(call.model ?? 'unknown'),
          serviceTier: String(call.serviceTier ?? 'default'),
          promptTokens: Number(call.promptTokens ?? 0),
          cachedPromptTokens: Number(call.cachedPromptTokens ?? 0),
          completionTokens: Number(call.completionTokens ?? 0),
          totalTokens: Number(call.totalTokens ?? 0),
          estimatedCostUsd: cost === null || cost === undefined ? null : Number(cost),
        }];
      })
    : [];
  const totalCost = raw.estimatedCostUsd;
  return {
    currency: 'USD',
    estimated: Boolean(raw.estimated ?? true),
    pricingVersion: String(raw.pricingVersion ?? 'unknown'),
    pricingComplete: Boolean(raw.pricingComplete),
    promptTokens: Number(raw.promptTokens ?? 0),
    cachedPromptTokens: Number(raw.cachedPromptTokens ?? 0),
    completionTokens: Number(raw.completionTokens ?? 0),
    totalTokens: Number(raw.totalTokens ?? 0),
    estimatedCostUsd:
      totalCost === null || totalCost === undefined ? null : Number(totalCost),
    calls,
  };
}

export type ReviewListResponse = {
  items: ReviewItem[];
  total: number;
};

export type ReviewCorrections = {
  title?: string;
  description?: string;
  kind?: 'hackathon' | 'ai_offer';
  officialUrl?: string;
  claimUrl?: string;
  fields?: Record<string, unknown>;
};

export async function fetchAdminMe(): Promise<AdminMe | null> {
  try {
    return await apiRequest<AdminMe>('/admin/auth/me', { credentials: 'include' });
  } catch (err) {
    const status = (err as { status?: number }).status;
    if (status === 401 || status === 403) return null;
    throw err;
  }
}

export async function startAdminGoogleLogin(): Promise<string> {
  const data = await apiRequest<{ authorizeUrl: string }>('/admin/auth/google/start');
  return data.authorizeUrl;
}

export async function adminLogout(csrfToken: string): Promise<void> {
  await apiRequest('/admin/auth/logout', {
    method: 'POST',
    credentials: 'include',
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function fetchReviewItems(options?: {
  state?: string;
  limit?: number;
}): Promise<ReviewListResponse> {
  return apiRequest<ReviewListResponse>('/admin/review-items', {
    credentials: 'include',
    query: {
      state: options?.state,
      limit: options?.limit ?? 50,
    },
  });
}

export async function approveReviewItem(
  id: string,
  expectedVersion: number,
  csrfToken: string,
  notes?: string,
  corrections: ReviewCorrections = {},
): Promise<void> {
  await apiRequest(`/admin/review-items/${id}/approve`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'X-CSRF-Token': csrfToken },
    body: { expectedVersion, notes, corrections },
  });
}

export async function rejectReviewItem(
  id: string,
  expectedVersion: number,
  reason: string,
  csrfToken: string,
): Promise<void> {
  await apiRequest(`/admin/review-items/${id}/reject`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'X-CSRF-Token': csrfToken },
    body: { expectedVersion, reason },
  });
}
