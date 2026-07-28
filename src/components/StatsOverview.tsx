import React from 'react';
import { Trophy, Gift, Flame, ListChecks } from 'lucide-react';

interface StatsOverviewProps {
  totalPrizeValue: number;
  totalHackathons: number;
  totalDeals: number;
  unverifiedCount: number;
  /** Show review-queue count (operators only). */
  showQueueStat?: boolean;
}

export const StatsOverview: React.FC<StatsOverviewProps> = ({
  totalPrizeValue,
  totalHackathons,
  totalDeals,
  unverifiedCount,
  showQueueStat = false,
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
      <div className="sharetopus-card p-5 rounded-[24px] bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] relative overflow-hidden group hover:translate-y-[-2px] transition-all">
        <div className="flex items-center justify-between">
          <span className="text-xs font-mono font-extrabold text-[#1C1B18] dark:text-[#B8C4D2] uppercase tracking-wider">LISTED PRIZE SUM</span>
          <div className="p-2 rounded-full bg-[#059669]/15 text-[#059669] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
            <Trophy className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3 text-3xl font-extrabold text-[#1C1B18] dark:text-white font-mono tracking-tight flex items-baseline gap-1">
          <span className="text-[#059669]">${totalPrizeValue.toLocaleString()}</span>
          <span className="text-xs text-[#1C1B18] dark:text-[#B8C4D2] font-bold font-sans">USD*</span>
        </div>
        <div className="mt-1 text-xs text-[#1C1B18] dark:text-[#B8C4D2] font-bold">
          From loaded results · TBA prizes count as $0
        </div>
      </div>

      <div className="sharetopus-card p-5 rounded-[24px] bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] relative overflow-hidden group hover:translate-y-[-2px] transition-all">
        <div className="flex items-center justify-between">
          <span className="text-xs font-mono font-extrabold text-[#1C1B18] dark:text-[#B8C4D2] uppercase tracking-wider">HACKATHONS</span>
          <div className="p-2 rounded-full bg-[#FF5A36]/15 text-[#FF5A36] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
            <Flame className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3 text-3xl font-extrabold text-[#1C1B18] dark:text-white font-mono tracking-tight flex items-baseline gap-1">
          <span className="text-[#FF5A36]">{totalHackathons}</span>
          <span className="text-xs text-[#1C1B18] dark:text-[#B8C4D2] font-bold font-sans">listed</span>
        </div>
        <div className="mt-1 text-xs text-[#1C1B18] dark:text-[#B8C4D2] font-bold">
          Status varies · check each card
        </div>
      </div>

      <div className="sharetopus-card p-5 rounded-[24px] bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] relative overflow-hidden group hover:translate-y-[-2px] transition-all">
        <div className="flex items-center justify-between">
          <span className="text-xs font-mono font-extrabold text-[#1C1B18] dark:text-[#B8C4D2] uppercase tracking-wider">AI OFFERS</span>
          <div className="p-2 rounded-full bg-[#7C3AED]/15 text-[#7C3AED] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
            <Gift className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3 text-3xl font-extrabold text-[#1C1B18] dark:text-white font-mono tracking-tight flex items-baseline gap-1">
          <span className="text-[#7C3AED]">{totalDeals}</span>
          <span className="text-xs text-[#1C1B18] dark:text-[#B8C4D2] font-bold font-sans">listed</span>
        </div>
        <div className="mt-1 text-xs text-[#1C1B18] dark:text-[#B8C4D2] font-bold">
          Free tiers, credits, promos
        </div>
      </div>

      {showQueueStat && (
        <div className="sharetopus-card p-5 rounded-[24px] bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] relative overflow-hidden group hover:translate-y-[-2px] transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-extrabold text-[#1C1B18] dark:text-[#B8C4D2] uppercase tracking-wider">REVIEW QUEUE</span>
            <div className="p-2 rounded-full bg-[#0284C7]/15 text-[#0284C7] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
              <ListChecks className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 text-3xl font-extrabold text-[#1C1B18] dark:text-white font-mono tracking-tight flex items-baseline gap-1">
            <span className="text-[#0284C7]">{unverifiedCount}</span>
            <span className="text-xs text-[#1C1B18] dark:text-[#B8C4D2] font-bold font-sans">open</span>
          </div>
          <div className="mt-1 text-xs text-[#1C1B18] dark:text-[#B8C4D2] font-bold">
            Operator review items
          </div>
        </div>
      )}

    </section>
  );
};
