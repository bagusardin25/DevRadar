import type { ApiProxyOptions } from './messages';

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export async function apiRequest<T>(path: string, options: ApiProxyOptions = {}): Promise<T> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(
      { type: 'API_REQUEST', id: crypto.randomUUID(), path, options },
      (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        if (response?.error) {
          reject(new ApiError(0, response.error));
          return;
        }
        resolve(response?.data as T);
      },
    );
  });
}

export interface SubmissionReceipt {
  trackingId: string;
  status: string;
  message: string;
  duplicate: boolean;
}

export interface SubmissionStatus {
  trackingId: string;
  status: string;
  submittedAt: string;
  message: string;
  review?: {
    recommendation: string;
    confidence: number;
    summary: string;
  };
}

export interface SearchResult {
  items: Array<{
    id: string;
    kind: string;
    title: string;
    prizeLabel?: string;
    offerValue?: string;
    verificationStatus: string;
  }>;
  total: number;
}

export function submitUrl(url: string, claimedType?: string, claimedTitle?: string): Promise<SubmissionReceipt> {
  return apiRequest<SubmissionReceipt>('/submissions', {
    method: 'POST',
    body: { url, claimedType, claimedTitle },
  });
}

export function getSubmissionStatus(trackingId: string): Promise<SubmissionStatus> {
  return apiRequest<SubmissionStatus>(`/submissions/${trackingId}`);
}

export function searchCatalogue(query: string, limit = 5): Promise<SearchResult> {
  return apiRequest<SearchResult>('/search', {
    query: { q: query, limit },
  });
}
