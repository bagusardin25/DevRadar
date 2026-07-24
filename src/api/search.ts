import { apiRequest } from './client';

export type CombinedSearchResult = {
  id: string;
  kind: 'hackathon' | 'ai_offer';
  title: string;
  slug: string;
  verificationStatus: string;
  confidenceScore: number;
  [key: string]: unknown;
};

export type CombinedSearchResponse = {
  items: CombinedSearchResult[];
  nextCursor: string | null;
  totalEstimate: number;
};

export async function combinedSearch(options?: {
  q?: string;
  kind?: 'hackathon' | 'ai_offer';
  status?: string;
  cursor?: string;
  limit?: number;
  signal?: AbortSignal;
}): Promise<CombinedSearchResponse> {
  return apiRequest<CombinedSearchResponse>('/search', {
    query: {
      q: options?.q,
      kind: options?.kind,
      status: options?.status,
      cursor: options?.cursor,
      limit: options?.limit ?? 50,
    },
    signal: options?.signal,
  });
}
