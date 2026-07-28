/**
 * Countdown & urgency utilities for deadline display (Wave D — D1).
 *
 * Centralises the "how urgent is this deadline?" logic so cards, modals,
 * and future email digests can all share the same copy & colours.
 */

export type UrgencyLevel = 'critical' | 'warning' | 'normal' | 'closed';

export interface DeadlineInfo {
  /** Days remaining (0 = closes today, negative = already closed). */
  daysLeft: number;
  /** Hours remaining (for sub-day precision on critical items). */
  hoursLeft: number;
  /** Display-ready label, e.g. "Closes today", "3 days left", "Reg closed". */
  label: string;
  /** Short label for tight spaces (card footer). */
  shortLabel: string;
  /** Urgency level for colour theming. */
  urgency: UrgencyLevel;
  /** Tailwind-compatible text colour class. */
  colorClass: string;
  /** Hex colour for inline styles. */
  colorHex: string;
  /** Background tint (rgba) for pill badges. */
  bgTint: string;
}

/**
 * Compute deadline info from an ISO date string.
 *
 * @param isoDate  ISO 8601 string (e.g. `hackathon.registrationDeadline`)
 * @param closedLabel  Label when deadline has passed (default "Reg closed")
 */
export function getDeadlineInfo(
  isoDate: string | null | undefined,
  closedLabel = 'Reg closed',
): DeadlineInfo | null {
  if (!isoDate) return null;

  const deadline = new Date(isoDate);
  if (Number.isNaN(deadline.getTime())) return null;

  const now = new Date();
  const diffMs = deadline.getTime() - now.getTime();
  const diffHours = diffMs / (1000 * 60 * 60);
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  // Already closed
  if (diffMs < 0) {
    return {
      daysLeft: diffDays,
      hoursLeft: Math.floor(diffHours),
      label: closedLabel,
      shortLabel: 'Closed',
      urgency: 'closed',
      colorClass: 'text-gray-400',
      colorHex: '#9CA3AF',
      bgTint: 'rgba(156,163,175,0.12)',
    };
  }

  // Closes today (< 24h)
  if (diffDays <= 0 || diffHours < 24) {
    const hrs = Math.max(0, Math.floor(diffHours));
    return {
      daysLeft: 0,
      hoursLeft: hrs,
      label: hrs <= 1 ? 'Closes in < 1 hr!' : `Closes today · ${hrs}h left`,
      shortLabel: 'Closes today!',
      urgency: 'critical',
      colorClass: 'text-red-500',
      colorHex: '#EF4444',
      bgTint: 'rgba(239,68,68,0.12)',
    };
  }

  // Tomorrow
  if (diffDays === 1) {
    return {
      daysLeft: 1,
      hoursLeft: Math.floor(diffHours),
      label: 'Closes tomorrow',
      shortLabel: '1 day left',
      urgency: 'critical',
      colorClass: 'text-red-500',
      colorHex: '#EF4444',
      bgTint: 'rgba(239,68,68,0.12)',
    };
  }

  // 2–3 days — still critical
  if (diffDays <= 3) {
    return {
      daysLeft: diffDays,
      hoursLeft: Math.floor(diffHours),
      label: `${diffDays} days left`,
      shortLabel: `${diffDays}d left`,
      urgency: 'critical',
      colorClass: 'text-red-500',
      colorHex: '#EF4444',
      bgTint: 'rgba(239,68,68,0.12)',
    };
  }

  // 4–7 days — warning amber
  if (diffDays <= 7) {
    return {
      daysLeft: diffDays,
      hoursLeft: Math.floor(diffHours),
      label: `${diffDays} days left`,
      shortLabel: `${diffDays}d left`,
      urgency: 'warning',
      colorClass: 'text-amber-500',
      colorHex: '#F59E0B',
      bgTint: 'rgba(245,158,11,0.12)',
    };
  }

  // 8–14 days — still noteworthy
  if (diffDays <= 14) {
    return {
      daysLeft: diffDays,
      hoursLeft: Math.floor(diffHours),
      label: `${diffDays} days left`,
      shortLabel: `${diffDays}d left`,
      urgency: 'normal',
      colorClass: 'text-emerald-500',
      colorHex: '#10B981',
      bgTint: 'rgba(16,185,129,0.10)',
    };
  }

  // > 14 days — comfortable
  return {
    daysLeft: diffDays,
    hoursLeft: Math.floor(diffHours),
    label: `${diffDays} days left`,
    shortLabel: `${diffDays}d`,
    urgency: 'normal',
    colorClass: 'text-emerald-500',
    colorHex: '#10B981',
    bgTint: 'rgba(16,185,129,0.10)',
  };
}

/**
 * Count the number of active (non-default) filters for the "Filters (N)" badge.
 */
export function countActiveFilters(filters: {
  activeModule?: string;
  searchQuery: string;
  mode: string;
  region: string;
  eligibility: string;
  technology: string;
  offerType: string;
  verificationStatus: string;
  onlyClosingSoon: boolean;
  onlyBigPrizes: boolean;
  onlyFreeNoCard: boolean;
}): number {
  let count = 0;
  if (filters.searchQuery.trim()) count++;
  if (filters.region) count++;
  if (filters.technology) count++;
  if (filters.verificationStatus) count++;
  if (filters.activeModule === 'ai_deal') {
    if (filters.offerType) count++;
    if (filters.onlyFreeNoCard) count++;
  } else {
    if (filters.mode !== 'all') count++;
    if (filters.eligibility) count++;
    if (filters.onlyClosingSoon) count++;
    if (filters.onlyBigPrizes) count++;
  }
  return count;
}
