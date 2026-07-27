import type {
  EffortEstimate,
  HackathonMode,
  OfferType,
  VerificationStatus,
} from '../types';
import { apiRequest } from './client';

export type AdminListingInput = {
  slug: string;
  title: string;
  description: string;
  verificationStatus: VerificationStatus;
  confidenceScore: number;
};

export type AdminListingRecord = AdminListingInput & {
  id: string;
  kind: 'hackathon' | 'ai_offer';
  firstSeenAt: string;
  publishedAt: string | null;
  lastCheckedAt: string | null;
  createdAt: string;
  updatedAt: string;
};

export type AdminHackathonDetails = {
  organizer: string;
  organizerLogo: string | null;
  registrationOpenAt: string | null;
  registrationDeadline: string | null;
  submissionDeadline: string | null;
  mode: HackathonMode;
  location: string | null;
  eligibleCountries: string[];
  eligibility: string[];
  teamMin: number;
  teamMax: number;
  prizeValue: number;
  prizeCurrency: string;
  prizeLabel: string;
  technologies: string[];
  officialUrl: string;
  suitableReasons: string[];
  effortEstimate: EffortEstimate | null;
};

export type AdminAIOfferDetails = {
  productName: string;
  provider: string;
  providerLogo: string | null;
  offerType: OfferType;
  offerValue: string;
  targetUsers: string[];
  requirements: string[];
  startsAt: string | null;
  expiresAt: string | null;
  supportedRegions: string[];
  officialTermsUrl: string;
  claimUrl: string;
  tags: string[];
  suitableReasons: string[];
};

export type AdminHackathonInput = {
  listing: AdminListingInput;
  hackathon: AdminHackathonDetails;
};

export type AdminAIOfferInput = {
  listing: AdminListingInput;
  aiOffer: AdminAIOfferDetails;
};

export type AdminHackathonRecord = {
  listing: AdminListingRecord;
  hackathon: AdminHackathonDetails & {
    listingId: string;
    createdAt: string;
    updatedAt: string;
  };
};

export type AdminAIOfferRecord = {
  listing: AdminListingRecord;
  aiOffer: AdminAIOfferDetails & {
    listingId: string;
    createdAt: string;
    updatedAt: string;
  };
};

type AdminListResponse<T> = {
  items: T[];
  total: number;
};

function writeOptions(csrfToken: string, body?: unknown) {
  return {
    credentials: 'include' as const,
    headers: { 'X-CSRF-Token': csrfToken },
    body,
  };
}

export function fetchAdminHackathons(query?: string): Promise<AdminListResponse<AdminHackathonRecord>> {
  return apiRequest('/admin/catalogue/hackathons', {
    credentials: 'include',
    query: { q: query, limit: 200 },
  });
}

export function fetchAdminAIOffers(query?: string): Promise<AdminListResponse<AdminAIOfferRecord>> {
  return apiRequest('/admin/catalogue/ai-offers', {
    credentials: 'include',
    query: { q: query, limit: 200 },
  });
}

export function createAdminHackathon(
  input: AdminHackathonInput,
  csrfToken: string,
): Promise<AdminHackathonRecord> {
  return apiRequest('/admin/catalogue/hackathons', {
    method: 'POST',
    ...writeOptions(csrfToken, input),
  });
}

export function updateAdminHackathon(
  id: string,
  input: AdminHackathonInput,
  csrfToken: string,
): Promise<AdminHackathonRecord> {
  return apiRequest(`/admin/catalogue/hackathons/${id}`, {
    method: 'PUT',
    ...writeOptions(csrfToken, input),
  });
}

export async function deleteAdminHackathon(id: string, csrfToken: string): Promise<void> {
  await apiRequest(`/admin/catalogue/hackathons/${id}`, {
    method: 'DELETE',
    ...writeOptions(csrfToken),
  });
}

export function createAdminAIOffer(
  input: AdminAIOfferInput,
  csrfToken: string,
): Promise<AdminAIOfferRecord> {
  return apiRequest('/admin/catalogue/ai-offers', {
    method: 'POST',
    ...writeOptions(csrfToken, input),
  });
}

export function updateAdminAIOffer(
  id: string,
  input: AdminAIOfferInput,
  csrfToken: string,
): Promise<AdminAIOfferRecord> {
  return apiRequest(`/admin/catalogue/ai-offers/${id}`, {
    method: 'PUT',
    ...writeOptions(csrfToken, input),
  });
}

export async function deleteAdminAIOffer(id: string, csrfToken: string): Promise<void> {
  await apiRequest(`/admin/catalogue/ai-offers/${id}`, {
    method: 'DELETE',
    ...writeOptions(csrfToken),
  });
}
