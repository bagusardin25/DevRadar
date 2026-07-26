import React from 'react';
import { X } from 'lucide-react';
import { formatPrizePool } from '../utils/formatPrize';
import type { Hackathon } from '../types';
import { useModalA11y } from '../hooks/useModalA11y';

interface CompareModalProps {
  items: Hackathon[];
  onClose: () => void;
  onRemove: (id: string) => void;
}

export const CompareModal: React.FC<CompareModalProps> = ({
  items,
  onClose,
  onRemove,
}) => {
  // Called before the early return below — hooks must run every render.
  const dialogRef = useModalA11y<HTMLDivElement>(items.length > 0, onClose);

  if (items.length === 0) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/65 overflow-y-auto font-sans">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="compare-modal-title"
        className="sharetopus-card w-full max-w-5xl rounded-t-[28px] sm:rounded-[28px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[8px_8px_0_0_#1C1B18] dark:shadow-[8px_8px_0_0_#D6DCE5] overflow-hidden my-0 sm:my-8 max-h-[95vh] flex flex-col"
      >
        {/* Header */}
        <div className="flex items-start sm:items-center justify-between gap-3 p-4 sm:p-5 border-b border-[#D6D5CF] dark:border-slate-800 bg-[#F8F9F4] dark:bg-[#1A2336] shrink-0">
          <div className="min-w-0">
            <h2 id="compare-modal-title" className="text-base sm:text-lg font-extrabold text-[#1C1B18] dark:text-white tracking-tight">
              Compare opportunities
            </h2>
            <p className="text-xs sm:text-sm text-[#4A4845] dark:text-[#B8C4D2] font-bold mt-0.5">
              Prize, effort, deadlines, mode, and stack — side by side
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-white hover:bg-[#FF5A36] hover:text-white transition-all shrink-0"
            aria-label="Close compare"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Comparison Table */}
        <div className="p-3 sm:p-6 overflow-x-auto flex-1">
          <table className="w-full text-left text-xs sm:text-sm border-collapse min-w-[520px]">
            <thead>
              <tr className="border-b-2 border-[#1C1B18] dark:border-[#D6DCE5]">
                <th className="p-3 w-32 sm:w-40 text-[12px] font-extrabold font-mono text-[#736F66] dark:text-[#94A3B8] uppercase tracking-wide">
                  Metric
                </th>
                {items.map((item) => (
                  <th
                    key={item.id}
                    className="p-3 min-w-[180px] sm:min-w-[220px] text-[#1C1B18] dark:text-white font-extrabold text-sm align-top"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="leading-snug line-clamp-2">{item.title}</span>
                      <button
                        type="button"
                        onClick={() => onRemove(item.id)}
                        className="text-[#736F66] hover:text-[#FF5A36] shrink-0"
                        aria-label={`Remove ${item.title}`}
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                    <div className="text-[12px] text-[#4A4845] dark:text-[#B8C4D2] font-bold mt-1">
                      {item.organizer}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#D6D5CF] dark:divide-slate-700 text-[#1C1B18] dark:text-[#E8ECF1] font-bold">
              <tr>
                <td className="p-3 font-extrabold text-[#736F66] dark:text-[#94A3B8] text-[12px]">
                  Prize pool
                </td>
                {items.map((item) => (
                  <td
                    key={item.id}
                    className="p-3 font-extrabold text-[#059669] dark:text-[#34D399] text-sm"
                  >
                    {formatPrizePool(item, { compact: true })}
                  </td>
                ))}
              </tr>
              <tr className="bg-[#F8F9F4]/80 dark:bg-[#1A2336]/40">
                <td className="p-3 font-extrabold text-[#736F66] dark:text-[#94A3B8] text-[12px]">
                  Effort
                </td>
                {items.map((item) => (
                  <td key={item.id} className="p-3 text-[#0284C7] dark:text-[#38BDF8]">
                    {item.effortEstimate}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="p-3 font-extrabold text-[#736F66] dark:text-[#94A3B8] text-[12px]">
                  Reg. deadline
                </td>
                {items.map((item) => (
                  <td key={item.id} className="p-3 text-[#D97706] dark:text-[#FBBF24]">
                    {item.registrationDeadline
                      ? new Date(item.registrationDeadline).toLocaleDateString(undefined, {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric',
                        })
                      : '—'}
                  </td>
                ))}
              </tr>
              <tr className="bg-[#F8F9F4]/80 dark:bg-[#1A2336]/40">
                <td className="p-3 font-extrabold text-[#736F66] dark:text-[#94A3B8] text-[12px]">
                  Mode
                </td>
                {items.map((item) => (
                  <td key={item.id} className="p-3 uppercase font-extrabold text-[#FF5A36]">
                    {item.mode}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="p-3 font-extrabold text-[#736F66] dark:text-[#94A3B8] text-[12px]">
                  Team size
                </td>
                {items.map((item) => (
                  <td key={item.id} className="p-3">
                    {item.teamMin}–{item.teamMax}
                  </td>
                ))}
              </tr>
              <tr className="bg-[#F8F9F4]/80 dark:bg-[#1A2336]/40">
                <td className="p-3 font-extrabold text-[#736F66] dark:text-[#94A3B8] text-[12px]">
                  Confidence
                </td>
                {items.map((item) => (
                  <td key={item.id} className="p-3 text-[#7C3AED] dark:text-[#C4B5FD] font-extrabold">
                    {Math.round(item.confidenceScore * 100)}%
                  </td>
                ))}
              </tr>
              <tr>
                <td className="p-3 font-extrabold text-[#736F66] dark:text-[#94A3B8] text-[12px]">
                  Stack
                </td>
                {items.map((item) => (
                  <td key={item.id} className="p-3 text-[12px] sm:text-sm leading-relaxed">
                    {item.technologies.join(', ') || '—'}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
