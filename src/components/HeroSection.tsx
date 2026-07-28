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
import type { FilterMeta } from '../api';
import { countActiveFilters } from '../utils/countdown';

const FALLBACK_FILTERS: FilterMeta = {
  technologies: ['AI', 'Next.js', 'Python', 'Student'],
  regions: ['Worldwide', 'Asia', 'Europe', 'North America'],
  eligibilityLabels: ['Student', 'Open to all', 'Professional'],
  offerTypes: ['free_credits', 'free_tier', 'student_program', 'free_model'],
  modes: ['online', 'hybrid', 'in_person'],
  verificationStatuses: ['verified_active', 'likely_active', 'needs_review'],
};

const LABELS: Record<string, string> = {
  online: 'Online only',
  hybrid: 'Hybrid',
  in_person: 'In-person',
  free_credits: 'Free API credits',
  free_tier: 'Permanent free tier',
  trial: 'Free trial',
  student_program: 'Student program',
  open_source_program: 'Open-source program',
  hackathon_credits: 'Hackathon credits',
  promo_code: 'Promo code',
  free_model: 'Free AI models',
  self_hosted_weights: 'Self-hosted weights',
  verified_active: 'Verified active',
  likely_active: 'Likely active',
  needs_review: 'Needs review',
};

function optionLabel(value: string): string {
  return LABELS[value] ?? value.replaceAll('_', ' ');
}

function availableOptions(values: string[] | undefined, fallback: string[], selected = ''): string[] {
  const options = values?.length ? values : fallback;
  return [...new Set(selected ? [selected, ...options] : options)];
}

interface HeroSectionProps {
  filters: FilterState;
  setFilters: React.Dispatch<React.SetStateAction<FilterState>>;
  filterMeta?: FilterMeta | null;
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
  filterMeta,
  totalResults,
  verifiedCount,
  onTriggerLiveDiscovery,
  isSearchingLive
}) => {
  const [showFilters, setShowFilters] = useState(false);
  const activeFilterCount = countActiveFilters(filters);
  const modes = availableOptions(filterMeta?.modes, FALLBACK_FILTERS.modes, filters.mode === 'all' ? '' : filters.mode);
  const regions = availableOptions(filterMeta?.regions, FALLBACK_FILTERS.regions, filters.region);
  const eligibilityLabels = availableOptions(
    filterMeta?.eligibilityLabels,
    FALLBACK_FILTERS.eligibilityLabels,
    filters.eligibility,
  );
  const technologies = availableOptions(
    filterMeta?.technologies,
    FALLBACK_FILTERS.technologies,
    filters.technology,
  );
  const offerTypes = availableOptions(
    filterMeta?.offerTypes,
    FALLBACK_FILTERS.offerTypes,
    filters.offerType,
  );
  const verificationStatuses = availableOptions(
    filterMeta?.verificationStatuses,
    FALLBACK_FILTERS.verificationStatuses,
    filters.verificationStatus,
  );

  const presetChips = filters.activeModule === 'hackathon' ? [
    { label: 'All Hackathons', icon: Flame, apply: () => setFilters(f => ({ ...f, searchQuery: '', mode: 'all', region: '', eligibility: '', technology: '', verificationStatus: '', onlyClosingSoon: false, onlyBigPrizes: false })) },
    { label: 'Online & Worldwide', icon: Globe, apply: () => setFilters(f => ({ ...f, mode: 'online', region: 'Worldwide' })) },
    { label: '$10k+ Prize Pool', icon: DollarSign, apply: () => setFilters(f => ({ ...f, onlyBigPrizes: true })) },
    { label: 'Closing < 14 Days', icon: Clock, apply: () => setFilters(f => ({ ...f, onlyClosingSoon: true })) },
    { label: 'AI & LLM Focus', icon: Bot, apply: () => setFilters(f => ({ ...f, technology: 'AI' })) },
    { label: 'Student Eligible', icon: GraduationCap, apply: () => setFilters(f => ({ ...f, eligibility: 'Student' })) }
  ] : [
    { label: 'All AI Deals', icon: Zap, apply: () => setFilters(f => ({ ...f, searchQuery: '', region: '', technology: '', offerType: '', verificationStatus: '', onlyFreeNoCard: false })) },
    { label: 'Free Credits · No Card', icon: CreditCard, apply: () => setFilters(f => ({ ...f, offerType: 'free_credits', onlyFreeNoCard: true })) },
    { label: 'Permanent Free Tier', icon: InfinityIcon, apply: () => setFilters(f => ({ ...f, offerType: 'free_tier' })) },
    { label: 'Student Packs', icon: GraduationCap, apply: () => setFilters(f => ({ ...f, offerType: 'student_program' })) },
    { label: 'Free Open Models / Price Drops', icon: Brain, apply: () => setFilters(f => ({ ...f, offerType: 'free_model' })) }
  ];

  return (
    <section
      aria-labelledby="catalogue-heading"
      className="relative py-6 sm:py-10 md:py-14 px-4 md:px-8 max-w-6xl mx-auto text-center font-sans"
    >
      
      <div className="space-y-4 sm:space-y-6">
        
        {/* Top Eyebrow Badge */}
        <div className="hidden sm:inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-extrabold border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-[#F8FAF9] shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5]">
          <span className="size-2.5 rounded-full bg-[#FF5A36]"></span>
          <span>Provenance pipeline (Official sites → Extractor → Verifier)</span>
        </div>

        {/* Sharetopus Headline */}
        <h1 id="catalogue-heading" className="text-3xl sm:text-5xl md:text-6xl font-extrabold tracking-[-0.04em] text-[#1C1B18] dark:text-white leading-[1.05]">
          Find bounties.<br />
          Win <span className="italic text-[#D23B14] dark:text-[#FF5A36]">everywhere.</span>
        </h1>

        {/* Issue 3 Fix: Subtitle Text - High Contrast Bold Black/White */}
        <p className="text-sm sm:text-lg text-[#1C1B18] dark:text-[#F8FAF9] font-bold sm:font-extrabold max-w-2xl mx-auto leading-relaxed">
          The simplest way to discover hackathons, claim free AI credits, and track model price drops across every ecosystem — without subscription fees or API key requirements.
        </p>

        {/* Mode selector: query the existing catalogue vs scan registered sources now */}
        <div className="flex items-center justify-center gap-3 pt-2">
          <div className="inline-flex items-center gap-2 p-1.5 rounded-full bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[3px_3px_0_0_#1C1B18] dark:shadow-[3px_3px_0_0_#D6DCE5] text-xs font-bold">
            <button
              type="button"
              onClick={() => setFilters(f => ({ ...f, searchExecutionMode: 'indexed' }))}
              aria-pressed={filters.searchExecutionMode === 'indexed'}
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
              type="button"
              onClick={() => {
                setFilters(f => ({ ...f, searchExecutionMode: 'live_discovery' }));
                onTriggerLiveDiscovery();
              }}
              disabled={isSearchingLive}
              aria-pressed={filters.searchExecutionMode === 'live_discovery'}
              className={`flex items-center gap-2 px-4 py-2 rounded-full transition-all ${
                filters.searchExecutionMode === 'live_discovery'
                  ? 'bg-[#D23B14] text-white font-extrabold'
                  : 'text-[#1C1B18] dark:text-slate-200 hover:text-[#C2410C] dark:hover:text-[#FF8A6B]'
              }`}
            >
              <Globe className={`w-3.5 h-3.5 ${isSearchingLive ? 'animate-spin' : ''}`} />
              <span>{isSearchingLive ? 'Scanning sources…' : 'Scan sources'}</span>
            </button>
          </div>
        </div>

        {/* Main Search Command Bar */}
        <div className="relative max-w-3xl mx-auto">
          <div className="sharetopus-card p-3 rounded-[28px] bg-white dark:bg-[#131A29] flex flex-col sm:flex-row items-center gap-3 shadow-[6px_6px_0_0_#1C1B18] dark:shadow-[6px_6px_0_0_#D6DCE5]">
            <div className="relative flex-1 w-full">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[#1C1B18] dark:text-[#F8FAF9]" />
              <label htmlFor="catalogue-search" className="sr-only">Search opportunities</label>
              <input
                id="catalogue-search"
                type="search"
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
                  type="button"
                  aria-label="Clear search"
                  onClick={() => setFilters(f => ({ ...f, searchQuery: '' }))}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#1C1B18] hover:text-[#FF5A36]"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <button
                type="button"
                onClick={() => setShowFilters(!showFilters)}
                aria-expanded={showFilters}
                aria-controls="advanced-filter-panel"
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
                  type="button"
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
          <div className="sharetopus-card p-4 rounded-[20px] bg-[#FFF1EE] dark:bg-[#2A1715] border-[#FF5A36] text-left max-w-3xl mx-auto space-y-2">
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
        <div className="no-scrollbar flex items-center justify-start sm:justify-center gap-2 overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0 pt-2 pb-2 text-xs snap-x">
          <span className="hidden sm:inline text-[#1C1B18] dark:text-[#F8FAF9] font-mono font-extrabold uppercase text-[12px] whitespace-nowrap mr-1">Presets:</span>
          {presetChips.map((chip, idx) => {
            const ChipIcon = chip.icon;
            return (
              <button
                type="button"
                key={idx}
                onClick={chip.apply}
                className="snap-start shrink-0 flex items-center gap-1.5 px-4 py-2 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-white font-extrabold text-xs shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5] hover:bg-[#D23B14] hover:text-white transition-all"
              >
                <ChipIcon className="w-3.5 h-3.5 text-[#FF5A36] group-hover:text-white" />
                <span>{chip.label}</span>
              </button>
            );
          })}
        </div>

        {/* Expanded Filters Drawer */}
        {showFilters && (
          <div id="advanced-filter-panel" className="sharetopus-card p-4 sm:p-6 rounded-[24px] bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-left max-w-3xl mx-auto space-y-4 animate-in fade-in duration-200">
            <div className="flex items-center justify-between border-b border-[#D6D5CF] dark:border-slate-800 pb-3">
              <span className="font-extrabold text-sm text-[#1C1B18] dark:text-white">
                Advanced Filter Criteria
                {activeFilterCount > 0 && (
                  <span className="ml-2 filter-counter">{activeFilterCount}</span>
                )}
              </span>
              <button 
                type="button"
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

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-xs font-sans">
              
              {filters.activeModule === 'hackathon' && (
                <div className="space-y-1.5">
                  <label htmlFor="filter-mode" className="text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold">Participation Mode</label>
                  <select
                    id="filter-mode"
                    value={filters.mode}
                    onChange={(e) =>
                      setFilters(f => ({ ...f, mode: e.target.value as FilterState['mode'] }))
                    }
                    className="w-full bg-[#F3F4EF] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white rounded-xl p-2.5 outline-none font-bold"
                  >
                    <option value="all">All Modes</option>
                    {modes.map((mode) => (
                      <option key={mode} value={mode}>{optionLabel(mode)}</option>
                    ))}
                  </select>
                </div>
              )}

              {filters.activeModule === 'ai_deal' && (
                <div className="space-y-1.5">
                  <label htmlFor="filter-offer-type" className="text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold">Offer Type</label>
                  <select
                    id="filter-offer-type"
                    value={filters.offerType}
                    onChange={(e) => setFilters(f => ({ ...f, offerType: e.target.value }))}
                    className="w-full bg-[#F3F4EF] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white rounded-xl p-2.5 outline-none font-bold"
                  >
                    <option value="">All Offers</option>
                    {offerTypes.map((offerType) => (
                      <option key={offerType} value={offerType}>{optionLabel(offerType)}</option>
                    ))}
                  </select>
                </div>
              )}

              <div className="space-y-1.5">
                <label htmlFor="filter-region" className="text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold">Region</label>
                <select
                  id="filter-region"
                  value={filters.region}
                  onChange={(e) => setFilters(f => ({ ...f, region: e.target.value }))}
                  className="w-full bg-[#F3F4EF] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white rounded-xl p-2.5 outline-none font-bold"
                >
                  <option value="">All Regions</option>
                  {regions.map((region) => (
                    <option key={region} value={region}>{region}</option>
                  ))}
                </select>
              </div>

              {filters.activeModule === 'hackathon' && (
                <div className="space-y-1.5">
                  <label htmlFor="filter-eligibility" className="text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold">Eligibility</label>
                  <select
                    id="filter-eligibility"
                    value={filters.eligibility}
                    onChange={(e) => setFilters(f => ({ ...f, eligibility: e.target.value }))}
                    className="w-full bg-[#F3F4EF] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white rounded-xl p-2.5 outline-none font-bold"
                  >
                    <option value="">All Eligibility</option>
                    {eligibilityLabels.map((label) => (
                      <option key={label} value={label}>{label}</option>
                    ))}
                  </select>
                </div>
              )}

              <div className="space-y-1.5">
                <label htmlFor="filter-technology" className="text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold">Technology / Tag</label>
                <select
                  id="filter-technology"
                  value={filters.technology}
                  onChange={(e) => setFilters(f => ({ ...f, technology: e.target.value }))}
                  className="w-full bg-[#F3F4EF] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white rounded-xl p-2.5 outline-none font-bold"
                >
                  <option value="">All Technologies</option>
                  {technologies.map((technology) => (
                    <option key={technology} value={technology}>{technology}</option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="filter-verification" className="text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold">Verification Status</label>
                <select
                  id="filter-verification"
                  value={filters.verificationStatus}
                  onChange={(e) => setFilters(f => ({ ...f, verificationStatus: e.target.value }))}
                  className="w-full bg-[#F3F4EF] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white rounded-xl p-2.5 outline-none font-bold"
                >
                  <option value="">All Statuses</option>
                  {verificationStatuses.map((status) => (
                    <option key={status} value={status}>{optionLabel(status)}</option>
                  ))}
                </select>
              </div>

              <div className="flex flex-col justify-end space-y-2">
                {filters.activeModule === 'hackathon' ? (
                  <>
                    <label className="flex items-center gap-2 cursor-pointer text-[#1C1B18] dark:text-[#F8FAF9] font-bold">
                      <input
                        type="checkbox"
                        checked={filters.onlyClosingSoon}
                        onChange={(e) => setFilters(f => ({ ...f, onlyClosingSoon: e.target.checked }))}
                        className="rounded accent-[#FF5A36]"
                      />
                      <span>Closing in &lt; 14 Days</span>
                    </label>
                  <label className="flex items-center gap-2 cursor-pointer text-[#1C1B18] dark:text-[#F8FAF9] font-bold">
                    <input
                      type="checkbox"
                      checked={filters.onlyBigPrizes}
                      onChange={(e) => setFilters(f => ({ ...f, onlyBigPrizes: e.target.checked }))}
                      className="rounded accent-[#FF5A36]"
                    />
                    <span>$10,000+ Prize Pools</span>
                  </label>
                  </>
                ) : (
                  <label className="flex items-center gap-2 cursor-pointer text-[#1C1B18] dark:text-[#F8FAF9] font-bold">
                    <input
                      type="checkbox"
                      checked={filters.onlyFreeNoCard}
                      onChange={(e) => setFilters(f => ({ ...f, onlyFreeNoCard: e.target.checked }))}
                      className="rounded accent-[#FF5A36]"
                    />
                    <span>No credit card required</span>
                  </label>
                )}
              </div>

            </div>
          </div>
        )}

        {/* Result count. "verified" is reported as its own number rather than
            applied to the whole set: most listings sit at likely_active, so
            calling every result verified overstates what the pipeline knows. */}
        <div className="flex items-center justify-between gap-3 flex-wrap text-xs text-[#1C1B18] dark:text-[#F8FAF9] pt-2 font-mono max-w-3xl mx-auto font-medium">
          <div>
            {/* Explicit {' '} — JSX drops the whitespace around expressions on
                their own line, which would read as "22opportunities" to a
                screen reader and to anyone copying the text. */}
            Found{' '}
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
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-[#059669]" /> Tier 1 Verified</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-[#D97706]" /> Tier 3 X Signal</span>
          </div>
        </div>

      </div>
    </section>
  );
};
