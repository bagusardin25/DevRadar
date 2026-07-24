import { useState, useMemo, useEffect, useCallback, useRef } from 'react';
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

import type { FilterState, Hackathon, AIDeal } from './types';
import {
  ApiError,
  type AdminMe,
  type CatalogueStats,
  type ReviewItem,
  adminLogout,
  approveReviewItem,
  fetchAIOffers,
  fetchAdminMe,
  fetchCatalogueStats,
  fetchHackathons,
  fetchReviewItems,
  loadAlertIds,
  loadBookmarkIds,
  rejectReviewItem,
  saveAlertIds,
  saveBookmarkIds,
  startAdminGithubLogin,
  startLiveDiscovery,
  toggleId,
  waitForDiscovery,
} from './api';
import { FilterX, Loader2, AlertCircle } from 'lucide-react';

const STORAGE_KEYS = {
  LAYOUT: 'devradar_layout_v1',
  THEME: 'devradar_theme_v1',
};

export function App() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.THEME);
    return saved === 'dark' || saved === 'light' ? saved : 'light';
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
    searchExecutionMode: 'indexed',
  });

  // Debounced catalogue query (ignore UI-only fields like activeModule / layout).
  const [queryFilters, setQueryFilters] = useState(filters);
  useEffect(() => {
    const t = window.setTimeout(() => {
      setQueryFilters((prev) => {
        const next: FilterState = {
          ...prev,
          searchQuery: filters.searchQuery,
          mode: filters.mode,
          region: filters.region,
          eligibility: filters.eligibility,
          technology: filters.technology,
          offerType: filters.offerType,
          verificationStatus: filters.verificationStatus,
          onlyClosingSoon: filters.onlyClosingSoon,
          onlyBigPrizes: filters.onlyBigPrizes,
          onlyFreeNoCard: filters.onlyFreeNoCard,
        };
        const same =
          prev.searchQuery === next.searchQuery &&
          prev.mode === next.mode &&
          prev.region === next.region &&
          prev.eligibility === next.eligibility &&
          prev.technology === next.technology &&
          prev.offerType === next.offerType &&
          prev.verificationStatus === next.verificationStatus &&
          prev.onlyClosingSoon === next.onlyClosingSoon &&
          prev.onlyBigPrizes === next.onlyBigPrizes &&
          prev.onlyFreeNoCard === next.onlyFreeNoCard;
        return same ? prev : next;
      });
    }, 300);
    return () => window.clearTimeout(t);
  }, [
    filters.searchQuery,
    filters.mode,
    filters.region,
    filters.eligibility,
    filters.technology,
    filters.offerType,
    filters.verificationStatus,
    filters.onlyClosingSoon,
    filters.onlyBigPrizes,
    filters.onlyFreeNoCard,
  ]);

  const [viewLayout, setViewLayout] = useState<'grid' | 'compact'>(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.LAYOUT);
    return saved === 'compact' || saved === 'grid' ? saved : 'grid';
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.LAYOUT, viewLayout);
  }, [viewLayout]);

  const [bookmarkIds, setBookmarkIds] = useState<Set<string>>(() => loadBookmarkIds());
  const [alertIds, setAlertIds] = useState<Set<string>>(() => loadAlertIds());
  /** Cache of bookmarked entities so the drawer works when filters change. */
  const [bookmarkCache, setBookmarkCache] = useState<{
    hackathons: Record<string, Hackathon>;
    deals: Record<string, AIDeal>;
  }>({ hackathons: {}, deals: {} });

  useEffect(() => {
    saveBookmarkIds(bookmarkIds);
  }, [bookmarkIds]);

  useEffect(() => {
    saveAlertIds(alertIds);
  }, [alertIds]);

  const [hackathons, setHackathons] = useState<Hackathon[]>([]);
  const [aiDeals, setAiDeals] = useState<AIDeal[]>([]);
  const [hackTotal, setHackTotal] = useState(0);
  const [dealTotal, setDealTotal] = useState(0);
  const [stats, setStats] = useState<CatalogueStats | null>(null);

  const [catalogueLoading, setCatalogueLoading] = useState(true);
  const [catalogueError, setCatalogueError] = useState<string | null>(null);

  const [selectedItem, setSelectedItem] = useState<Hackathon | AIDeal | null>(null);
  const [compareItems, setCompareItems] = useState<Hackathon[]>([]);

  const [isBookmarksOpen, setIsBookmarksOpen] = useState(false);
  const [isSubmitOpen, setIsSubmitOpen] = useState(false);
  const [isExtensionOpen, setIsExtensionOpen] = useState(false);
  const [isSearchingLive, setIsSearchingLive] = useState(false);
  const [liveDiscoveryMessage, setLiveDiscoveryMessage] = useState<string | null>(null);

  // Admin review state
  const [admin, setAdmin] = useState<AdminMe | null>(null);
  const [reviewItems, setReviewItems] = useState<ReviewItem[]>([]);
  const [reviewTotal, setReviewTotal] = useState(0);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

  const hackAbort = useRef<AbortController | null>(null);
  const dealAbort = useRef<AbortController | null>(null);

  const applyLocalFlags = useCallback(
    <T extends { id: string }>(items: T[]): (T & { bookmarked: boolean; alertEnabled: boolean })[] =>
      items.map((item) => ({
        ...item,
        bookmarked: bookmarkIds.has(item.id),
        alertEnabled: alertIds.has(item.id),
      })),
    [bookmarkIds, alertIds],
  );

  const loadCatalogue = useCallback(async () => {
    setCatalogueLoading(true);
    setCatalogueError(null);

    hackAbort.current?.abort();
    dealAbort.current?.abort();
    const hCtrl = new AbortController();
    const dCtrl = new AbortController();
    hackAbort.current = hCtrl;
    dealAbort.current = dCtrl;

    // Read prefs at call time so toggling bookmarks does not re-bind this callback.
    const bookmarks = loadBookmarkIds();
    const alerts = loadAlertIds();

    try {
      const [hackPage, dealPage, statsRes] = await Promise.all([
        fetchHackathons(queryFilters, {
          limit: 50,
          bookmarks,
          alerts,
          signal: hCtrl.signal,
        }),
        fetchAIOffers(queryFilters, {
          limit: 50,
          bookmarks,
          alerts,
          signal: dCtrl.signal,
        }),
        fetchCatalogueStats(hCtrl.signal).catch(() => null),
      ]);

      setHackathons(hackPage.items);
      setHackTotal(hackPage.totalEstimate);
      setAiDeals(dealPage.items);
      setDealTotal(dealPage.totalEstimate);
      if (statsRes) setStats(statsRes);
      // Refresh bookmark cache from freshly loaded rows that are still bookmarked.
      setBookmarkCache((prev) => {
        const nextH = { ...prev.hackathons };
        const nextD = { ...prev.deals };
        for (const h of hackPage.items) {
          if (bookmarks.has(h.id)) nextH[h.id] = h;
        }
        for (const d of dealPage.items) {
          if (bookmarks.has(d.id)) nextD[d.id] = d;
        }
        return { hackathons: nextH, deals: nextD };
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      const message =
        err instanceof ApiError
          ? err.detail
          : err instanceof Error
            ? err.message
            : 'Failed to load catalogue';
      setCatalogueError(message);
      setHackathons([]);
      setAiDeals([]);
    } finally {
      setCatalogueLoading(false);
    }
  }, [queryFilters]);

  useEffect(() => {
    void loadCatalogue();
  }, [loadCatalogue]);

  // Re-apply bookmark/alert flags without refetch when only local prefs change
  useEffect(() => {
    setHackathons((prev) => applyLocalFlags(prev));
    setAiDeals((prev) => applyLocalFlags(prev));
  }, [bookmarkIds, alertIds, applyLocalFlags]);
  const loadAdminSession = useCallback(async () => {
    try {
      const me = await fetchAdminMe();
      setAdmin(me);
      return me;
    } catch {
      setAdmin(null);
      return null;
    }
  }, []);

  const loadReviewQueue = useCallback(async () => {
    setReviewLoading(true);
    setReviewError(null);
    try {
      const me = admin ?? (await loadAdminSession());
      if (!me) {
        setReviewItems([]);
        setReviewTotal(0);
        setReviewError(null);
        return;
      }
      const data = await fetchReviewItems({ state: 'open', limit: 50 });
      setReviewItems(data.items);
      setReviewTotal(data.total);
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.detail
          : err instanceof Error
            ? err.message
            : 'Failed to load review queue';
      setReviewError(message);
      setReviewItems([]);
      setReviewTotal(0);
    } finally {
      setReviewLoading(false);
    }
  }, [admin, loadAdminSession]);

  useEffect(() => {
    if (filters.activeModule === 'admin_queue') {
      void loadReviewQueue();
    }
  }, [filters.activeModule, loadReviewQueue]);

  // After GitHub OAuth redirect
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('admin_auth') === 'ok') {
      void loadAdminSession().then(() => {
        setFilters((f) => ({ ...f, activeModule: 'admin_queue' }));
        window.history.replaceState({}, '', window.location.pathname);
      });
    }
  }, [loadAdminSession]);

  const handleTriggerLiveDiscovery = async () => {
    const q = filters.searchQuery.trim() || 'AI hackathon';
    setIsSearchingLive(true);
    setLiveDiscoveryMessage(null);
    try {
      const receipt = await startLiveDiscovery({
        query: q,
        connectors: ['devpost'],
        resultCap: 10,
      });
      setLiveDiscoveryMessage(receipt.message || `Discovery started (${receipt.status})`);
      await waitForDiscovery(receipt.id, { timeoutMs: 45_000 });
      await loadCatalogue();
      setLiveDiscoveryMessage('Live discovery finished — catalogue refreshed.');
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.detail
          : err instanceof Error
            ? err.message
            : 'Live discovery failed';
      setLiveDiscoveryMessage(message);
    } finally {
      setIsSearchingLive(false);
    }
  };

  const handleToggleBookmark = (id: string) => {
    setBookmarkIds((prev) => {
      const next = toggleId(prev, id);
      setBookmarkCache((cache) => {
        const hackathonsMap = { ...cache.hackathons };
        const dealsMap = { ...cache.deals };
        if (next.has(id)) {
          const h = hackathons.find((x) => x.id === id);
          const d = aiDeals.find((x) => x.id === id);
          if (h) hackathonsMap[id] = { ...h, bookmarked: true };
          if (d) dealsMap[id] = { ...d, bookmarked: true };
        } else {
          delete hackathonsMap[id];
          delete dealsMap[id];
        }
        return { hackathons: hackathonsMap, deals: dealsMap };
      });
      return next;
    });
  };

  const handleToggleAlert = (id: string) => {
    setAlertIds((prev) => toggleId(prev, id));
  };

  const handleToggleCompare = (hack: Hackathon) => {
    if (compareItems.some((i) => i.id === hack.id)) {
      setCompareItems((prev) => prev.filter((i) => i.id !== hack.id));
    } else {
      if (compareItems.length >= 3) {
        alert('You can compare up to 3 hackathons side-by-side.');
        return;
      }
      setCompareItems((prev) => [...prev, hack]);
    }
  };

  const handleAdminLogin = async () => {
    try {
      const url = await startAdminGithubLogin();
      window.location.href = url;
    } catch (err) {
      setReviewError(err instanceof Error ? err.message : 'Login start failed');
    }
  };

  const handleAdminLogout = async () => {
    if (!admin) return;
    try {
      await adminLogout(admin.csrfToken);
    } catch {
      /* still clear local session view */
    }
    setAdmin(null);
    setReviewItems([]);
    setReviewTotal(0);
  };

  const handleApprove = async (item: ReviewItem) => {
    if (!admin) throw new Error('Not signed in');
    await approveReviewItem(item.id, item.version, admin.csrfToken);
    await loadReviewQueue();
    await loadCatalogue();
  };

  const handleReject = async (item: ReviewItem) => {
    if (!admin) throw new Error('Not signed in');
    await rejectReviewItem(item.id, item.version, 'Rejected via admin UI', admin.csrfToken);
    await loadReviewQueue();
  };

  const totalPrizePoolValue = useMemo(() => {
    return hackathons.reduce((sum, h) => sum + (Number.isFinite(h.prizeValue) ? h.prizeValue : 0), 0);
  }, [hackathons]);

  const bookmarkedHackathons = useMemo(() => {
    return [...bookmarkIds]
      .map((id) => bookmarkCache.hackathons[id] ?? hackathons.find((h) => h.id === id))
      .filter((h): h is Hackathon => Boolean(h))
      .map((h) => ({ ...h, bookmarked: true, alertEnabled: alertIds.has(h.id) }));
  }, [bookmarkIds, bookmarkCache.hackathons, hackathons, alertIds]);

  const bookmarkedDeals = useMemo(() => {
    return [...bookmarkIds]
      .map((id) => bookmarkCache.deals[id] ?? aiDeals.find((d) => d.id === id))
      .filter((d): d is AIDeal => Boolean(d))
      .map((d) => ({ ...d, bookmarked: true, alertEnabled: alertIds.has(d.id) }));
  }, [bookmarkIds, bookmarkCache.deals, aiDeals, alertIds]);

  const totalBookmarks = bookmarkIds.size;

  const displayHackCount = stats?.hackathonsActive ?? hackTotal;
  const displayDealCount = stats?.aiOffersActive ?? dealTotal;

  return (
    <div className="min-h-screen flex flex-col font-sans transition-colors duration-250 bg-[#F3F4EF] dark:bg-[#090C15] text-[#1C1B18] dark:text-[#F8FAF9]">
      <Header
        filters={filters}
        setFilters={setFilters}
        bookmarkCount={totalBookmarks}
        unverifiedCount={reviewTotal}
        onOpenBookmarks={() => setIsBookmarksOpen(true)}
        onOpenSubmit={() => setIsSubmitOpen(true)}
        onOpenExtensionPanel={() => setIsExtensionOpen(true)}
        viewLayout={viewLayout}
        setViewLayout={setViewLayout}
        theme={theme}
        setTheme={setTheme}
      />

      <main className="flex-1 pb-16">
        <StatsOverview
          totalPrizeValue={totalPrizePoolValue}
          totalHackathons={displayHackCount}
          totalDeals={displayDealCount}
          unverifiedCount={reviewTotal}
        />

        {catalogueError && filters.activeModule !== 'admin_queue' && filters.activeModule !== 'pipeline' && (
          <div className="max-w-6xl mx-auto px-4 lg:px-8 pt-4">
            <div className="sharetopus-card p-4 rounded-2xl border-[1.5px] border-[#FF5A36] bg-[#FF5A36]/10 flex items-start gap-3 text-xs font-bold">
              <AlertCircle className="w-5 h-5 text-[#FF5A36] shrink-0" />
              <div>
                <div className="font-extrabold">Could not load catalogue from API</div>
                <p className="mt-1 opacity-90">{catalogueError}</p>
                <p className="mt-1 text-[11px] font-mono opacity-70">
                  Ensure the backend is running and Vite proxy targets it (default http://127.0.0.1:8000).
                </p>
                <button
                  type="button"
                  onClick={() => void loadCatalogue()}
                  className="btn-sharetopus-secondary text-xs py-1.5 px-3 mt-2 font-bold"
                >
                  Retry
                </button>
              </div>
            </div>
          </div>
        )}

        {liveDiscoveryMessage && (
          <div className="max-w-6xl mx-auto px-4 lg:px-8 pt-3">
            <div className="text-xs font-bold font-mono px-3 py-2 rounded-xl bg-white dark:bg-[#131A29] border border-[#1C1B18] dark:border-[#D6DCE5]">
              {liveDiscoveryMessage}
            </div>
          </div>
        )}

        {filters.activeModule === 'hackathon' && (
          <div>
            <HeroSection
              filters={filters}
              setFilters={setFilters}
              totalResults={hackTotal || hackathons.length}
              onTriggerLiveDiscovery={() => void handleTriggerLiveDiscovery()}
              isSearchingLive={isSearchingLive}
            />

            <div className="max-w-6xl mx-auto px-4 lg:px-8 pt-8">
              {catalogueLoading ? (
                <div className="sharetopus-card p-12 text-center rounded-[24px] bg-white dark:bg-[#131A29]">
                  <Loader2 className="w-8 h-8 animate-spin text-[#FF5A36] mx-auto mb-3" />
                  <p className="text-xs font-bold">Loading verified hackathons…</p>
                </div>
              ) : hackathons.length === 0 ? (
                <div className="sharetopus-card p-12 text-center rounded-[24px] space-y-3 bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-white">
                  <FilterX className="w-10 h-10 text-[#FF5A36] mx-auto" />
                  <h3 className="text-lg font-extrabold">No Hackathons Matched Your Filter</h3>
                  <p className="text-xs font-bold text-slate-700 dark:text-slate-300">
                    Try resetting filters, or wait until listings are approved in the review queue.
                  </p>
                  <button
                    type="button"
                    onClick={() =>
                      setFilters((f) => ({
                        ...f,
                        searchQuery: '',
                        mode: 'all',
                        technology: '',
                        onlyClosingSoon: false,
                        onlyBigPrizes: false,
                      }))
                    }
                    className="btn-sharetopus-secondary text-xs py-2 px-4 font-bold"
                  >
                    Reset All Filters
                  </button>
                </div>
              ) : (
                <div
                  className={
                    viewLayout === 'grid' ? 'grid grid-cols-1 md:grid-cols-2 gap-6' : 'space-y-4'
                  }
                >
                  {hackathons.map((hackathon) => (
                    <HackathonCard
                      key={hackathon.id}
                      hackathon={hackathon}
                      onSelect={(item) => setSelectedItem(item)}
                      onToggleBookmark={handleToggleBookmark}
                      onToggleAlert={handleToggleAlert}
                      onToggleCompare={handleToggleCompare}
                      isCompared={compareItems.some((i) => i.id === hackathon.id)}
                      viewLayout={viewLayout}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {filters.activeModule === 'ai_deal' && (
          <div>
            <HeroSection
              filters={filters}
              setFilters={setFilters}
              totalResults={dealTotal || aiDeals.length}
              onTriggerLiveDiscovery={() => void handleTriggerLiveDiscovery()}
              isSearchingLive={isSearchingLive}
            />

            <div className="max-w-6xl mx-auto px-4 lg:px-8 pt-8">
              {catalogueLoading ? (
                <div className="sharetopus-card p-12 text-center rounded-[24px] bg-white dark:bg-[#131A29]">
                  <Loader2 className="w-8 h-8 animate-spin text-[#7C3AED] mx-auto mb-3" />
                  <p className="text-xs font-bold">Loading AI offers…</p>
                </div>
              ) : aiDeals.length === 0 ? (
                <div className="sharetopus-card p-12 text-center rounded-[24px] space-y-3 bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-white">
                  <FilterX className="w-10 h-10 text-[#FF5A36] mx-auto" />
                  <h3 className="text-lg font-extrabold">No AI Deals Matched Your Filter</h3>
                  <p className="text-xs font-bold text-slate-700 dark:text-slate-300">
                    Try selecting all offer types or clearing search.
                  </p>
                </div>
              ) : (
                <div
                  className={
                    viewLayout === 'grid' ? 'grid grid-cols-1 md:grid-cols-2 gap-6' : 'space-y-4'
                  }
                >
                  {aiDeals.map((deal) => (
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

        {filters.activeModule === 'pipeline' && <PipelineViewer />}

        {filters.activeModule === 'admin_queue' && (
          <AdminQueue
            items={reviewItems}
            total={reviewTotal}
            admin={admin}
            loading={reviewLoading}
            error={reviewError}
            onRefresh={() => void loadReviewQueue()}
            onLogin={() => void handleAdminLogin()}
            onLogout={() => void handleAdminLogout()}
            onApprove={handleApprove}
            onReject={handleReject}
          />
        )}
      </main>

      {compareItems.length > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 sharetopus-card px-6 py-3.5 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-white shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] flex items-center gap-4 text-xs font-mono font-extrabold">
          <span className="text-[#7C3AED] font-extrabold">
            Comparing {compareItems.length} Opportunity (
            {compareItems.map((i) => i.title.substring(0, 15)).join(', ')}...)
          </span>
          <button
            type="button"
            onClick={() => setSelectedItem(compareItems[0])}
            className="btn-sharetopus-primary text-xs py-1.5 px-4 font-extrabold"
          >
            Open Side-by-Side Table
          </button>
          <button
            type="button"
            onClick={() => setCompareItems([])}
            className="text-[#1C1B18] hover:text-[#FF5A36] dark:text-white font-extrabold"
          >
            Clear
          </button>
        </div>
      )}

      <DetailModal item={selectedItem} onClose={() => setSelectedItem(null)} />

      <CompareModal
        items={compareItems}
        onClose={() => setCompareItems([])}
        onRemove={(id) => setCompareItems((prev) => prev.filter((i) => i.id !== id))}
      />

      <ChromeExtensionSidePanel
        isOpen={isExtensionOpen}
        onClose={() => setIsExtensionOpen(false)}
      />

      <SubmitModal
        isOpen={isSubmitOpen}
        onClose={() => setIsSubmitOpen(false)}
        onSubmitted={() => {
          if (filters.activeModule === 'admin_queue') void loadReviewQueue();
        }}
      />

      <BookmarksDrawer
        isOpen={isBookmarksOpen}
        onClose={() => setIsBookmarksOpen(false)}
        bookmarkedHackathons={bookmarkedHackathons}
        bookmarkedDeals={bookmarkedDeals}
        onRemoveBookmark={handleToggleBookmark}
        onToggleAlert={handleToggleAlert}
      />

      <footer className="border-t border-[#D6D5CF] dark:border-slate-800 bg-[#E5E6DF] dark:bg-[#090C15] py-8 px-4 lg:px-8 text-xs font-mono text-[#1C1B18] dark:text-slate-200 font-bold">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-extrabold text-[#1C1B18] dark:text-white text-sm tracking-tight">
              DevRadar Intelligence
            </span>
            <span>• 100% Open Source (MIT) • No Login • Frictionless</span>
          </div>
          <div>
            Data: live API · Tier 1 Official Domains + Tier 2 Aggregators + Tier 3 Discovery
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
