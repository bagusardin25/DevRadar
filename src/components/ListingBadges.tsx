import React from 'react';
import type { FieldCompleteness, VerificationStatus } from '../types';
import {
  badgeToneClass,
  completenessBadges,
  statusBadge,
  type ListingBadge,
} from '../utils/listingBadges';

interface ListingBadgesProps {
  status: VerificationStatus;
  completeness?: FieldCompleteness | null;
  /** Extra badges (e.g. source tier). */
  extra?: ListingBadge[];
  className?: string;
}

export const ListingBadges: React.FC<ListingBadgesProps> = ({
  status,
  completeness,
  extra = [],
  className = '',
}) => {
  const badges: ListingBadge[] = [
    statusBadge(status),
    ...completenessBadges(completeness),
    ...extra,
  ];

  return (
    <div className={`flex items-center gap-1.5 flex-wrap ${className}`}>
      {badges.map((b) => (
        <span
          key={b.key}
          title={b.title}
          className={`px-2.5 py-1 rounded-full border text-[12px] font-extrabold tracking-wide ${badgeToneClass(b.tone)}`}
        >
          {b.label}
        </span>
      ))}
    </div>
  );
};
