import React, { useState } from 'react';
import { 
  Search, 
  Globe, 
  Database, 
  Filter, 
  X, 
  RefreshCw,
  Flame,
  DollarSign,
  Clock,
  Bot,
  GraduationCap,
  Zap,
  CreditCard,
  Infinity as InfinityIcon,
  Brain
} from 'lucide-react';
import type { FilterState } from '../types';
import { countActiveFilters } from '../utils/countdown';

interface HeroSectionProps {
  filters: FilterState;
  setFilters: React.Dispatch<React.SetStateAction<FilterState>>;
  totalResults: number;
  onTriggerLiveDiscovery: () => void;
  isSearchingLive: boolean;
}

export const HeroSection: React.FC<HeroSectionProps> = ({
  filters,
  setFilters,
  totalResults,
  onTriggerLiveDiscovery,
  isSearchingLive
}) => {
  const [showFilters, setShowFilters] = useState(false);
  const activeFilterCount = countActiveFilters(filters);

  const presetChips = filters.activeModule === 'hackathon' ? [
    { label: 'All Hackathons', icon: Flame, apply: () => setFilters(f => ({ ...f, searchQuery: '', mode: 'all', verificationStatus: '' })) },
    { label: 'Online & Worldwide', icon: Globe, apply: () => setFilters(f => ({ ...f, mode: 'online', region: 'Worldwide' })) },
    { label: '$10k+ Prize Pool', icon: DollarSign, apply: () => setFilters(f => ({ ...f, onlyBigPrizes: true })) },
    { label: 'Closing < 14 Days', icon: Clock, apply: () => setFilters(f => ({ ...f, onlyClosingSoon: true })) },
    { label: 'AI & LLM Focus', icon: Bot, apply: () => setFilters(f => ({ ...f, technology: 'AI' })) },
    { label: 'Student Eligible', icon: GraduationCap, apply: () => setFilters(f => ({ ...f, eligibility: 'Student' })) }
  ] : [
    { label: 'All AI Deals', icon: Zap, apply: () => setFilters(f => ({ ...f, searchQuery: '', offerType: '', verificationStatus: '' })) },
    { label: 'No Credit Card / Free Credits', icon: CreditCard, apply: () => setFilters(f => ({ ...f, offerType: 'free_credits' })) },
    { label: 'Permanent Free Tier', icon: InfinityIcon, apply: () => setFilters(f => ({ ...f, offerType: 'free_tier' })) },
    { label: 'Student Packs', icon: GraduationCap, apply: () => setFilters(f => ({ ...f, offerType: 'student_program' })) },
    { label: 'Free Open Models / Price Drops', icon: Brain, apply: () => setFilters(f => ({ ...f, offerType: 'free_model' })) }
  ];

  return (
    <div className="relative py-10 md:py-14 px-4 md:px-8 max-w-6xl mx-auto text-center font-sans">
      
      <div className="space-y-6">
        
        {/* Top Eyebrow Badge */}
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-extrabold border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-[#F8FAF9] shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5]">
          <span className="size-2.5 rounded-full bg-[#FF5A36]"></span>
          <span>Provenance pipeline (Official sites → Extractor → Verifier)</span>
        </div>

        {/* Sharetopus Headline */}
        <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-[-0.04em] text-[#1C1B18] dark:text-white leading-[1.05]">
          Find bounties.<br />
          Win <span className="italic text-[#FF5A36]">everywhere.</span>
        </h1>

        {/* Issue 3 Fix: Subtitle Text - High Contrast Bold Black/White */}
        <p className="text-base sm:text-lg text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold max-w-2xl mx-auto leading-relaxed">
          The simplest way to discover hackathons, claim free AI credits, and track model price drops across every ecosystem — without subscription fees or API key requirements.
        </p>

        {/* Mode Selector (Indexed vs Live Web Discovery) */}
        <div className="flex items-center justify-center gap-3 pt-2">
          <div className="inline-flex items-center gap-2 p-1.5 rounded-full bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[3px_3px_0_0_#1C1B18] dark:shadow-[3px_3px_0_0_#D6DCE5] text-xs font-bold">
            <button
              onClick={() => setFilters(f => ({ ...f, searchExecutionMode: 'indexed' }))}
              className={`flex items-center gap-2 px-4 py-2 rounded-full transition-all ${
                filters.searchExecutionMode === 'indexed'
                  ? 'bg-[#1C1B18] text-white dark:bg-white dark:text-[#1C1B18] font-extrabold'
                  : 'text-[#1C1B18] dark:text-slate-200 hover:text-[#FF5A36]'
              }`}
            >
              <Database className="w-3.5 h-3.5" />
              <span>Indexed Search</span>
            </button>

            <button
              onClick={() => {
                setFilters(f => ({ ...f, searchExecutionMode: 'live_discovery' }));
                onTriggerLiveDiscovery();
              }}
              disabled={isSearchingLive}
              className={`flex items-center gap-2 px-4 py-2 rounded-full transition-all ${
                filters.searchExecutionMode === 'live_discovery'
                  ? 'bg-[#FF5A36] text-white font-extrabold'
                  : 'text-[#1C1B18] dark:text-slate-200 hover:text-[#FF5A36]'
              }`}
            >
              <Globe className={`w-3.5 h-3.5 ${isSearchingLive ? 'animate-spin' : ''}`} />
              <span>{isSearchingLive ? 'Scanning sources…' : 'Live Web Discovery'}</span>
            </button>
          </div>
        </div>

        {/* Main Search Command Bar */}
        <div className="relative max-w-3xl mx-auto">
          <div className="sharetopus-card p-3 rounded-[28px] bg-white dark:bg-[#131A29] flex flex-col sm:flex-row items-center gap-3 shadow-[6px_6px_0_0_#1C1B18] dark:shadow-[6px_6px_0_0_#D6DCE5]">
            <div className="relative flex-1 w-full">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[#1C1B18] dark:text-[#F8FAF9]" />
              <input
                type="text"
                value={filters.searchQuery}
                onChange={(e) => setFilters(f => ({ ...f, searchQuery: e.target.value }))}
                placeholder={
                  filters.activeModule === 'hackathon'
                    ? 'Search hackathons e.g., "online AI", "Next.js", "$10k USD"...'
                    : 'Search AI deals e.g., "free credits", "Claude 3.7", "Vercel"...'
                }
                className="w-full bg-transparent text-[#1C1B18] dark:text-white pl-12 pr-4 py-3 text-base outline-none font-extrabold placeholder:text-[#545454] dark:placeholder:text-slate-400"
              />
              {filters.searchQuery && (
                <button 
                  onClick={() => setFilters(f => ({ ...f, searchQuery: '' }))}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#1C1B18] hover:text-[#FF5A36]"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <button
                onClick={() => setShowFilters(!showFilters)}
                className={`flex-1 sm:flex-none flex items-center justify-center gap-2 px-5 py-3 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-xs font-extrabold transition-all ${
                  showFilters 
                    ? 'bg-[#1C1B18] text-white'
                    : 'bg-[#F3F4EF] dark:bg-[#1A2336] text-[#1C1B18] dark:text-white hover:bg-[#1C1B18] hover:text-white'
                }`}
              >
                <Filter className="w-4 h-4" />
                <span>Filters</span>
                {activeFilterCount > 0 && (
                  <span className="filter-counter">{activeFilterCount}</span>
                )}
              </button>

              {filters.searchExecutionMode === 'live_discovery' && (
                <button
                  onClick={onTriggerLiveDiscovery}
                  disabled={isSearchingLive}
                  className="btn-sharetopus-primary text-xs py-3 px-5 font-extrabold"
                >
                  <RefreshCw className={`w-4 h-4 ${isSearchingLive ? 'animate-spin' : ''}`} />
                  <span>Run discovery</span>
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Live Discovery Banner — describes only what the run actually does. */}
        {isSearchingLive && (
          <div className="sharetopus-card p-4 rounded-[20px] bg-[#FFF1EE] border-[#FF5A36] text-left max-w-3xl mx-auto space-y-2">
            <div className="flex items-center justify-between text-xs font-bold text-[#FF5A36]">
              <span className="flex items-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin" />
                Fetching configured sources…
              </span>
              <span className="font-mono font-bold">Results appear below when done</span>
            </div>
            <p className="text-xs text-[#1C1B18] dark:text-[#D6DCE5] font-mono font-bold">
              Seed URLs &amp; RSS feeds → Fetch → Parse → Extract → Verify
            </p>
          </div>
        )}

        {/* Presets / Filter Chips */}
        <div className="flex items-center justify-center gap-2 overflow-x-auto pt-2 pb-1 text-xs">
          <span className="text-[#1C1B18] dark:text-[#F8FAF9] font-mono font-extrabold uppercase text-[12px] whitespace-nowrap mr-1">Presets:</span>
          {presetChips.map((chip, idx) => {
            const ChipIcon = chip.icon;
            return (
              <button
                key={idx}
                onClick={chip.apply}
                className="flex items-center gap-1.5 px-4 py-2 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-white font-extrabold text-xs shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5] hover:bg-[#FF5A36] hover:text-white transition-all"
              >
                <ChipIcon className="w-3.5 h-3.5 text-[#FF5A36] group-hover:text-white" />
                <span>{chip.label}</span>
              </button>
            );
          })}
        </div>

        {/* Expanded Filters Drawer */}
        {showFilters && (
          <div className="sharetopus-card p-6 rounded-[24px] bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-left max-w-3xl mx-auto space-y-4 animate-in fade-in duration-200">
            <div className="flex items-center justify-between border-b border-[#D6D5CF] dark:border-slate-800 pb-3">
              <span className="font-extrabold text-sm text-[#1C1B18] dark:text-white">
                Advanced Filter Criteria
                {activeFilterCount > 0 && (
                  <span className="ml-2 filter-counter">{activeFilterCount}</span>
                )}
              </span>
              <button 
                onClick={() => setFilters(f => ({
                  ...f,
                  mode: 'all',
                  region: '',
                  eligibility: '',
                  technology: '',
                  offerType: '',
                  verificationStatus: '',
                  onlyClosingSoon: false,
                  onlyBigPrizes: false,
                  onlyFreeNoCard: false
                }))}
                className="text-xs text-[#FF5A36] font-extrabold hover:underline"
              >
                Reset Filters
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-xs font-sans">
              
              {filters.activeModule === 'hackathon' && (
                <div className="space-y-1.5">
                  <label className="text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold">Participation Mode</label>
                  <select
                    value={filters.mode}
                    onChange={(e) => setFilters(f => ({ ...f, mode: e.target.value as any }))}
                    className="w-full bg-[#F3F4EF] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white rounded-xl p-2.5 outline-none font-bold"
                  >
                    <option value="all">All Modes</option>
                    <option value="online">Online Only</option>
                    <option value="hybrid">Hybrid</option>
                    <option value="in_person">In-Person</option>
                  </select>
                </div>
              )}

              {filters.activeModule === 'ai_deal' && (
                <div className="space-y-1.5">
                  <label className="text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold">Offer Type</label>
                  <select
                    value={filters.offerType}
                    onChange={(e) => setFilters(f => ({ ...f, offerType: e.target.value }))}
                    className="w-full bg-[#F3F4EF] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white rounded-xl p-2.5 outline-none font-bold"
                  >
                    <option value="">All Offers</option>
                    <option value="free_credits">Free API Credits ($)</option>
                    <option value="free_tier">Permanent Free Tier</option>
                    <option value="student_program">Student Program</option>
                    <option value="free_model">Free AI Models</option>
                  </select>
                </div>
              )}

              <div className="space-y-1.5">
                <label className="text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold">Technology / Tag</label>
                <select
                  value={filters.technology}
                  onChange={(e) => setFilters(f => ({ ...f, technology: e.target.value }))}
                  className="w-full bg-[#F3F4EF] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white rounded-xl p-2.5 outline-none font-bold"
                >
                  <option value="">All Technologies</option>
                  <option value="AI">AI & LLM</option>
                  <option value="Next.js">Next.js & Web</option>
                  <option value="Python">Python & PyTorch</option>
                  <option value="Student">Student Developer</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold">Verification Status</label>
                <select
                  value={filters.verificationStatus}
                  onChange={(e) => setFilters(f => ({ ...f, verificationStatus: e.target.value }))}
                  className="w-full bg-[#F3F4EF] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white rounded-xl p-2.5 outline-none font-bold"
                >
                  <option value="">All Statuses</option>
                  <option value="verified_active">Verified Active (Tier 1/2)</option>
                  <option value="likely_active">Likely Active</option>
                  <option value="needs_review">Needs Review (Raw Signal)</option>
                </select>
              </div>

              <div className="flex flex-col justify-end space-y-2">
                <label className="flex items-center gap-2 cursor-pointer text-[#1C1B18] dark:text-[#F8FAF9] font-bold">
                  <input
                    type="checkbox"
                    checked={filters.onlyClosingSoon}
                    onChange={(e) => setFilters(f => ({ ...f, onlyClosingSoon: e.target.checked }))}
                    className="rounded accent-[#FF5A36]"
                  />
                  <span>Closing in &lt; 14 Days</span>
                </label>

                {filters.activeModule === 'hackathon' && (
                  <label className="flex items-center gap-2 cursor-pointer text-[#1C1B18] dark:text-[#F8FAF9] font-bold">
                    <input
                      type="checkbox"
                      checked={filters.onlyBigPrizes}
                      onChange={(e) => setFilters(f => ({ ...f, onlyBigPrizes: e.target.checked }))}
                      className="rounded accent-[#FF5A36]"
                    />
                    <span>$10,000+ Prize Pools</span>
                  </label>
                )}
              </div>

            </div>
          </div>
        )}

        {/* Issue 4 Fix: Showing __ verified opportunities - 100% Bold High Contrast Display */}
        <div className="flex items-center justify-between text-xs text-[#1C1B18] dark:text-[#F8FAF9] pt-2 font-mono max-w-3xl mx-auto font-extrabold">
          <div>
            Showing <strong className="text-[#FF5A36] dark:text-[#D6DCE5] text-sm font-extrabold mx-1">{totalResults}</strong> verified opportunities
            {activeFilterCount > 0 && (
              <span className="ml-1 text-[#FF5A36]">· {activeFilterCount} filter{activeFilterCount > 1 ? 's' : ''} active</span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-[#059669]" /> Tier 1 Verified</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-[#D97706]" /> Tier 3 X Signal</span>
          </div>
        </div>

      </div>
    </div>
  );
};
