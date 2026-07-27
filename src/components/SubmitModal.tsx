import React, { useEffect, useState } from 'react';
import {
  X,
  PlusCircle,
  CheckCircle2,
  Info,
  AlertCircle,
  RefreshCw,
  Clipboard,
  Sparkles,
  Loader2,
} from 'lucide-react';
import {
  createSubmission,
  fetchSubmissionStatus,
  ApiError,
  type SubmissionState,
  type SubmissionStatus,
} from '../api';
import { useModalA11y } from '../hooks/useModalA11y';

interface SubmitModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** Called after a successful API submission (optional UI refresh hook). */
  onSubmitted?: (trackingId: string) => void;
}

const fieldClass =
  'w-full bg-white dark:bg-[#0F1624] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white rounded-xl p-2.5 outline-none focus:border-[#FF5A36] focus:ring-2 focus:ring-[#FF5A36]/20 font-bold text-xs transition-all';

const LAST_TRACKING_KEY = 'devradar_last_submission_tracking_v1';
const FINAL_STATES = new Set<SubmissionState>([
  'accepted',
  'rejected',
  'duplicate',
  'review_failed',
]);

const STATUS_STEP: Record<SubmissionState, number> = {
  received: 0,
  queued: 0,
  fetching: 1,
  processing: 1,
  reviewing: 2,
  awaiting_admin: 3,
  review_failed: 3,
  duplicate: 3,
  accepted: 3,
  rejected: 3,
};

export const SubmitModal: React.FC<SubmitModalProps> = ({
  isOpen,
  onClose,
  onSubmitted,
}) => {
  // Called before the `!isOpen` early return below — hooks must run every render.
  const dialogRef = useModalA11y<HTMLDivElement>(isOpen, onClose);
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [type, setType] = useState<'hackathon' | 'ai_offer'>('hackathon');
  const [website, setWebsite] = useState(''); // honeypot
  const [formOpenedAt, setFormOpenedAt] = useState(() => Math.floor(Date.now() / 1000));
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [trackingId, setTrackingId] = useState<string | null>(null);
  const [lastTrackingId, setLastTrackingId] = useState<string | null>(null);
  const [submissionStatus, setSubmissionStatus] = useState<SubmissionStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setFormOpenedAt(Math.floor(Date.now() / 1000));
      setSubmitted(false);
      setTrackingId(null);
      setSubmissionStatus(null);
      setLastTrackingId(window.localStorage.getItem(LAST_TRACKING_KEY));
      setError(null);
      setSubmitting(false);
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen || !trackingId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | null = null;
    let active = true;

    const poll = async () => {
      setStatusLoading(true);
      try {
        const next = await fetchSubmissionStatus(trackingId, controller.signal);
        if (!active) return;
        setSubmissionStatus(next);
        setError(null);
        if (!FINAL_STATES.has(next.status)) {
          timer = setTimeout(() => void poll(), 3500);
        }
      } catch (err) {
        if (!active || (err instanceof Error && err.name === 'AbortError')) return;
        setError(err instanceof Error ? err.message : 'Could not refresh submission status');
        timer = setTimeout(() => void poll(), 6000);
      } finally {
        if (active) setStatusLoading(false);
      }
    };

    void poll();
    return () => {
      active = false;
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [isOpen, trackingId]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url || !title || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const receipt = await createSubmission(
        {
          url,
          claimedTitle: title,
          claimedType: type,
          formOpenedAt,
          website: website || '',
        },
        crypto.randomUUID(),
      );
      setTrackingId(receipt.trackingId);
      setLastTrackingId(receipt.trackingId);
      window.localStorage.setItem(LAST_TRACKING_KEY, receipt.trackingId);
      setSubmitted(true);
      onSubmitted?.(receipt.trackingId);
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.detail
          : err instanceof Error
            ? err.message
            : 'Submission failed';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  const refreshStatus = async () => {
    if (!trackingId || statusLoading) return;
    setStatusLoading(true);
    try {
      setSubmissionStatus(await fetchSubmissionStatus(trackingId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not refresh submission status');
    } finally {
      setStatusLoading(false);
    }
  };

  const startNewSubmission = () => {
    setTitle('');
    setUrl('');
    setWebsite('');
    setSubmitted(false);
    setTrackingId(null);
    setSubmissionStatus(null);
    setError(null);
    setFormOpenedAt(Math.floor(Date.now() / 1000));
  };

  const resumeTracking = () => {
    if (!lastTrackingId) return;
    setTrackingId(lastTrackingId);
    setSubmitted(true);
    setSubmissionStatus(null);
    setError(null);
  };

  const currentState = submissionStatus?.status ?? 'queued';
  const currentStep = STATUS_STEP[currentState];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/65 font-sans">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="submit-modal-title"
        className="sharetopus-card w-full max-w-lg rounded-[28px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[8px_8px_0_0_#1C1B18] dark:shadow-[8px_8px_0_0_#D6DCE5] overflow-hidden animate-in zoom-in-95 duration-200"
      >
        {/* Header — match DetailModal */}
        <div className="flex items-center justify-between p-5 border-b border-[#D6D5CF] dark:border-slate-800 bg-[#F8F9F4] dark:bg-[#1A2336]">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-[#0284C7]/15 text-[#0284C7]">
              <PlusCircle className="w-5 h-5" />
            </div>
            <div>
              <h3 id="submit-modal-title" className="text-lg font-extrabold text-[#1C1B18] dark:text-white tracking-tight">
                Submit Missing Opportunity
              </h3>
              <p className="text-[11px] font-bold text-[#1C1B18]/70 dark:text-slate-300">
                Community tip · verified before indexing
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close submit form"
            className="p-2 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-white hover:bg-[#FF5A36] hover:text-white transition-all font-bold"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 sm:p-6">
          {submitted ? (
            <div className="space-y-4">
              <div className="w-14 h-14 mx-auto rounded-full bg-[#059669]/15 border-[1.5px] border-[#059669] flex items-center justify-center text-[#059669]">
                {statusLoading && !submissionStatus ? (
                  <Loader2 className="w-7 h-7 animate-spin" />
                ) : (
                  <CheckCircle2 className="w-8 h-8" />
                )}
              </div>
              <div className="text-center space-y-1.5">
                <h4 className="text-base font-extrabold text-[#1C1B18] dark:text-white">
                  Submission tracker
                </h4>
                <span className="inline-flex px-3 py-1 rounded-full border border-[#0284C7] bg-[#0284C7]/10 text-[#0284C7] dark:text-[#7DD3FC] text-[10px] font-mono font-extrabold uppercase">
                  {currentState.replaceAll('_', ' ')}
                </span>
                <p className="text-xs font-bold text-slate-700 dark:text-slate-300">
                  {submissionStatus?.message ?? 'Queued for verification.'}
                </p>
              </div>

              <div className="grid grid-cols-4 gap-1.5" aria-label="Submission progress">
                {['Queued', 'Fetch', 'AI review', 'Admin'].map((label, index) => (
                  <div key={label} className="space-y-1 text-center">
                    <div
                      className={`h-2 rounded-full border border-[#1C1B18] dark:border-[#D6DCE5] ${index <= currentStep ? 'bg-[#059669]' : 'bg-[#E5E6DF] dark:bg-[#1A2336]'}`}
                    />
                    <span className="text-[9px] font-mono font-extrabold text-slate-600 dark:text-slate-300">
                      {label}
                    </span>
                  </div>
                ))}
              </div>

              <div className="rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-[#F8F9F4] dark:bg-[#1A2336] p-3 space-y-1.5">
                <div className="text-[10px] uppercase tracking-wide font-extrabold text-slate-500">
                  Tracking ID
                </div>
                <div className="flex items-center gap-2">
                  <code className="min-w-0 flex-1 truncate font-mono text-[11px] font-extrabold text-[#0284C7] dark:text-[#7DD3FC]">
                    {trackingId}
                  </code>
                  <button
                    type="button"
                    onClick={() => trackingId && void navigator.clipboard.writeText(trackingId)}
                    className="btn-sharetopus-secondary p-2"
                    aria-label="Copy tracking ID"
                  >
                    <Clipboard className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {submissionStatus?.review && (
                <div className="rounded-2xl border-[1.5px] border-[#7C3AED] bg-[#7C3AED]/10 p-4 space-y-2 text-left">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 text-[#7C3AED] dark:text-[#C4B5FD]">
                      <Sparkles className="w-4 h-4" />
                      <span className="text-[11px] font-extrabold uppercase">AI initial review</span>
                    </div>
                    <span className="text-[10px] font-mono font-extrabold uppercase">
                      {submissionStatus.review.recommendation.replaceAll('_', ' ')} ·{' '}
                      {submissionStatus.review.confidence}/100
                    </span>
                  </div>
                  <p className="text-xs font-bold text-[#1C1B18] dark:text-slate-100">
                    {submissionStatus.review.summary}
                  </p>
                  {submissionStatus.review.concerns.length > 0 && (
                    <ul className="space-y-1 text-[11px] font-bold text-slate-700 dark:text-slate-200">
                      {submissionStatus.review.concerns.map((concern, index) => (
                        <li key={`${concern.severity}-${index}`}>
                          <span className="uppercase font-mono text-[9px] opacity-60 mr-1">
                            {concern.severity}
                          </span>
                          {concern.message}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {error && (
                <div className="p-3 rounded-2xl bg-[#FF5A36]/10 border-[1.5px] border-[#FF5A36] text-xs font-bold flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-[#FF5A36] shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              <div className="flex flex-wrap justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => void refreshStatus()}
                  disabled={statusLoading}
                  className="btn-sharetopus-secondary text-xs py-2 px-3"
                >
                  <RefreshCw className={`w-3.5 h-3.5 inline mr-1 ${statusLoading ? 'animate-spin' : ''}`} />
                  Refresh
                </button>
                <button type="button" onClick={startNewSubmission} className="btn-sharetopus-secondary text-xs py-2 px-3">
                  Submit another
                </button>
                <button type="button" onClick={onClose} className="btn-sharetopus-primary text-xs py-2 px-4">
                  Close
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 text-xs">
              {lastTrackingId && (
                <button
                  type="button"
                  onClick={resumeTracking}
                  className="w-full p-3 rounded-2xl bg-[#0284C7]/10 border-[1.5px] border-[#0284C7] text-[#0284C7] dark:text-[#7DD3FC] font-extrabold text-[11px] flex items-center justify-center gap-2"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Continue tracking your last submission
                </button>
              )}
              <div className="space-y-1.5">
                <label className="text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold text-[11px] uppercase tracking-wide">
                  Opportunity Type
                </label>
                <select
                  value={type}
                  onChange={(e) => setType(e.target.value as 'hackathon' | 'ai_offer')}
                  className={fieldClass}
                >
                  <option value="hackathon">Hackathon / Developer Bounty</option>
                  <option value="ai_offer">AI Deal / Free Credits / Model Promo</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold text-[11px] uppercase tracking-wide">
                  Opportunity Title
                </label>
                <input
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g., Anthropic Claude Hackathon 2026"
                  className={fieldClass}
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold text-[11px] uppercase tracking-wide">
                  Official Source / Terms URL
                </label>
                <input
                  type="url"
                  required
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://..."
                  className={`${fieldClass} font-mono`}
                />
              </div>

              {/* Honeypot — hidden from users */}
              <div
                className="absolute -left-[9999px] opacity-0 h-0 overflow-hidden"
                aria-hidden="true"
              >
                <label htmlFor="website">Website</label>
                <input
                  id="website"
                  name="website"
                  type="text"
                  tabIndex={-1}
                  autoComplete="off"
                  value={website}
                  onChange={(e) => setWebsite(e.target.value)}
                />
              </div>

              {error && (
                <div className="p-3 rounded-2xl bg-[#FF5A36]/10 border-[1.5px] border-[#FF5A36] text-[#1C1B18] dark:text-white font-bold text-[11px] flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-[#FF5A36] shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              <div className="p-3.5 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-slate-200 font-bold text-[11px] flex items-start gap-2">
                <Info className="w-4 h-4 text-[#0284C7] shrink-0 mt-0.5" />
                <span>
                  Sent to{' '}
                  <code className="font-mono font-extrabold text-[#FF5A36]">
                    POST /api/v1/submissions
                  </code>
                  . Tier 1/2 verification runs before public indexing.
                </span>
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="btn-sharetopus-secondary text-xs py-2 px-4 font-extrabold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="btn-sharetopus-primary text-xs py-2 px-4 font-extrabold disabled:opacity-50"
                >
                  {submitting ? 'Submitting…' : 'Submit & Trigger Verifier'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
