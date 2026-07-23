import React from 'react';
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
  Cpu,
  GraduationCap,
  Trophy,
  Sun,
  Moon
} from 'lucide-react';
import type { FilterState } from '../types';

interface HeaderProps {
  filters: FilterState;
  setFilters: React.Dispatch<React.SetStateAction<FilterState>>;
  bookmarkCount: number;
  unverifiedCount: number;
  onOpenBookmarks: () => void;
  onOpenSubmit: () => void;
  onOpenExtensionPanel: () => void;
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
  onOpenBookmarks,
  onOpenSubmit,
  onOpenExtensionPanel,
  viewLayout,
  setViewLayout,
  theme,
  setTheme
}) => {
  return (
    <div className="sticky top-0 z-40 w-full flex flex-col font-sans">
      
      {/* Top Ticker Marquee Bar */}
      <div className="w-full bg-[#E5E6DF] dark:bg-[#090C15] border-b border-[#D6D5CF] dark:border-slate-800 py-1.5 px-4 overflow-hidden text-[11px] font-mono text-[#4A4845] dark:text-[#B8C4D2] font-semibold">
        <div className="max-w-6xl mx-auto flex items-center justify-between gap-4">
          <div className="flex items-center gap-2 shrink-0 pr-4 bg-[#E5E6DF] dark:bg-[#090C15] z-10 font-bold">
            <span className="flex h-2 w-2 relative">
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#FF5A36]"></span>
            </span>
            <span className="text-[#FF5A36] flex items-center gap-1">
              <Flame className="w-3.5 h-3.5 text-[#FF5A36]" />
              LIVE TICKER:
            </span>
          </div>

          <div className="overflow-hidden flex-1 relative">
            <div className="animate-marquee whitespace-nowrap flex items-center gap-8 text-[#1C1B18] dark:text-white font-bold">
              <span className="flex items-center gap-1.5"><DollarSign className="w-3.5 h-3.5 text-[#059669] inline" /><strong className="text-[#059669]">$50,000 USD</strong> Global AI Agents Challenge by Anthropic & Vercel</span>
              <span className="text-[#736F66] dark:text-[#A3A096]">•</span>
              <span className="flex items-center gap-1.5"><Cpu className="w-3.5 h-3.5 text-[#7C3AED] inline" /><strong className="text-[#7C3AED]">DEEPSEEK-V4-FLASH</strong> API drops to $0.28/1M Output Tokens</span>
              <span className="text-[#736F66] dark:text-[#A3A096]">•</span>
              <span className="flex items-center gap-1.5"><GraduationCap className="w-3.5 h-3.5 text-[#0284C7] inline" /><strong className="text-[#0284C7]">GITHUB PACK</strong> Free Copilot Pro + $200 Azure AI Credits</span>
              <span className="text-[#736F66] dark:text-[#A3A096]">•</span>
              <span className="flex items-center gap-1.5"><Trophy className="w-3.5 h-3.5 text-[#FF5A36] inline" /><strong className="text-[#FF5A36]">$25,000 USD</strong> Open Source AI Infra Hackathon by Hugging Face</span>
            </div>
          </div>

          <div className="hidden lg:flex items-center gap-2 text-[#059669] dark:text-emerald-400 shrink-0 font-bold">
            <Unlock className="w-3.5 h-3.5" />
            <span>100% OPEN SOURCE • NO LOGIN REQUIRED</span>
          </div>
        </div>
      </div>

      {/* Main Sticky Header */}
      <header className="w-full border-b border-[#D6D5CF] dark:border-slate-800 bg-[#F3F4EF]/95 dark:bg-[#090C15]/95 backdrop-blur-md px-4 lg:px-8 py-3.5">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          
          {/* Brand & System Status */}
          <div className="flex items-center gap-4 w-full md:w-auto justify-between md:justify-start">
            <div className="flex items-center gap-3 cursor-pointer group" onClick={() => setFilters(f => ({ ...f, activeModule: 'hackathon' }))}>
              <div className="relative flex items-center justify-center w-10 h-10 rounded-2xl bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] text-[#FF5A36] shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5] group-hover:scale-105 transition-all">
                <img src="/logomark.png" alt="DevRadar Logo" className="w-8 h-8 object-contain" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-extrabold text-xl tracking-[-0.04em] text-[#1C1B18] dark:text-white">Dev<span className="text-[#FF5A36]">Radar</span></span>
                </div>
              </div>
            </div>

            {/* Layout Switcher (Grid vs Compact) */}
            <div className="hidden md:flex items-center gap-1 p-1 bg-white dark:bg-[#131A29] rounded-full border-[1.5px] border-[#1C1B18] shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5]">
              <button
                onClick={() => setViewLayout('grid')}
                title="Grid View"
                className={`p-1.5 rounded-full transition-all ${
                  viewLayout === 'grid' ? 'bg-[#FF5A36] text-white font-bold' : 'text-[#4A4845] dark:text-[#B8C4D2] hover:text-[#1C1B18]'
                }`}
              >
                <LayoutGrid className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setViewLayout('compact')}
                title="Compact List View"
                className={`p-1.5 rounded-full transition-all ${
                  viewLayout === 'compact' ? 'bg-[#FF5A36] text-white font-bold' : 'text-[#4A4845] dark:text-[#B8C4D2] hover:text-[#1C1B18]'
                }`}
              >
                <List className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Module Switcher Nav Pills */}
          <div className="flex items-center gap-1 bg-white dark:bg-[#131A29] p-1.5 rounded-full border-[1.5px] border-[#1C1B18] shadow-[3px_3px_0_0_#1C1B18] dark:shadow-[3px_3px_0_0_#D6DCE5] text-xs sm:text-sm font-extrabold w-full md:w-auto overflow-x-auto">
            <button
              onClick={() => setFilters(f => ({ ...f, activeModule: 'hackathon' }))}
              className={`flex items-center gap-2 px-4 py-2 rounded-full transition-all whitespace-nowrap ${
                filters.activeModule === 'hackathon'
                  ? 'bg-[#FF5A36] text-white font-bold shadow-sm'
                  : 'text-[#1C1B18] dark:text-[#D6DCE5] hover:text-[#FF5A36]'
              }`}
            >
              <Radar className="w-4 h-4" />
              <span className="hidden sm:inline">Radar</span>
            </button>

            <button
              onClick={() => setFilters(f => ({ ...f, activeModule: 'ai_deal' }))}
              className={`flex items-center gap-2 px-4 py-2 rounded-full transition-all whitespace-nowrap ${
                filters.activeModule === 'ai_deal'
                  ? 'bg-[#7C3AED] text-white font-bold shadow-sm'
                  : 'text-[#1C1B18] dark:text-[#D6DCE5] hover:text-[#7C3AED]'
              }`}
            >
              <Zap className="w-4 h-4" />
              <span className="hidden sm:inline">AI Deals</span>
            </button>

            <button
              onClick={() => setFilters(f => ({ ...f, activeModule: 'pipeline' }))}
              className={`flex items-center gap-2 px-4 py-2 rounded-full transition-all whitespace-nowrap ${
                filters.activeModule === 'pipeline'
                  ? 'bg-[#059669] text-white font-bold shadow-sm'
                  : 'text-[#1C1B18] dark:text-[#D6DCE5] hover:text-[#059669]'
              }`}
            >
              <Activity className="w-4 h-4" />
              <span className="hidden sm:inline">Pipeline</span>
            </button>

            <button
              onClick={() => setFilters(f => ({ ...f, activeModule: 'admin_queue' }))}
              className={`flex items-center gap-2 px-4 py-2 rounded-full transition-all whitespace-nowrap ${
                filters.activeModule === 'admin_queue'
                  ? 'bg-[#D97706] text-white font-bold shadow-sm'
                  : 'text-[#1C1B18] dark:text-[#D6DCE5] hover:text-[#D97706]'
              }`}
            >
              <ShieldCheck className="w-4 h-4" />
              <span className="hidden sm:inline">Review</span>
              {unverifiedCount > 0 && (
                <span className="px-2 py-0.2 rounded-full bg-[#1C1B18] text-white text-[11px] font-mono font-bold">
                  {unverifiedCount}
                </span>
              )}
            </button>
          </div>

          {/* Action Controls */}
          <div className="flex items-center gap-2 w-full md:w-auto justify-end">
            
            {/* Theme Toggle Button */}
            <button
              onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
              title="Toggle Theme"
              className="p-2.5 rounded-full bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] text-[#1C1B18] dark:text-white shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5] hover:translate-x-[-1px] transition-all font-bold"
            >
              {theme === 'light' ? <Moon className="w-4 h-4 text-[#1C1B18]" /> : <Sun className="w-4 h-4 text-amber-400" />}
            </button>

            {/* GitHub Repo */}
            <a
              href="https://github.com/bagusardin25/DevRadar.git"
              target="_blank"
              rel="noreferrer"
              title="GitHub Open Source Repository"
              className="hidden sm:flex p-2.5 rounded-full bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] text-[#1C1B18] dark:text-white shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5] hover:translate-x-[-1px] transition-all font-bold"
            >
              <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
              </svg>
            </a>

            {/* Extension Sidepanel Button */}
            <button
              onClick={onOpenExtensionPanel}
              title="Open Extension"
              className="p-2.5 rounded-full bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] text-[#1C1B18] dark:text-white shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5] hover:translate-x-[-1px] transition-all font-bold"
            >
              <Globe className="w-4 h-4 text-[#FF5A36]" />
            </button>

            {/* Submit Opportunity */}
            <button
              onClick={onOpenSubmit}
              className="btn-sharetopus-primary text-xs py-2 px-4 font-bold"
            >
              <Plus className="w-4 h-4" />
              <span className="hidden sm:inline">Submit</span>
            </button>

            {/* Bookmarks Drawer Trigger */}
            <button
              onClick={onOpenBookmarks}
              className="relative p-2.5 rounded-full bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] text-[#1C1B18] dark:text-white shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5] hover:translate-x-[-1px] transition-all font-bold"
            >
              <Bookmark className="w-4 h-4 text-[#FF5A36]" />
              {bookmarkCount > 0 && (
                <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-[#FF5A36] text-[10px] font-extrabold text-white shadow-md">
                  {bookmarkCount}
                </span>
              )}
            </button>
          </div>

        </div>
      </header>
    </div>
  );
};
