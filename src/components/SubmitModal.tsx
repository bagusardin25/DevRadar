import React, { useState } from 'react';
import { X, PlusCircle, CheckCircle2, Info } from 'lucide-react';

interface SubmitModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (title: string, url: string, type: 'hackathon' | 'ai_deal') => void;
}

export const SubmitModal: React.FC<SubmitModalProps> = ({
  isOpen,
  onClose,
  onSubmit
}) => {
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [type, setType] = useState<'hackathon' | 'ai_deal'>('hackathon');
  const [submitted, setSubmitted] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url || !title) return;
    setSubmitted(true);
    setTimeout(() => {
      onSubmit(title, url, type);
      setSubmitted(false);
      setTitle('');
      setUrl('');
      onClose();
    }, 1200);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
      <div className="glass-panel w-full max-w-lg rounded-2xl border-sky-500/30 bg-[#0b0f19] shadow-2xl p-6 space-y-5 animate-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <PlusCircle className="w-5 h-5 text-sky-400" />
            <h3 className="text-lg font-bold text-white">Submit Missing Opportunity</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {submitted ? (
          <div className="py-8 text-center space-y-3">
            <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto animate-bounce" />
            <h4 className="text-base font-bold text-white">Opportunity Submitted!</h4>
            <p className="text-xs text-slate-400">Our Fetcher & Verifier Engine is processing your URL. It will appear in the Review Queue shortly.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4 text-xs">
            <div className="space-y-1.5">
              <label className="text-slate-300 font-semibold">Opportunity Type</label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value as any)}
                className="w-full bg-slate-900 border border-slate-800 text-white rounded-lg p-2.5 outline-none focus:border-sky-500"
              >
                <option value="hackathon">Hackathon / Developer Bounty</option>
                <option value="ai_deal">AI Deal / Free Credits / Model Promo</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-slate-300 font-semibold">Opportunity Title</label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., Anthropic Claude 3.7 Hackathon 2026"
                className="w-full bg-slate-900 border border-slate-800 text-white rounded-lg p-2.5 outline-none focus:border-sky-500"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-slate-300 font-semibold">Official Source / Terms URL</label>
              <input
                type="url"
                required
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://..."
                className="w-full bg-slate-900 border border-slate-800 text-white rounded-lg p-2.5 outline-none focus:border-sky-500 font-mono"
              />
            </div>

            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-slate-400 font-mono text-[11px] flex items-center gap-2">
              <Info className="w-4 h-4 text-sky-400 shrink-0" />
              <span>DevRadar will run Tier 1/2 verification against this URL before adding it to verified active search indexes.</span>
            </div>

            <div className="pt-2 flex justify-end gap-2">
              <button type="button" onClick={onClose} className="btn-secondary text-xs">
                Cancel
              </button>
              <button type="submit" className="btn-primary text-xs font-semibold">
                Submit & Trigger Verifier
              </button>
            </div>
          </form>
        )}

      </div>
    </div>
  );
};
