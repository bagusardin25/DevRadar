import React, { useState } from 'react';
import { Bell, X, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { createAlert } from '../api/alerts';

interface AlertSubscribeModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AlertSubscribeModal: React.FC<AlertSubscribeModalProps> = ({ isOpen, onClose }) => {
  const [email, setEmail] = useState('');
  const [targetType, setTargetType] = useState<'all' | 'hackathon' | 'ai_offer'>('all');
  const [frequency, setFrequency] = useState<'daily' | 'weekly' | 'instant'>('weekly');
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus('loading');
    setErrorMessage('');
    
    try {
      await createAlert({ email, targetType, frequency });
      setStatus('success');
      setTimeout(() => {
        onClose();
        setStatus('idle');
        setEmail('');
        setTargetType('all');
        setFrequency('weekly');
      }, 2000);
    } catch (err: any) {
      setStatus('error');
      setErrorMessage(err.message || 'Failed to subscribe');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="sharetopus-card max-w-md w-full p-6 rounded-[28px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[6px_6px_0_0_#1C1B18] dark:shadow-[6px_6px_0_0_#D6DCE5] space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-extrabold text-[#1C1B18] dark:text-white flex items-center gap-2">
            <Bell className="w-5 h-5 text-[#1C1B18] dark:text-white" />
            Subscribe to Alerts
          </h2>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
            <X className="w-5 h-5 text-[#1C1B18] dark:text-white" />
          </button>
        </div>

        {status === 'success' ? (
          <div className="flex flex-col items-center justify-center py-6 space-y-3">
            <CheckCircle2 className="w-12 h-12 text-green-500" />
            <p className="text-center font-bold text-[#1C1B18] dark:text-white">Successfully subscribed!</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-extrabold text-[#1C1B18] dark:text-white">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-[#F3F4EF] dark:bg-[#090C15] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-xs font-bold text-[#1C1B18] dark:text-white focus:outline-none focus:ring-2 focus:ring-[#FF5A36]"
                placeholder="you@example.com"
              />
            </div>
            
            <div className="space-y-1.5">
              <label className="text-xs font-extrabold text-[#1C1B18] dark:text-white">Target Type</label>
              <select
                value={targetType}
                onChange={(e) => setTargetType(e.target.value as 'all' | 'hackathon' | 'ai_offer')}
                className="w-full px-4 py-2.5 rounded-xl bg-[#F3F4EF] dark:bg-[#090C15] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-xs font-bold text-[#1C1B18] dark:text-white focus:outline-none focus:ring-2 focus:ring-[#FF5A36]"
              >
                <option value="hackathon">Hackathon</option>
                <option value="ai_offer">AI Offer</option>
                <option value="all">All</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-extrabold text-[#1C1B18] dark:text-white">Frequency</label>
              <select
                value={frequency}
                onChange={(e) => setFrequency(e.target.value as 'daily' | 'weekly' | 'instant')}
                className="w-full px-4 py-2.5 rounded-xl bg-[#F3F4EF] dark:bg-[#090C15] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-xs font-bold text-[#1C1B18] dark:text-white focus:outline-none focus:ring-2 focus:ring-[#FF5A36]"
              >
                <option value="instant">Instant</option>
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
              </select>
            </div>

            {status === 'error' && (
              <div className="flex items-center gap-2 p-3 text-sm text-red-600 bg-red-50 dark:bg-red-900/20 rounded-xl border-[1.5px] border-red-200 dark:border-red-800">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <p className="font-bold">{errorMessage}</p>
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="btn-sharetopus-secondary flex-1"
              >
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
