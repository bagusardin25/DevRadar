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
};

export async function startLiveDiscovery(input: {
  query: string;
  connectors?: string[];
  resultCap?: number;
}): Promise<DiscoveryReceipt> {
  return apiRequest<DiscoveryReceipt>('/discovery-runs', {
    method: 'POST',
    body: {
      query: input.query,
      connectors: input.connectors ?? ['devpost'],
      resultCap: input.resultCap ?? 10,
      confirmLiveDiscovery: true,
    },
  });
}

export async function getDiscoveryRun(runId: string): Promise<DiscoveryStatus> {
  return apiRequest<DiscoveryStatus>(`/discovery-runs/${runId}`);
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
