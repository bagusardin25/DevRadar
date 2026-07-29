import React from 'react';
import { Trophy, Gift, Flame, ListChecks } from 'lucide-react';

interface StatsOverviewProps {
  totalPrizeValue: number;
  totalHackathons: number;
  totalDeals: number;
  unverifiedCount: number;
  /** Show review-queue count (operators only). */
  showQueueStat?: boolean;
  /** Render skeleton bars in place of numbers while the catalogue is loading. */
  loading?: boolean;
}

// Card container shared style — keeps layout stable when swapping in skeletons.
const CARD =
  'sharetopus-card p-5 rounded-[24px] bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] relative overflow-hidden group hover:translate-y-[-2px] transition-all';
const LABEL =
  'text-xs font-mono font-extrabold text-[#1C1B18] dark:text-[#B8C4D2] uppercase tracking-wider';
const SUFFIX = 'text-xs text-[#1C1B18] dark:text-[#B8C4D2] font-bold font-sans';
const SUBLINE = 'mt-1 text-xs text-[#1C1B18] dark:text-[#B8C4D2] font-bold';
const NUMBER_ROW =
  'mt-3 text-3xl font-extrabold text-[#1C1B18] dark:text-white font-mono tracking-tight flex items-baseline gap-1';

/**
 * Skeleton bar sized to roughly match the rendered number so the card doesn't
 * jump when the real value arrives. Colored at low opacity of the card's
 * accent so each card still reads as itself while loading.
 */
const Skeleton: React.FC<{ accent: string; width: string }> = ({ accent, width }) => (
  <span
    aria-hidden="true"
    className={`inline-block h-8 rounded-md animate-pulse ${accent} ${width}`}
  />
);

export const StatsOverview: React.FC<StatsOverviewProps> = ({
  totalPrizeValue,
  totalHackathons,
  totalDeals,
  unverifiedCount,
  showQueueStat = false,
  loading = false,
}) => {
  const cols = showQueueStat
    ? 'grid-cols-2 md:grid-cols-4'
    : 'grid-cols-1 sm:grid-cols-3';

  return (
    <section
      aria-label="Catalogue summary"
      className={`hidden sm:grid ${cols} gap-4 max-w-6xl mx-auto px-4 lg:px-8 pt-6 font-sans`}
    >
      {/* Sum of known prize pools on the current result set (not a guarantee) */}
      <div className={CARD} aria-busy={loading}>
        <div className="flex items-center justify-between">
          <span className={LABEL}>LISTED PRIZE SUM</span>
          <div className="p-2 rounded-full bg-[#059669]/15 text-[#059669] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
            <Trophy className="w-4 h-4" />
          </div>
        </div>
        <div className={NUMBER_ROW}>
          {loading ? (
            <Skeleton accent="bg-[#059669]/25 dark:bg-[#059669]/35" width="w-32" />
          ) : (
            <span className="text-[#059669]">${totalPrizeValue.toLocaleString()}</span>
          )}
          <span className={SUFFIX}>USD*</span>
        </div>
        <div className={SUBLINE}>
          From current results · TBA prizes count as $0
        </div>
      </div>

      <div className={CARD} aria-busy={loading}>
        <div className="flex items-center justify-between">
          <span className={LABEL}>HACKATHONS</span>
          <div className="p-2 rounded-full bg-[#FF5A36]/15 text-[#FF5A36] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
            <Flame className="w-4 h-4" />
          </div>
        </div>
        <div className={NUMBER_ROW}>
          {loading ? (
            <Skeleton accent="bg-[#FF5A36]/25 dark:bg-[#FF5A36]/35" width="w-14" />
          ) : (
            <span className="text-[#FF5A36]">{totalHackathons}</span>
          )}
          <span className={SUFFIX}>listed</span>
        </div>
        <div className={SUBLINE}>
          Status varies · check each card
        </div>
      </div>

      <div className={CARD} aria-busy={loading}>
        <div className="flex items-center justify-between">
          <span className={LABEL}>AI OFFERS</span>
          <div className="p-2 rounded-full bg-[#7C3AED]/15 text-[#7C3AED] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
            <Gift className="w-4 h-4" />
          </div>
        </div>
        <div className={NUMBER_ROW}>
          {loading ? (
            <Skeleton accent="bg-[#7C3AED]/25 dark:bg-[#7C3AED]/35" width="w-14" />
          ) : (
            <span className="text-[#7C3AED]">{totalDeals}</span>
          )}
          <span className={SUFFIX}>listed</span>
        </div>
        <div className={SUBLINE}>
          Free tiers, credits, promos
        </div>
      </div>

      {showQueueStat && (
        <div className={CARD} aria-busy={loading}>
          <div className="flex items-center justify-between">
            <span className={LABEL}>REVIEW QUEUE</span>
            <div className="p-2 rounded-full bg-[#0284C7]/15 text-[#0284C7] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
              <ListChecks className="w-4 h-4" />
            </div>
          </div>
          <div className={NUMBER_ROW}>
            {loading ? (
              <Skeleton accent="bg-[#0284C7]/25 dark:bg-[#0284C7]/35" width="w-12" />
            ) : (
              <span className="text-[#0284C7]">{unverifiedCount}</span>
            )}
            <span className={SUFFIX}>open</span>
          </div>
          <div className={SUBLINE}>
            Operator review items
          </div>
        </div>
      )}

    </section>
  );
};
