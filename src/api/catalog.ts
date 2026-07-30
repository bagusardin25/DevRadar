import type { AIDeal, FilterState, Hackathon } from '../types';
import { apiRequest } from './client';
import { normalizeAIDeal, normalizeHackathon } from './normalize';

export type CollectionResponse<T> = {
  items: T[];
  nextCursor: string | null;
  totalEstimate: number;
};

export type CatalogueStats = {
  hackathonsActive: number;
  aiOffersActive: number;
  sourcesEnabled: number;
  lastIndexedAt: string | null;
};

export type FilterMeta = {
  technologies: string[];
  regions: string[];
  eligibilityLabels: string[];
  offerTypes: string[];
  modes: string[];
  verificationStatuses: string[];
};

function applyLocalFlags<T extends { id: string; bookmarked?: boolean; alertEnabled?: boolean }>(
  items: T[],
  bookmarks: Set<string>,
  alerts: Set<string>,
): T[] {
  return items.map((item) => ({
    ...item,
    bookmarked: bookmarks.has(item.id),
    alertEnabled: alerts.has(item.id),
  }));
}

export async function fetchHackathons(
  filters: FilterState,
  options?: {
    cursor?: string;
    limit?: number;
    bookmarks?: Set<string>;
    alerts?: Set<string>;
    signal?: AbortSignal;
  },
): Promise<CollectionResponse<Hackathon>> {
  const data = await apiRequest<CollectionResponse<Record<string, unknown>>>('/hackathons', {
    query: {
      q: filters.searchQuery || undefined,
      mode: filters.mode !== 'all' ? filters.mode : undefined,
      region: filters.region || undefined,
      eligibility: filters.eligibility || undefined,
      technology: filters.technology || undefined,
      status: filters.verificationStatus || undefined,
      onlyClosingSoon: filters.onlyClosingSoon || undefined,
      onlyBigPrizes: filters.onlyBigPrizes || undefined,
      cursor: options?.cursor,
      limit: options?.limit ?? 50,
    },
    signal: options?.signal,
  });

  const items = data.items.map((raw) =>
    normalizeHackathon(raw, {
      bookmarked: options?.bookmarks?.has(String(raw.id)),
      alertEnabled: options?.alerts?.has(String(raw.id)),
    }),
  );

  return {
    items: applyLocalFlags(items, options?.bookmarks ?? new Set(), options?.alerts ?? new Set()),
    nextCursor: data.nextCursor,
    totalEstimate: data.totalEstimate,
  };
}

export async function fetchAIOffers(
  filters: FilterState,
  options?: {
    cursor?: string;
    limit?: number;
    bookmarks?: Set<string>;
    alerts?: Set<string>;
    signal?: AbortSignal;
  },
): Promise<CollectionResponse<AIDeal>> {
  const data = await apiRequest<CollectionResponse<Record<string, unknown>>>('/ai-offers', {
    query: {
      q: filters.searchQuery || undefined,
      offerType: filters.offerType || undefined,
      region: filters.region || undefined,
      tags: filters.technology || undefined,
      status: filters.verificationStatus || undefined,
      onlyFreeNoCard: filters.onlyFreeNoCard || undefined,
      cursor: options?.cursor,
      limit: options?.limit ?? 50,
    },
    signal: options?.signal,
  });

  const items = data.items.map((raw) =>
    normalizeAIDeal(raw, {
      bookmarked: options?.bookmarks?.has(String(raw.id)),
      alertEnabled: options?.alerts?.has(String(raw.id)),
    }),
  );

  return {
    items: applyLocalFlags(items, options?.bookmarks ?? new Set(), options?.alerts ?? new Set()),
    nextCursor: data.nextCursor,
    totalEstimate: data.totalEstimate,
  };
}

export async function fetchCatalogueStats(signal?: AbortSignal): Promise<CatalogueStats> {
  const data = await apiRequest<CatalogueStats>('/stats', { signal });
  return {
    hackathonsActive: Number(data.hackathonsActive ?? 0),
    aiOffersActive: Number(data.aiOffersActive ?? 0),
    sourcesEnabled: Number(data.sourcesEnabled ?? 0),
    lastIndexedAt: data.lastIndexedAt ?? null,
  };
}

export async function fetchFilterMeta(signal?: AbortSignal): Promise<FilterMeta> {
  return apiRequest<FilterMeta>('/meta/filters', { signal });
}
