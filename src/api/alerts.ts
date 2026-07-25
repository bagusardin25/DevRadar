import { apiRequest } from './client';

export type AlertFilterInput = {
  kind?: 'hackathon' | 'ai_offer' | 'all';
  q?: string;
  mode?: 'online' | 'hybrid' | 'in_person' | 'all';
  technology?: string;
  minPrize?: number;
  onlyBigPrizes?: boolean;
  onlyClosingSoon?: boolean;
  closingSoonDays?: number;
  region?: string;
  offerType?: string;
  status?: string;
};

export type AlertCreateInput = {
  email: string;
  /** @deprecated prefer filters.kind */
  targetType?: 'hackathon' | 'ai_offer' | 'all';
  filters?: AlertFilterInput;
  /** Mapped to backend `cadence` */
  frequency?: 'daily' | 'weekly' | 'instant';
  cadence?: 'daily' | 'weekly' | 'instant';
  /** Honeypot — leave empty */
  website?: string;
};

export type AlertCreateResponse = {
  status: string;
  message?: string;
};

/**
 * Build the filters object sent to POST /alerts.
 * Backend normalizes camelCase / snake_case and stores a canonical form.
 */
export function buildAlertFilters(input: AlertCreateInput): Record<string, unknown> {
  const filters: Record<string, unknown> = { ...(input.filters || {}) };

  const kind = input.filters?.kind ?? input.targetType;
  if (kind && kind !== 'all') {
    filters.kind = kind;
  } else {
    delete filters.kind;
  }

  if (filters.mode === 'all') delete filters.mode;
  if (!filters.technology) delete filters.technology;
  if (!filters.q) delete filters.q;
  if (!filters.region) delete filters.region;
  if (!filters.offerType) delete filters.offerType;
  if (!filters.status) delete filters.status;

  if (filters.onlyBigPrizes) {
    delete filters.minPrize;
  } else if (typeof filters.minPrize === 'number' && filters.minPrize <= 0) {
    delete filters.minPrize;
  }

  if (!filters.onlyClosingSoon) {
    delete filters.onlyClosingSoon;
    delete filters.closingSoonDays;
  }

  return filters;
}

export async function createAlert(input: AlertCreateInput): Promise<AlertCreateResponse> {
  const cadence = input.cadence || input.frequency || 'weekly';
  return apiRequest<AlertCreateResponse>('/alerts', {
    method: 'POST',
    body: {
      email: input.email,
      filters: buildAlertFilters(input),
      cadence,
      // Honeypot field (bots fill "website")
      website: input.website || undefined,
    },
  });
}

export async function unsubscribeAlert(token: string): Promise<void> {
  await apiRequest('/alerts/unsubscribe', {
    method: 'POST',
    query: { token },
  });
}
