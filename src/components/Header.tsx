import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Radar,
  Zap,
  ShieldCheck,
  Bookmark,
  Plus,
  Activity,
  Flame,
  Unlock,
  DollarSign,
  GraduationCap,
  Trophy,
  Bell,
  Database,
  Gift,
  Clock,
  FolderKanban,
  BookOpen,
  Settings2,
} from 'lucide-react';
import type { FilterState, Hackathon, AIDeal } from '../types';
import { buildCatalogueHighlights } from '../utils/buildHighlights';
import { HeaderPreferences } from './HeaderPreferences';

interface HeaderProps {
  filters: FilterState;
  setFilters: React.Dispatch<React.SetStateAction<FilterState>>;
  bookmarkCount: number;
  unverifiedCount: number;
  showAdminNav?: boolean;
  hackathons?: Hackathon[];
  aiDeals?: AIDeal[];
  onOpenBookmarks: () => void;
  onOpenSubmit: () => void;
  onOpenExtensionPanel: () => void;
  onOpenAlerts: () => void;
  onOpenAdmin?: () => void;
  viewLayout: 'grid' | 'compact';
  setViewLayout: (layout: 'grid' | 'compact') => void;
  theme: 'light' | 'dark';
  setTheme: (theme: 'light' | 'dark') => void;
}

export const Header: React.FC<HeaderProps> = ({
  filters,
  setFilters,
  bookmarkCount,
  unverifiedCount,
  showAdminNav = false,
  hackathons = [],
  aiDeals = [],
  onOpenBookmarks,
  onOpenSubmit,
  onOpenExtensionPanel,
  onOpenAlerts,
  onOpenAdmin,
  viewLayout,
  setViewLayout,
  theme,
  setTheme,
}) => {
  const highlights = useMemo(
    () => buildCatalogueHighlights(hackathons, aiDeals),
    [hackathons, aiDeals],
  );

  // Duplicate list for seamless marquee loop
  const tickerItems = [...highlights, ...highlights];
  const mobileTickerItem = highlights[0];

  // Pause the marquee once the user has scrolled past the initial fold.
  // The header is `sticky top-0` so the marquee never leaves the viewport —
  // IntersectionObserver won't trigger. A scroll-depth threshold is the honest
  // proxy for "user is now reading results, no need to keep the ticker moving".
  const marqueeRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const el = marqueeRef.current;
    if (!el) return;
    const onScroll = () => {
      el.classList.toggle('marquee-paused', window.scrollY > 300);
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // Consolidate low-frequency display and resource controls so the primary
  // header row stays focused on alerts, submissions, and saved opportunities.
  const [preferencesOpen, setPreferencesOpen] = useState(false);
  const preferencesRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!preferencesOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (preferencesRef.current && !preferencesRef.current.contains(e.target as Node)) {
        setPreferencesOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setPreferencesOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [preferencesOpen]);

  const iconFor = (kind: string) => {
    switch (kind) {
      case 'prize':
        return <Trophy className="w-3.5 h-3.5 text-[#FF5A36] shrink-0" />;
      case 'closing':
        return <Clock className="w-3.5 h-3.5 text-[#D97706] shrink-0" />;
      case 'offer':
        return <Gift className="w-3.5 h-3.5 text-[#7C3AED] shrink-0" />;
      default:
        return <DollarSign className="w-3.5 h-3.5 text-[#059669] shrink-0" />;
    }
  };

  const emphasisClassFor = (kind: string) =>
    kind === 'closing'
      ? 'text-[#92400E] dark:text-[#FBBF24]'
      : kind === 'offer'
        ? 'text-[#6D28D9] dark:text-[#C4B5FD]'
        : 'text-[#065F46] dark:text-[#34D399]';

  const isAdminContext = showAdminNav || filters.activeModule === 'admin_queue';
  const accessLabel = showAdminNav
    ? 'Admin session active'
    : filters.activeModule === 'admin_queue'
      ? 'Admin sign-in required'
      : 'Public browsing \u00B7 no login';

  return (
    <div className="sticky top-0 z-40 w-full flex flex-col font-sans">
      {/* Catalogue highlights strip (from real data — not a fake live feed) */}
      <div className="w-full bg-[#E5E6DF] dark:bg-[#090C15] border-b border-[#D6D5CF] dark:border-slate-800 px-4 py-2 sm:px-6 sm:py-2.5 overflow-hidden text-[12px] leading-5 font-mono text-[#4A4845] dark:text-[#B8C4D2] font-semibold">
        <div className="isolate max-w-6xl mx-auto flex min-h-5 items-center justify-between gap-4">
          <div className="relative z-20 flex items-center gap-2 shrink-0 py-0.5 pr-3 sm:pr-5 bg-[#E5E6DF] dark:bg-[#090C15] font-bold">
            <Flame className="w-3.5 h-3.5 text-[#FF5A36]" />
            {/* The ticker sits on #E5E6DF, darker than a card, so these accents
                go one step deeper than the --text-* tokens to clear 4.5:1. */}
            <span className="text-[#9A3412] dark:text-[#FF8A6B] whitespace-nowrap">HIGHLIGHTS</span>
          </div>

          <div className="relative z-0 min-w-0 flex-1 overflow-hidden pl-1 sm:pl-2">
            {mobileTickerItem ? (
              <div className="flex min-w-0 items-center gap-1.5 py-0.5 font-bold text-[#1C1B18] dark:text-white md:hidden">
                {iconFor(mobileTickerItem.kind)}
                <strong className={`shrink-0 ${emphasisClassFor(mobileTickerItem.kind)}`}>
                  {mobileTickerItem.emphasis}
                </strong>
                <span className="min-w-0 truncate">{mobileTickerItem.label}</span>
              </div>
            ) : null}
            <div className="hidden md:block">
              <div
                ref={marqueeRef}
                className="animate-marquee whitespace-nowrap flex items-center gap-6 py-0.5 text-[#1C1B18] dark:text-white font-bold md:gap-8"
              >
              {tickerItems.map((item, i) => (
                <span key={`${item.id}-${i}`} className="inline-flex items-center gap-1.5 shrink-0">
                  {iconFor(item.kind)}
                  <strong
                    className={emphasisClassFor(item.kind)}
                  >
                    {item.emphasis}
                  </strong>
                  <span className="max-w-[200px] sm:max-w-none truncate">{item.label}</span>
                  {/* Decorative separator — hidden so it is not announced
                      between every single ticker item. */}
                  <span aria-hidden="true" className="text-[#5C594F] dark:text-[#A3A096] ml-2">•</span>
                </span>
              ))}
            </div>
              </div>
          </div>

          <div className="hidden lg:flex items-center gap-2 text-[#065F46] dark:text-emerald-400 shrink-0 font-bold text-[12px]">
            <Unlock className="w-3.5 h-3.5" />
            <span>OPEN SOURCE · NO END-USER LOGIN</span>
          </div>
        </div>
      </div>

      <header className="w-full border-b border-[#D6D5CF] dark:border-slate-800 bg-[#F3F4EF] dark:bg-[#090C15] px-3 sm:px-4 lg:px-8 py-3 sm:py-3.5">
        <div className="max-w-6xl mx-auto flex flex-col gap-3 md:gap-4">
          <div className="flex items-center justify-between gap-3 w-full">
            <button
              type="button"
              aria-label="Go to DevRadar hackathon catalogue"
              className="flex items-center gap-2 sm:gap-3 group min-w-0 text-left rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#FF5A36] focus-visible:ring-offset-2"
              onClick={() => setFilters((f) => ({ ...f, activeModule: 'hackathon' }))}
            >
              <div className="relative flex items-center justify-center w-10 h-10 rounded-2xl bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#FF5A36] shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5] group-hover:scale-105 transition-transform shrink-0">
                <picture>
                  <source srcSet="/logomark.webp" type="image/webp" />
                  <img
                    src="/logomark.png"
                    alt="DevRadar Logo"
                    width={32}
                    height={32}
                    decoding="async"
                    className="w-8 h-8 object-contain"
                  />
                </picture>
              </div>
              <div className="min-w-0">
                <span className="font-extrabold text-lg sm:text-xl tracking-[-0.04em] text-[#1C1B18] dark:text-white">
                  Dev<span className="text-[#FF5A36]">Radar</span>
                </span>
              </div>
            </button>

            <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
              <div ref={preferencesRef} className="relative">
                <button
                  type="button"
                  onClick={() => setPreferencesOpen((open) => !open)}
                  title="Preferences"
                  aria-label="Open preferences"
                  aria-haspopup="dialog"
                  aria-expanded={preferencesOpen}
                  aria-controls="header-preferences"
                  className={`p-2 sm:p-2.5 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5] font-bold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#D23B14] ${
                    preferencesOpen
                      ? 'bg-[#1C1B18] text-white dark:bg-white dark:text-[#1C1B18]'
                      : 'bg-white text-[#1C1B18] dark:bg-[#131A29] dark:text-white'
                  }`}
                >
                  <Settings2 className="w-4 h-4" />
                </button>
                <HeaderPreferences
                  isOpen={preferencesOpen}
                  viewLayout={viewLayout}
                  setViewLayout={setViewLayout}
                  theme={theme}
                  setTheme={setTheme}
                  onOpenExtensionPanel={onOpenExtensionPanel}
                  onClose={() => setPreferencesOpen(false)}
                />
              </div>

              <button
                type="button"
                onClick={onOpenAlerts}
                title="Email alerts"
                aria-label="Subscribe to email alerts"
                className="p-2 sm:p-2.5 rounded-full bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5] font-bold"
              >
                <Bell className="w-4 h-4 text-[#7C3AED]" />
              </button>

              <button
                type="button"
                onClick={onOpenSubmit}
                // The label is hidden below `sm`, so without this the button
                // announces as an unnamed "+" on mobile.
                aria-label="Submit a missing opportunity"
                title="Submit a missing opportunity"
                className="btn-sharetopus-primary text-xs py-2 px-3 sm:px-4 font-bold"
              >
                <Plus className="w-4 h-4" />
                <span className="hidden sm:inline">Submit</span>
              </button>

              <button
                type="button"
                onClick={onOpenBookmarks}
                aria-label={
                  bookmarkCount > 0
                    ? `Saved opportunities (${bookmarkCount})`
                    : 'Saved opportunities'
                }
                title="Saved opportunities"
                className="relative p-2 sm:p-2.5 rounded-full bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5] font-bold"
              >
                <Bookmark className="w-4 h-4 text-[#FF5A36]" />
                {bookmarkCount > 0 && (
                  <span
                    aria-hidden="true"
                    className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-[#D23B14] text-[12px] font-extrabold text-white shadow-md"
                  >
                    {bookmarkCount}
                  </span>
                )}
              </button>
            </div>
          </div>

          {/* Module switcher — scrollable on mobile */}
          <nav aria-label="DevRadar sections" className="flex items-center gap-1 bg-white dark:bg-[#131A29] p-1.5 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[3px_3px_0_0_#1C1B18] dark:shadow-[3px_3px_0_0_#D6DCE5] text-xs sm:text-sm font-extrabold w-full overflow-x-auto no-scrollbar">
            <button
              type="button"
              onClick={() => setFilters((f) => ({ ...f, activeModule: 'hackathon' }))}
              aria-pressed={filters.activeModule === 'hackathon'}
              className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-2 rounded-full transition-all whitespace-nowrap shrink-0 ${
                filters.activeModule === 'hackathon'
                  ? 'bg-[#D23B14] text-white font-bold shadow-sm'
                  : 'text-[#1C1B18] dark:text-[#D6DCE5] hover:text-[#C2410C] dark:hover:text-[#FF8A6B]'
              }`}
            >
              <Radar className="w-4 h-4" />
              <span>Radar</span>
            </button>

            <button
              type="button"
              onClick={() => setFilters((f) => ({ ...f, activeModule: 'ai_deal' }))}
              aria-pressed={filters.activeModule === 'ai_deal'}
              className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-2 rounded-full transition-all whitespace-nowrap shrink-0 ${
                filters.activeModule === 'ai_deal'
                  ? 'bg-[#7C3AED] text-white font-bold shadow-sm'
                  : 'text-[#1C1B18] dark:text-[#D6DCE5] hover:text-[#7C3AED]'
              }`}
            >
              <Zap className="w-4 h-4" />
              <span>AI Deals</span>
            </button>

            {showAdminNav && (
              <>
                <button
                  type="button"
                  onClick={() => setFilters((f) => ({ ...f, activeModule: 'pipeline' }))}
                  aria-pressed={filters.activeModule === 'pipeline'}
                  className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-2 rounded-full transition-all whitespace-nowrap shrink-0 ${
                    filters.activeModule === 'pipeline'
                      ? 'bg-[#059669] text-white font-bold shadow-sm'
                      : 'text-[#1C1B18] dark:text-[#D6DCE5] hover:text-[#059669]'
                  }`}
                >
                  <Activity className="w-4 h-4" />
                  <span className="hidden xs:inline sm:inline">Pipeline</span>
                </button>

                <button
                  type="button"
                  onClick={() => setFilters((f) => ({ ...f, activeModule: 'admin_queue' }))}
                  aria-pressed={filters.activeModule === 'admin_queue'}
                  className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-2 rounded-full transition-all whitespace-nowrap shrink-0 ${
                    filters.activeModule === 'admin_queue'
                      ? 'bg-[#D97706] text-white font-bold shadow-sm'
                      : 'text-[#1C1B18] dark:text-[#D6DCE5] hover:text-[#D97706]'
                  }`}
                >
                  <ShieldCheck className="w-4 h-4" />
                  <span>Review</span>
                  {unverifiedCount > 0 && (
                    <span className="px-2 py-0.5 rounded-full bg-[#1C1B18] text-white text-[12px] font-mono font-bold">
                      {unverifiedCount}
                    </span>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => setFilters((f) => ({ ...f, activeModule: 'catalogue' }))}
                  aria-pressed={filters.activeModule === 'catalogue'}
                  className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-2 rounded-full transition-all whitespace-nowrap shrink-0 ${
                    filters.activeModule === 'catalogue'
                      ? 'bg-[#D23B14] text-white font-bold shadow-sm'
                      : 'text-[#1C1B18] dark:text-[#D6DCE5] hover:text-[#D23B14]'
                  }`}
                >
                  <FolderKanban className="w-4 h-4" />
                  <span>Catalog</span>
                </button>

                <button
                  type="button"
                  onClick={() => setFilters((f) => ({ ...f, activeModule: 'sources' }))}
                  aria-pressed={filters.activeModule === 'sources'}
                  className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-2 rounded-full transition-all whitespace-nowrap shrink-0 ${
                    filters.activeModule === 'sources'
                      ? 'bg-[#2563EB] text-white font-bold shadow-sm'
                      : 'text-[#1C1B18] dark:text-[#D6DCE5] hover:text-[#2563EB]'
                  }`}
                >
                  <Database className="w-4 h-4" />
                  <span>Sources</span>
                </button>
              </>
            )}

            <button
              type="button"
              onClick={() => setFilters((f) => ({ ...f, activeModule: 'guide' }))}
              className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-2 rounded-full transition-all whitespace-nowrap shrink-0 ${
                filters.activeModule === 'guide'
                  ? 'bg-[#1C1B18] dark:bg-white text-white dark:text-[#1C1B18] font-bold shadow-sm'
                  : 'text-[#1C1B18] dark:text-[#D6DCE5] hover:text-[#736F66] dark:hover:text-white'
              }`}
            >
              <BookOpen className="w-4 h-4" />
              <span>Guide</span>
            </button>

            {!showAdminNav && onOpenAdmin && (
              <button
                type="button"
                onClick={onOpenAdmin}
                aria-pressed={filters.activeModule === 'admin_queue'}
                title="Operator login (Google OAuth)"
                aria-label="Operator admin login"
                className={`flex items-center gap-1.5 sm:gap-2 px-3 py-2 rounded-full transition-all whitespace-nowrap shrink-0 text-[#1C1B18] dark:text-[#D6DCE5] hover:text-[#D97706] ${
                  filters.activeModule === 'admin_queue' ? 'bg-[#D97706]/15 font-bold' : ''
                }`}
              >
                <ShieldCheck className="w-4 h-4" />
                <span>Operator</span>
                <span className="rounded-full border border-[#D97706] bg-[#D97706] px-1.5 py-0.5 text-[9px] font-extrabold uppercase tracking-wide leading-none text-white">
                  Admin
                </span>
              </button>
            )}

            <span className="hidden sm:inline-flex items-center gap-1 ml-auto pl-2 text-[12px] font-bold text-[#736F66] dark:text-[#94A3B8] shrink-0">
              {isAdminContext ? (
                <ShieldCheck className="w-3.5 h-3.5" />
              ) : (
                <GraduationCap className="w-3.5 h-3.5" />
              )}
              {accessLabel}
            </span>
          </nav>
        </div>
      </header>
    </div>
  );
};
