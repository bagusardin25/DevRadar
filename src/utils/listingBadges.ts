import type { FieldCompleteness, VerificationStatus } from '../types';

export type BadgeTone = 'green' | 'amber' | 'red' | 'slate' | 'blue' | 'purple';

export interface ListingBadge {
  key: string;
  label: string;
  tone: BadgeTone;
  title?: string;
}

const TONE_CLASS: Record<BadgeTone, string> = {
  green:
    'bg-[#059669]/15 text-[#059669] dark:text-[#34D399] border-[#059669]',
  amber:
    'bg-[#D97706]/15 text-[#D97706] dark:text-[#FBBF24] border-[#D97706]',
  red: 'bg-[#DC2626]/15 text-[#DC2626] dark:text-[#F87171] border-[#DC2626]',
  slate:
    'bg-[#F3F4EF] dark:bg-[#1A2336] text-[#1C1B18] dark:text-[#F8FAF9] border-[#1C1B18] dark:border-[#D6DCE5]',
  blue: 'bg-[#0284C7]/15 text-[#0284C7] dark:text-[#38BDF8] border-[#0284C7]',
  purple:
    'bg-[#7C3AED]/15 text-[#7C3AED] dark:text-[#C4B5FD] border-[#7C3AED]',
};

export function badgeToneClass(tone: BadgeTone): string {
  return TONE_CLASS[tone];
}

export function statusBadge(status: VerificationStatus): ListingBadge {
  switch (status) {
    case 'verified_active':
      return { key: 'status', label: 'VERIFIED', tone: 'green' };
    case 'likely_active':
      return { key: 'status', label: 'LIKELY', tone: 'blue' };
    case 'registration_closed':
      return { key: 'status', label: 'REG CLOSED', tone: 'amber' };
    case 'expired':
      return { key: 'status', label: 'EXPIRED', tone: 'red' };
    case 'cancelled':
      return { key: 'status', label: 'CANCELLED', tone: 'red' };
    case 'needs_review':
    default:
      return { key: 'status', label: 'NEEDS REVIEW', tone: 'amber' };
  }
}

/** Trust / data-quality badges from completeness payload. */
export function completenessBadges(
  completeness?: FieldCompleteness | null,
): ListingBadge[] {
  if (!completeness) return [];
  const out: ListingBadge[] = [];
  const flags = new Set(completeness.flags || []);

  if (flags.has('closing_soon')) {
    out.push({
      key: 'closing',
      label: 'CLOSING SOON',
      tone: 'amber',
      title: 'Deadline within 14 days',
    });
  }
  if (flags.has('prize_tba')) {
    out.push({
      key: 'prize_tba',
      label: 'PRIZE TBA',
      tone: 'slate',
      title: 'Prize pool not fully confirmed',
    });
  }
  if (flags.has('weak_url')) {
    out.push({
      key: 'weak_url',
      label: 'WEAK URL',
      tone: 'amber',
      title: 'Primary link is social or a generic hub — verify on official site',
    });
  }
  if (flags.has('deadline_passed') || flags.has('expired')) {
    out.push({
      key: 'deadline',
      label: 'PAST DEADLINE',
      tone: 'red',
    });
  }
  if (flags.has('no_expiry')) {
    out.push({
      key: 'no_expiry',
      label: 'NO EXPIRY',
      tone: 'slate',
      title: 'Permanent free tier or expiry unknown',
    });
  }

  const score = completeness.score ?? 0;
  if (score > 0) {
    out.push({
      key: 'complete',
      label: `${score}% FIELDS`,
      tone: score >= 85 ? 'green' : score >= 60 ? 'blue' : 'amber',
      title:
        completeness.missing?.length
          ? `Missing: ${completeness.missing.join(', ')}`
          : 'Core fields present',
    });
  }

  return out;
}
