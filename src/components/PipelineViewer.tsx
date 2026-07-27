import React, { useState, useEffect } from 'react';
import { 
  Activity, 
  Layers, 
  ShieldCheck, 
  Cpu, 
  Database, 
  Globe, 
  Sparkles,
  Server,
  FileCode,
  Workflow,
  Share2,
  RefreshCw,
  Loader2,
  CheckCircle2,
  XCircle,
  RotateCcw,
} from 'lucide-react';
import { fetchCrawlRuns, retryCrawlRun } from '../api/pipeline';
import type { CrawlRun } from '../api/pipeline';

interface PipelineViewerProps {
  admin?: { subject: string; email: string; csrfToken: string } | null;
}

export const PipelineViewer: React.FC<PipelineViewerProps> = ({ admin }) => {
  const [crawlRuns, setCrawlRuns] = useState<CrawlRun[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [runsError, setRunsError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);

  const loadRuns = async () => {
    if (!admin) return;
    setRunsLoading(true);
    setRunsError(null);
    try {
      const data = await fetchCrawlRuns();
      setCrawlRuns(data);
    } catch (err) {
      setRunsError(err instanceof Error ? err.message : 'Failed to load crawl runs');
    } finally {
      setRunsLoading(false);
    }
  };

  useEffect(() => {
    void loadRuns();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [admin]);

  const handleRetry = async (runId: string) => {
    if (!admin) return;
    setRetrying(runId);
    try {
      const updated = await retryCrawlRun(runId, admin.csrfToken);
      setCrawlRuns((prev) => prev.map((r) => (r.id === runId ? updated : r)));
    } catch (err) {
      setRunsError(err instanceof Error ? err.message : 'Retry failed');
    } finally {
      setRetrying(null);
    }
  };

  const pipelineSteps = [
    { name: '1. Source Scheduler', desc: 'Periodic cron polling & X API stream listener', icon: Activity, status: 'Active' },
    { name: '2. Fetcher / Worker', desc: 'Headless Chrome worker & HTTP client', icon: Globe, status: 'Active' },
    { name: '3. Raw Doc Storage', desc: 'Immutable HTML / JSON snippet archive', icon: Server, status: 'Active' },
    { name: '4. Rule Parser', desc: 'Cleans navbars, footers, ads & noise', icon: FileCode, status: 'Active' },
    { name: '5. LLM Extractor', desc: 'Extracts structured JSON fields', icon: Cpu, status: 'Active' },
    { name: '6. Normalizer', desc: 'Standardizes ISO dates, currencies & timezone', icon: Sparkles, status: 'Active' },
    { name: '7. Deduplicator', desc: 'Merges multi-source signals (X + Devpost)', icon: Layers, status: 'Active' },
    { name: '8. Verification Engine', desc: 'HTTP HEAD checks & deadline validation', icon: ShieldCheck, status: 'Active' },
    { name: '9. PostgreSQL & API', desc: 'Full-text & trigram indexed search API', icon: Database, status: 'Active' },
  ];

  function statusBadge(status: string) {
    const s = status.toLowerCase();
    if (['completed', 'done'].includes(s)) return 'bg-[#059669]/15 text-[#059669] border-[#059669]';
    if (['failed', 'error'].includes(s)) return 'bg-[#FF5A36]/15 text-[#FF5A36] border-[#FF5A36]';
    if (['queued', 'running', 'in_progress'].includes(s)) return 'bg-[#D97706]/15 text-[#D97706] border-[#D97706]';
    return 'bg-slate-400/15 text-slate-500 border-slate-400';
  }

  return (
    <div className="space-y-8 max-w-6xl mx-auto px-4 lg:px-8 py-6 font-sans">
      
      {/* Top Banner */}
      <div className="sharetopus-card p-6 rounded-[28px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] space-y-3">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-2xl bg-[#059669]/15 text-[#059669] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
            <Workflow className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-extrabold text-[#1C1B18] dark:text-white">DevRadar Multi-Tier Data Ingestion Pipeline</h2>
            <p className="text-xs text-[#1C1B18] dark:text-[#F8FAF9] font-bold">
              Architecture separated into deterministic fetchers, rule-based parsers, and LLM structured extraction as defined in <code className="text-[#FF5A36] font-mono font-extrabold">konsep.md</code>.
            </p>
          </div>
        </div>
      </div>

      {/* Visual Pipeline Flow Grid */}
      <div className="sharetopus-card p-6 rounded-[28px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] space-y-4">
        <h3 className="text-base font-extrabold text-[#1C1B18] dark:text-white flex items-center gap-2 font-mono">
          <Cpu className="w-5 h-5 text-[#FF5A36]" />
          9-Step Deterministic + AI Processing Flow
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          {pipelineSteps.map((step, idx) => {
            const Icon = step.icon;
            return (
              <div key={idx} className="sharetopus-card p-4 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-[#F8F9F4] dark:bg-[#1A2336] space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded-xl bg-white dark:bg-[#131A29] border border-[#1C1B18] dark:border-[#D6DCE5] text-[#FF5A36]">
                      <Icon className="w-4 h-4" />
                    </div>
                    <span className="font-extrabold text-xs text-[#1C1B18] dark:text-white">{step.name}</span>
                  </div>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-extrabold bg-[#059669]/15 text-[#059669] border border-[#059669]">
                    {step.status}
                  </span>
                </div>
                <p className="text-[11px] text-[#1C1B18] dark:text-[#F8FAF9] font-bold">{step.desc}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Live Crawl Runs (from backend) */}
      {admin && (
        <div className="sharetopus-card p-6 rounded-[28px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-extrabold text-[#1C1B18] dark:text-white flex items-center gap-2 font-mono">
              <Activity className="w-5 h-5 text-[#D97706]" />
              Live Crawl Runs
              {crawlRuns.length > 0 && (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-extrabold bg-[#D97706]/15 text-[#D97706] border border-[#D97706]">
                  {crawlRuns.length}
                </span>
              )}
            </h3>
            <button
              type="button"
              onClick={() => void loadRuns()}
              disabled={runsLoading}
              className="btn-sharetopus-secondary text-[10px] py-1.5 px-3 font-bold flex items-center gap-1"
            >
              <RefreshCw className={`w-3 h-3 ${runsLoading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>

          {runsError && (
            <p className="text-xs text-[#FF5A36] font-bold">{runsError}</p>
          )}

          {runsLoading ? (
            <div className="text-center py-6">
              <Loader2 className="w-6 h-6 animate-spin text-[#D97706] mx-auto" />
            </div>
          ) : crawlRuns.length === 0 ? (
            <p className="text-xs text-slate-500 font-bold text-center py-4">No crawl runs recorded yet.</p>
          ) : (
            <div className="space-y-2">
              {crawlRuns.slice(0, 10).map((run) => {
                const isFailed = ['failed', 'error'].includes(run.status.toLowerCase());
                return (
                  <div key={run.id} className="flex items-center justify-between gap-3 px-4 py-3 rounded-2xl border border-[#1C1B18]/10 dark:border-white/10 bg-[#F8F9F4] dark:bg-[#1A2336]">
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <span className={`shrink-0 px-2 py-0.5 rounded-full text-[10px] font-mono font-extrabold border ${statusBadge(run.status)}`}>
                        {run.status}
                      </span>
                      <span className="text-[11px] font-mono font-extrabold text-[#1C1B18] dark:text-white truncate">
                        {run.trigger}
                      </span>
                      <span className="flex items-center gap-1 text-[10px] font-mono text-[#059669]">
                        <CheckCircle2 className="w-3 h-3" />{run.discoveredCount}
                      </span>
                      <span className="flex items-center gap-1 text-[10px] font-mono text-[#2563EB]">
                        <Globe className="w-3 h-3" />{run.fetchedCount}
                      </span>
                      {run.failedCount > 0 && (
                        <span className="flex items-center gap-1 text-[10px] font-mono text-[#FF5A36]">
                          <XCircle className="w-3 h-3" />{run.failedCount}
                        </span>
                      )}
                    </div>
                    {isFailed && (
                      <button
                        type="button"
                        onClick={() => void handleRetry(run.id)}
                        disabled={retrying === run.id}
                        className="btn-sharetopus-secondary text-[10px] py-1 px-2 font-bold flex items-center gap-1 shrink-0"
                      >
                        {retrying === run.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
                        Retry
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Source Hierarchy Tiers */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* Tier 1 */}
        <div className="sharetopus-card p-5 rounded-[24px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] space-y-3">
          <div className="flex items-center justify-between">
            <span className="px-3 py-1 rounded-full bg-[#059669]/15 text-[#059669] border border-[#059669] text-xs font-extrabold">Tier 1 — Official</span>
            <span className="text-[10px] font-mono text-[#059669] font-extrabold">100% Weight</span>
          </div>
          <h4 className="font-extrabold text-[#1C1B18] dark:text-white text-sm">Official Organization Websites</h4>
          <p className="text-xs text-[#1C1B18] dark:text-[#F8FAF9] font-bold">
            Rules pages, official blogs, pricing tables, documentation, changelogs, and verified company repositories.
          </p>
          <ul className="text-xs text-[#1C1B18] dark:text-[#B8C4D2] space-y-1 font-mono font-extrabold">
            <li>• anthropic.com/hackathon</li>
            <li>• vercel.com/pricing</li>
            <li>• github.com/education</li>
          </ul>
        </div>

        {/* Tier 2 */}
        <div className="sharetopus-card p-5 rounded-[24px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] space-y-3">
          <div className="flex items-center justify-between">
            <span className="px-3 py-1 rounded-full bg-[#7C3AED]/15 text-[#7C3AED] border border-[#7C3AED] text-xs font-extrabold">Tier 2 — Aggregator</span>
            <span className="text-[10px] font-mono text-[#7C3AED] font-extrabold">80% Weight</span>
          </div>
          <h4 className="font-extrabold text-[#1C1B18] dark:text-white text-sm">Curated Developer Aggregators</h4>
          <p className="text-xs text-[#1C1B18] dark:text-[#F8FAF9] font-bold">
            Devpost directory, Major League Hacking (MLH), HackerEarth challenges, Kaggle competitions.
          </p>
          <ul className="text-xs text-[#1C1B18] dark:text-[#B8C4D2] space-y-1 font-mono font-extrabold">
            <li>• devpost.com</li>
            <li>• mlh.io</li>
            <li>• hackerearth.com</li>
          </ul>
        </div>

        {/* Tier 3 */}
        <div className="sharetopus-card p-5 rounded-[24px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] space-y-3">
          <div className="flex items-center justify-between">
            <span className="px-3 py-1 rounded-full bg-[#D97706]/15 text-[#D97706] border border-[#D97706] text-xs font-extrabold">Tier 3 — X Signal</span>
            <span className="text-[10px] font-mono text-[#D97706] font-extrabold">Needs Verification</span>
          </div>
          <h4 className="font-extrabold text-[#1C1B18] dark:text-white text-sm">Social Discovery & Posts</h4>
          <p className="text-xs text-[#1C1B18] dark:text-[#F8FAF9] font-bold">
            X (Twitter) posts, Reddit, Discord announcements. Used purely to discover external URLs for verification.
          </p>
          <ul className="text-xs text-[#1C1B18] dark:text-[#B8C4D2] space-y-1 font-mono font-extrabold">
            <li>• X Recent Search API</li>
            <li>• Discovered candidate links</li>
            <li>• Requires Tier 1 check</li>
          </ul>
        </div>

      </div>

      {/* X Query Strategy Box */}
      <div className="sharetopus-card p-6 rounded-[28px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] space-y-3">
        <h4 className="font-extrabold text-[#1C1B18] dark:text-white text-sm font-mono flex items-center gap-2">
          <Share2 className="w-4 h-4 text-[#FF5A36]" />
          X Discovery API Search Operator Rules
        </h4>
        <div className="p-4 rounded-2xl bg-[#090C15] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#34D399] font-mono text-xs overflow-x-auto space-y-2 font-bold">
          <div>// Query Group 1: Online Hackathons & AI Challenges</div>
          <div className="text-[#D6DCE5]">("hackathon" OR "developer challenge") (online OR virtual OR worldwide) -is:retweet</div>
          
          <div className="pt-2">// Query Group 2: Free AI Credits & Promos</div>
          <div className="text-[#A78BFA]">("free credits" OR "free tier" OR "developer credits") (AI OR LLM OR coding) -is:retweet</div>
        </div>
      </div>

    </div>
  );
};
