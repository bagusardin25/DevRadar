import { apiRequest } from './client';

export type AdminMe = {
  githubId: string;
  login: string;
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

export type ReviewListResponse = {
  items: ReviewItem[];
  total: number;
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

export async function startAdminGithubLogin(): Promise<string> {
  const data = await apiRequest<{ authorizeUrl: string }>('/admin/auth/github/start');
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
): Promise<void> {
  await apiRequest(`/admin/review-items/${id}/approve`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'X-CSRF-Token': csrfToken },
    body: { expectedVersion, notes },
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
