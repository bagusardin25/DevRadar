import { useState, useEffect, useCallback } from 'react';
import {
  Globe, Sparkles, Calendar, Bookmark, Zap, Wrench,
  Search, Send, Loader2, AlertCircle, CheckCircle2,
  Sun, Moon, Settings, ChevronRight, ExternalLink,
  RefreshCw, Clock,
} from 'lucide-react';
import type { Message } from '../shared/messages';
import type { ExtractionResult, HackathonFields, AIOfferFields } from '../shared/types';
import { submitUrl, searchCatalogue, getSubmissionStatus } from '../shared/api';
import type { SubmissionReceipt, SearchResult } from '../shared/api';
import { getSettings, saveSettings, addToHistory } from '../shared/storage';
import { generateICS } from '../shared/ics';

type ViewState = 'idle' | 'analyzing' | 'results' | 'submitted' | 'settings' | 'error';

const hasChromeRuntime = typeof chrome !== 'undefined' && !!chrome.runtime?.sendMessage;

function downloadICS(title: string, dateStr: string) {
  const ics = generateICS(title, dateStr);
  const blob = new Blob([ics], { type: 'text/calendar' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${title.replace(/[^a-zA-Z0-9]/g, '_').slice(0, 40)}.ics`;
  a.click();
  URL.revokeObjectURL(url);
}

export function App() {
  const [view, setView] = useState<ViewState>('idle');
  const [darkMode, setDarkMode] = useState(false);
  const [tabInfo, setTabInfo] = useState<{ url: string; title: string }>({ url: '', title: '' });
  const [result, setResult] = useState<ExtractionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submission, setSubmission] = useState<SubmissionReceipt | null>(null);
  const [submissionStatus, setSubmissionStatus] = useState<string | null>(null);
  const [similar, setSimilar] = useState<SearchResult | null>(null);
  const [apiBaseUrl, setApiBaseUrl] = useState('http://localhost:8000');

  useEffect(() => {
    getSettings().then((s) => {
      setApiBaseUrl(s.apiBaseUrl);
      if (s.darkMode === 'dark' || (s.darkMode === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        setDarkMode(true);
      }
    });
    fetchTabInfo();
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (darkMode) {
      root.classList.add('dark', 'dark-theme');
    } else {
      root.classList.remove('dark', 'dark-theme');
    }
  }, [darkMode]);

  const fetchTabInfo = useCallback(() => {
    if (!hasChromeRuntime) {
      setTabInfo({ url: 'https://example.com/hackathon', title: 'Dev preview — no Chrome APIs' });
      return;
    }
    chrome.runtime.sendMessage({ type: 'GET_TAB_INFO' } satisfies Message, (resp: Message) => {
      if (resp?.type === 'TAB_INFO') {
        setTabInfo(resp.data);
      }
    });
  }, []);

  const handleAnalyze = useCallback(() => {
    setView('analyzing');
    setError(null);
    setResult(null);
    setSimilar(null);
    setSubmission(null);
    setSubmissionStatus(null);

    if (!hasChromeRuntime) {
      setError('Chrome extension APIs not available in dev preview');
      setView('error');
      return;
    }
    chrome.runtime.sendMessage({ type: 'ANALYZE_TAB' } satisfies Message, (resp: Message) => {
      if (resp?.type === 'EXTRACTION_RESULT') {
        setResult(resp.data);
        setView('results');
        addToHistory(tabInfo.url, resp.data);
        const title = ('title' in resp.data.fields) ? (resp.data.fields as HackathonFields).title : null;
        if (title) {
          searchCatalogue(title, 3).then(setSimilar).catch(() => {});
        }
      } else if (resp?.type === 'ANALYZE_ERROR') {
        setError(resp.error);
        setView('error');
      } else {
        setError('Unexpected response from background');
        setView('error');
      }
    });
  }, [tabInfo.url]);

  const handleSubmit = useCallback(async () => {
    if (!result) return;
    try {
      const fields = result.fields;
      const title = 'title' in fields ? fields.title : null;
      const receipt = await submitUrl(tabInfo.url, result.listingKind !== 'unknown' ? result.listingKind : undefined, title || undefined);
      setSubmission(receipt);
      setView('submitted');

      const poll = async (id: string, attempts = 0) => {
        if (attempts > 20) return;
        try {
          const status = await getSubmissionStatus(id);
          setSubmissionStatus(status.status);
          if (!['queued', 'fetching', 'reviewing', 'processing'].includes(status.status)) return;
          setTimeout(() => poll(id, attempts + 1), 3000);
        } catch { /* stop polling */ }
      };
      poll(receipt.trackingId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Submission failed');
    }
  }, [result, tabInfo.url]);

  const handleSaveSettings = useCallback(async () => {
    await saveSettings({ apiBaseUrl, darkMode: darkMode ? 'dark' : 'light' });
    setView('idle');
    fetchTabInfo();
  }, [apiBaseUrl, darkMode, fetchTabInfo]);

  const handleReset = useCallback(() => {
    setView('idle');
    setResult(null);
    setError(null);
    setSubmission(null);
    setSimilar(null);
    fetchTabInfo();
  }, [fetchTabInfo]);

  return (
    <div className="min-h-screen flex flex-col font-sans bg-[var(--bg-warm)] text-[var(--ink-primary)]">
      {/* Header */}
      <div className="p-3 border-b-[2px] border-[var(--border-dark)] bg-[var(--bg-card)] flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-xl bg-[#FF5A36] text-white border-[1.5px] border-[var(--border-dark)] shadow-[2px_2px_0_0_var(--border-dark)]">
            <Globe className="w-4 h-4" />
          </div>
          <div>
            <h1 className="text-xs font-extrabold">DevRadar Extension</h1>
            <p className="text-[9px] font-mono text-[var(--ink-muted)] font-bold">v1.0.0 • Side Panel</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setDarkMode(!darkMode)}
            className="p-1.5 rounded-lg border-[1.5px] border-[var(--border-dark)] bg-[var(--bg-card)] hover:bg-[#FF5A36] hover:text-white transition-colors shadow-[1.5px_1.5px_0_0_var(--border-dark)]"
            title={darkMode ? 'Light mode' : 'Dark mode'}
          >
            {darkMode ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={() => setView(view === 'settings' ? 'idle' : 'settings')}
            className="p-1.5 rounded-lg border-[1.5px] border-[var(--border-dark)] bg-[var(--bg-card)] hover:bg-[#FF5A36] hover:text-white transition-colors shadow-[1.5px_1.5px_0_0_var(--border-dark)]"
            title="Settings"
          >
            <Settings className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Tab Preview (always visible except settings) */}
        {view !== 'settings' && (
          <div className="sharetopus-card p-3 space-y-1.5">
            <div className="flex items-center justify-between text-[10px] font-mono font-extrabold text-[var(--ink-muted)]">
              <span>CURRENT TAB</span>
              <span className="text-[var(--text-emerald)]">Active</span>
            </div>
            <div className="font-extrabold text-[11px] truncate">{tabInfo.url || 'No page loaded'}</div>
            {tabInfo.title && (
              <p className="text-[10px] text-[var(--ink-secondary)] font-bold truncate">{tabInfo.title}</p>
            )}
          </div>
        )}

        {/* Idle State */}
        {view === 'idle' && (
          <button
            onClick={handleAnalyze}
            className="w-full btn-sharetopus-primary justify-center text-xs py-3 rounded-full font-extrabold"
          >
            <Sparkles className="w-4 h-4" />
            <span>Analyze This Page</span>
          </button>
        )}

        {/* Analyzing State */}
        {view === 'analyzing' && (
          <div className="sharetopus-card p-6 text-center space-y-3">
            <Loader2 className="w-8 h-8 animate-spin text-[#FF5A36] mx-auto" />
            <p className="text-xs font-bold">Extracting page data...</p>
            <p className="text-[10px] text-[var(--ink-muted)] font-mono">Scraping DOM, detecting dates & prizes</p>
          </div>
        )}

        {/* Error State */}
        {view === 'error' && (
          <div className="sharetopus-card p-4 space-y-3">
            <div className="flex items-center gap-2 text-[var(--text-red)]">
              <AlertCircle className="w-5 h-5" />
              <span className="text-xs font-extrabold">Analysis Failed</span>
            </div>
            <p className="text-[11px] text-[var(--ink-secondary)] font-mono">{error}</p>
            <button onClick={handleReset} className="btn-sharetopus-secondary text-[11px] py-2 px-4">
              <RefreshCw className="w-3.5 h-3.5" /> Try Again
            </button>
          </div>
        )}

        {/* Results State */}
        {view === 'results' && result && (
          <ResultsView
            result={result}
            tabUrl={tabInfo.url}
            similar={similar}
            onSubmit={handleSubmit}
            onReset={handleReset}
          />
        )}

        {/* Submitted State */}
        {view === 'submitted' && submission && (
          <div className="sharetopus-card p-4 space-y-3">
            <div className="flex items-center gap-2 text-[var(--text-emerald)]">
              <Send className="w-4 h-4" />
              <span className="text-xs font-extrabold">Submitted to DevRadar</span>
            </div>
            <div className="p-2.5 rounded-xl bg-[var(--bg-card-alt)] border-[1.5px] border-[var(--border-dark)] space-y-1 text-[11px] font-mono">
              <div className="flex justify-between">
                <span className="text-[var(--ink-muted)]">Status</span>
                <span className="font-bold">{submissionStatus || submission.status}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--ink-muted)]">Tracking</span>
                <span className="font-bold truncate ml-2 max-w-[160px]">{submission.trackingId}</span>
              </div>
              {submission.duplicate && (
                <div className="text-[var(--text-amber)] text-[10px]">Duplicate — already submitted</div>
              )}
            </div>
            <p className="text-[10px] text-[var(--ink-muted)]">{submission.message}</p>
            <button onClick={handleReset} className="btn-sharetopus-secondary text-[11px] py-2 px-4 w-full justify-center">
              <RefreshCw className="w-3.5 h-3.5" /> Analyze Another Page
            </button>
          </div>
        )}

        {/* Settings View */}
        {view === 'settings' && (
          <div className="sharetopus-card p-4 space-y-4">
            <h2 className="text-xs font-extrabold">Extension Settings</h2>
            <div className="space-y-2">
              <label className="text-[10px] font-mono font-bold text-[var(--ink-muted)]">API Base URL</label>
              <input
                type="url"
                value={apiBaseUrl}
                onChange={(e) => setApiBaseUrl(e.target.value)}
                className="w-full px-3 py-2 text-[11px] font-mono rounded-xl border-[1.5px] border-[var(--border-dark)] bg-[var(--bg-card-alt)] text-[var(--ink-primary)] shadow-[var(--shadow-neo-sm)]"
                placeholder="http://localhost:8000"
              />
              <p className="text-[9px] text-[var(--ink-muted)]">Backend URL for submission & search. Leave default for local dev.</p>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold">Dark Mode</span>
              <button
                onClick={() => setDarkMode(!darkMode)}
                className={`px-3 py-1 rounded-full text-[10px] font-bold border-[1.5px] border-[var(--border-dark)] shadow-[var(--shadow-neo-sm)] ${
                  darkMode ? 'bg-[#FF5A36] text-white' : 'bg-[var(--bg-card)]'
                }`}
              >
                {darkMode ? 'ON' : 'OFF'}
              </button>
            </div>
            <button onClick={handleSaveSettings} className="btn-sharetopus-primary text-[11px] py-2 px-4 w-full justify-center">
              Save Settings
            </button>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t-[2px] border-[var(--border-dark)] bg-[var(--bg-card)] text-[10px] font-mono font-bold text-[var(--ink-muted)] flex items-center justify-between">
        <span>DevRadar Extension v1.0</span>
        {view === 'results' && (
          <button onClick={handleReset} className="text-[#FF5A36] font-extrabold hover:underline">
            Reset
          </button>
        )}
      </div>
    </div>
  );
}

function ResultsView({
  result, tabUrl, similar, onSubmit, onReset,
}: {
  result: ExtractionResult;
  tabUrl: string;
  similar: SearchResult | null;
  onSubmit: () => void;
  onReset: () => void;
}) {
  const fields = result.fields;
  const isHackathon = result.listingKind === 'hackathon';
  const hf = isHackathon ? (fields as HackathonFields) : null;
  const af = !isHackathon && result.listingKind === 'ai_offer' ? (fields as AIOfferFields) : null;
  const title = hf?.title || af?.title || 'Unknown Page';
  const confidence = result.confidence;

  const confidenceColor = confidence >= 70
    ? 'text-[var(--text-emerald)] border-[var(--accent-emerald)] bg-[rgba(5,150,105,0.1)]'
    : confidence >= 40
      ? 'text-[var(--text-amber)] border-[#F59E0B] bg-[rgba(245,158,11,0.1)]'
      : 'text-[var(--text-red)] border-[#EF4444] bg-[rgba(239,68,68,0.1)]';

  const kindLabel = result.listingKind === 'hackathon' ? 'HACKATHON'
    : result.listingKind === 'ai_offer' ? 'AI OFFER'
    : 'UNKNOWN TYPE';

  const kindColor = result.listingKind === 'hackathon'
    ? 'text-[var(--text-emerald)] bg-[rgba(5,150,105,0.12)] border-[rgba(5,150,105,0.3)]'
    : result.listingKind === 'ai_offer'
      ? 'text-[#A855F7] bg-[rgba(168,85,247,0.12)] border-[rgba(168,85,247,0.3)]'
      : 'text-[var(--ink-muted)] bg-[var(--bg-card-alt)] border-[var(--line-subtle)]';

  return (
    <div className="space-y-3">
      {/* Classification + Confidence */}
      <div className="sharetopus-card p-3.5 space-y-3">
        <div className="flex items-center justify-between">
          <span className={`px-2.5 py-0.5 rounded-full text-[9px] font-extrabold font-mono border ${kindColor}`}>
            {kindLabel}
          </span>
          <span className={`font-mono font-extrabold text-[11px] px-2.5 py-0.5 rounded-full border ${confidenceColor}`}>
            {confidence}% Match
          </span>
        </div>

        <div className="space-y-1">
          <h2 className="font-extrabold text-sm leading-tight">{title}</h2>
          {hf?.organizer && <p className="text-[11px] text-[var(--ink-secondary)] font-bold">{hf.organizer}</p>}
          {af?.provider && <p className="text-[11px] text-[var(--ink-secondary)] font-bold">{af.provider}</p>}
        </div>

        {/* Prize / Offer Value */}
        {hf?.prizeLabel && (
          <div className="text-[var(--text-emerald)] font-mono font-extrabold text-xs">{hf.prizeLabel}</div>
        )}
        {af?.offerValue && (
          <div className="text-[#A855F7] font-mono font-extrabold text-xs">{af.offerValue}</div>
        )}

        {/* Extracted Details */}
        <div className="p-2.5 bg-[var(--bg-card-alt)] rounded-xl space-y-1.5 font-mono text-[10px] border-[1.5px] border-[var(--border-dark)] font-bold">
          {hf?.registrationDeadline && (
            <div className="flex items-center gap-1.5">
              <Calendar className="w-3 h-3 text-[#FF5A36] shrink-0" />
              <span>Reg Deadline: <strong>{new Date(hf.registrationDeadline).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</strong></span>
            </div>
          )}
          {hf?.submissionDeadline && (
            <div className="flex items-center gap-1.5">
              <Zap className="w-3 h-3 text-[#FF5A36] shrink-0" />
              <span>Submission: <strong>{new Date(hf.submissionDeadline).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</strong></span>
            </div>
          )}
          {af?.expiresAt && (
            <div className="flex items-center gap-1.5">
              <Clock className="w-3 h-3 text-[#FF5A36] shrink-0" />
              <span>Expires: <strong>{new Date(af.expiresAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</strong></span>
            </div>
          )}
          {hf?.mode && (
            <div className="flex items-center gap-1.5">
              <Globe className="w-3 h-3 text-[#FF5A36] shrink-0" />
              <span>Mode: <strong className="capitalize">{hf.mode.replace('_', ' ')}</strong></span>
            </div>
          )}
          {((hf?.technologies?.length ?? 0) > 0 || (af?.tags?.length ?? 0) > 0) && (
            <div className="flex items-center gap-1.5">
              <Wrench className="w-3 h-3 text-[#FF5A36] shrink-0" />
              <span>Tech: <strong>{(hf?.technologies || af?.tags || []).slice(0, 5).join(', ')}</strong></span>
            </div>
          )}
          {af?.offerType && (
            <div className="flex items-center gap-1.5">
              <Sparkles className="w-3 h-3 text-[#FF5A36] shrink-0" />
              <span>Type: <strong className="capitalize">{af.offerType.replace(/_/g, ' ')}</strong></span>
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-2 gap-2 pt-1">
          {(hf?.submissionDeadline || hf?.registrationDeadline) && (
            <button
              onClick={() => downloadICS(title || 'Event', (hf?.submissionDeadline || hf?.registrationDeadline)!)}
              className="flex items-center justify-center gap-1.5 p-2 rounded-full border-[1.5px] border-[var(--border-dark)] bg-[var(--bg-card)] font-extrabold text-[10px] shadow-[2px_2px_0_0_var(--border-dark)] hover:translate-x-[-1px] transition-all"
            >
              <Calendar className="w-3 h-3" /> Export .ics
            </button>
          )}
          <button
            onClick={() => { if (tabUrl) window.open(tabUrl, '_blank'); }}
            className="flex items-center justify-center gap-1.5 p-2 rounded-full border-[1.5px] border-[var(--border-dark)] bg-[var(--bg-card)] font-extrabold text-[10px] shadow-[2px_2px_0_0_var(--border-dark)] hover:translate-x-[-1px] transition-all"
          >
            <ExternalLink className="w-3 h-3" /> Open Page
          </button>
        </div>
      </div>

      {/* Submit to DevRadar */}
      <button
        onClick={onSubmit}
        className="w-full btn-sharetopus-primary justify-center text-[11px] py-2.5 rounded-full font-extrabold"
      >
        <Send className="w-3.5 h-3.5" />
        <span>Submit to DevRadar Catalogue</span>
      </button>

      {/* Similar Opportunities */}
      {similar && similar.items.length > 0 && (
        <div className="sharetopus-card p-3.5 space-y-2.5">
          <div className="font-extrabold text-[9px] font-mono tracking-wider text-[var(--ink-muted)]">
            {similar.items.length} SIMILAR IN CATALOGUE:
          </div>
          <div className="space-y-1.5">
            {similar.items.map((item, i) => (
              <div
                key={i}
                className="p-2 rounded-xl bg-[var(--bg-card-alt)] border-[1.5px] border-[var(--border-dark)] text-[10px] font-extrabold flex items-center justify-between shadow-[1.5px_1.5px_0_0_var(--border-dark)]"
              >
                <span className="truncate mr-2">{item.title}</span>
                <span className="text-[var(--text-emerald)] font-mono shrink-0">
                  {item.prizeLabel || item.offerValue || ''}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Description */}
      {fields.description && (
        <div className="sharetopus-card p-3.5 space-y-2">
          <div className="font-extrabold text-[9px] font-mono tracking-wider text-[var(--ink-muted)]">DESCRIPTION</div>
          <p className="text-[10px] text-[var(--ink-secondary)] leading-relaxed line-clamp-4">{fields.description}</p>
        </div>
      )}
    </div>
  );
}
