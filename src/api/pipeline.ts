import { apiRequest } from './client';

// --- Sources ---

export type Source = {
  id: string;
  name: string;
  connectorType: string;
  trustTier: string;
  baseUrl: string | null;
  enabled: boolean;
  credentialRef: string | null;
  pollingPolicy: Record<string, unknown>;
  fetchPolicy: Record<string, unknown>;
};

export type SourceCreateInput = {
  name: string;
  connectorType: string;
  trustTier: string;
  baseUrl?: string;
  enabled?: boolean;
  credentialRef?: string;
  pollingPolicy?: Record<string, unknown>;
  fetchPolicy?: Record<string, unknown>;
};

export type SourceUpdateInput = {
  name?: string;
  enabled?: boolean;
  baseUrl?: string;
  credentialRef?: string;
  pollingPolicy?: Record<string, unknown>;
  fetchPolicy?: Record<string, unknown>;
};

export async function fetchSources(): Promise<Source[]> {
  const data = await apiRequest<{ items: Source[] }>('/admin/sources', {
    credentials: 'include',
  });
  return data.items;
}

export async function createSource(
  input: SourceCreateInput,
  csrfToken: string,
): Promise<Source> {
  return apiRequest<Source>('/admin/sources', {
    method: 'POST',
    credentials: 'include',
    headers: { 'X-CSRF-Token': csrfToken },
    body: input,
  });
}

export async function getSource(sourceId: string): Promise<Source> {
  return apiRequest<Source>(`/admin/sources/${sourceId}`, {
    credentials: 'include',
  });
}

export async function updateSource(
  sourceId: string,
  input: SourceUpdateInput,
  csrfToken: string,
): Promise<Source> {
  return apiRequest<Source>(`/admin/sources/${sourceId}`, {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'X-CSRF-Token': csrfToken },
    body: input,
  });
}

// --- Crawl Runs ---

export type CrawlRun = {
  id: string;
  sourceId: string;
  status: string;
  trigger: string;
  discoveredCount: number;
  fetchedCount: number;
  failedCount: number;
  errorSummary: string | null;
  idempotencyKey: string | null;
};

export async function fetchCrawlRuns(): Promise<CrawlRun[]> {
  const data = await apiRequest<{ items: CrawlRun[] }>('/admin/crawl-runs', {
    credentials: 'include',
  });
  return data.items;
}

export async function retryCrawlRun(
  runId: string,
  csrfToken: string,
): Promise<CrawlRun> {
  return apiRequest<CrawlRun>(`/admin/crawl-runs/${runId}/retry`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'X-CSRF-Token': csrfToken },
  });
}
