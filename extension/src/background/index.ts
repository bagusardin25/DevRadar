import type { Message } from '../shared/messages';
import type { PageData } from '../shared/types';
import { extract } from '../shared/extractor';
import { handleApiProxy } from './apiProxy';
import { PendingAnalysisRegistry } from './pendingAnalyses';

const pendingAnalyses = new PendingAnalysisRegistry<PageData>();

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

chrome.action.onClicked.addListener((tab) => {
  if (chrome.sidePanel && tab.windowId) {
    chrome.sidePanel.open({ windowId: tab.windowId });
  }
});

if (chrome.sidePanel) {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
}
