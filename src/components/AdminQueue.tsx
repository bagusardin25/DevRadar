import React, { useState } from 'react';
import {
  ShieldCheck,
  X,
  ExternalLink,
  RefreshCw,
  LogIn,
  LogOut,
  AlertCircle,
  Sparkles,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ArrowLeft,
  Inbox,
} from 'lucide-react';
import type {
  AdminMe,
  AIReviewRecommendation,
  ReviewCorrections,
  ReviewItem,
} from '../api';
import { readAIReview, readAIUsage, readVerification } from '../api';

interface AdminQueueProps {
  items: ReviewItem[];
  total: number;
  admin: AdminMe | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onLogin: () => void;
  onLogout: () => void;
  onBackToRadar: () => void;
  onApprove: (
    item: ReviewItem,
    corrections: ReviewCorrections,
    notes?: string,
  ) => Promise<void>;
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

type RecoStyle = {
  label: string;
  className: string;
  Icon: React.ComponentType<{ className?: string }>;
};

const RECO_STYLE: Record<AIReviewRecommendation, RecoStyle> = {
  approve: {
    label: 'Approve',
    className: 'text-[#059669] border-[#059669] bg-[#059669]/12',
    Icon: CheckCircle2,
  },
  reject: {
    label: 'Reject',
    className: 'text-[#FF5A36] border-[#FF5A36] bg-[#FF5A36]/12',
    Icon: XCircle,
  },
  needs_more_info: {
    label: 'Needs info',
    className: 'text-[#D97706] border-[#D97706] bg-[#D97706]/12',
    Icon: AlertTriangle,
  },
};

const SEVERITY_DOT: Record<'high' | 'medium' | 'low', string> = {
  high: 'bg-[#FF5A36]',
  medium: 'bg-[#D97706]',
  low: 'bg-slate-400',
};

function formatSuggested(value: unknown): string {
  if (Array.isArray(value)) return value.map(String).join(', ');
  if (value && typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function formatEstimatedUsd(value: number): string {
  if (value === 0) return '$0.000000';
  return `$${value < 0.01 ? value.toFixed(6) : value.toFixed(4)}`;
}

function formatTokenCount(value: number): string {
  return new Intl.NumberFormat('en-US').format(value);
}

function parseSuggested(value: string, template: unknown): unknown {
  if (Array.isArray(template)) {
    return value
      .split(',')
      .map((part) => part.trim())
      .filter(Boolean);
  }
  if (typeof template === 'number') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : template;
  }
  if (typeof template === 'boolean') return value.toLowerCase() === 'true';
  if (template && typeof template === 'object') {
    try {
      return JSON.parse(value) as unknown;
    } catch {
      return template;
    }
  }
  return value;
}

function hasPublishableMinimum(
  snapshot: Record<string, unknown>,
  corrections: ReviewCorrections = {},
): boolean {
  const snapshotFields =
    snapshot.fields && typeof snapshot.fields === 'object' && !Array.isArray(snapshot.fields)
      ? (snapshot.fields as Record<string, unknown>)
      : {};
  const fields = { ...snapshotFields, ...(corrections.fields ?? {}) };
  const title =
    corrections.title ?? snapshot.title ?? snapshot.claimedTitle ?? fields.title ?? fields.product_name;
  const kind = corrections.kind ?? snapshot.kind ?? snapshot.claimedType ?? fields.kind;
  const url =
    corrections.officialUrl ??
    corrections.claimUrl ??
    snapshot.officialUrl ??
    snapshot.url ??
    fields.official_url ??
    fields.official_terms_url ??
    fields.claim_url;
  return Boolean(title && (kind === 'hackathon' || kind === 'ai_offer') && url);
}

/** CodeRabbit-style automated pre-review shown above the raw snapshot. */
const AIReviewPanel: React.FC<{ snapshot: Record<string, unknown> }> = ({ snapshot }) => {
  const review = readAIReview(snapshot);
  const verification = readVerification(snapshot);
  const usage = readAIUsage(snapshot);
  if (!review) return null;
  const reco = RECO_STYLE[review.recommendation];
  const RecoIcon = reco.Icon;
  const suggested = Object.entries(review.suggestedFields);

  return (
    <div className="rounded-2xl border-[1.5px] border-[#7C3AED] bg-[#7C3AED]/[0.06] dark:bg-[#7C3AED]/[0.14] p-4 space-y-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-[#7C3AED] dark:text-[#C4B5FD]" />
          <span className="text-xs font-extrabold uppercase tracking-wide text-[#7C3AED] dark:text-[#C4B5FD]">
            AI Initial Review
          </span>
          <span className="text-[10px] font-mono font-bold text-slate-500 dark:text-slate-400">
            {review.model ?? review.engine}
          </span>
        </div>
        <span
          className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border-[1.5px] text-[11px] font-extrabold uppercase ${reco.className}`}
        >
          <RecoIcon className="w-3.5 h-3.5" />
          {reco.label}
          <span className="opacity-70 font-mono normal-case">· {review.confidence}/100</span>
        </span>
      </div>

      <p className="text-xs font-bold text-[#1C1B18] dark:text-slate-100 leading-relaxed">
        {review.summary}
      </p>

      {verification && (
        <div className="text-[10px] font-mono font-bold text-slate-600 dark:text-slate-300">
          verify: {verification.status} · {verification.score}/100 ·{' '}
          {verification.publishable ? 'publishable' : 'not publishable'}
        </div>
      )}

      {usage && (
        <div
          aria-label="AI usage estimate"
          className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-[#7C3AED]/30 bg-white/70 px-3 py-2 text-[10px] font-mono font-extrabold text-slate-600 dark:bg-[#0F1624]/70 dark:text-slate-300"
        >
          <span>
            {usage.calls.length === 0
              ? 'No paid model calls'
              : `${usage.calls.length} model call${usage.calls.length === 1 ? '' : 's'}`}
          </span>
          <span>{formatTokenCount(usage.totalTokens)} tokens</span>
          <span className="text-[#7C3AED] dark:text-[#C4B5FD]">
            {usage.estimatedCostUsd === null
              ? 'Pricing unavailable'
              : `${formatEstimatedUsd(usage.estimatedCostUsd)} est.`}
          </span>
          {usage.cachedPromptTokens > 0 && (
            <span>{formatTokenCount(usage.cachedPromptTokens)} cached</span>
          )}
        </div>
      )}

      {review.concerns.length > 0 && (
        <ul className="space-y-1.5">
          {review.concerns.map((c, i) => (
            <li
              key={i}
              className="flex items-start gap-2 text-[11px] font-bold text-[#1C1B18] dark:text-slate-200"
            >
              <span
                className={`mt-1 w-2 h-2 rounded-full shrink-0 ${SEVERITY_DOT[c.severity]}`}
                aria-hidden
              />
              <span>
                <span className="uppercase text-[9px] font-mono opacity-60 mr-1">{c.severity}</span>
                {c.message}
              </span>
            </li>
          ))}
        </ul>
      )}

      {suggested.length > 0 && (
        <details className="text-[11px]">
          <summary className="cursor-pointer font-extrabold text-[#7C3AED] dark:text-[#C4B5FD]">
            Suggested fields ({suggested.length})
          </summary>
          <dl className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">
            {suggested.map(([k, v]) => (
              <div key={k} className="flex gap-1.5 min-w-0">
                <dt className="font-mono font-extrabold text-slate-500 dark:text-slate-400 shrink-0">
                  {k}:
                </dt>
                <dd className="font-bold text-[#1C1B18] dark:text-slate-100 truncate">
                  {formatSuggested(v)}
                </dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </div>
  );
};

export const AdminQueue: React.FC<AdminQueueProps> = ({
  items,
  total,
  admin,
  loading,
  error,
  onRefresh,
  onLogin,
  onLogout,
  onBackToRadar,
  onApprove,
  onReject,
}) => {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Record<string, string>>>({});
  const [selectedFields, setSelectedFields] = useState<Record<string, string[]>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [coreDrafts, setCoreDrafts] = useState<
    Record<
      string,
      { title: string; description: string; kind: 'hackathon' | 'ai_offer'; officialUrl: string }
    >
  >({});

  const beginFieldReview = (item: ReviewItem) => {
    const snapshot = item.candidateSnapshot;
    const fields =
      snapshot.fields && typeof snapshot.fields === 'object' && !Array.isArray(snapshot.fields)
        ? (snapshot.fields as Record<string, unknown>)
        : {};
    const rawKind = snapshot.kind ?? snapshot.claimedType ?? fields.kind;
    const suggested = readAIReview(item.candidateSnapshot)?.suggestedFields ?? {};
    setDrafts((current) => ({
      ...current,
      [item.id]: Object.fromEntries(
        Object.entries(suggested).map(([key, value]) => [key, formatSuggested(value)]),
      ),
    }));
    setSelectedFields((current) => ({ ...current, [item.id]: Object.keys(suggested) }));
    setCoreDrafts((current) => ({
      ...current,
      [item.id]: {
        title: String(snapshot.title ?? snapshot.claimedTitle ?? fields.title ?? fields.product_name ?? ''),
        description: String(snapshot.description ?? fields.description ?? ''),
        kind: rawKind === 'ai_offer' ? 'ai_offer' : 'hackathon',
        officialUrl: String(
          snapshot.officialUrl ??
            snapshot.url ??
            fields.official_url ??
            fields.official_terms_url ??
            fields.claim_url ??
            '',
        ),
      },
    }));
    setEditingId(item.id);
  };

  const buildCorrections = (item: ReviewItem): ReviewCorrections => {
    const suggested = readAIReview(item.candidateSnapshot)?.suggestedFields ?? {};
    const selected = new Set(selectedFields[item.id] ?? []);
    const draft = drafts[item.id] ?? {};
    const corrections: ReviewCorrections = {};
    const fields: Record<string, unknown> = {};

    for (const [key, template] of Object.entries(suggested)) {
      if (!selected.has(key)) continue;
      const parsed = parseSuggested(draft[key] ?? formatSuggested(template), template);
      if (key === 'title') corrections.title = String(parsed);
      else if (key === 'description') corrections.description = String(parsed);
      else if (key === 'kind' && (parsed === 'hackathon' || parsed === 'ai_offer')) {
        corrections.kind = parsed;
      } else {
        fields[key] = parsed;
      }
      if (key === 'official_url' || key === 'official_terms_url') {
        corrections.officialUrl = String(parsed);
      }
      if (key === 'claim_url') corrections.claimUrl = String(parsed);
    }
    const core = coreDrafts[item.id];
    if (core) {
      if (core.title.trim()) corrections.title = core.title.trim();
      if (core.description.trim()) corrections.description = core.description.trim();
      corrections.kind = core.kind;
      if (core.officialUrl.trim()) {
        corrections.officialUrl = core.officialUrl.trim();
        fields.official_url = core.officialUrl.trim();
      }
    }
    if (Object.keys(fields).length > 0) corrections.fields = fields;
    return corrections;
  };

  const runApprove = async (item: ReviewItem) => {
    setBusyId(item.id);
    setActionError(null);
    try {
      await onApprove(item, buildCorrections(item), notes[item.id]?.trim() || undefined);
      setEditingId(null);
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

  const shownUsage = items.map((item) => readAIUsage(item.candidateSnapshot));
  const shownTokens = shownUsage.reduce(
    (total, usage) => total + (usage?.totalTokens ?? 0),
    0,
  );
  const shownCost = shownUsage.reduce(
    (total, usage) => total + (usage?.estimatedCostUsd ?? 0),
    0,
  );
  const shownPricingComplete = shownUsage.every(
    (usage) => usage === null || usage.pricingComplete,
  );

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
              Pending:{' '}
              <strong className="text-[#D97706] font-extrabold">{admin ? total : '--'}</strong>
            </div>
            {admin ? (
              <div className="text-[10px] text-[#7C3AED] dark:text-[#C4B5FD]">
                Shown AI:{' '}
                {shownPricingComplete
                  ? formatEstimatedUsd(shownCost) + ' est.'
                  : 'pricing unavailable'} /{' '}
                {formatTokenCount(shownTokens)} tokens
              </div>
            ) : null}
            <div className="text-[10px] text-[#1C1B18] dark:text-slate-300">
              {admin ? `Signed in as ${admin.email}` : 'Requires authentication'}
            </div>
          </div>
          {admin ? (
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
              <button
                type="button"
                onClick={onLogout}
                className="btn-sharetopus-secondary text-xs py-1.5 px-3 font-bold"
              >
                <LogOut className="w-3.5 h-3.5 inline mr-1" />
                Logout
              </button>
            </div>
          ) : null}
        </div>
      </div>

      {(error || actionError) && (
        <div className="sharetopus-card p-4 rounded-2xl border-[1.5px] border-[#FF5A36] bg-[#FF5A36]/10 text-xs font-bold text-[#1C1B18] dark:text-white flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-[#FF5A36] shrink-0 mt-0.5" />
          <span>{error || actionError}</span>
        </div>
      )}

      {!admin && !loading ? (
        <div className="sharetopus-card mx-auto max-w-2xl p-8 sm:p-12 text-center rounded-[28px] space-y-4 bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5]">
          <div className="mx-auto flex w-fit items-center gap-2 rounded-full border border-[#D97706] bg-[#D97706]/10 px-3 py-1.5 text-[10px] font-extrabold uppercase tracking-wider text-[#B45309] dark:text-[#FBBF24]">
            <ShieldCheck className="h-3.5 w-3.5" />
            Admin access
          </div>
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border-[1.5px] border-[#1C1B18] bg-[#D97706]/15 text-[#D97706] dark:border-[#D6DCE5]">
            <LogIn className="h-7 w-7" />
          </div>
          <h3 className="text-lg font-extrabold text-[#1C1B18] dark:text-white">
            Sign in to the operator workspace
          </h3>
          <p className="text-xs font-bold text-slate-700 dark:text-slate-300 max-w-md mx-auto">
            Use an allowlisted Google account to review submissions and manage the public catalogue.
          </p>
          <button type="button" onClick={onLogin} className="btn-sharetopus-primary text-xs py-2.5 px-5 font-bold">
            <LogIn className="mr-1.5 inline h-4 w-4" />
            Continue with Google
          </button>
        </div>
      ) : loading && items.length === 0 ? (
        <div className="sharetopus-card p-12 text-center rounded-[24px] bg-white dark:bg-[#131A29]">
          <RefreshCw className="w-8 h-8 animate-spin text-[#D97706] mx-auto mb-3" />
          <p className="text-xs font-bold">Loading review queue…</p>
        </div>
      ) : items.length === 0 ? (
        <div className="sharetopus-card p-7 sm:p-10 text-center rounded-[24px] space-y-4 bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-white">
          <div className="relative mx-auto max-w-sm rounded-2xl border-[1.5px] border-dashed border-[#9C988E] bg-[#F8F9F4] p-4 text-left dark:border-slate-600 dark:bg-[#1A2336]" aria-hidden="true">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-[10px] font-mono font-extrabold uppercase text-slate-600 dark:text-slate-300">
                <Inbox className="h-4 w-4 text-[#059669]" />
                Queue preview
              </div>
              <span className="rounded-full bg-[#059669]/15 px-2 py-1 text-[9px] font-extrabold text-[#047857] dark:text-[#34D399]">
                0 open
              </span>
            </div>
            <div className="mt-4 space-y-2 opacity-60">
              <div className="h-2.5 w-3/4 rounded-full bg-[#D6D5CF] dark:bg-slate-600" />
              <div className="h-2.5 w-1/2 rounded-full bg-[#E5E6DF] dark:bg-slate-700" />
            </div>
            <div className="absolute -bottom-3 -right-2 flex h-10 w-10 items-center justify-center rounded-full border-[1.5px] border-[#059669] bg-white text-[#059669] shadow-[2px_2px_0_0_#059669] dark:bg-[#131A29]">
              <ShieldCheck className="h-5 w-5" />
            </div>
          </div>
          <h3 className="text-lg font-extrabold">Review Queue Clear!</h3>
          <p className="text-xs font-bold text-slate-700 dark:text-slate-300">
            No open review items. New submissions will appear here automatically.
          </p>
          <button type="button" onClick={onBackToRadar} className="btn-sharetopus-secondary px-4 py-2 text-xs font-bold">
            <ArrowLeft className="mr-1.5 inline h-4 w-4" />
            Back to Radar
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((item) => {
            const urls = snapshotUrls(item.candidateSnapshot);
            const title = snapshotTitle(item.candidateSnapshot);
            const review = readAIReview(item.candidateSnapshot);
            const suggested = Object.entries(review?.suggestedFields ?? {});
            const isEditing = editingId === item.id;
            const pendingCorrections = isEditing ? buildCorrections(item) : {};
            const canPublish =
              Boolean(item.listingId) ||
              hasPublishableMinimum(item.candidateSnapshot, pendingCorrections);
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

                <AIReviewPanel snapshot={item.candidateSnapshot} />

                {isEditing && (
                  <div className="rounded-2xl border-[1.5px] border-[#0284C7] bg-[#0284C7]/[0.06] dark:bg-[#0284C7]/[0.12] p-4 space-y-3">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <div>
                        <h4 className="text-xs font-extrabold text-[#0284C7] dark:text-[#7DD3FC] uppercase tracking-wide">
                          Confirm AI-suggested fields
                        </h4>
                        <p className="text-[10px] font-bold text-slate-600 dark:text-slate-300 mt-1">
                          Checked fields become explicit admin corrections. Unchecked fields keep the extracted value.
                        </p>
                      </div>
                      {suggested.length > 0 && (
                        <div className="flex gap-1.5">
                          <button
                            type="button"
                            onClick={() =>
                              setSelectedFields((current) => ({
                                ...current,
                                [item.id]: suggested.map(([key]) => key),
                              }))
                            }
                            className="btn-sharetopus-secondary text-[10px] py-1 px-2"
                          >
                            Select all
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              setSelectedFields((current) => ({ ...current, [item.id]: [] }))
                            }
                            className="btn-sharetopus-secondary text-[10px] py-1 px-2"
                          >
                            Clear
                          </button>
                        </div>
                      )}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                      <label className="space-y-1">
                        <span className="text-[10px] font-mono font-extrabold uppercase">Title</span>
                        <input
                          type="text"
                          value={coreDrafts[item.id]?.title ?? ''}
                          onChange={(event) =>
                            setCoreDrafts((current) => ({
                              ...current,
                              [item.id]: { ...current[item.id], title: event.target.value },
                            }))
                          }
                          className="w-full rounded-lg border border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#0F1624] px-2 py-1.5 text-[11px] font-bold"
                        />
                      </label>
                      <label className="space-y-1">
                        <span className="text-[10px] font-mono font-extrabold uppercase">Type</span>
                        <select
                          value={coreDrafts[item.id]?.kind ?? 'hackathon'}
                          onChange={(event) =>
                            setCoreDrafts((current) => ({
                              ...current,
                              [item.id]: {
                                ...current[item.id],
                                kind: event.target.value as 'hackathon' | 'ai_offer',
                              },
                            }))
                          }
                          className="w-full rounded-lg border border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#0F1624] px-2 py-1.5 text-[11px] font-bold"
                        >
                          <option value="hackathon">Hackathon</option>
                          <option value="ai_offer">AI offer</option>
                        </select>
                      </label>
                      <label className="space-y-1 md:col-span-2">
                        <span className="text-[10px] font-mono font-extrabold uppercase">Official URL</span>
                        <input
                          type="url"
                          value={coreDrafts[item.id]?.officialUrl ?? ''}
                          onChange={(event) =>
                            setCoreDrafts((current) => ({
                              ...current,
                              [item.id]: { ...current[item.id], officialUrl: event.target.value },
                            }))
                          }
                          className="w-full rounded-lg border border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#0F1624] px-2 py-1.5 text-[11px] font-bold"
                        />
                      </label>
                      <label className="space-y-1 md:col-span-2">
                        <span className="text-[10px] font-mono font-extrabold uppercase">Description</span>
                        <textarea
                          rows={2}
                          value={coreDrafts[item.id]?.description ?? ''}
                          onChange={(event) =>
                            setCoreDrafts((current) => ({
                              ...current,
                              [item.id]: { ...current[item.id], description: event.target.value },
                            }))
                          }
                          className="w-full rounded-lg border border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#0F1624] px-2 py-1.5 text-[11px] font-bold"
                        />
                      </label>
                    </div>

                    {suggested.length === 0 ? (
                      <p className="text-[11px] font-bold text-slate-700 dark:text-slate-200">
                        No AI field corrections were proposed. The extracted snapshot will be published as shown below.
                      </p>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                        {suggested.map(([key, original]) => {
                          const selected = (selectedFields[item.id] ?? []).includes(key);
                          return (
                            <label
                              key={key}
                              className={`rounded-xl border p-2.5 space-y-1.5 ${selected ? 'border-[#0284C7] bg-white dark:bg-[#0F1624]' : 'border-slate-300 dark:border-slate-700 opacity-65'}`}
                            >
                              <span className="flex items-center gap-2 text-[10px] font-mono font-extrabold">
                                <input
                                  type="checkbox"
                                  checked={selected}
                                  onChange={(event) =>
                                    setSelectedFields((current) => {
                                      const next = new Set(current[item.id] ?? []);
                                      if (event.target.checked) next.add(key);
                                      else next.delete(key);
                                      return { ...current, [item.id]: [...next] };
                                    })
                                  }
                                />
                                {key}
                              </span>
                              <input
                                type="text"
                                value={drafts[item.id]?.[key] ?? formatSuggested(original)}
                                disabled={!selected}
                                onChange={(event) =>
                                  setDrafts((current) => ({
                                    ...current,
                                    [item.id]: {
                                      ...(current[item.id] ?? {}),
                                      [key]: event.target.value,
                                    },
                                  }))
                                }
                                className="w-full rounded-lg border border-[#1C1B18] dark:border-[#D6DCE5] bg-[#F8F9F4] dark:bg-[#131A29] px-2 py-1.5 text-[11px] font-bold disabled:cursor-not-allowed"
                              />
                            </label>
                          );
                        })}
                      </div>
                    )}

                    <label className="block space-y-1">
                      <span className="text-[10px] font-mono font-extrabold uppercase">Admin note</span>
                      <input
                        type="text"
                        value={notes[item.id] ?? ''}
                        onChange={(event) =>
                          setNotes((current) => ({ ...current, [item.id]: event.target.value }))
                        }
                        placeholder="What did you verify?"
                        className="w-full rounded-xl border border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#0F1624] px-3 py-2 text-[11px] font-bold"
                      />
                    </label>
                  </div>
                )}

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
                  {!canPublish && (
                    <span className="mr-auto rounded-full border border-[#D97706] bg-[#D97706]/10 px-3 py-1.5 text-[10px] font-extrabold text-[#B45309] dark:text-[#FBBF24]">
                      Missing publishable title, type, or URL
                    </span>
                  )}
                  {suggested.length > 0 && (
                    <button
                      type="button"
                      onClick={() =>
                        isEditing ? setEditingId(null) : beginFieldReview(item)
                      }
                      disabled={busyId === item.id}
                      className="btn-sharetopus-secondary text-xs py-2 px-4"
                    >
                      <Sparkles className="w-4 h-4 inline mr-1" />
                      {isEditing ? 'Close field review' : 'Review suggested fields'}
                    </button>
                  )}
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
                    onClick={() => {
                      if (!isEditing) beginFieldReview(item);
                      else void runApprove(item);
                    }}
                    disabled={busyId === item.id || (isEditing && !canPublish)}
                    aria-label={
                      busyId === item.id
                        ? 'Working'
                        : !isEditing
                          ? 'Review publish fields'
                          : 'Approve and publish'
                    }
                    className="btn-sharetopus-primary text-xs py-2 px-4 bg-[#059669] hover:bg-[#047857]"
                  >
                    <RefreshCw className={`w-4 h-4 inline mr-1 ${busyId === item.id ? 'animate-spin' : ''}`} />
                    <span className="text-xs">
                      {busyId === item.id
                        ? 'Working...'
                        : !isEditing
                          ? 'Review publish fields'
                          : 'Approve & Publish'}
                    </span>
                  </button>
                  {isEditing && (
                    <button
                      type="button"
                      onClick={() => setEditingId(null)}
                      disabled={busyId === item.id}
                      className="btn-sharetopus-secondary text-xs py-2 px-3"
                    >
                      Cancel edit
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
