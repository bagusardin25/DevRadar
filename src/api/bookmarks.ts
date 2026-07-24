/** Browser-only bookmark / alert preference storage (no server account). */

const BOOKMARKS_KEY = 'devradar_bookmarks_v1';
const ALERTS_KEY = 'devradar_alerts_v1';

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
