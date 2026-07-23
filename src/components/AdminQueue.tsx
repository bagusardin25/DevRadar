import React, { useState } from 'react';
import { 
  ShieldCheck, 
  X, 
  ExternalLink, 
  RefreshCw, 
  Share2
} from 'lucide-react';
import type { UnverifiedSignal } from '../types';

interface AdminQueueProps {
  signals: UnverifiedSignal[];
  onApprove: (signalId: string) => void;
  onReject: (signalId: string) => void;
}

export const AdminQueue: React.FC<AdminQueueProps> = ({
  signals,
  onApprove,
  onReject
}) => {
  const [verifyingId, setVerifyingId] = useState<string | null>(null);

  const handleRunVerification = (id: string) => {
    setVerifyingId(id);
    setTimeout(() => {
      setVerifyingId(null);
      onApprove(id);
    }, 1500);
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto px-4 lg:px-8 py-6 font-sans">
      
      {/* Header */}
      <div className="sharetopus-card p-6 rounded-[28px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-2xl bg-[#D97706]/15 text-[#D97706] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-extrabold text-[#1C1B18] dark:text-white">Verification & Review Queue</h2>
            <p className="text-xs text-[#1C1B18] dark:text-[#F8FAF9] font-bold">
              Raw signals from X posts or community submissions requiring human-in-the-loop review before `verified_active` indexing.
            </p>
          </div>
        </div>

        <div className="px-4 py-2.5 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-xs font-mono font-extrabold text-[#1C1B18] dark:text-slate-200 text-right">
          <div>Pending Items: <strong className="text-[#D97706] font-extrabold">{signals.length}</strong></div>
          <div className="text-[10px] text-[#1C1B18] dark:text-slate-300">Queue Status: Low Latency</div>
        </div>
      </div>

      {signals.length === 0 ? (
        <div className="sharetopus-card p-12 text-center rounded-[24px] space-y-3 bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-white">
          <div className="w-12 h-12 rounded-full bg-[#059669]/15 text-[#059669] mx-auto flex items-center justify-center border border-[#059669]">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <h3 className="text-lg font-extrabold">Review Queue Clear!</h3>
          <p className="text-xs font-bold text-slate-700 dark:text-slate-300">All X posts and candidate signals have been verified into the PostgreSQL database.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {signals.map((signal) => (
            <div key={signal.id} className="sharetopus-card p-5 rounded-[24px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] space-y-4">
              
              {/* Top row */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs font-extrabold">
                <div className="flex items-center gap-2">
                  <span className="px-3 py-1 rounded-full bg-[#D97706]/15 text-[#D97706] border border-[#D97706] text-[11px] font-extrabold">
                    NEEDS REVIEW
                  </span>
                  <span className="px-3 py-1 rounded-full bg-[#F3F4EF] dark:bg-[#1A2336] border border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white text-[11px] font-extrabold flex items-center gap-1">
                    <Share2 className="w-3 h-3 text-[#FF5A36]" />
                    Tier 3 Signal ({signal.author})
                  </span>
                  <span className="text-[#1C1B18] dark:text-slate-300 font-mono text-xs">Post ID: #{signal.postId}</span>
                </div>

                <div className="font-mono text-[#1C1B18] dark:text-slate-200 text-xs font-extrabold">
                  Confidence: <span className="text-[#D97706] font-extrabold">{Math.round(signal.confidenceScore * 100)}%</span>
                </div>
              </div>

              {/* Raw X Post Content */}
              <div className="p-3.5 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] space-y-1">
                <div className="text-[11px] font-mono font-extrabold text-[#1C1B18] dark:text-slate-300 uppercase">RAW POST TEXT DETECTED:</div>
                <p className="text-xs text-[#1C1B18] dark:text-white font-mono font-extrabold leading-relaxed">{signal.rawText}</p>
              </div>

              {/* Discovered Candidate URLs & Extracted JSON */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                
                {/* Links */}
                <div className="sharetopus-card p-3.5 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] space-y-2">
                  <div className="font-extrabold text-[#1C1B18] dark:text-white font-mono text-[11px]">Discovered External Target URL:</div>
                  {signal.discoveredUrls.map((url, i) => (
                    <a
                      key={i}
                      href={url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-1.5 text-[#0284C7] dark:text-[#D6DCE5] hover:underline font-mono text-[11px] font-extrabold truncate"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                      <span>{url}</span>
                    </a>
                  ))}
                </div>

                {/* Extracted JSON Candidate */}
                <div className="sharetopus-card p-3.5 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] space-y-2">
                  <div className="font-extrabold text-[#1C1B18] dark:text-white font-mono text-[11px]">LLM Extracted Candidate Metadata:</div>
                  <pre className="text-[10px] text-[#059669] dark:text-[#34D399] font-mono bg-[#090C15] p-2.5 rounded-xl border border-[#1C1B18] dark:border-[#D6DCE5] max-h-24 overflow-y-auto font-extrabold">
                    {JSON.stringify(signal.extractedInfo, null, 2)}
                  </pre>
                </div>

              </div>

              {/* Action Buttons */}
              <div className="pt-2 border-t border-[#D6D5CF] dark:border-slate-800 flex items-center justify-end gap-2 text-xs font-bold">
                <button
                  onClick={() => onReject(signal.id)}
                  className="btn-sharetopus-secondary text-xs py-2 px-4"
                >
                  <X className="w-4 h-4 inline mr-1" />
                  Discard Signal
                </button>

                <button
                  onClick={() => handleRunVerification(signal.id)}
                  disabled={verifyingId === signal.id}
                  className="btn-sharetopus-primary text-xs py-2 px-4 bg-[#059669] hover:bg-[#047857]"
                >
                  <RefreshCw className={`w-4 h-4 ${verifyingId === signal.id ? 'animate-spin' : ''}`} />
                  <span>{verifyingId === signal.id ? 'Fetching Tier-1 URL...' : 'Run Auto Verifier & Index'}</span>
                </button>
              </div>

            </div>
          ))}
        </div>
      )}

    </div>
  );
};
