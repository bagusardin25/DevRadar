import React from 'react';
import { X, Bookmark, ExternalLink, Trash2, Trophy, Gift } from 'lucide-react';
import { formatPrizePool } from '../utils/formatPrize';
import type { Hackathon, AIDeal } from '../types';

interface BookmarksDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  bookmarkedHackathons: Hackathon[];
  bookmarkedDeals: AIDeal[];
  onRemoveBookmark: (id: string) => void;
  onToggleAlert: (id: string) => void;
}

export const BookmarksDrawer: React.FC<BookmarksDrawerProps> = ({
  isOpen,
  onClose,
  bookmarkedHackathons,
  bookmarkedDeals,
  onRemoveBookmark
}) => {
  if (!isOpen) return null;

  const total = bookmarkedHackathons.length + bookmarkedDeals.length;

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[420px] bg-white dark:bg-[#131A29] border-l-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[8px_0_0_0_#1C1B18] dark:shadow-[8px_0_0_0_#D6DCE5] flex flex-col justify-between animate-in slide-in-from-right duration-300 font-sans">
      
      {/* Drawer Header */}
      <div className="p-4 border-b border-[#D6D5CF] dark:border-slate-800 bg-[#F8F9F4] dark:bg-[#1A2336] flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-2xl bg-[#FF5A36]/15 text-[#FF5A36] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
            <Bookmark className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-extrabold text-[#1C1B18] dark:text-white">Saved Opportunities</h3>
            <p className="text-xs font-mono font-bold text-[#1C1B18] dark:text-[#B8C4D2]">{total} Items saved in browser</p>
          </div>
        </div>

        <button 
          onClick={onClose}
          className="p-2 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-white hover:bg-[#FF5A36] hover:text-white transition-all font-bold"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Drawer Body */}
      <div className="p-4 flex-1 overflow-y-auto space-y-4 text-xs">
        {total === 0 ? (
          <div className="py-12 text-center space-y-2">
            <Bookmark className="w-10 h-10 text-[#736F66] mx-auto" />
            <h4 className="font-extrabold text-[#1C1B18] dark:text-white text-sm">No Saved Opportunities</h4>
            <p className="text-xs text-[#1C1B18] dark:text-[#B8C4D2] font-bold">Click the bookmark icon on any card to save it for quick access.</p>
          </div>
        ) : (
          <div className="space-y-3">
            
            {/* Hackathons */}
            {bookmarkedHackathons.length > 0 && (
              <div className="space-y-2">
                <span className="font-mono text-[11px] font-extrabold text-[#FF5A36] uppercase">SAVED HACKATHONS ({bookmarkedHackathons.length})</span>
                {bookmarkedHackathons.map(h => (
                  <div key={h.id} className="sharetopus-card p-3 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-[#F8F9F4] dark:bg-[#1A2336] flex items-center justify-between gap-2">
                    <div className="space-y-0.5 min-w-0">
                      <div className="font-extrabold text-[#1C1B18] dark:text-white text-xs truncate flex items-center gap-1.5">
                        <Trophy className="w-3.5 h-3.5 text-[#FF5A36] shrink-0" />
                        <span className="truncate">{h.title}</span>
                      </div>
                      <div className="text-[11px] font-mono text-[#059669] font-extrabold">
                        {formatPrizePool(h, { compact: true })}
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      <a href={h.officialUrl} target="_blank" rel="noreferrer" className="p-1.5 rounded-full border border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#1A2336] text-[#1C1B18] dark:text-white hover:bg-[#FF5A36] hover:text-white">
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                      <button onClick={() => onRemoveBookmark(h.id)} className="p-1.5 rounded-full border border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#1A2336] text-[#FF5A36] hover:bg-[#FF5A36] hover:text-white">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* AI Deals */}
            {bookmarkedDeals.length > 0 && (
              <div className="space-y-2 pt-2">
                <span className="font-mono text-[11px] font-extrabold text-[#7C3AED] uppercase">SAVED AI DEALS ({bookmarkedDeals.length})</span>
                {bookmarkedDeals.map(d => (
                  <div key={d.id} className="sharetopus-card p-3 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-[#F8F9F4] dark:bg-[#1A2336] flex items-center justify-between gap-2">
                    <div className="space-y-0.5 min-w-0">
                      <div className="font-extrabold text-[#1C1B18] dark:text-white text-xs truncate flex items-center gap-1.5">
                        <Gift className="w-3.5 h-3.5 text-[#7C3AED] shrink-0" />
                        <span className="truncate">{d.productName}</span>
                      </div>
                      <div className="text-[11px] font-mono text-[#7C3AED] font-extrabold">{d.offerValue}</div>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      <a href={d.claimUrl} target="_blank" rel="noreferrer" className="p-1.5 rounded-full border border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#1A2336] text-[#1C1B18] dark:text-white hover:bg-[#7C3AED] hover:text-white">
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                      <button onClick={() => onRemoveBookmark(d.id)} className="p-1.5 rounded-full border border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#1A2336] text-[#FF5A36] hover:bg-[#FF5A36] hover:text-white">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

          </div>
        )}
      </div>

      {/* Drawer Footer */}
      <div className="p-4 border-t border-[#D6D5CF] dark:border-slate-800 bg-[#F8F9F4] dark:bg-[#1A2336] text-[11px] font-mono font-extrabold text-[#1C1B18] dark:text-[#D6DCE5] flex items-center justify-between">
        <span>DevRadar Storage Sync</span>
        <button onClick={onClose} className="btn-sharetopus-secondary text-xs py-1 px-3">
          Close
        </button>
      </div>

    </div>
  );
};
