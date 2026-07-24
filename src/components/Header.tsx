import React, { useMemo } from 'react';
import {
  Radar,
  Zap,
  ShieldCheck,
  Bookmark,
  Plus,
  Globe,
  Activity,
  Flame,
  LayoutGrid,
  List,
  Unlock,
  DollarSign,
  GraduationCap,
  Trophy,
  Sun,
  Moon,
  Bell,
  Database,
  Gift,
  Clock,
} from 'lucide-react';
import type { FilterState, Hackathon, AIDeal } from '../types';
import { buildCatalogueHighlights } from '../utils/buildHighlights';

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

  return (
    <div className="sticky top-0 z-40 w-full flex flex-col font-sans">
      {/* Catalogue highlights strip (from real data — not a fake live feed) */}
      <div className="w-full bg-[#E5E6DF] dark:bg-[#090C15] border-b border-[#D6D5CF] dark:border-slate-800 py-1.5 px-3 sm:px-4 overflow-hidden text-[12px] font-mono text-[#4A4845] dark:text-[#B8C4D2] font-semibold">
        <div className="max-w-6xl mx-auto flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 shrink-0 pr-2 sm:pr-4 bg-[#E5E6DF] dark:bg-[#090C15] z-10 font-bold">
            <Flame className="w-3.5 h-3.5 text-[#FF5A36]" />
            <span className="text-[#FF5A36] whitespace-nowrap">HIGHLIGHTS</span>
          </div>

          <div className="overflow-hidden flex-1 relative min-w-0">
            <div className="animate-marquee whitespace-nowrap flex items-center gap-6 sm:gap-8 text-[#1C1B18] dark:text-white font-bold">
              {tickerItems.map((item, i) => (
                <span key={`${item.id}-${i}`} className="inline-flex items-center gap-1.5 shrink-0">
                  {iconFor(item.kind)}
                  <strong
                    className={
                      item.kind === 'closing'
                        ? 'text-[#D97706]'
                        : item.kind === 'offer'
                          ? 'text-[#7C3AED]'
                          : 'text-[#059669]'
                    }
                  >
                    {item.emphasis}
                  </strong>
                  <span className="max-w-[200px] sm:max-w-none truncate">{item.label}</span>
                  <span className="text-[#736F66] dark:text-[#A3A096] ml-2">•</span>
                </span>
              ))}
            </div>
          </div>

          <div className="hidden lg:flex items-center gap-2 text-[#059669] dark:text-emerald-400 shrink-0 font-bold text-[12px]">
            <Unlock className="w-3.5 h-3.5" />
            <span>OPEN SOURCE · NO END-USER LOGIN</span>
          </div>
        </div>
      </div>

      <header className="w-full border-b border-[#D6D5CF] dark:border-slate-800 bg-[#F3F4EF] dark:bg-[#090C15] px-3 sm:px-4 lg:px-8 py-3 sm:py-3.5">
        <div className="max-w-6xl mx-auto flex flex-col gap-3 md:gap-4">
          <div className="flex items-center justify-between gap-3 w-full">
            <div
              className="flex items-center gap-2 sm:gap-3 cursor-pointer group min-w-0"
              onClick={() => setFilters((f) => ({ ...f, activeModule: 'hackathon' }))}
            >
              <div className="relative flex items-center justify-center w-10 h-10 rounded-2xl bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] text-[#FF5A36] shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5] group-hover:scale-105 transition-transform shrink-0">
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
            </div>

            <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
              <div className="hidden sm:flex items-center gap-1 p-1 bg-white dark:bg-[#131A29] rounded-full border-[1.5px] border-[#1C1B18] shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5]">
                <button
                  type="button"
                  onClick={() => setViewLayout('grid')}
                  title="Grid View"
                  className={`p-1.5 rounded-full transition-all ${
                    viewLayout === 'grid'
                      ? 'bg-[#FF5A36] text-white font-bold'
                      : 'text-[#4A4845] dark:text-[#B8C4D2] hover:text-[#1C1B18]'
                  }`}
                >
                  <LayoutGrid className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => setViewLayout('compact')}
                  title="Compact List View"
                  className={`p-1.5 rounded-full transition-all ${
                    viewLayout === 'compact'
                      ? 'bg-[#FF5A36] text-white font-bold'
                      : 'text-[#4A4845] dark:text-[#B8C4D2] hover:text-[#1C1B18]'
                  }`}
                >
                  <List className="w-3.5 h-3.5" />
                </button>
              </div>

              <button
                type="button"
                onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
                title="Toggle Theme"
                className="p-2 sm:p-2.5 rounded-full bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] text-[#1C1B18] dark:text-white shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5] font-bold"
              >
                {theme === 'light' ? (
                  <Moon className="w-4 h-4 text-[#1C1B18]" />
                ) : (
                  <Sun className="w-4 h-4 text-amber-400" />
                )}
              </button>

              <a
                href="https://github.com/bagusardin25/DevRadar.git"
                target="_blank"
                rel="noreferrer"
                title="GitHub"
                className="hidden sm:flex p-2.5 rounded-full bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] text-[#1C1B18] dark:text-white shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5] font-bold"
              >
                <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
                  <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                </svg>
              </a>

              <button
                type="button"
                onClick={onOpenExtensionPanel}
                title="Extension preview"
                className="hidden sm:flex p-2.5 rounded-full bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] text-[#1C1B18] dark:text-white shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5] font-bold"
              >
                <Globe className="w-4 h-4 text-[#FF5A36]" />
              </button>

              <button
                type="button"
                onClick={onOpenAlerts}
                title="Email alerts"
                className="p-2 sm:p-2.5 rounded-full bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] text-[#1C1B18] dark:text-white shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5] font-bold"
              >
                <Bell className="w-4 h-4 text-[#7C3AED]" />
              </button>

              <button
                type="button"
                onClick={onOpenSubmit}
                className="btn-sharetopus-primary text-xs py-2 px-3 sm:px-4 font-bold"
              >
                <Plus className="w-4 h-4" />
                <span className="hidden sm:inline">Submit</span>
              </button>

              <button
                type="button"
                onClick={onOpenBookmarks}
                className="relative p-2 sm:p-2.5 rounded-full bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] text-[#1C1B18] dark:text-white shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5] font-bold"
              >
                <Bookmark className="w-4 h-4 text-[#FF5A36]" />
                {bookmarkCount > 0 && (
                  <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-[#FF5A36] text-[12px] font-extrabold text-white shadow-md">
                    {bookmarkCount}
                  </span>
                )}
              </button>
            </div>
          </div>

          {/* Module switcher — scrollable on mobile */}
          <div className="flex items-center gap-1 bg-white dark:bg-[#131A29] p-1.5 rounded-full border-[1.5px] border-[#1C1B18] shadow-[3px_3px_0_0_#1C1B18] dark:shadow-[3px_3px_0_0_#D6DCE5] text-xs sm:text-sm font-extrabold w-full overflow-x-auto no-scrollbar">
            <button
              type="button"
              onClick={() => setFilters((f) => ({ ...f, activeModule: 'hackathon' }))}
              className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-2 rounded-full transition-all whitespace-nowrap shrink-0 ${
                filters.activeModule === 'hackathon'
                  ? 'bg-[#FF5A36] text-white font-bold shadow-sm'
                  : 'text-[#1C1B18] dark:text-[#D6DCE5] hover:text-[#FF5A36]'
              }`}
            >
              <Radar className="w-4 h-4" />
              <span>Radar</span>
            </button>

            <button
              type="button"
              onClick={() => setFilters((f) => ({ ...f, activeModule: 'ai_deal' }))}
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
                  onClick={() => setFilters((f) => ({ ...f, activeModule: 'sources' }))}
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

            {!showAdminNav && onOpenAdmin && (
              <button
                type="button"
                onClick={onOpenAdmin}
                title="Operator login (GitHub OAuth)"
                className={`flex items-center gap-1.5 sm:gap-2 px-3 py-2 rounded-full transition-all whitespace-nowrap shrink-0 text-[#1C1B18] dark:text-[#D6DCE5] hover:text-[#D97706] ${
                  filters.activeModule === 'admin_queue' ? 'bg-[#D97706]/15 font-bold' : ''
                }`}
              >
                <ShieldCheck className="w-4 h-4" />
                <span>Operator</span>
              </button>
            )}

            <span className="hidden sm:inline-flex items-center gap-1 ml-auto pl-2 text-[12px] font-bold text-[#736F66] dark:text-[#94A3B8] shrink-0">
              <GraduationCap className="w-3.5 h-3.5" />
              No login required
            </span>
          </div>
        </div>
      </header>
    </div>
  );
};
