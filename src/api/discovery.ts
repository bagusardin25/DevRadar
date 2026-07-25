import { apiRequest } from './client';

export type DiscoveryReceipt = {
  id: string;
  status: string;
  message: string;
};

export type DiscoveryStatus = {
  id: string;
  status: string;
  query: string;
  verifiedListingIds: string[];
  costUnits: number;
  /** How many candidate URLs the run resolved from configured sources. */
  candidates: number;
  fetched: number;
  published: number;
  needsReview: number;
  failed: number;
  /** Set when a run finished without finding anything, explaining why. */
  errorSummary: string | null;
  startedAt: string | null;
  finishedAt: string | null;
};

/**
 * Only `official_site` and `rss` have a real crawler behind them; the
 * devpost/mlh/hackerearth connectors are fixture-only stubs that return nothing.
 */
export const IMPLEMENTED_CONNECTORS = ['official_site', 'rss'] as const;

export async function startLiveDiscovery(input: {
  query: string;
  module?: 'hackathon' | 'ai_offer';
  connectors?: string[];
  resultCap?: number;
}): Promise<DiscoveryReceipt> {
  return apiRequest<DiscoveryReceipt>('/discovery-runs', {
    method: 'POST',
    body: {
      query: input.query,
      module: input.module ?? 'hackathon',
      connectors: input.connectors ?? [...IMPLEMENTED_CONNECTORS],
      resultCap: input.resultCap ?? 10,
      confirmLiveDiscovery: true,
    },
  });
}

export async function getDiscoveryRun(runId: string): Promise<DiscoveryStatus> {
  return apiRequest<DiscoveryStatus>(`/discovery-runs/${runId}`);
}

/**
 * Plain-language outcome for a discovery run.
 *
 * Never claims work that did not happen: a run that is still queued means the
 * background worker never picked it up, and a run with no candidates reports
 * the backend's reason rather than a generic success.
 */
export function describeDiscoveryResult(run: DiscoveryStatus): string {
  const status = run.status.toLowerCase();

  if (status === 'queued') {
    return 'Still queued — the background worker is not processing jobs. Nothing was scanned.';
  }
  if (status === 'running') {
    return 'Still running in the background. Reload in a moment to see any new listings.';
  }
  if (status === 'failed' || status === 'error') {
    return `Discovery failed: ${run.errorSummary || 'unknown error'}`;
  }

  if (run.candidates === 0) {
    return run.errorSummary || 'No discovery sources are configured, so nothing was scanned.';
  }

  const parts = [`Scanned ${run.fetched} of ${run.candidates} page(s)`];
  parts.push(
    run.published > 0
      ? `${run.published} listing(s) verified`
      : 'nothing passed verification',
  );
  if (run.needsReview > 0) parts.push(`${run.needsReview} queued for review`);
  if (run.failed > 0) parts.push(`${run.failed} unreachable`);
  return `${parts.join(' — ')}.`;
}

/** Poll until terminal status or timeout. */
export async function waitForDiscovery(
  runId: string,
  options?: { intervalMs?: number; timeoutMs?: number },
): Promise<DiscoveryStatus> {
  const intervalMs = options?.intervalMs ?? 1500;
  const timeoutMs = options?.timeoutMs ?? 60_000;
  const started = Date.now();
  while (true) {
    const status = await getDiscoveryRun(runId);
    const s = status.status.toLowerCase();
    if (['completed', 'failed', 'cancelled', 'done', 'error'].includes(s)) {
      return status;
    }
    if (Date.now() - started > timeoutMs) {
      return status;
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}
