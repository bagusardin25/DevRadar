import React from 'react';
import { Trophy, Gift, ShieldCheck, Flame } from 'lucide-react';

interface StatsOverviewProps {
  totalPrizeValue: number;
  totalHackathons: number;
  totalDeals: number;
  unverifiedCount: number;
}

export const StatsOverview: React.FC<StatsOverviewProps> = ({
  totalPrizeValue,
  totalHackathons,
  totalDeals,
  unverifiedCount
}) => {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-6xl mx-auto px-4 lg:px-8 pt-6 font-sans">
      
      {/* Total Bounties Value */}
      <div className="sharetopus-card p-5 rounded-[24px] bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] relative overflow-hidden group hover:translate-y-[-2px] transition-all">
        <div className="flex items-center justify-between">
          <span className="text-xs font-mono font-extrabold text-[#1C1B18] dark:text-[#B8C4D2] uppercase tracking-wider">ACTIVE PRIZE POOL</span>
          <div className="p-2 rounded-full bg-[#059669]/15 text-[#059669] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
            <Trophy className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3 text-3xl font-extrabold text-[#1C1B18] dark:text-white font-mono tracking-tight flex items-baseline gap-1">
          <span className="text-[#059669]">${totalPrizeValue.toLocaleString()}</span>
          <span className="text-xs text-[#1C1B18] dark:text-[#B8C4D2] font-bold font-sans">USD</span>
        </div>
        <div className="mt-1 text-xs text-[#1C1B18] dark:text-[#B8C4D2] font-bold">
          <span className="text-[#059669] font-extrabold">100% Guaranteed</span> Bounties
        </div>
      </div>

      {/* Verified Hackathons */}
      <div className="sharetopus-card p-5 rounded-[24px] bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] relative overflow-hidden group hover:translate-y-[-2px] transition-all">
        <div className="flex items-center justify-between">
          <span className="text-xs font-mono font-extrabold text-[#1C1B18] dark:text-[#B8C4D2] uppercase tracking-wider">ONLINE HACKATHONS</span>
          <div className="p-2 rounded-full bg-[#FF5A36]/15 text-[#FF5A36] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
            <Flame className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3 text-3xl font-extrabold text-[#1C1B18] dark:text-white font-mono tracking-tight flex items-baseline gap-1">
          <span className="text-[#FF5A36]">{totalHackathons}</span>
          <span className="text-xs text-[#1C1B18] dark:text-[#B8C4D2] font-bold font-sans">Events</span>
        </div>
        <div className="mt-1 text-xs text-[#1C1B18] dark:text-[#B8C4D2] font-bold">
          <span className="text-[#FF5A36] font-extrabold">Tier 1/2</span> Checked Deadlines
        </div>
      </div>

      {/* Verified AI Deals */}
      <div className="sharetopus-card p-5 rounded-[24px] bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] relative overflow-hidden group hover:translate-y-[-2px] transition-all">
        <div className="flex items-center justify-between">
          <span className="text-xs font-mono font-extrabold text-[#1C1B18] dark:text-[#B8C4D2] uppercase tracking-wider">FREE AI CREDITS</span>
          <div className="p-2 rounded-full bg-[#7C3AED]/15 text-[#7C3AED] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
            <Gift className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3 text-3xl font-extrabold text-[#1C1B18] dark:text-white font-mono tracking-tight flex items-baseline gap-1">
          <span className="text-[#7C3AED]">{totalDeals}</span>
          <span className="text-xs text-[#1C1B18] dark:text-[#B8C4D2] font-bold font-sans">Offers</span>
        </div>
        <div className="mt-1 text-xs text-[#1C1B18] dark:text-[#B8C4D2] font-bold">
          Includes <span className="text-[#7C3AED] font-extrabold">Claude, Vercel, GitHub</span>
        </div>
      </div>

      {/* Verification Pipeline Status */}
      <div className="sharetopus-card p-5 rounded-[24px] bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] relative overflow-hidden group hover:translate-y-[-2px] transition-all">
        <div className="flex items-center justify-between">
          <span className="text-xs font-mono font-extrabold text-[#1C1B18] dark:text-[#B8C4D2] uppercase tracking-wider">PIPELINE HEALTH</span>
          <div className="p-2 rounded-full bg-[#0284C7]/15 text-[#0284C7] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
            <ShieldCheck className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3 text-3xl font-extrabold text-[#1C1B18] dark:text-white font-mono tracking-tight flex items-baseline gap-1">
          <span className="text-[#0284C7]">99.4%</span>
          <span className="text-xs text-[#1C1B18] dark:text-[#B8C4D2] font-bold font-sans">Accuracy</span>
        </div>
        <div className="mt-1 text-xs text-[#1C1B18] dark:text-[#B8C4D2] font-bold flex items-center justify-between">
          <span>Pending Signals:</span>
          <span className="text-[#D97706] font-extrabold">{unverifiedCount} Queue</span>
        </div>
      </div>

    </div>
  );
};
