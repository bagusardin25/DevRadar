import React, { useEffect, useState } from 'react';
import { X, PlusCircle, CheckCircle2, Info, AlertCircle } from 'lucide-react';
import { createSubmission, ApiError } from '../api';

interface SubmitModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** Called after a successful API submission (optional UI refresh hook). */
  onSubmitted?: (trackingId: string) => void;
}

const fieldClass =
  'w-full bg-white dark:bg-[#0F1624] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white rounded-xl p-2.5 outline-none focus:border-[#FF5A36] focus:ring-2 focus:ring-[#FF5A36]/20 font-bold text-xs transition-all';

export const SubmitModal: React.FC<SubmitModalProps> = ({
  isOpen,
  onClose,
  onSubmitted,
}) => {
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [type, setType] = useState<'hackathon' | 'ai_offer'>('hackathon');
  const [website, setWebsite] = useState(''); // honeypot
  const [formOpenedAt, setFormOpenedAt] = useState(() => Math.floor(Date.now() / 1000));
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [trackingId, setTrackingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setFormOpenedAt(Math.floor(Date.now() / 1000));
      setSubmitted(false);
      setTrackingId(null);
      setError(null);
      setSubmitting(false);
    }
  }, [isOpen]);

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
      setSubmitted(true);
      onSubmitted?.(receipt.trackingId);
      setTimeout(() => {
        setTitle('');
        setUrl('');
        setSubmitted(false);
        setTrackingId(null);
        onClose();
      }, 2200);
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/65 font-sans">
      <div className="sharetopus-card w-full max-w-lg rounded-[28px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[8px_8px_0_0_#1C1B18] dark:shadow-[8px_8px_0_0_#D6DCE5] overflow-hidden animate-in zoom-in-95 duration-200">
        {/* Header — match DetailModal */}
        <div className="flex items-center justify-between p-5 border-b border-[#D6D5CF] dark:border-slate-800 bg-[#F8F9F4] dark:bg-[#1A2336]">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-[#0284C7]/15 text-[#0284C7]">
              <PlusCircle className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-extrabold text-[#1C1B18] dark:text-white tracking-tight">
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
            className="p-2 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-white hover:bg-[#FF5A36] hover:text-white transition-all font-bold"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 sm:p-6">
          {submitted ? (
            <div className="py-10 text-center space-y-3">
              <div className="w-14 h-14 mx-auto rounded-full bg-[#059669]/15 border-[1.5px] border-[#059669] flex items-center justify-center text-[#059669]">
                <CheckCircle2 className="w-8 h-8 animate-bounce" />
              </div>
              <h4 className="text-base font-extrabold text-[#1C1B18] dark:text-white">
                Opportunity Submitted!
              </h4>
              <p className="text-xs font-bold text-slate-700 dark:text-slate-300 max-w-sm mx-auto">
                Queued for verification. Tracking ID:{' '}
                <span className="font-mono text-[#0284C7] dark:text-[#7DD3FC]">{trackingId}</span>
              </p>
            </div>
          ) : (
            <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 text-xs">
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
