import { useState, useMemo, useEffect, useCallback, useRef, lazy, Suspense } from 'react';
import { Header } from './components/Header';
import { HeroSection } from './components/HeroSection';
import { StatsOverview } from './components/StatsOverview';
import { HackathonCard } from './components/HackathonCard';
import { AIDealCard } from './components/AIDealCard';
import { DetailModal } from './components/DetailModal';
import { CompareModal } from './components/CompareModal';
import { SubmitModal } from './components/SubmitModal';
import { BookmarksDrawer } from './components/BookmarksDrawer';
import { AlertSubscribeModal } from './components/AlertSubscribeModal';
import { Pagination } from './components/Pagination';

import type { FilterState, Hackathon, AIDeal, VerificationStatus } from './types';
import {
  ApiError,
  type AdminMe,
  type CatalogueStats,
  type ReviewCorrections,
  type ReviewItem,
  adminLogout,
  approveReviewItem,
  fetchAIOffers,
  fetchAdminMe,
  fetchCatalogueStats,
  fetchHackathons,
  fetchReviewItems,
  loadAlertIds,
  describeDiscoveryResult,
  loadBookmarkIds,
  loadBookmarkSnapshots,
  saveBookmarkSnapshots,
  reconcileSnapshots,
  upsertSnapshot,
  removeSnapshot,
  parseShareIdsFromSearch,
  rejectReviewItem,
  saveAlertIds,
  saveBookmarkIds,
  startAdminGoogleLogin,
  startLiveDiscovery,
  toggleId,
  waitForDiscovery,
} from './api';
import { MOCK_HACKATHONS, MOCK_AI_DEALS } from './data/mockData';
import { FilterX, Loader2, WifiOff } from 'lucide-react';

/** Heavy admin / tooling views — split out of the initial catalogue bundle. */
const PipelineViewer = lazy(() =>
  import('./components/PipelineViewer').then((m) => ({ default: m.PipelineViewer })),
);
const AdminQueue = lazy(() =>
  import('./components/AdminQueue').then((m) => ({ default: m.AdminQueue })),
);
const AdminCatalogueManager = lazy(() =>
  import('./components/AdminCatalogueManager').then((m) => ({ default: m.AdminCatalogueManager })),
);
const ChromeExtensionSidePanel = lazy(() =>
  import('./components/ChromeExtensionSidePanel').then((m) => ({
    default: m.ChromeExtensionSidePanel,
  })),
);
const SourcesManager = lazy(() =>
  import('./components/SourcesManager').then((m) => ({ default: m.SourcesManager })),
);

function ModuleFallback() {
  return (
    <div className="max-w-6xl mx-auto px-4 lg:px-8 pt-10 flex items-center justify-center gap-2 text-xs font-bold">
      <Loader2 className="w-5 h-5 animate-spin text-[#FF5A36]" />
      Loading module…
    </div>
  );
}

const STORAGE_KEYS = {
  LAYOUT: 'devradar_layout_v1',
  THEME: 'devradar_theme_v1',
};

/** Filter mock hackathons locally when backend is offline. */
function filterMockHackathons(items: Hackathon[], filters: FilterState): Hackathon[] {
  return items.filter((h) => {
    const q = filters.searchQuery.toLowerCase();
    if (q && q.length >= 2) {
      const searchable = `${h.title} ${h.organizer} ${h.description} ${h.technologies.join(' ')} ${h.eligibility.join(' ')} ${h.eligibleCountries.join(' ')}`.toLowerCase();
      if (!searchable.includes(q)) return false;
    }
    if (filters.mode !== 'all' && h.mode !== filters.mode) return false;
    if (filters.technology && !h.technologies.some((t) => t.toLowerCase().includes(filters.technology.toLowerCase()))) return false;
    if (filters.eligibility && !h.eligibility.some((e) => e.toLowerCase().includes(filters.eligibility.toLowerCase()))) return false;
    if (filters.verificationStatus && h.verificationStatus !== filters.verificationStatus) return false;
    if (filters.onlyClosingSoon) {
      const deadline = new Date(h.registrationDeadline);
      const diffDays = (deadline.getTime() - Date.now()) / (1000 * 60 * 60 * 24);
      if (diffDays > 14 || diffDays < 0) return false;
    }
    if (filters.onlyBigPrizes && h.prizeValue < 10000) return false;
    return true;
  });
}

/** Filter mock AI deals locally when backend is offline. */
function filterMockAIDeals(items: AIDeal[], filters: FilterState): AIDeal[] {
  return items.filter((d) => {
    const q = filters.searchQuery.toLowerCase();
    if (q && q.length >= 2) {
      const searchable = `${d.productName} ${d.provider} ${d.description} ${d.tags.join(' ')} ${d.offerValue} ${d.targetUsers.join(' ')}`.toLowerCase();
      if (!searchable.includes(q)) return false;
    }
    if (filters.offerType && d.offerType !== filters.offerType) return false;
    if (filters.verificationStatus && d.verificationStatus !== filters.verificationStatus) return false;
    if (filters.technology && !d.tags.some((t) => t.toLowerCase().includes(filters.technology.toLowerCase()))) return false;
    if (filters.onlyFreeNoCard) {
      const reqText = d.requirements.join(' ').toLowerCase();
      if (reqText.includes('credit card')) return false;
    }
    return true;
  });
}

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

  // Pause marquee / continuous work when the tab is not visible
  useEffect(() => {
    const onVis = () => {
      document.documentElement.classList.toggle('tab-hidden', document.hidden);
    };
    onVis();
    document.addEventListener('visibilitychange', onVis);
    return () => document.removeEventListener('visibilitychange', onVis);
  }, []);

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
  /** Cache of bookmarked entities so the drawer works when filters change.
      Persisted to localStorage — without persistence, a bookmark whose id
      isn't on the currently-loaded catalogue page vanishes from the drawer. */
  const [bookmarkCache, setBookmarkCache] = useState<{
    hackathons: Record<string, Hackathon>;
    deals: Record<string, AIDeal>;
  }>(() => loadBookmarkSnapshots());

  useEffect(() => {
    saveBookmarkIds(bookmarkIds);
  }, [bookmarkIds]);

  // Any change to the cache — refresh from a new fetch, toggle add, toggle
  // remove — has to make it to storage; otherwise a reload puts us right back
  // in the original bug.
  useEffect(() => {
    saveBookmarkSnapshots(bookmarkCache);
  }, [bookmarkCache]);

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
  const [isAlertModalOpen, setIsAlertModalOpen] = useState(false);
  const [alertConfirmMsg, setAlertConfirmMsg] = useState<string | null>(null);
  /** Read-only shared bookmark ids from ?bm= / ?bookmarks= (does not overwrite local). */
  const [sharedBookmarkIds, setSharedBookmarkIds] = useState<string[] | null>(null);
  const [isSearchingLive, setIsSearchingLive] = useState(false);
  const [liveDiscoveryMessage, setLiveDiscoveryMessage] = useState<string | null>(null);
  const [, setIsOfflineMode] = useState(false);

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
      setIsOfflineMode(false);
      // Refresh cached snapshots for any bookmarked row that reappeared in this
      // page, and drop snapshots whose id is no longer bookmarked at all.
      setBookmarkCache((prev) =>
        reconcileSnapshots(prev, bookmarks, {
          hackathons: hackPage.items,
          deals: dealPage.items,
        }),
      );
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      const message =
        err instanceof ApiError
          ? err.detail
          : err instanceof Error
            ? err.message
            : 'Failed to load catalogue';
      setCatalogueError(message);
      // Fallback to mock data so the UI is never empty during offline dev
      const bookmarks = loadBookmarkIds();
      const alerts = loadAlertIds();
      const filteredH = filterMockHackathons(MOCK_HACKATHONS, queryFilters);
      const filteredD = filterMockAIDeals(MOCK_AI_DEALS, queryFilters);
      const mockH = filteredH.map((h) => ({
        ...h,
        bookmarked: bookmarks.has(h.id),
        alertEnabled: alerts.has(h.id),
      }));
      const mockD = filteredD.map((d) => ({
        ...d,
        bookmarked: bookmarks.has(d.id),
        alertEnabled: alerts.has(d.id),
      }));
      setHackathons(mockH);
      setHackTotal(mockH.length);
      setAiDeals(mockD);
      setDealTotal(mockD.length);
      setIsOfflineMode(true);
    } finally {
      setCatalogueLoading(false);
    }
  }, [queryFilters]);

  useEffect(() => {
    void loadCatalogue();
  }, [loadCatalogue]);

  // Pagination & Rows Per Page State
  const [rowsPerPage, setRowsPerPage] = useState<number>(12);
  const [currentPage, setCurrentPage] = useState<number>(1);

  // Reset pagination to page 1 whenever filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [filters]);

  // Derive flags in memory — avoids remapping + setState of the full catalogue
  const displayHackathons = useMemo(
    () => applyLocalFlags(hackathons),
    [hackathons, applyLocalFlags],
  );
  const displayAiDeals = useMemo(
    () => applyLocalFlags(aiDeals),
    [aiDeals, applyLocalFlags],
  );

  /**
   * How many loaded rows are actually `verified_active`, or undefined when the
   * loaded set is smaller than the server-side total. Reporting a verified
   * count measured over 50 rows against a total of 300 would be misleading, so
   * in that case the header shows the plain total instead.
   */
  const countVerified = useCallback(
    (rows: Array<{ verificationStatus: VerificationStatus }>, total: number) =>
      rows.length >= total
        ? rows.filter((r) => r.verificationStatus === 'verified_active').length
        : undefined,
    [],
  );

  const verifiedHackathonCount = useMemo(
    () => countVerified(displayHackathons, hackTotal || displayHackathons.length),
    [countVerified, displayHackathons, hackTotal],
  );
  const verifiedDealCount = useMemo(
    () => countVerified(displayAiDeals, dealTotal || displayAiDeals.length),
    [countVerified, displayAiDeals, dealTotal],
  );

  const paginatedHackathons = useMemo(() => {
    if (rowsPerPage === 0) return displayHackathons;
    const start = (currentPage - 1) * rowsPerPage;
    return displayHackathons.slice(start, start + rowsPerPage);
  }, [displayHackathons, currentPage, rowsPerPage]);

  const paginatedAiDeals = useMemo(() => {
    if (rowsPerPage === 0) return displayAiDeals;
    const start = (currentPage - 1) * rowsPerPage;
    return displayAiDeals.slice(start, start + rowsPerPage);
  }, [displayAiDeals, currentPage, rowsPerPage]);

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

  // After Google OAuth redirect, alert confirmation, or shared bookmark link
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('admin_auth') === 'ok') {
      void loadAdminSession().then(() => {
        setFilters((f) => ({ ...f, activeModule: 'admin_queue' }));
        window.history.replaceState({}, '', window.location.pathname);
      });
    }
    if (params.get('admin_auth') === 'error') {
      const reason = params.get('reason') || 'unknown_error';
      setReviewError(`Google login failed: ${reason}`);
      setFilters((f) => ({ ...f, activeModule: 'admin_queue' }));
      window.history.replaceState({}, '', window.location.pathname);
    }
    if (params.get('alert') === 'confirmed') {
      setAlertConfirmMsg('✅ Email alert subscription confirmed! You will receive notifications.');
      window.history.replaceState({}, '', window.location.pathname);
    }
    if (params.get('alert') === 'unsubscribed') {
      setAlertConfirmMsg('You have been unsubscribed from DevRadar email alerts.');
      window.history.replaceState({}, '', window.location.pathname);
    }
    const shared = parseShareIdsFromSearch(window.location.search);
    if (shared.length > 0) {
      setSharedBookmarkIds(shared);
      setIsBookmarksOpen(true);
      // Keep ?bm= in the URL so the link remains shareable while viewing.
    }
  }, [loadAdminSession]);

  const handleTriggerLiveDiscovery = async () => {
    const trimmed = filters.searchQuery.trim();
    const q = trimmed.length >= 2 ? trimmed : 'AI hackathon';
    setIsSearchingLive(true);
    setLiveDiscoveryMessage(null);
    try {
      const receipt = await startLiveDiscovery({
        query: q,
        module: filters.activeModule === 'ai_deal' ? 'ai_offer' : 'hackathon',
        resultCap: 10,
      });
      setLiveDiscoveryMessage(receipt.message || `Discovery started (${receipt.status})`);
      const result = await waitForDiscovery(receipt.id, { timeoutMs: 45_000 });
      // Only claim a refresh when the run actually published something.
      if (result.published > 0) {
        await loadCatalogue();
      }
      setLiveDiscoveryMessage(describeDiscoveryResult(result));
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

  const handleToggleBookmark = useCallback((id: string) => {
    setBookmarkIds((prev) => {
      const next = toggleId(prev, id);
      setBookmarkCache((cache) => {
        if (next.has(id)) {
          const h = hackathons.find((x) => x.id === id);
          if (h) return upsertSnapshot(cache, h, 'hackathon');
          const d = aiDeals.find((x) => x.id === id);
          if (d) return upsertSnapshot(cache, d, 'ai_deal');
          return cache;
        }
        return removeSnapshot(cache, id);
      });
      return next;
    });
  }, [hackathons, aiDeals]);

  const handleToggleAlert = useCallback((id: string) => {
    setAlertIds((prev) => toggleId(prev, id));
  }, []);

  const handleToggleCompare = useCallback((hack: Hackathon) => {
    setCompareItems((prev) => {
      if (prev.some((i) => i.id === hack.id)) {
        return prev.filter((i) => i.id !== hack.id);
      }
      if (prev.length >= 3) {
        alert('You can compare up to 3 hackathons side-by-side.');
        return prev;
      }
      return [...prev, hack];
    });
  }, []);

  const handleSelectItem = useCallback((item: Hackathon | AIDeal) => {
    setSelectedItem(item);
  }, []);

  const handleAdminLogin = async () => {
    try {
      const url = await startAdminGoogleLogin();
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

  const handleApprove = async (
    item: ReviewItem,
    corrections: ReviewCorrections = {},
    notes?: string,
  ) => {
    if (!admin) throw new Error('Not signed in');
    await approveReviewItem(item.id, item.version, admin.csrfToken, notes, corrections);
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

  /** Shared-link view: resolve ids against cache + loaded catalogue (read-only). */
  const sharedHackathons = useMemo(() => {
    if (!sharedBookmarkIds?.length) return [];
    return sharedBookmarkIds
      .map(
        (id) =>
          bookmarkCache.hackathons[id] ??
          hackathons.find((h) => h.id === id) ??
          bookmarkedHackathons.find((h) => h.id === id),
      )
      .filter((h): h is Hackathon => Boolean(h))
      .map((h) => ({ ...h, bookmarked: bookmarkIds.has(h.id), alertEnabled: alertIds.has(h.id) }));
  }, [
    sharedBookmarkIds,
    bookmarkCache.hackathons,
    hackathons,
    bookmarkedHackathons,
    bookmarkIds,
    alertIds,
  ]);

  const sharedDeals = useMemo(() => {
    if (!sharedBookmarkIds?.length) return [];
    return sharedBookmarkIds
      .map(
        (id) =>
          bookmarkCache.deals[id] ??
          aiDeals.find((d) => d.id === id) ??
          bookmarkedDeals.find((d) => d.id === id),
      )
      .filter((d): d is AIDeal => Boolean(d))
      .map((d) => ({ ...d, bookmarked: bookmarkIds.has(d.id), alertEnabled: alertIds.has(d.id) }));
  }, [sharedBookmarkIds, bookmarkCache.deals, aiDeals, bookmarkedDeals, bookmarkIds, alertIds]);

  const totalBookmarks = bookmarkIds.size;

  const handleImportBookmarkIds = useCallback((ids: string[], mode: 'merge' | 'replace') => {
    setBookmarkIds((prev) => {
      if (mode === 'replace') return new Set(ids);
      const next = new Set(prev);
      for (const id of ids) next.add(id);
      return next;
    });
  }, []);

  const handleSaveSharedToLocal = useCallback(() => {
    if (!sharedBookmarkIds?.length) return;
    setBookmarkIds((prev) => {
      const next = new Set(prev);
      for (const id of sharedBookmarkIds) next.add(id);
      return next;
    });
    setSharedBookmarkIds(null);
    window.history.replaceState({}, '', window.location.pathname);
  }, [sharedBookmarkIds]);

  const handleClearShared = useCallback(() => {
    setSharedBookmarkIds(null);
    window.history.replaceState({}, '', window.location.pathname);
  }, []);

  const displayHackCount = stats?.hackathonsActive ?? hackTotal;
  const displayDealCount = stats?.aiOffersActive ?? dealTotal;

  return (
    <div className="min-h-screen flex flex-col font-sans transition-colors duration-250 bg-[#F3F4EF] dark:bg-[#090C15] text-[#1C1B18] dark:text-[#F8FAF9]">
      <Header
        filters={filters}
        setFilters={setFilters}
        bookmarkCount={totalBookmarks}
        unverifiedCount={reviewTotal}
        showAdminNav={Boolean(admin)}
        hackathons={displayHackathons}
        aiDeals={displayAiDeals}
        onOpenBookmarks={() => setIsBookmarksOpen(true)}
        onOpenSubmit={() => setIsSubmitOpen(true)}
        onOpenExtensionPanel={() => setIsExtensionOpen(true)}
        onOpenAlerts={() => setIsAlertModalOpen(true)}
        onOpenAdmin={() => setFilters((f) => ({ ...f, activeModule: 'admin_queue' }))}
        viewLayout={viewLayout}
        setViewLayout={setViewLayout}
        theme={theme}
        setTheme={setTheme}
      />

      <main className="flex-1 pb-16">
        {filters.activeModule !== 'admin_queue' || admin ? (
          <StatsOverview
            totalPrizeValue={totalPrizePoolValue}
            totalHackathons={displayHackCount}
            totalDeals={displayDealCount}
            unverifiedCount={reviewTotal}
            showQueueStat={Boolean(admin)}
          />
        ) : null}

        {catalogueError &&
          filters.activeModule !== 'admin_queue' &&
          filters.activeModule !== 'pipeline' &&
          filters.activeModule !== 'catalogue' && (
          <div className="max-w-6xl mx-auto px-4 lg:px-8 pt-4">
            <div className="sharetopus-card p-4 rounded-2xl border-[1.5px] border-[#D97706] bg-[#D97706]/10 flex items-start gap-3 text-xs font-bold text-[#1C1B18] dark:text-[#F8FAF9]">
              <WifiOff className="w-5 h-5 text-[#D97706] shrink-0" />
              <div>
                <div className="font-extrabold">Backend Offline — Showing Demo Data</div>
                <p className="mt-1 opacity-90">{catalogueError}</p>
                <p className="mt-1 text-[11px] font-mono opacity-70">
                  Start the backend (uvicorn app.main:app) at http://127.0.0.1:8000 to load real data.
                </p>
                <button
                  type="button"
                  onClick={() => { setIsOfflineMode(false); void loadCatalogue(); }}
                  className="btn-sharetopus-secondary text-xs py-1.5 px-3 mt-2 font-bold"
                >
                  Retry Connection
                </button>
              </div>
            </div>
          </div>
        )}

        {alertConfirmMsg && (
          <div className="max-w-6xl mx-auto px-4 lg:px-8 pt-3">
            <div className="sharetopus-card p-3 rounded-2xl border-[1.5px] border-[#059669] bg-[#059669]/10 flex items-center justify-between text-xs font-bold text-[#059669] dark:text-[#34D399]">
              <span>{alertConfirmMsg}</span>
              <button type="button" onClick={() => setAlertConfirmMsg(null)} className="font-extrabold hover:opacity-70">×</button>
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
              verifiedCount={verifiedHackathonCount}
              onTriggerLiveDiscovery={() => void handleTriggerLiveDiscovery()}
              isSearchingLive={isSearchingLive}
            />

            <div className="max-w-6xl mx-auto px-4 lg:px-8 pt-8">
              {catalogueLoading ? (
                <div className="sharetopus-card p-12 text-center rounded-[24px] bg-white dark:bg-[#131A29]">
                  <Loader2 className="w-8 h-8 animate-spin text-[#FF5A36] mx-auto mb-3" />
                  <p className="text-xs font-bold">Loading verified hackathons…</p>
                </div>
              ) : displayHackathons.length === 0 ? (
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
                <div className="space-y-6">
                  <div
                    className={
                      viewLayout === 'grid'
                        ? 'grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6'
                        : 'space-y-4'
                    }
                  >
                    {paginatedHackathons.map((hackathon) => (
                      <HackathonCard
                        key={hackathon.id}
                        hackathon={hackathon}
                        onSelect={handleSelectItem}
                        onToggleBookmark={handleToggleBookmark}
                        onToggleAlert={handleToggleAlert}
                        onToggleCompare={handleToggleCompare}
                        isCompared={compareItems.some((i) => i.id === hackathon.id)}
                        viewLayout={viewLayout}
                      />
                    ))}
                  </div>

                  <Pagination
                    currentPage={currentPage}
                    totalItems={displayHackathons.length}
                    rowsPerPage={rowsPerPage}
                    onPageChange={(p) => {
                      setCurrentPage(p);
                      window.scrollTo({ top: 400, behavior: 'smooth' });
                    }}
                    onRowsPerPageChange={(r) => {
                      setRowsPerPage(r);
                      setCurrentPage(1);
                    }}
                  />
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
              verifiedCount={verifiedDealCount}
              onTriggerLiveDiscovery={() => void handleTriggerLiveDiscovery()}
              isSearchingLive={isSearchingLive}
            />

            <div className="max-w-6xl mx-auto px-4 lg:px-8 pt-8">
              {catalogueLoading ? (
                <div className="sharetopus-card p-12 text-center rounded-[24px] bg-white dark:bg-[#131A29]">
                  <Loader2 className="w-8 h-8 animate-spin text-[#7C3AED] mx-auto mb-3" />
                  <p className="text-xs font-bold">Loading AI offers…</p>
                </div>
              ) : displayAiDeals.length === 0 ? (
                <div className="sharetopus-card p-12 text-center rounded-[24px] space-y-3 bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-white">
                  <FilterX className="w-10 h-10 text-[#FF5A36] mx-auto" />
                  <h3 className="text-lg font-extrabold">No AI Deals Matched Your Filter</h3>
                  <p className="text-xs font-bold text-slate-700 dark:text-slate-300">
                    Try selecting all offer types or clearing search.
                  </p>
                </div>
              ) : (
                <div className="space-y-6">
                  <div
                    className={
                      viewLayout === 'grid'
                        ? 'grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6'
                        : 'space-y-4'
                    }
                  >
                    {paginatedAiDeals.map((deal) => (
                      <AIDealCard
                        key={deal.id}
                        deal={deal}
                        onSelect={handleSelectItem}
                        onToggleBookmark={handleToggleBookmark}
                        onToggleAlert={handleToggleAlert}
                        viewLayout={viewLayout}
                      />
                    ))}
                  </div>

                  <Pagination
                    currentPage={currentPage}
                    totalItems={displayAiDeals.length}
                    rowsPerPage={rowsPerPage}
                    onPageChange={(p) => {
                      setCurrentPage(p);
                      window.scrollTo({ top: 400, behavior: 'smooth' });
                    }}
                    onRowsPerPageChange={(r) => {
                      setRowsPerPage(r);
                      setCurrentPage(1);
                    }}
                  />
                </div>
              )}
            </div>
          </div>
        )}

        {filters.activeModule === 'catalogue' && admin && (
          <Suspense fallback={<ModuleFallback />}>
            <AdminCatalogueManager
              admin={admin}
              onCatalogueChanged={() => void loadCatalogue()}
            />
          </Suspense>
        )}

        {filters.activeModule === 'pipeline' && admin && (
          <Suspense fallback={<ModuleFallback />}>
            <PipelineViewer admin={admin} />
          </Suspense>
        )}

        {filters.activeModule === 'sources' && admin && (
          <Suspense fallback={<ModuleFallback />}>
            <SourcesManager admin={admin} onLogin={() => void handleAdminLogin()} />
          </Suspense>
        )}

        {/* Review always reachable so operators can start Google login */}
        {filters.activeModule === 'admin_queue' && (
          <Suspense fallback={<ModuleFallback />}>
            <AdminQueue
              items={reviewItems}
              total={reviewTotal}
              admin={admin}
              loading={reviewLoading}
              error={reviewError}
              onRefresh={() => void loadReviewQueue()}
              onLogin={() => void handleAdminLogin()}
              onLogout={() => void handleAdminLogout()}
              onBackToRadar={() =>
                setFilters((current) => ({ ...current, activeModule: 'hackathon' }))
              }
              onApprove={handleApprove}
              onReject={handleReject}
            />
          </Suspense>
        )}

        {/* If an operator loses the session, keep the login recovery path visible. */}
        {(filters.activeModule === 'pipeline' ||
          filters.activeModule === 'catalogue' ||
          filters.activeModule === 'sources') &&
          !admin && (
          <div className="max-w-6xl mx-auto px-4 lg:px-8 pt-10">
            <div className="sharetopus-card p-8 rounded-[24px] text-center space-y-3">
              <p className="text-sm font-extrabold">Operator tools require a signed-in admin session.</p>
              <button
                type="button"
                className="btn-sharetopus-primary text-xs font-bold"
                onClick={() => setFilters((f) => ({ ...f, activeModule: 'admin_queue' }))}
              >
                Open operator login
              </button>
            </div>
          </div>
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

      {isExtensionOpen && (
        <Suspense fallback={null}>
          <ChromeExtensionSidePanel
            isOpen={isExtensionOpen}
            onClose={() => setIsExtensionOpen(false)}
          />
        </Suspense>
      )}

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
        bookmarkedHackathons={
          sharedBookmarkIds ? sharedHackathons : bookmarkedHackathons
        }
        bookmarkedDeals={sharedBookmarkIds ? sharedDeals : bookmarkedDeals}
        onRemoveBookmark={handleToggleBookmark}
        onToggleAlert={handleToggleAlert}
        onImportIds={handleImportBookmarkIds}
        sharedMode={Boolean(sharedBookmarkIds)}
        sharedIds={sharedBookmarkIds ?? []}
        onSaveSharedToLocal={handleSaveSharedToLocal}
        onClearShared={handleClearShared}
      />

      <AlertSubscribeModal
        isOpen={isAlertModalOpen}
        onClose={() => setIsAlertModalOpen(false)}
        defaultKind={
          filters.activeModule === 'ai_deal'
            ? 'ai_offer'
            : filters.activeModule === 'hackathon'
              ? 'hackathon'
              : 'all'
        }
        defaultTechnology={filters.technology}
        defaultMode={filters.mode}
        defaultOnlyClosingSoon={filters.onlyClosingSoon}
        defaultOnlyBigPrizes={filters.onlyBigPrizes}
      />

      <footer className="border-t border-[#D6D5CF] dark:border-slate-800 bg-[#E5E6DF] dark:bg-[#090C15] py-8 px-4 lg:px-8 text-xs font-mono text-[#1C1B18] dark:text-slate-200 font-bold">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex flex-col sm:flex-row sm:items-center gap-2">
            <span className="font-extrabold text-[#1C1B18] dark:text-white text-sm tracking-tight">
              DevRadar
            </span>
            <span>MIT · no end-user login · bookmarks stay in your browser</span>
          </div>
          <div className="text-center sm:text-right opacity-90 max-w-xl">
            DevRadar is an independent index and is not affiliated with any organiser or
            vendor listed. Listings are community/operator-verified and can go stale —
            always confirm on the official page before registering or paying.
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
