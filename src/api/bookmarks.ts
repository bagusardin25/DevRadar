/** Browser-only bookmark / alert preference storage (no server account). */

import type { AIDeal, Hackathon } from '../types';

const BOOKMARKS_KEY = 'devradar_bookmarks_v1';
const ALERTS_KEY = 'devradar_alerts_v1';
/**
 * Snapshot of each bookmarked item's full row, keyed by id.
 *
 * Without this the drawer could only render bookmarks whose id happened to be
 * on the currently-loaded catalogue page — bookmark something under filter A,
 * switch to filter B, reload, and the item silently vanished from the drawer
 * even though its id was still saved.
 */
const BOOKMARK_SNAPSHOTS_KEY = 'devradar_bookmark_snapshots_v1';

/** Export format version for import/export JSON. */
export const BOOKMARK_EXPORT_VERSION = 1 as const;

export type BookmarkExportPayload = {
  version: typeof BOOKMARK_EXPORT_VERSION;
  exportedAt: string;
  /** Listing UUIDs / ids saved in the browser */
  ids: string[];
  /** Optional labels for human readability (not required to re-import) */
  items?: Array<{
    id: string;
    kind: 'hackathon' | 'ai_deal' | 'unknown';
    title: string;
  }>;
};

function readIdSet(key: string): Set<string> {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.map(String));
  } catch {
    return new Set();
  }
}

function writeIdSet(key: string, ids: Set<string>): void {
  localStorage.setItem(key, JSON.stringify([...ids]));
}

export function loadBookmarkIds(): Set<string> {
  return readIdSet(BOOKMARKS_KEY);
}

export function loadAlertIds(): Set<string> {
  return readIdSet(ALERTS_KEY);
}

export function saveBookmarkIds(ids: Set<string>): void {
  writeIdSet(BOOKMARKS_KEY, ids);
}

export function saveAlertIds(ids: Set<string>): void {
  writeIdSet(ALERTS_KEY, ids);
}

export function toggleId(ids: Set<string>, id: string): Set<string> {
  const next = new Set(ids);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}

/** Persisted snapshot of every bookmarked row, so the drawer works regardless
    of which filter or page is currently loaded. */
export interface BookmarkSnapshotStore {
  hackathons: Record<string, Hackathon>;
  deals: Record<string, AIDeal>;
}

/** Strip transient local flags so a snapshot never carries stale bookmarked /
    alertEnabled state from a previous session. */
function stripLocalFlags<T extends { bookmarked?: boolean; alertEnabled?: boolean }>(
  item: T,
): T {
  const { bookmarked: _b, alertEnabled: _a, ...rest } = item;
  void _b; void _a;
  return rest as T;
}

export function loadBookmarkSnapshots(): BookmarkSnapshotStore {
  try {
    const raw = localStorage.getItem(BOOKMARK_SNAPSHOTS_KEY);
    if (!raw) return { hackathons: {}, deals: {} };
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== 'object') return { hackathons: {}, deals: {} };
    const store = parsed as Partial<BookmarkSnapshotStore>;
    return {
      hackathons: store.hackathons && typeof store.hackathons === 'object' ? store.hackathons : {},
      deals: store.deals && typeof store.deals === 'object' ? store.deals : {},
    };
  } catch {
    return { hackathons: {}, deals: {} };
  }
}

export function saveBookmarkSnapshots(store: BookmarkSnapshotStore): void {
  try {
    localStorage.setItem(BOOKMARK_SNAPSHOTS_KEY, JSON.stringify(store));
  } catch {
    // Quota errors are non-fatal — the in-memory cache still works this session.
  }
}

/** Prune snapshots for ids that are no longer bookmarked and merge in updated
    rows for ids that are. Returns a new store; input is not mutated. */
export function reconcileSnapshots(
  store: BookmarkSnapshotStore,
  ids: Set<string>,
  updates: { hackathons?: Hackathon[]; deals?: AIDeal[] } = {},
): BookmarkSnapshotStore {
  const hackathons: Record<string, Hackathon> = {};
  const deals: Record<string, AIDeal> = {};
  for (const id of ids) {
    if (store.hackathons[id]) hackathons[id] = store.hackathons[id];
    if (store.deals[id]) deals[id] = store.deals[id];
  }
  for (const h of updates.hackathons ?? []) {
    if (ids.has(h.id)) hackathons[h.id] = stripLocalFlags(h);
  }
  for (const d of updates.deals ?? []) {
    if (ids.has(d.id)) deals[d.id] = stripLocalFlags(d);
  }
  return { hackathons, deals };
}

export function upsertSnapshot(
  store: BookmarkSnapshotStore,
  item: Hackathon | AIDeal,
  kind: 'hackathon' | 'ai_deal',
): BookmarkSnapshotStore {
  if (kind === 'hackathon') {
    return {
      hackathons: { ...store.hackathons, [item.id]: stripLocalFlags(item as Hackathon) },
      deals: store.deals,
    };
  }
  return {
    hackathons: store.hackathons,
    deals: { ...store.deals, [item.id]: stripLocalFlags(item as AIDeal) },
  };
}

export function removeSnapshot(
  store: BookmarkSnapshotStore,
  id: string,
): BookmarkSnapshotStore {
  if (!store.hackathons[id] && !store.deals[id]) return store;
  const hackathons = { ...store.hackathons };
  const deals = { ...store.deals };
  delete hackathons[id];
  delete deals[id];
  return { hackathons, deals };
}

/** Build a portable export document from current ids + optional titles. */
export function buildBookmarkExport(
  ids: Iterable<string>,
  items?: BookmarkExportPayload['items'],
): BookmarkExportPayload {
  const unique = [...new Set([...ids].map(String).filter(Boolean))];
  return {
    version: BOOKMARK_EXPORT_VERSION,
    exportedAt: new Date().toISOString(),
    ids: unique,
    ...(items && items.length > 0 ? { items } : {}),
  };
}

/** Parse import JSON (supports `{ ids: [] }` or legacy bare string array). */
export function parseBookmarkImport(raw: unknown): string[] {
  if (Array.isArray(raw)) {
    return [...new Set(raw.map(String).filter(Boolean))];
  }
  if (raw && typeof raw === 'object') {
    const obj = raw as Record<string, unknown>;
    if (Array.isArray(obj.ids)) {
      return [...new Set(obj.ids.map(String).filter(Boolean))];
    }
    // Accept { bookmarks: string[] } or { hackathons, deals }
    if (Array.isArray(obj.bookmarks)) {
      return [...new Set(obj.bookmarks.map(String).filter(Boolean))];
    }
    const parts: string[] = [];
    if (Array.isArray(obj.hackathons)) parts.push(...obj.hackathons.map(String));
    if (Array.isArray(obj.deals)) parts.push(...obj.deals.map(String));
    if (parts.length) return [...new Set(parts.filter(Boolean))];
  }
  throw new Error('Invalid bookmark file: expected { ids: string[] } or a string array');
}

/** Compact query-string share: ?bm=id1,id2,id3 (max ~80 ids for URL safety). */
const SHARE_PARAM = 'bm';
const SHARE_MAX_IDS = 80;

export function buildShareUrl(
  ids: Iterable<string>,
  baseUrl: string = typeof window !== 'undefined' ? window.location.origin + window.location.pathname : '',
): string {
  const unique = [...new Set([...ids].map(String).filter(Boolean))].slice(0, SHARE_MAX_IDS);
  const url = new URL(baseUrl || 'http://localhost/');
  if (unique.length === 0) {
    url.searchParams.delete(SHARE_PARAM);
  } else {
    url.searchParams.set(SHARE_PARAM, unique.join(','));
  }
  return url.toString();
}

/** Parse shared bookmark ids from the current page URL (or provided search string). */
export function parseShareIdsFromSearch(search: string = typeof window !== 'undefined' ? window.location.search : ''): string[] {
  const params = new URLSearchParams(search.startsWith('?') ? search : `?${search}`);
  // Support bm= and legacy bookmarks=
  const raw = params.get(SHARE_PARAM) || params.get('bookmarks') || '';
  if (!raw.trim()) return [];
  return [
    ...new Set(
      raw
        .split(/[,]+/)
        .map((s) => s.trim())
        .filter(Boolean)
        .slice(0, SHARE_MAX_IDS),
    ),
  ];
}

export function downloadBookmarkJson(payload: BookmarkExportPayload, filename = 'devradar-bookmarks.json'): void {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function readBookmarkFile(file: File): Promise<string[]> {
  const text = await file.text();
  let parsed: unknown;
  try {
    parsed = JSON.parse(text) as unknown;
  } catch {
    throw new Error('File is not valid JSON');
  }
  return parseBookmarkImport(parsed);
}
