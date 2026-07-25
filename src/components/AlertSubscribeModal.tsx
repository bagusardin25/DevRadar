import React, { useState } from 'react';
import { Bell, X, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { createAlert } from '../api/alerts';

interface AlertSubscribeModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** Optional defaults from current catalogue filters */
  defaultKind?: 'all' | 'hackathon' | 'ai_offer';
  defaultTechnology?: string;
  defaultMode?: 'all' | 'online' | 'hybrid' | 'in_person';
  defaultOnlyClosingSoon?: boolean;
  defaultOnlyBigPrizes?: boolean;
}

export const AlertSubscribeModal: React.FC<AlertSubscribeModalProps> = ({
  isOpen,
  onClose,
  defaultKind = 'all',
  defaultTechnology = '',
  defaultMode = 'all',
  defaultOnlyClosingSoon = false,
  defaultOnlyBigPrizes = false,
}) => {
  const [email, setEmail] = useState('');
  const [targetType, setTargetType] = useState<'all' | 'hackathon' | 'ai_offer'>(defaultKind);
  const [frequency, setFrequency] = useState<'daily' | 'weekly' | 'instant'>('weekly');
  const [mode, setMode] = useState<'all' | 'online' | 'hybrid' | 'in_person'>(defaultMode);
  const [technology, setTechnology] = useState(defaultTechnology);
  const [onlyClosingSoon, setOnlyClosingSoon] = useState(defaultOnlyClosingSoon);
  const [onlyBigPrizes, setOnlyBigPrizes] = useState(defaultOnlyBigPrizes);
  const [minPrize, setMinPrize] = useState('');
  const [query, setQuery] = useState('');
  // Honeypot
  const [website, setWebsite] = useState('');
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');

  if (!isOpen) return null;

  const resetForm = () => {
    setEmail('');
    setTargetType(defaultKind);
    setFrequency('weekly');
    setMode(defaultMode);
    setTechnology(defaultTechnology);
    setOnlyClosingSoon(defaultOnlyClosingSoon);
    setOnlyBigPrizes(defaultOnlyBigPrizes);
    setMinPrize('');
    setQuery('');
    setWebsite('');
    setStatus('idle');
    setErrorMessage('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus('loading');
    setErrorMessage('');

    try {
      const minPrizeNum = minPrize.trim() ? Number(minPrize) : undefined;
      await createAlert({
        email,
        targetType,
        frequency,
        website: website || undefined,
        filters: {
          kind: targetType,
          q: query.trim() || undefined,
          mode: mode !== 'all' ? mode : undefined,
          technology: technology.trim() || undefined,
          onlyClosingSoon: onlyClosingSoon || undefined,
          onlyBigPrizes: onlyBigPrizes || undefined,
          minPrize:
            !onlyBigPrizes && minPrizeNum != null && !Number.isNaN(minPrizeNum) && minPrizeNum > 0
              ? minPrizeNum
              : undefined,
        },
      });
      setStatus('success');
      setTimeout(() => {
        onClose();
        resetForm();
      }, 2200);
    } catch (err: unknown) {
      setStatus('error');
      const msg =
        err && typeof err === 'object' && 'message' in err
          ? String((err as { message: string }).message)
          : 'Failed to subscribe';
      setErrorMessage(msg);
    }
  };

  const inputClass =
    'w-full px-4 py-2.5 rounded-xl bg-[#F3F4EF] dark:bg-[#090C15] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-xs font-bold text-[#1C1B18] dark:text-white focus:outline-none focus:ring-2 focus:ring-[#FF5A36]';
  const labelClass = 'text-xs font-extrabold text-[#1C1B18] dark:text-white';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="sharetopus-card max-w-md w-full max-h-[90vh] overflow-y-auto p-6 rounded-[28px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[6px_6px_0_0_#1C1B18] dark:shadow-[6px_6px_0_0_#D6DCE5] space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-extrabold text-[#1C1B18] dark:text-white flex items-center gap-2">
            <Bell className="w-5 h-5 text-[#1C1B18] dark:text-white" />
            Subscribe to Alerts
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            aria-label="Close"
          >
            <X className="w-5 h-5 text-[#1C1B18] dark:text-white" />
          </button>
        </div>

        <p className="text-xs font-bold text-[#736F66] dark:text-[#B8C4D2] leading-relaxed">
          No account required. Confirm via email once — we only notify on matches to your filters.
          Self-host operators configure SMTP/Resend.
        </p>

        {status === 'success' ? (
          <div className="flex flex-col items-center justify-center py-6 space-y-3">
            <CheckCircle2 className="w-12 h-12 text-green-500" />
            <p className="text-center font-bold text-[#1C1B18] dark:text-white">
              Check your email to confirm
            </p>
            <p className="text-center text-xs font-bold text-[#736F66] dark:text-[#B8C4D2]">
              Alerts stay pending until you open the confirmation link.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Honeypot — hidden from humans */}
            <div className="absolute -left-[9999px] opacity-0 h-0 overflow-hidden" aria-hidden>
              <label htmlFor="alert-website">Website</label>
              <input
                id="alert-website"
                tabIndex={-1}
                autoComplete="off"
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
              />
            </div>

            <div className="space-y-1.5">
              <label className={labelClass} htmlFor="alert-email">
                Email
              </label>
              <input
                id="alert-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={inputClass}
                placeholder="you@example.com"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className={labelClass} htmlFor="alert-kind">
                  Target
                </label>
                <select
                  id="alert-kind"
                  value={targetType}
                  onChange={(e) => setTargetType(e.target.value as typeof targetType)}
                  className={inputClass}
                >
                  <option value="all">All</option>
                  <option value="hackathon">Hackathon</option>
                  <option value="ai_offer">AI Offer</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <label className={labelClass} htmlFor="alert-cadence">
                  Frequency
                </label>
                <select
                  id="alert-cadence"
                  value={frequency}
                  onChange={(e) => setFrequency(e.target.value as typeof frequency)}
                  className={inputClass}
                >
                  <option value="instant">Instant</option>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                </select>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className={labelClass} htmlFor="alert-q">
                Keywords (optional)
              </label>
              <input
                id="alert-q"
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className={inputClass}
                placeholder="e.g. AI, LLM, Rust"
              />
            </div>

            {targetType !== 'ai_offer' && (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className={labelClass} htmlFor="alert-mode">
                    Mode
                  </label>
                  <select
                    id="alert-mode"
                    value={mode}
                    onChange={(e) => setMode(e.target.value as typeof mode)}
                    className={inputClass}
                  >
                    <option value="all">Any mode</option>
                    <option value="online">Online</option>
                    <option value="hybrid">Hybrid</option>
                    <option value="in_person">In person</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className={labelClass} htmlFor="alert-tech">
                    Technology
                  </label>
                  <input
                    id="alert-tech"
                    type="text"
                    value={technology}
                    onChange={(e) => setTechnology(e.target.value)}
                    className={inputClass}
                    placeholder="Python, Solana…"
                  />
                </div>
              </div>
            )}

            {targetType === 'ai_offer' && (
              <div className="space-y-1.5">
                <label className={labelClass} htmlFor="alert-tech-deal">
                  Tags / tech
                </label>
                <input
                  id="alert-tech-deal"
                  type="text"
                  value={technology}
                  onChange={(e) => setTechnology(e.target.value)}
                  className={inputClass}
                  placeholder="OpenAI, credits…"
                />
              </div>
            )}

            {targetType !== 'ai_offer' && (
              <div className="space-y-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={onlyBigPrizes}
                    onChange={(e) => setOnlyBigPrizes(e.target.checked)}
                    className="rounded border-[#1C1B18]"
                  />
                  <span className="text-xs font-bold text-[#1C1B18] dark:text-white">
                    Big prizes only ($10k+)
                  </span>
                </label>
                {!onlyBigPrizes && (
                  <div className="space-y-1.5 pl-6">
                    <label className={labelClass} htmlFor="alert-min-prize">
                      Min prize (USD, optional)
                    </label>
                    <input
                      id="alert-min-prize"
                      type="number"
                      min={0}
                      step={100}
                      value={minPrize}
                      onChange={(e) => setMinPrize(e.target.value)}
                      className={inputClass}
                      placeholder="5000"
                    />
                  </div>
                )}
              </div>
            )}

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={onlyClosingSoon}
                onChange={(e) => setOnlyClosingSoon(e.target.checked)}
                className="rounded border-[#1C1B18]"
              />
              <span className="text-xs font-bold text-[#1C1B18] dark:text-white">
                Closing within 14 days
              </span>
            </label>

            {status === 'error' && (
              <div className="flex items-center gap-2 p-3 text-sm text-red-600 bg-red-50 dark:bg-red-900/20 rounded-xl border-[1.5px] border-red-200 dark:border-red-800">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <p className="font-bold">{errorMessage}</p>
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <button type="button" onClick={onClose} className="btn-sharetopus-secondary flex-1">
                Cancel
              </button>
              <button
                type="submit"
                disabled={status === 'loading'}
                className="btn-sharetopus-primary flex-1 flex items-center justify-center gap-2"
              >
                {status === 'loading' && <Loader2 className="w-4 h-4 animate-spin" />}
                Subscribe
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
