import React, { useState } from 'react';
import {
  Search,
  Globe,
  Database,
  Filter,
  X,
  RefreshCw,
  RotateCcw,
  DollarSign,
  Clock,
  Bot,
  GraduationCap,
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
  /**
   * How many of the results carry `verified_active`. Omit when the loaded page
   * does not cover `totalResults`, so the count is never shown against a
   * denominator it was not measured over.
   */
  verifiedCount?: number;
  onTriggerLiveDiscovery: () => void;
  isSearchingLive: boolean;
}

export const HeroSection: React.FC<HeroSectionProps> = ({
  filters,
  setFilters,
  totalResults,
  verifiedCount,
  onTriggerLiveDiscovery,
  isSearchingLive
}) => {
  const [showFilters, setShowFilters] = useState(false);
  const activeFilterCount = countActiveFilters(filters);

  // Preset chips carry `isActive` so users see which filter is applied, and a
  // single `toggle` that inverts the state — clicking an active chip removes
  // its filter instead of re-applying a no-op.
  const presetChips = filters.activeModule === 'hackathon' ? [
    {
      label: 'Online & Worldwide',
      icon: Globe,
      isActive: filters.mode === 'online' && filters.region === 'Worldwide',
      toggle: () => setFilters(f =>
        f.mode === 'online' && f.region === 'Worldwide'
          ? { ...f, mode: 'all', region: '' }
          : { ...f, mode: 'online', region: 'Worldwide' }
      ),
    },
    {
      label: '$10k+ Prize Pool',
      icon: DollarSign,
      isActive: filters.onlyBigPrizes,
      toggle: () => setFilters(f => ({ ...f, onlyBigPrizes: !f.onlyBigPrizes })),
    },
    {
      label: 'Closing < 14 Days',
      icon: Clock,
      isActive: filters.onlyClosingSoon,
      toggle: () => setFilters(f => ({ ...f, onlyClosingSoon: !f.onlyClosingSoon })),
    },
    {
      label: 'AI & LLM Focus',
      icon: Bot,
      isActive: filters.technology === 'AI',
      toggle: () => setFilters(f => ({ ...f, technology: f.technology === 'AI' ? '' : 'AI' })),
    },
    {
      label: 'Student Eligible',
      icon: GraduationCap,
      isActive: filters.eligibility === 'Student',
      toggle: () => setFilters(f => ({ ...f, eligibility: f.eligibility === 'Student' ? '' : 'Student' })),
    },
  ] : [
    {
      label: 'No Credit Card / Free Credits',
      icon: CreditCard,
      isActive: filters.offerType === 'free_credits',
      toggle: () => setFilters(f => ({ ...f, offerType: f.offerType === 'free_credits' ? '' : 'free_credits' })),
    },
    {
      label: 'Permanent Free Tier',
      icon: InfinityIcon,
      isActive: filters.offerType === 'free_tier',
      toggle: () => setFilters(f => ({ ...f, offerType: f.offerType === 'free_tier' ? '' : 'free_tier' })),
    },
    {
      label: 'Student Packs',
      icon: GraduationCap,
      isActive: filters.offerType === 'student_program',
      toggle: () => setFilters(f => ({ ...f, offerType: f.offerType === 'student_program' ? '' : 'student_program' })),
    },
    {
      label: 'Free Open Models / Price Drops',
      icon: Brain,
      isActive: filters.offerType === 'free_model',
      toggle: () => setFilters(f => ({ ...f, offerType: f.offerType === 'free_model' ? '' : 'free_model' })),
    },
  ];

  const clearAll = () => setFilters(f => ({
    ...f,
    searchQuery: '',
    mode: 'all',
    region: '',
    eligibility: '',
    technology: '',
    offerType: '',
    verificationStatus: '',
    onlyClosingSoon: false,
    onlyBigPrizes: false,
    onlyFreeNoCard: false,
  }));
  const hasAnyFilter = activeFilterCount > 0 || filters.searchQuery.trim().length > 0;

  return (
    <div className="relative py-6 md:py-10 px-4 md:px-8 max-w-6xl mx-auto text-center font-sans">

      <div className="space-y-5">

        {/* Top Eyebrow Badge — benefit language, not internal pipeline jargon */}
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-extrabold border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-[#F8FAF9] shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5]">
          <span className="size-2.5 rounded-full bg-[#059669]"></span>
          <span>Every listing verified from its official source</span>
        </div>

        {/* Sharetopus Headline */}
        <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-[-0.04em] text-[#1C1B18] dark:text-white leading-[1.05]">
          Find bounties.<br />
          Win <span className="italic text-[#D23B14] dark:text-[#FF5A36]">everywhere.</span>
        </h1>

        {/* Subtitle — single line, benefit-forward */}
        <p className="text-base sm:text-lg text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold max-w-2xl mx-auto leading-relaxed">
          Hackathons, free AI credits, and model price drops. No login, no fees, no API keys.
        </p>

        {/* Mode selector — the pill toggles WHERE we search (catalogue vs live),
            NOT whether we run. The actual live scan is one explicit button in the
            search bar so users don't accidentally burn their 5/hr rate limit. */}
        <div className="flex flex-col items-center gap-2 pt-2">
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
              <span>Catalogue</span>
            </button>

            <button
              onClick={() => setFilters(f => ({ ...f, searchExecutionMode: 'live_discovery' }))}
              className={`flex items-center gap-2 px-4 py-2 rounded-full transition-all ${
                filters.searchExecutionMode === 'live_discovery'
                  ? 'bg-[#D23B14] text-white font-extrabold'
                  : 'text-[#1C1B18] dark:text-slate-200 hover:text-[#C2410C] dark:hover:text-[#FF8A6B]'
              }`}
            >
              <Globe className="w-3.5 h-3.5" />
              <span>Live scan</span>
            </button>
          </div>
          {filters.searchExecutionMode === 'live_discovery' && !isSearchingLive && (
            <p className="text-[11px] font-mono text-slate-500 dark:text-slate-400">
              Live scan takes ~30s · limited to 5 attempts per hour.
            </p>
          )}
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
                    ? 'Search hackathons: online AI, Next.js, $10k prize…'
                    : 'Search AI deals: free credits, Claude, Vercel…'
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
                  title="Scans configured sources live. Takes ~30 seconds. Uses 1 of your 5 hourly attempts."
                  className="btn-sharetopus-primary text-xs py-3 px-5 font-extrabold"
                >
                  <RefreshCw className={`w-4 h-4 ${isSearchingLive ? 'animate-spin' : ''}`} />
                  <span>{isSearchingLive ? 'Scanning…' : 'Scan now'}</span>
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Presets / Filter Chips — additive presets first, then a distinct
            secondary "Clear all" chip that only appears when there is anything
            to clear (avoids offering a no-op when the state is already clean). */}
        <div className="flex items-center justify-center gap-2 overflow-x-auto pt-2 pb-1 text-xs">
          <span className="text-[#1C1B18] dark:text-[#F8FAF9] font-mono font-extrabold uppercase text-[12px] whitespace-nowrap mr-1">Presets:</span>
          {presetChips.map((chip, idx) => {
            const ChipIcon = chip.icon;
            const { isActive } = chip;
            return (
              <button
                key={idx}
                type="button"
                onClick={chip.toggle}
                aria-pressed={isActive}
                title={isActive ? `Remove "${chip.label}" filter` : `Apply "${chip.label}" filter`}
                className={`flex items-center gap-1.5 px-4 py-2 rounded-full border-[1.5px] font-extrabold text-xs shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5] transition-all ${
                  isActive
                    ? 'bg-[#D23B14] text-white border-[#D23B14]'
                    : 'bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-white border-[#1C1B18] dark:border-[#D6DCE5] hover:bg-[#D23B14] hover:text-white hover:border-[#D23B14]'
                }`}
              >
                <ChipIcon className={`w-3.5 h-3.5 ${isActive ? 'text-white' : 'text-[#FF5A36]'}`} />
                <span>{chip.label}</span>
                {isActive && <X className="w-3 h-3 opacity-80" />}
              </button>
            );
          })}
          {hasAnyFilter && (
            <button
              type="button"
              onClick={clearAll}
              title="Reset search and all active filters"
              className="flex items-center gap-1.5 px-3 py-2 rounded-full border-[1.5px] border-dashed border-[#1C1B18]/40 dark:border-white/30 bg-transparent text-[#1C1B18]/70 dark:text-white/70 font-bold text-xs hover:border-solid hover:border-[#FF5A36] hover:text-[#FF5A36] transition-all"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Clear</span>
            </button>
          )}
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

        {/* Result summary bar — a distinct strip so users read this as a
            transition into the results grid rather than a caption of the
            preset chips above. "verified" is reported as its own count instead
            of applied to the whole set: most listings sit at likely_active, so
            calling every result verified overstates what the pipeline knows. */}
        <div className="mt-3 flex items-center justify-between gap-3 flex-wrap max-w-3xl mx-auto px-4 py-2.5 rounded-2xl border-[1.5px] border-[#1C1B18]/15 dark:border-white/15 bg-white/70 dark:bg-[#131A29]/70 text-xs font-mono text-[#1C1B18] dark:text-[#F8FAF9] font-medium">
          <div>
            {/* Explicit {' '} — JSX drops the whitespace around expressions on
                their own line, which would read as "22opportunities" to a
                screen reader and to anyone copying the text. */}
            Showing{' '}
            <strong className="text-[#C2410C] dark:text-[#D6DCE5] text-sm font-extrabold">{totalResults}</strong>{' '}
            {totalResults === 1 ? 'opportunity' : 'opportunities'}
            {verifiedCount != null && (
              <span className="text-[#047857] dark:text-[#34D399]">
                {' · '}
                <strong className="font-extrabold">{verifiedCount}</strong> verified
              </span>
            )}
            {activeFilterCount > 0 && (
              <span className="text-[#C2410C] dark:text-[#FF8A6B]">
                {' · '}
                {activeFilterCount} filter{activeFilterCount > 1 ? 's' : ''} active
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-[#059669]" /> Verified from source</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-[#D97706]" /> Community-reported</span>
          </div>
        </div>

      </div>
    </div>
  );
};
