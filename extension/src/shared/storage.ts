import type { ExtensionSettings, AnalysisHistory, ExtractionResult } from './types';
import { DEFAULT_API_BASE_URL } from './constants';

const DEFAULTS: ExtensionSettings = {
  apiBaseUrl: DEFAULT_API_BASE_URL,
  darkMode: 'auto',
};

const hasChromeStorage = typeof chrome !== 'undefined' && chrome.storage?.local;
const MAX_HISTORY_ITEMS = 50;
const MAX_URL_LENGTH = 2048;

export function sanitizeSettings(raw: unknown): ExtensionSettings {
  const value = raw && typeof raw === 'object' ? raw as Record<string, unknown> : {};
  let apiBaseUrl = DEFAULT_API_BASE_URL;
  if (typeof value.apiBaseUrl === 'string' && value.apiBaseUrl.length <= MAX_URL_LENGTH) {
    try {
      const parsed = new URL(value.apiBaseUrl.trim());
      if (
        (parsed.protocol === 'http:' || parsed.protocol === 'https:') &&
        !parsed.username &&
        !parsed.password
      ) {
        apiBaseUrl = parsed.toString().replace(/\/+$/, '');
      }
    } catch { /* retain safe default */ }
  }
  const darkMode =
    value.darkMode === 'light' || value.darkMode === 'dark' || value.darkMode === 'auto'
      ? value.darkMode
      : DEFAULTS.darkMode;
  return { apiBaseUrl, darkMode };
}

export function sanitizeHistory(raw: unknown): AnalysisHistory[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((entry): entry is AnalysisHistory => {
      if (!entry || typeof entry !== 'object') return false;
      const item = entry as Partial<AnalysisHistory>;
      return (
        typeof item.url === 'string' &&
        item.url.length > 0 &&
        item.url.length <= MAX_URL_LENGTH &&
        typeof item.analyzedAt === 'string' &&
        !!item.result &&
        typeof item.result === 'object'
      );
    })
    .slice(0, MAX_HISTORY_ITEMS);
}

export async function getSettings(): Promise<ExtensionSettings> {
  if (!hasChromeStorage) return DEFAULTS;
  const result = await chrome.storage.local.get('settings');
  return sanitizeSettings(result.settings);
}

export async function saveSettings(settings: Partial<ExtensionSettings>): Promise<void> {
  if (!hasChromeStorage) return;
  const current = await getSettings();
  await chrome.storage.local.set({ settings: sanitizeSettings({ ...current, ...settings }) });
}

export async function getHistory(): Promise<AnalysisHistory[]> {
  if (!hasChromeStorage) return [];
  const result = await chrome.storage.local.get('history');
  return sanitizeHistory(result.history);
}

export async function addToHistory(url: string, extraction: ExtractionResult): Promise<void> {
  if (!hasChromeStorage) return;
  const history = await getHistory();
  const entry: AnalysisHistory = {
    url: url.slice(0, MAX_URL_LENGTH),
    result: extraction,
    analyzedAt: new Date().toISOString(),
  };
  const updated = [entry, ...history.filter((h) => h.url !== entry.url)].slice(
    0,
    MAX_HISTORY_ITEMS,
  );
  await chrome.storage.local.set({ history: updated });
}

export async function clearHistory(): Promise<void> {
  if (!hasChromeStorage) return;
  await chrome.storage.local.set({ history: [] });
}
