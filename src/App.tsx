import { useState, useMemo, useEffect } from 'react';
import { Header } from './components/Header';
import { HeroSection } from './components/HeroSection';
import { StatsOverview } from './components/StatsOverview';
import { HackathonCard } from './components/HackathonCard';
import { AIDealCard } from './components/AIDealCard';
import { DetailModal } from './components/DetailModal';
import { PipelineViewer } from './components/PipelineViewer';
import { AdminQueue } from './components/AdminQueue';
import { ChromeExtensionSidePanel } from './components/ChromeExtensionSidePanel';
import { CompareModal } from './components/CompareModal';
import { SubmitModal } from './components/SubmitModal';
import { BookmarksDrawer } from './components/BookmarksDrawer';

import { MOCK_HACKATHONS, MOCK_AI_DEALS, MOCK_UNVERIFIED_SIGNALS } from './data/mockData';
import type { FilterState, Hackathon, AIDeal, UnverifiedSignal } from './types';
import { FilterX } from 'lucide-react';

const STORAGE_KEYS = {
  BOOKMARKS: 'devradar_bookmarks_v1',
  LAYOUT: 'devradar_layout_v1',
  THEME: 'devradar_theme_v1',
  HACKATHONS: 'devradar_hackathons_v1',
  DEALS: 'devradar_deals_v1',
  SIGNALS: 'devradar_signals_v1'
};

export function App() {
  // Theme state (Sharetopus Warm Light vs Cyber Dark)
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.THEME);
    return (saved === 'dark' || saved === 'light') ? saved : 'light';
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.THEME, theme);
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark', 'dark-theme');
    } else {
      root.classList.remove('dark', 'dark-theme');
    }
  }, [theme]);

  const [filters, setFilters] = useState<FilterState>({
    searchQuery: '',
    activeModule: 'hackathon',
    mode: 'all',
    region: '',
    eligibility: '',
    technology: '',
    offerType: '',
    verificationStatus: '',
    onlyClosingSoon: false,
    onlyBigPrizes: false,
    onlyFreeNoCard: false,
    searchExecutionMode: 'indexed'
  });

  // LocalStorage layout preference
  const [viewLayout, setViewLayout] = useState<'grid' | 'compact'>(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.LAYOUT);
    return (saved === 'compact' || saved === 'grid') ? saved : 'grid';
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.LAYOUT, viewLayout);
  }, [viewLayout]);

  // LocalStorage hackathons & bookmarks persistence
  const [hackathons, setHackathons] = useState<Hackathon[]>(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.HACKATHONS);
    return saved ? JSON.parse(saved) : MOCK_HACKATHONS;
  });

  const [aiDeals, setAiDeals] = useState<AIDeal[]>(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.DEALS);
    return saved ? JSON.parse(saved) : MOCK_AI_DEALS;
  });

  const [unverifiedSignals, setUnverifiedSignals] = useState<UnverifiedSignal[]>(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.SIGNALS);
    return saved ? JSON.parse(saved) : MOCK_UNVERIFIED_SIGNALS;
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.HACKATHONS, JSON.stringify(hackathons));
  }, [hackathons]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.DEALS, JSON.stringify(aiDeals));
  }, [aiDeals]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.SIGNALS, JSON.stringify(unverifiedSignals));
  }, [unverifiedSignals]);
  
  const [selectedItem, setSelectedItem] = useState<Hackathon | AIDeal | null>(null);
  const [compareItems, setCompareItems] = useState<Hackathon[]>([]);
  
  const [isBookmarksOpen, setIsBookmarksOpen] = useState(false);
  const [isSubmitOpen, setIsSubmitOpen] = useState(false);
  const [isExtensionOpen, setIsExtensionOpen] = useState(false);
  const [isSearchingLive, setIsSearchingLive] = useState(false);

  // Calculate stats summary values
  const totalPrizePoolValue = useMemo(() => {
    return hackathons.reduce((sum, h) => sum + h.prizeValue, 0);
  }, [hackathons]);

  // Trigger Live Web Discovery Pipeline Simulation
  const handleTriggerLiveDiscovery = () => {
    setIsSearchingLive(true);
    setTimeout(() => {
      setIsSearchingLive(false);
      const newDiscoveredHack: Hackathon = {
        id: `hack-live-${Date.now()}`,
        title: 'Live Discovered: DeepSeek & Vercel AI Challenge',
        organizer: 'DeepSeek & Vercel',
        description: 'Newly discovered on X! Build ultra-fast reasoning bots with DeepSeek-v4-Pro and Flash models hosted on Vercel AI SDK.',
        registrationOpenAt: new Date().toISOString(),
        registrationDeadline: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
        submissionDeadline: new Date(Date.now() + 21 * 24 * 60 * 60 * 1000).toISOString(),
        mode: 'online',
        eligibleCountries: ['Worldwide'],
        eligibility: ['Developer', 'Student'],
        teamMin: 1,
        teamMax: 4,
        prizeValue: 35000,
        prizeCurrency: 'USD',
        technologies: ['DeepSeek', 'Vercel', 'AI', 'Next.js'],
        officialUrl: 'https://vercel.com/events/deepseek-challenge-2026',
        discoverySources: [
          {
            type: 'official_site',
            url: 'https://vercel.com/events/deepseek-challenge-2026',
            fetchedAt: new Date().toISOString(),
            tier: 'Tier 1 (Official)'
          },
          {
            type: 'x',
            url: 'https://x.com/deepseek_ai/status/1899990192',
            author: '@deepseek_ai',
            fetchedAt: new Date().toISOString(),
            tier: 'Tier 3 (Discovery Signal)'
          }
        ],
        verificationStatus: 'verified_active',
        confidenceScore: 0.96,
        lastCheckedAt: new Date().toISOString(),
        suitableReasons: [
          'Freshly discovered live signal',
          'High Prize Pool ($35,000 USD)',
          'Free DeepSeek API credits'
        ],
        effortEstimate: '1-2 Weeks',
        audit: {
          lastCheckedAt: new Date().toISOString(),
          confidenceScore: 0.96,
          scoreBreakdown: {
            statusAndDeadline: 35,
            keywordMatch: 25,
            sourceCredibility: 18,
            freshness: 14,
            completeness: 4
          },
          verifierNotes: 'Verified live HTTP 200 response on official Vercel terms page.',
          checkedUrls: ['https://vercel.com/events/deepseek-challenge-2026'],
          pipelineStep: 'verified'
        }
      };

      setHackathons(prev => [newDiscoveredHack, ...prev]);
    }, 2000);
  };

  const handleToggleBookmark = (id: string) => {
    setHackathons(prev => prev.map(h => h.id === id ? { ...h, bookmarked: !h.bookmarked } : h));
    setAiDeals(prev => prev.map(d => d.id === id ? { ...d, bookmarked: !d.bookmarked } : d));
  };

  const handleToggleAlert = (id: string) => {
    setHackathons(prev => prev.map(h => h.id === id ? { ...h, alertEnabled: !h.alertEnabled } : h));
    setAiDeals(prev => prev.map(d => d.id === id ? { ...d, alertEnabled: !d.alertEnabled } : d));
  };

  const handleToggleCompare = (hack: Hackathon) => {
    if (compareItems.some(i => i.id === hack.id)) {
      setCompareItems(prev => prev.filter(i => i.id !== hack.id));
    } else {
      if (compareItems.length >= 3) {
        alert('You can compare up to 3 hackathons side-by-side.');
        return;
      }
      setCompareItems(prev => [...prev, hack]);
    }
  };

  const handleAdminApprove = (signalId: string) => {
    const signal = unverifiedSignals.find(s => s.id === signalId);
    if (!signal) return;

    if (signal.candidateType === 'hackathon') {
      const ext = signal.extractedInfo as Partial<Hackathon>;
      const newHack: Hackathon = {
        id: `hack-approved-${Date.now()}`,
        title: ext.title || 'Approved Hackathon',
        organizer: ext.organizer || 'Ecosystem Partner',
        description: signal.rawText,
        registrationOpenAt: new Date().toISOString(),
        registrationDeadline: new Date(Date.now() + 20 * 24 * 60 * 60 * 1000).toISOString(),
        submissionDeadline: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
        mode: ext.mode || 'online',
        eligibleCountries: ['Worldwide'],
        eligibility: ['Developer'],
        teamMin: 1,
        teamMax: 4,
        prizeValue: ext.prizeValue || 10000,
        prizeCurrency: 'USD',
        technologies: ext.technologies || ['AI', 'Web'],
        officialUrl: signal.discoveredUrls[0] || 'https://devpost.com',
        discoverySources: [
          {
            type: 'x',
            url: `https://x.com/status/${signal.postId}`,
            author: signal.author,
            fetchedAt: new Date().toISOString(),
            tier: 'Tier 3 (Discovery Signal)'
          }
        ],
        verificationStatus: 'verified_active',
        confidenceScore: 0.92,
        lastCheckedAt: new Date().toISOString(),
        suitableReasons: [
          'Verified by DevRadar Admin Team',
          'Online Participation'
        ],
        effortEstimate: '1 Week',
        audit: {
          lastCheckedAt: new Date().toISOString(),
          confidenceScore: 0.92,
          scoreBreakdown: { statusAndDeadline: 35, keywordMatch: 23, sourceCredibility: 16, freshness: 14, completeness: 4 },
          verifierNotes: 'Manually verified target domain SSL and rules page by admin.',
          checkedUrls: signal.discoveredUrls,
          pipelineStep: 'verified'
        }
      };
      setHackathons(prev => [newHack, ...prev]);
    }
    setUnverifiedSignals(prev => prev.filter(s => s.id !== signalId));
  };

  const handleAdminReject = (signalId: string) => {
    setUnverifiedSignals(prev => prev.filter(s => s.id !== signalId));
  };

  const handleCommunitySubmit = (title: string, url: string, type: 'hackathon' | 'ai_deal') => {
    const newSig: UnverifiedSignal = {
      id: `sig-comm-${Date.now()}`,
      sourceType: 'x_post',
      postId: `comm-${Date.now()}`,
      author: '@community_member',
      rawText: `Community submission for ${title}: ${url}`,
      createdAt: new Date().toISOString(),
      discoveredUrls: [url],
      candidateType: type,
      extractedInfo: { title },
      verificationStatus: 'needs_review',
      confidenceScore: 0.65
    };
    setUnverifiedSignals(prev => [newSig, ...prev]);
  };

  // Filter Logic
  const filteredHackathons = useMemo(() => {
    return hackathons.filter(h => {
      if (filters.searchQuery) {
        const q = filters.searchQuery.toLowerCase();
        const matchesTitle = h.title.toLowerCase().includes(q);
        const matchesOrg = h.organizer.toLowerCase().includes(q);
        const matchesTech = h.technologies.some(t => t.toLowerCase().includes(q));
        if (!matchesTitle && !matchesOrg && !matchesTech) return false;
      }
      if (filters.mode !== 'all' && h.mode !== filters.mode) return false;
      if (filters.technology && !h.technologies.includes(filters.technology)) return false;
      if (filters.eligibility && !h.eligibility.includes(filters.eligibility)) return false;
      if (filters.verificationStatus && h.verificationStatus !== filters.verificationStatus) return false;
      if (filters.onlyBigPrizes && h.prizeValue < 10000) return false;
      if (filters.onlyClosingSoon) {
        const daysLeft = (new Date(h.registrationDeadline).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24);
        if (daysLeft > 14) return false;
      }
      return true;
    });
  }, [hackathons, filters]);

  const filteredDeals = useMemo(() => {
    return aiDeals.filter(d => {
      if (filters.searchQuery) {
        const q = filters.searchQuery.toLowerCase();
        const matchesName = d.productName.toLowerCase().includes(q);
        const matchesProvider = d.provider.toLowerCase().includes(q);
        const matchesTags = d.tags.some(t => t.toLowerCase().includes(q));
        if (!matchesName && !matchesProvider && !matchesTags) return false;
      }
      if (filters.offerType && d.offerType !== filters.offerType) return false;
      if (filters.verificationStatus && d.verificationStatus !== filters.verificationStatus) return false;
      return true;
    });
  }, [aiDeals, filters]);

  const bookmarkedHackathons = hackathons.filter(h => h.bookmarked);
  const bookmarkedDeals = aiDeals.filter(d => d.bookmarked);
  const totalBookmarks = bookmarkedHackathons.length + bookmarkedDeals.length;

  return (
    <div className="min-h-screen flex flex-col font-sans transition-colors duration-250 bg-[#F3F4EF] dark:bg-[#090C15] text-[#1C1B18] dark:text-[#F8FAF9]">
      
      {/* Top Header */}
      <Header
        filters={filters}
        setFilters={setFilters}
        bookmarkCount={totalBookmarks}
        unverifiedCount={unverifiedSignals.length}
        onOpenBookmarks={() => setIsBookmarksOpen(true)}
        onOpenSubmit={() => setIsSubmitOpen(true)}
        onOpenExtensionPanel={() => setIsExtensionOpen(true)}
        viewLayout={viewLayout}
        setViewLayout={setViewLayout}
        theme={theme}
        setTheme={setTheme}
      />

      {/* Main Content Area */}
      <main className="flex-1 pb-16">
        
        {/* Stats Overview Banner */}
        <StatsOverview
          totalPrizeValue={totalPrizePoolValue}
          totalHackathons={hackathons.length}
          totalDeals={aiDeals.length}
          unverifiedCount={unverifiedSignals.length}
        />

        {/* Module Switch: Search Hero & Radar Grid */}
        {filters.activeModule === 'hackathon' && (
          <div>
            <HeroSection
              filters={filters}
              setFilters={setFilters}
              totalResults={filteredHackathons.length}
              onTriggerLiveDiscovery={handleTriggerLiveDiscovery}
              isSearchingLive={isSearchingLive}
            />

            <div className="max-w-6xl mx-auto px-4 lg:px-8 pt-8">
              {filteredHackathons.length === 0 ? (
                <div className="sharetopus-card p-12 text-center rounded-[24px] space-y-3 bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-white">
                  <FilterX className="w-10 h-10 text-[#FF5A36] mx-auto" />
                  <h3 className="text-lg font-extrabold">No Hackathons Matched Your Filter</h3>
                  <p className="text-xs font-bold text-slate-700 dark:text-slate-300">Try resetting filters or switching search execution mode.</p>
                  <button 
                    onClick={() => setFilters(f => ({ ...f, searchQuery: '', mode: 'all', technology: '', onlyClosingSoon: false, onlyBigPrizes: false }))}
                    className="btn-sharetopus-secondary text-xs py-2 px-4 font-bold"
                  >
                    Reset All Filters
                  </button>
                </div>
              ) : (
                <div className={viewLayout === 'grid' ? "grid grid-cols-1 md:grid-cols-2 gap-6" : "space-y-4"}>
                  {filteredHackathons.map((hackathon) => (
                    <HackathonCard
                      key={hackathon.id}
                      hackathon={hackathon}
                      onSelect={(item) => setSelectedItem(item)}
                      onToggleBookmark={handleToggleBookmark}
                      onToggleAlert={handleToggleAlert}
                      onToggleCompare={handleToggleCompare}
                      isCompared={compareItems.some(i => i.id === hackathon.id)}
                      viewLayout={viewLayout}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* AI Deal Module */}
        {filters.activeModule === 'ai_deal' && (
          <div>
            <HeroSection
              filters={filters}
              setFilters={setFilters}
              totalResults={filteredDeals.length}
              onTriggerLiveDiscovery={handleTriggerLiveDiscovery}
              isSearchingLive={isSearchingLive}
            />

            <div className="max-w-6xl mx-auto px-4 lg:px-8 pt-8">
              {filteredDeals.length === 0 ? (
                <div className="sharetopus-card p-12 text-center rounded-[24px] space-y-3 bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-white">
                  <FilterX className="w-10 h-10 text-[#FF5A36] mx-auto" />
                  <h3 className="text-lg font-extrabold">No AI Deals Matched Your Filter</h3>
                  <p className="text-xs font-bold text-slate-700 dark:text-slate-300">Try selecting all offer types.</p>
                </div>
              ) : (
                <div className={viewLayout === 'grid' ? "grid grid-cols-1 md:grid-cols-2 gap-6" : "space-y-4"}>
                  {filteredDeals.map((deal) => (
                    <AIDealCard
                      key={deal.id}
                      deal={deal}
                      onSelect={(item) => setSelectedItem(item)}
                      onToggleBookmark={handleToggleBookmark}
                      onToggleAlert={handleToggleAlert}
                      viewLayout={viewLayout}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Pipeline Atlas */}
        {filters.activeModule === 'pipeline' && (
          <PipelineViewer />
        )}

        {/* Admin Review Queue */}
        {filters.activeModule === 'admin_queue' && (
          <AdminQueue
            signals={unverifiedSignals}
            onApprove={handleAdminApprove}
            onReject={handleAdminReject}
          />
        )}

      </main>

      {/* Floating Comparison Bar */}
      {compareItems.length > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 sharetopus-card px-6 py-3.5 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-white shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] flex items-center gap-4 text-xs font-mono font-extrabold">
          <span className="text-[#7C3AED] font-extrabold">
            Comparing {compareItems.length} Opportunity ({compareItems.map(i => i.title.substring(0, 15)).join(', ')}...)
          </span>
          <button
            onClick={() => setSelectedItem(compareItems[0])}
            className="btn-sharetopus-primary text-xs py-1.5 px-4 font-extrabold"
          >
            Open Side-by-Side Table
          </button>
          <button
            onClick={() => setCompareItems([])}
            className="text-[#1C1B18] hover:text-[#FF5A36] dark:text-white font-extrabold"
          >
            Clear
          </button>
        </div>
      )}

      {/* Modals & Drawers */}
      <DetailModal
        item={selectedItem}
        onClose={() => setSelectedItem(null)}
      />

      <CompareModal
        items={compareItems}
        onClose={() => setCompareItems([])}
        onRemove={(id) => setCompareItems(prev => prev.filter(i => i.id !== id))}
      />

      <ChromeExtensionSidePanel
        isOpen={isExtensionOpen}
        onClose={() => setIsExtensionOpen(false)}
      />

      <SubmitModal
        isOpen={isSubmitOpen}
        onClose={() => setIsSubmitOpen(false)}
        onSubmit={handleCommunitySubmit}
      />

      <BookmarksDrawer
        isOpen={isBookmarksOpen}
        onClose={() => setIsBookmarksOpen(false)}
        bookmarkedHackathons={bookmarkedHackathons}
        bookmarkedDeals={bookmarkedDeals}
        onRemoveBookmark={handleToggleBookmark}
        onToggleAlert={handleToggleAlert}
      />

      {/* Sharetopus Styled Footer */}
      <footer className="border-t border-[#D6D5CF] dark:border-slate-800 bg-[#E5E6DF] dark:bg-[#090C15] py-8 px-4 lg:px-8 text-xs font-mono text-[#1C1B18] dark:text-slate-200 font-bold">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-extrabold text-[#1C1B18] dark:text-white text-sm tracking-tight">DevRadar Intelligence</span>
            <span>• 100% Open Source (MIT) • No Login • Frictionless</span>
          </div>
          <div>
            Data Provenance: Tier 1 Official Domains + Tier 2 Aggregators + Tier 3 X Recent Search API
          </div>
        </div>
      </footer>

    </div>
  );
}

export default App;
