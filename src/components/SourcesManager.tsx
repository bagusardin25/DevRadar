import React, { useState, useEffect, useCallback } from 'react';
import {
  Database,
  RefreshCw,
  Loader2,
  AlertCircle,
  ShieldCheck,
  Globe,
  RotateCcw,
  CheckCircle2,
  XCircle,
  Clock,
} from 'lucide-react';
import { fetchSources, fetchCrawlRuns, retryCrawlRun } from '../api/pipeline';
import type { Source, CrawlRun } from '../api/pipeline';

interface SourcesManagerProps {
  admin: { githubId: string; login: string; csrfToken: string } | null;
  onLogin: () => void;
}

function statusBadge(status: string) {
  const s = status.toLowerCase();
  if (['completed', 'done', 'active'].includes(s)) {
    return 'bg-[#059669]/15 text-[#059669] border-[#059669]';
  }
  if (['failed', 'error'].includes(s)) {
    return 'bg-[#FF5A36]/15 text-[#FF5A36] border-[#FF5A36]';
  }
  if (['queued', 'running', 'in_progress'].includes(s)) {
    return 'bg-[#D97706]/15 text-[#D97706] border-[#D97706]';
  }
  return 'bg-slate-400/15 text-slate-500 border-slate-400';
}

function tierBadge(tier: string) {
  const t = tier.toLowerCase();
  if (t.includes('1') || t.includes('official')) {
    return 'bg-[#059669]/15 text-[#059669] border-[#059669]';
  }
  if (t.includes('2') || t.includes('aggregator')) {
    return 'bg-[#7C3AED]/15 text-[#7C3AED] border-[#7C3AED]';
  }
  return 'bg-[#D97706]/15 text-[#D97706] border-[#D97706]';
}

export const SourcesManager: React.FC<SourcesManagerProps> = ({ admin, onLogin }) => {
  const [sources, setSources] = useState<Source[]>([]);
  const [crawlRuns, setCrawlRuns] = useState<CrawlRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!admin) return;
    setLoading(true);
    setError(null);
    try {
      const [srcData, runData] = await Promise.all([
        fetchSources(),
        fetchCrawlRuns(),
      ]);
      setSources(srcData);
      setCrawlRuns(runData);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load data';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [admin]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleRetry = async (runId: string) => {
    if (!admin) return;
    setRetrying(runId);
    try {
      const updated = await retryCrawlRun(runId, admin.csrfToken);
      setCrawlRuns((prev) =>
        prev.map((r) => (r.id === runId ? updated : r)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Retry failed');
    } finally {
      setRetrying(null);
    }
  };

  // Not logged in
  if (!admin) {
    return (
      <div className="space-y-8 max-w-6xl mx-auto px-4 lg:px-8 py-6 font-sans">
        <div className="sharetopus-card p-8 rounded-[28px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] text-center space-y-4">
          <ShieldCheck className="w-12 h-12 text-[#2563EB] mx-auto" />
          <h2 className="text-xl font-extrabold text-[#1C1B18] dark:text-white">
            Admin Access Required
          </h2>
          <p className="text-xs text-[#1C1B18] dark:text-[#F8FAF9] font-bold max-w-md mx-auto">
            Sign in with GitHub to manage ingestion sources and view crawl pipeline runs.
          </p>
          <button
            type="button"
            onClick={onLogin}
            className="btn-sharetopus-primary text-xs py-2.5 px-6 font-extrabold"
          >
            Sign in with GitHub
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-6xl mx-auto px-4 lg:px-8 py-6 font-sans">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-2xl bg-[#2563EB]/15 text-[#2563EB] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
            <Database className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-extrabold text-[#1C1B18] dark:text-white">
              Sources & Pipeline
            </h2>
            <p className="text-xs text-[#1C1B18] dark:text-[#F8FAF9] font-bold">
              Manage ingestion sources and monitor crawl runs
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => void loadData()}
          disabled={loading}
          className="btn-sharetopus-secondary text-xs py-2 px-4 font-bold flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="sharetopus-card p-4 rounded-2xl border-[1.5px] border-[#FF5A36] bg-[#FF5A36]/10 flex items-start gap-3 text-xs font-bold">
          <AlertCircle className="w-5 h-5 text-[#FF5A36] shrink-0" />
          <div>
            <div className="font-extrabold">Error loading data</div>
            <p className="mt-1 opacity-90">{error}</p>
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="sharetopus-card p-12 text-center rounded-[24px] bg-white dark:bg-[#131A29]">
          <Loader2 className="w-8 h-8 animate-spin text-[#2563EB] mx-auto mb-3" />
          <p className="text-xs font-bold">Loading sources & crawl runs…</p>
        </div>
      )}

      {/* Data Sources Section */}
      {!loading && (
        <div className="sharetopus-card p-6 rounded-[28px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-extrabold text-[#1C1B18] dark:text-white flex items-center gap-2">
              <Globe className="w-5 h-5 text-[#2563EB]" />
              Data Sources
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-extrabold bg-[#2563EB]/15 text-[#2563EB] border border-[#2563EB]">
                {sources.length}
              </span>
            </h3>
          </div>

          {sources.length === 0 ? (
            <div className="text-center py-8">
              <Database className="w-8 h-8 text-slate-400 mx-auto mb-2" />
              <p className="text-xs font-bold text-slate-500">No sources configured yet</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {sources.map((src) => (
                <div
                  key={src.id}
                  className="sharetopus-card p-4 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-[#F8F9F4] dark:bg-[#1A2336] space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-extrabold text-xs text-[#1C1B18] dark:text-white truncate">
                      {src.name}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-extrabold border ${
                        src.enabled
                          ? 'bg-[#059669]/15 text-[#059669] border-[#059669]'
                          : 'bg-slate-400/15 text-slate-500 border-slate-400'
                      }`}
                    >
                      {src.enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-extrabold bg-[#2563EB]/15 text-[#2563EB] border border-[#2563EB]">
                      {src.connectorType}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-extrabold border ${tierBadge(src.trustTier)}`}
                    >
                      {src.trustTier}
                    </span>
                  </div>
                  {src.baseUrl && (
                    <p className="text-[11px] font-mono text-[#1C1B18] dark:text-[#B8C4D2] truncate">
                      {src.baseUrl}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Crawl Runs Section */}
      {!loading && (
        <div className="sharetopus-card p-6 rounded-[28px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] space-y-4">
          <h3 className="text-base font-extrabold text-[#1C1B18] dark:text-white flex items-center gap-2">
            <Clock className="w-5 h-5 text-[#D97706]" />
            Crawl Runs
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-extrabold bg-[#D97706]/15 text-[#D97706] border border-[#D97706]">
              {crawlRuns.length}
            </span>
          </h3>

          {crawlRuns.length === 0 ? (
            <div className="text-center py-8">
              <Clock className="w-8 h-8 text-slate-400 mx-auto mb-2" />
              <p className="text-xs font-bold text-slate-500">No crawl runs yet</p>
            </div>
          ) : (
            <div className="space-y-3">
              {crawlRuns.map((run) => {
                const isFailed = run.status.toLowerCase() === 'failed' || run.status.toLowerCase() === 'error';
                return (
                  <div
                    key={run.id}
                    className="sharetopus-card p-4 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-[#F8F9F4] dark:bg-[#1A2336] space-y-2"
                  >
                    <div className="flex items-center justify-between flex-wrap gap-2">
                      <div className="flex items-center gap-2">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-extrabold border ${statusBadge(run.status)}`}
                        >
                          {run.status}
                        </span>
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-extrabold bg-[#2563EB]/15 text-[#2563EB] border border-[#2563EB]">
                          {run.trigger}
                        </span>
                      </div>
                      {isFailed && (
                        <button
                          type="button"
                          onClick={() => void handleRetry(run.id)}
                          disabled={retrying === run.id}
                          className="btn-sharetopus-secondary text-[10px] py-1 px-3 font-bold flex items-center gap-1"
                        >
                          {retrying === run.id ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <RotateCcw className="w-3 h-3" />
                          )}
                          Retry
                        </button>
                      )}
                    </div>

                    <div className="flex items-center gap-4 text-[11px] font-mono font-extrabold flex-wrap">
                      <span className="flex items-center gap-1 text-[#059669]">
                        <CheckCircle2 className="w-3 h-3" />
                        {run.discoveredCount} discovered
                      </span>
                      <span className="flex items-center gap-1 text-[#2563EB]">
                        <Globe className="w-3 h-3" />
                        {run.fetchedCount} fetched
                      </span>
                      {run.failedCount > 0 && (
                        <span className="flex items-center gap-1 text-[#FF5A36]">
                          <XCircle className="w-3 h-3" />
                          {run.failedCount} failed
                        </span>
                      )}
                    </div>

                    {run.errorSummary && (
                      <p className="text-[11px] font-mono text-[#FF5A36] bg-[#FF5A36]/5 px-3 py-2 rounded-xl">
                        {run.errorSummary}
                      </p>
                    )}

                    <p className="text-[10px] font-mono text-slate-500 dark:text-slate-400 truncate">
                      Source: {run.sourceId}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
