import React, { useState } from 'react';
import {
  ShieldCheck,
  X,
  ExternalLink,
  RefreshCw,
  LogIn,
  LogOut,
  AlertCircle,
} from 'lucide-react';
import type { AdminMe, ReviewItem } from '../api';

interface AdminQueueProps {
  items: ReviewItem[];
  total: number;
  admin: AdminMe | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onLogin: () => void;
  onLogout: () => void;
  onApprove: (item: ReviewItem) => Promise<void>;
  onReject: (item: ReviewItem) => Promise<void>;
}

function snapshotTitle(snapshot: Record<string, unknown>): string {
  return (
    String(snapshot.title ?? snapshot.productName ?? snapshot.claimedTitle ?? 'Untitled candidate')
  );
}

function snapshotUrls(snapshot: Record<string, unknown>): string[] {
  const urls: string[] = [];
  if (typeof snapshot.officialUrl === 'string') urls.push(snapshot.officialUrl);
  if (typeof snapshot.claimUrl === 'string') urls.push(snapshot.claimUrl);
  if (typeof snapshot.url === 'string') urls.push(snapshot.url);
  if (Array.isArray(snapshot.discoveredUrls)) {
    for (const u of snapshot.discoveredUrls) {
      if (typeof u === 'string') urls.push(u);
    }
  }
  return [...new Set(urls)];
}

export const AdminQueue: React.FC<AdminQueueProps> = ({
  items,
  total,
  admin,
  loading,
  error,
  onRefresh,
  onLogin,
  onLogout,
  onApprove,
  onReject,
}) => {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const runApprove = async (item: ReviewItem) => {
    setBusyId(item.id);
    setActionError(null);
    try {
      await onApprove(item);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Approve failed');
    } finally {
      setBusyId(null);
    }
  };

  const runReject = async (item: ReviewItem) => {
    setBusyId(item.id);
    setActionError(null);
    try {
      await onReject(item);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Reject failed');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto px-4 lg:px-8 py-6 font-sans">
      <div className="sharetopus-card p-6 rounded-[28px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-2xl bg-[#D97706]/15 text-[#D97706] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-extrabold text-[#1C1B18] dark:text-white">
              Verification & Review Queue
            </h2>
            <p className="text-xs text-[#1C1B18] dark:text-[#F8FAF9] font-bold">
              Admin-only queue from the backend pipeline. Approve publishes to the public catalogue.
            </p>
          </div>
        </div>

        <div className="flex flex-col items-end gap-2">
          <div className="px-4 py-2.5 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-xs font-mono font-extrabold text-[#1C1B18] dark:text-slate-200 text-right">
            <div>
              Pending: <strong className="text-[#D97706] font-extrabold">{total}</strong>
            </div>
            <div className="text-[10px] text-[#1C1B18] dark:text-slate-300">
              {admin ? `Signed in as @${admin.login}` : 'Not authenticated'}
            </div>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onRefresh}
              disabled={loading}
              className="btn-sharetopus-secondary text-xs py-1.5 px-3 font-bold"
            >
              <RefreshCw className={`w-3.5 h-3.5 inline mr-1 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            {admin ? (
              <button
                type="button"
                onClick={onLogout}
                className="btn-sharetopus-secondary text-xs py-1.5 px-3 font-bold"
              >
                <LogOut className="w-3.5 h-3.5 inline mr-1" />
                Logout
              </button>
            ) : (
              <button
                type="button"
                onClick={onLogin}
                className="btn-sharetopus-primary text-xs py-1.5 px-3 font-bold"
              >
                <LogIn className="w-3.5 h-3.5 inline mr-1" />
                GitHub Login
              </button>
            )}
          </div>
        </div>
      </div>

      {(error || actionError) && (
        <div className="sharetopus-card p-4 rounded-2xl border-[1.5px] border-[#FF5A36] bg-[#FF5A36]/10 text-xs font-bold text-[#1C1B18] dark:text-white flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-[#FF5A36] shrink-0 mt-0.5" />
          <span>{error || actionError}</span>
        </div>
      )}

      {!admin && !loading ? (
        <div className="sharetopus-card p-12 text-center rounded-[24px] space-y-3 bg-white dark:bg-[#131A29]">
          <LogIn className="w-10 h-10 text-[#D97706] mx-auto" />
          <h3 className="text-lg font-extrabold text-[#1C1B18] dark:text-white">
            Admin session required
          </h3>
          <p className="text-xs font-bold text-slate-700 dark:text-slate-300 max-w-md mx-auto">
            Sign in with an allowlisted GitHub account to load review items from{' '}
            <code className="font-mono">/api/v1/admin/review-items</code>.
          </p>
          <button type="button" onClick={onLogin} className="btn-sharetopus-primary text-xs py-2 px-4 font-bold">
            Continue with GitHub
          </button>
        </div>
      ) : loading && items.length === 0 ? (
        <div className="sharetopus-card p-12 text-center rounded-[24px] bg-white dark:bg-[#131A29]">
          <RefreshCw className="w-8 h-8 animate-spin text-[#D97706] mx-auto mb-3" />
          <p className="text-xs font-bold">Loading review queue…</p>
        </div>
      ) : items.length === 0 ? (
        <div className="sharetopus-card p-12 text-center rounded-[24px] space-y-3 bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-white">
          <div className="w-12 h-12 rounded-full bg-[#059669]/15 text-[#059669] mx-auto flex items-center justify-center border border-[#059669]">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <h3 className="text-lg font-extrabold">Review Queue Clear!</h3>
          <p className="text-xs font-bold text-slate-700 dark:text-slate-300">
            No open review items in the backend.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((item) => {
            const urls = snapshotUrls(item.candidateSnapshot);
            const title = snapshotTitle(item.candidateSnapshot);
            return (
              <div
                key={item.id}
                className="sharetopus-card p-5 rounded-[24px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] space-y-4"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs font-extrabold">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="px-3 py-1 rounded-full bg-[#D97706]/15 text-[#D97706] border border-[#D97706] text-[11px] font-extrabold uppercase">
                      {item.state}
                    </span>
                    <span className="px-3 py-1 rounded-full bg-[#F3F4EF] dark:bg-[#1A2336] border border-[#1C1B18] dark:border-[#D6DCE5] text-[11px] font-extrabold">
                      {item.candidateType}
                    </span>
                    <span className="text-[#1C1B18] dark:text-slate-300 font-mono text-xs">
                      priority {item.priority} · v{item.version}
                    </span>
                  </div>
                  <div className="font-mono text-[#1C1B18] dark:text-slate-200 text-xs">
                    {new Date(item.createdAt).toLocaleString()}
                  </div>
                </div>

                <div>
                  <h3 className="text-base font-extrabold text-[#1C1B18] dark:text-white">{title}</h3>
                  <p className="text-xs font-bold text-slate-600 dark:text-slate-300 mt-1">{item.reason}</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div className="sharetopus-card p-3.5 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] space-y-2">
                    <div className="font-extrabold text-[#1C1B18] dark:text-white font-mono text-[11px]">
                      Target URLs
                    </div>
                    {urls.length === 0 ? (
                      <p className="text-[11px] text-slate-500">No URL in snapshot</p>
                    ) : (
                      urls.map((url) => (
                        <a
                          key={url}
                          href={url}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center gap-1.5 text-[#0284C7] dark:text-[#D6DCE5] hover:underline font-mono text-[11px] font-extrabold truncate"
                        >
                          <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                          <span>{url}</span>
                        </a>
                      ))
                    )}
                  </div>

                  <div className="sharetopus-card p-3.5 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] space-y-2">
                    <div className="font-extrabold text-[#1C1B18] dark:text-white font-mono text-[11px]">
                      Candidate Snapshot
                    </div>
                    <pre className="text-[10px] text-[#059669] dark:text-[#34D399] font-mono bg-[#090C15] p-2.5 rounded-xl border border-[#1C1B18] dark:border-[#D6DCE5] max-h-32 overflow-y-auto font-extrabold">
                      {JSON.stringify(item.candidateSnapshot, null, 2)}
                    </pre>
                  </div>
                </div>

                <div className="pt-2 border-t border-[#D6D5CF] dark:border-slate-800 flex items-center justify-end gap-2 text-xs font-bold">
                  <button
                    type="button"
                    onClick={() => void runReject(item)}
                    disabled={busyId === item.id}
                    className="btn-sharetopus-secondary text-xs py-2 px-4"
                  >
                    <X className="w-4 h-4 inline mr-1" />
                    Reject
                  </button>
                  <button
                    type="button"
                    onClick={() => void runApprove(item)}
                    disabled={busyId === item.id}
                    className="btn-sharetopus-primary text-xs py-2 px-4 bg-[#059669] hover:bg-[#047857]"
                  >
                    <RefreshCw className={`w-4 h-4 inline mr-1 ${busyId === item.id ? 'animate-spin' : ''}`} />
                    {busyId === item.id ? 'Working…' : 'Approve & Publish'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
