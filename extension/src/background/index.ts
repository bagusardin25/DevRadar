import type { Message } from '../shared/messages';
import type { PageData } from '../shared/types';
import { extract } from '../shared/extractor';
import { getSettings } from '../shared/storage';

let pendingResolve: ((data: PageData) => void) | null = null;

chrome.runtime.onMessage.addListener((message: Message, _sender, sendResponse) => {
  if (message.type === 'PAGE_DATA' && pendingResolve) {
    pendingResolve(message.data);
    pendingResolve = null;
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
  return new Promise((resolve, reject) => {
    pendingResolve = resolve;

    chrome.scripting.executeScript(
      {
        target: { tabId },
        files: ['content.js'],
      },
      (results) => {
        if (chrome.runtime.lastError) {
          pendingResolve = null;
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        if (!results || results.length === 0) {
          pendingResolve = null;
          reject(new Error('Content script injection failed'));
        }
      },
    );

    setTimeout(() => {
      if (pendingResolve) {
        pendingResolve = null;
        reject(new Error('Content script timed out (10s)'));
      }
    }, 10_000);
  });
}

async function handleApiProxy(
  path: string,
  options: { method?: string; query?: Record<string, string | number | boolean | undefined | null>; body?: unknown; headers?: Record<string, string> },
): Promise<unknown> {
  const settings = await getSettings();
  const base = settings.apiBaseUrl.replace(/\/+$/, '');
  const apiPath = path.startsWith('/') ? path : `/${path}`;

  let url = `${base}/api/v1${apiPath}`;
  if (options.query) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(options.query)) {
      if (value !== undefined && value !== null && value !== '') {
        params.set(key, String(value));
      }
    }
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }

  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...options.headers,
  };
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }

  const resp = await fetch(url, {
    method: options.method || 'GET',
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`API ${resp.status}: ${text.slice(0, 200)}`);
  }

  if (resp.status === 204) return null;
  return resp.json();
}

chrome.action.onClicked.addListener((tab) => {
  if (chrome.sidePanel && tab.windowId) {
    chrome.sidePanel.open({ windowId: tab.windowId });
  }
});

if (chrome.sidePanel) {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
}
