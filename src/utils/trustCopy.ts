import type { AIDeal, SourceTier, VerificationStatus } from '../types';
import { formatAppDate } from './dateTime';

/** Public, non-jargon label for a verification status. */
export function publicStatusLabel(status: VerificationStatus): {
  label: string;
  title: string;
} {
  switch (status) {
    case 'verified_active':
      return {
        label: 'Checked official',
        title: 'We fetched the official page and the listing still looks active',
      };
    case 'likely_active':
      return {
        label: 'Likely — confirm',
        title: 'Looks active, but confirm dates and terms on the official page',
      };
    case 'registration_closed':
      return { label: 'Registration closed', title: 'Registration is no longer open' };
    case 'expired':
      return { label: 'Ended', title: 'The deadline or offer window has passed' };
    case 'cancelled':
      return { label: 'Cancelled', title: 'This opportunity was cancelled' };
    case 'needs_review':
    default:
      return { label: 'Unconfirmed', title: 'Not yet checked against an official page' };
  }
}

/** Short provenance label — not "Tier 1 (Official)". */
export function publicSourceLabel(tier: SourceTier | string | undefined): string {
  const raw = (tier || '').toLowerCase();
  if (raw.includes('tier 1') || raw.includes('official')) return 'Official page';
  if (raw.includes('tier 2') || raw.includes('aggregator')) return 'Directory';
  if (raw.includes('tier 3') || raw.includes('signal')) return 'Social signal';
  return '';
}

export function checkedOnLabel(lastCheckedAt: string | undefined): string | null {
  if (!lastCheckedAt) return null;
  const formatted = formatAppDate(lastCheckedAt, { month: 'short', day: 'numeric' }, '');
  return formatted ? `Checked ${formatted}` : null;
}

export type OfferWindowKind = 'claim_by' | 'ongoing' | 'expired' | 'unknown';

export function offerWindow(deal: Pick<AIDeal, 'expiresAt' | 'offerType'>): {
  kind: OfferWindowKind;
  label: string;
} {
  if (deal.expiresAt) {
    const end = new Date(deal.expiresAt);
    if (!Number.isNaN(end.getTime()) && end.getTime() < Date.now()) {
      return { kind: 'expired', label: 'Claim window ended' };
    }
    const day = formatAppDate(deal.expiresAt, { month: 'short', day: 'numeric' }, '');
    return { kind: 'claim_by', label: day ? `Claim by ${day}` : 'Has an end date' };
  }
  if (deal.offerType === 'free_tier' || deal.offerType === 'free_model') {
    return { kind: 'ongoing', label: 'Ongoing free tier' };
  }
  return { kind: 'unknown', label: 'No stated end date' };
}

