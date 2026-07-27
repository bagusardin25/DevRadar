import type { ExtensionSettings, AnalysisHistory, ExtractionResult } from './types';
import { DEFAULT_API_BASE_URL } from './constants';

const DEFAULTS: ExtensionSettings = {
  apiBaseUrl: DEFAULT_API_BASE_URL,
  darkMode: 'auto',
};

const hasChromeStorage = typeof chrome !== 'undefined' && chrome.storage?.local;

export async function getSettings(): Promise<ExtensionSettings> {
  if (!hasChromeStorage) return DEFAULTS;
  const result = await chrome.storage.local.get('settings');
  return { ...DEFAULTS, ...(result.settings || {}) };
}

export async function saveSettings(settings: Partial<ExtensionSettings>): Promise<void> {
  if (!hasChromeStorage) return;
  const current = await getSettings();
  await chrome.storage.local.set({ settings: { ...current, ...settings } });
}

export async function getHistory(): Promise<AnalysisHistory[]> {
  if (!hasChromeStorage) return [];
  const result = await chrome.storage.local.get('history');
  return result.history || [];
}

export async function addToHistory(url: string, extraction: ExtractionResult): Promise<void> {
  if (!hasChromeStorage) return;
  const history = await getHistory();
  const entry: AnalysisHistory = {
    url,
    result: extraction,
    analyzedAt: new Date().toISOString(),
  };
  const updated = [entry, ...history.filter((h) => h.url !== url)].slice(0, 50);
  await chrome.storage.local.set({ history: updated });
}

export async function clearHistory(): Promise<void> {
  if (!hasChromeStorage) return;
  await chrome.storage.local.set({ history: [] });
}
