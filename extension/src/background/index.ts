import type { Message } from '../shared/messages';
import type { PageData } from '../shared/types';
import { extract } from '../shared/extractor';
import { getSettings } from '../shared/storage';
import { PendingAnalysisRegistry } from './pendingAnalyses';

const pendingAnalyses = new PendingAnalysisRegistry<PageData>();
const MAX_API_RESPONSE_BYTES = 2_097_152;
const MAX_API_REQUEST_BYTES = 1_048_576;

chrome.runtime.onMessage.addListener((message: Message, sender, sendResponse) => {
  if (message.type === 'PAGE_DATA') {
    const tabId = sender.tab?.id;
    if (tabId !== undefined) pendingAnalyses.resolve(tabId, message.data);
    return;
  }

  if (message.type === 'GET_TAB_INFO') {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tab = tabs[0];
      sendResponse({
        type: 'TAB_INFO',
        data: {
          url: tab?.url || '',
          title: tab?.title || '',
          favIconUrl: tab?.favIconUrl,
        },
      } satisfies Message);
    });
    return true;
  }

  if (message.type === 'ANALYZE_TAB') {
    handleAnalyze().then(sendResponse).catch((err) => {
      sendResponse({ type: 'ANALYZE_ERROR', error: String(err) } satisfies Message);
    });
    return true;
  }

  if (message.type === 'API_REQUEST') {
    handleApiProxy(message.path, message.options)
      .then((data) => sendResponse({ type: 'API_RESPONSE', id: message.id, data }))
      .catch((err) => sendResponse({ type: 'API_RESPONSE', id: message.id, data: null, error: String(err) }));
    return true;
  }
});

async function handleAnalyze(): Promise<Message> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !tab.url) {
    return { type: 'ANALYZE_ERROR', error: 'No active tab found' };
  }

  if (tab.url.startsWith('chrome://') || tab.url.startsWith('chrome-extension://') ||
      tab.url.startsWith('about:') || tab.url.startsWith('moz-extension://')) {
    return { type: 'ANALYZE_ERROR', error: 'Cannot analyze browser internal pages' };
  }

  const pageData = await injectAndScrape(tab.id);
  const result = extract(pageData);
  return { type: 'EXTRACTION_RESULT', data: result };
}

function injectAndScrape(tabId: number): Promise<PageData> {
  const result = pendingAnalyses.start(tabId, 10_000, 'Content script timed out (10s)');
  chrome.scripting.executeScript(
    {
      target: { tabId },
      files: ['content.js'],
    },
    (results) => {
      if (chrome.runtime.lastError) {
        pendingAnalyses.reject(tabId, new Error(chrome.runtime.lastError.message));
        return;
      }
      if (!results || results.length === 0) {
        pendingAnalyses.reject(tabId, new Error('Content script injection failed'));
      }
    },
  );
  return result;
}

async function handleApiProxy(
  path: string,
  options: { method?: string; query?: Record<string, string | number | boolean | undefined | null>; body?: unknown; headers?: Record<string, string> },
): Promise<unknown> {
  const settings = await getSettings();
  const base = settings.apiBaseUrl.replace(/\/+$/, '');
  if (path.length > 256 || path.includes('://') || path.includes('..')) {
    throw new Error('Invalid API path');
  }
  const apiPath = path.startsWith('/') ? path : `/${path}`;

  let url = `${base}/api/v1${apiPath}`;
  if (options.query) {
    const entries = Object.entries(options.query);
    if (entries.length > 20) throw new Error('Too many API query parameters');
    const params = new URLSearchParams();
    for (const [key, value] of entries) {
      if (value !== undefined && value !== null && value !== '') {
        const text = String(value);
        if (key.length > 64 || text.length > 512) {
          throw new Error('API query parameter is too long');
        }
        params.set(key, text);
      }
    }
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }

  const headers: Record<string, string> = {
    Accept: 'application/json',
  };
  const idempotencyKey = options.headers?.['Idempotency-Key'];
  if (idempotencyKey && idempotencyKey.length <= 200) {
    headers['Idempotency-Key'] = idempotencyKey;
  }
  let serializedBody: string | undefined;
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    serializedBody = JSON.stringify(options.body);
    if (new TextEncoder().encode(serializedBody).byteLength > MAX_API_REQUEST_BYTES) {
      throw new Error('API request body is too large');
    }
  }

  const method = (options.method || 'GET').toUpperCase();
  if (method !== 'GET' && method !== 'POST') throw new Error('Unsupported API method');
  const resp = await fetch(url, {
    method,
    headers,
    body: serializedBody,
  });

  const text = await readBoundedResponse(resp, MAX_API_RESPONSE_BYTES);
  if (!resp.ok) {
    throw new Error(`API ${resp.status}: ${text.slice(0, 200)}`);
  }

  if (resp.status === 204) return null;
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    throw new Error('API returned invalid JSON');
  }
}

async function readBoundedResponse(response: Response, maxBytes: number): Promise<string> {
  const declared = Number(response.headers.get('content-length') || 0);
  if (Number.isFinite(declared) && declared > maxBytes) {
    throw new Error('API response is too large');
  }
  if (!response.body) return response.text();

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let received = 0;
  let text = '';
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      received += value.byteLength;
      if (received > maxBytes) throw new Error('API response is too large');
      text += decoder.decode(value, { stream: true });
    }
    return text + decoder.decode();
  } finally {
    if (received > maxBytes) await reader.cancel();
    reader.releaseLock();
  }
}

chrome.action.onClicked.addListener((tab) => {
  if (chrome.sidePanel && tab.windowId) {
    chrome.sidePanel.open({ windowId: tab.windowId });
  }
});

if (chrome.sidePanel) {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
}
