import React, { useRef, useState } from 'react';
import {
  X,
  Bookmark,
  ExternalLink,
  Trash2,
  Trophy,
  Gift,
  Download,
  Upload,
  Link2,
  Check,
  Share2,
} from 'lucide-react';
import { formatPrizePool } from '../utils/formatPrize';
import type { Hackathon, AIDeal } from '../types';
import { useModalA11y } from '../hooks/useModalA11y';
import {
  buildBookmarkExport,
  buildShareUrl,
  downloadBookmarkJson,
  readBookmarkFile,
} from '../api/bookmarks';

interface BookmarksDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  bookmarkedHackathons: Hackathon[];
  bookmarkedDeals: AIDeal[];
  onRemoveBookmark: (id: string) => void;
  onToggleAlert: (id: string) => void;
  /** Merge imported ids into local bookmarks */
  onImportIds?: (ids: string[], mode: 'merge' | 'replace') => void;
  /** When viewing a shared list (read-only share link) */
  sharedMode?: boolean;
  sharedIds?: string[];
  onSaveSharedToLocal?: () => void;
  onClearShared?: () => void;
}

export const BookmarksDrawer: React.FC<BookmarksDrawerProps> = ({
  isOpen,
  onClose,
  bookmarkedHackathons,
  bookmarkedDeals,
  onRemoveBookmark,
  onImportIds,
  sharedMode = false,
  sharedIds = [],
  onSaveSharedToLocal,
  onClearShared,
}) => {
  // Called before the `!isOpen` early return below — hooks must run every render.
  const dialogRef = useModalA11y<HTMLDivElement>(isOpen, onClose);
  const fileRef = useRef<HTMLInputElement>(null);
  const [shareCopied, setShareCopied] = useState(false);
  const [importMsg, setImportMsg] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);

  if (!isOpen) return null;

  const total = bookmarkedHackathons.length + bookmarkedDeals.length;
  const allIds = [
    ...bookmarkedHackathons.map((h) => h.id),
    ...bookmarkedDeals.map((d) => d.id),
    ...(sharedMode ? sharedIds : []),
  ];
  const uniqueIds = [...new Set(allIds)];

  const handleExport = () => {
    const items = [
      ...bookmarkedHackathons.map((h) => ({
        id: h.id,
        kind: 'hackathon' as const,
        title: h.title,
      })),
      ...bookmarkedDeals.map((d) => ({
        id: d.id,
        kind: 'ai_deal' as const,
        title: d.productName,
      })),
    ];
    const payload = buildBookmarkExport(uniqueIds, items);
    downloadBookmarkJson(payload);
    setImportMsg(`Exported ${uniqueIds.length} id(s)`);
    setImportError(null);
  };

  const handleShare = async () => {
    const url = buildShareUrl(uniqueIds);
    try {
      await navigator.clipboard.writeText(url);
      setShareCopied(true);
      setTimeout(() => setShareCopied(false), 2000);
    } catch {
      // Fallback: prompt
      window.prompt('Copy share link:', url);
    }
  };

  const handleImportFile = async (file: File) => {
    setImportError(null);
    setImportMsg(null);
    try {
      const ids = await readBookmarkFile(file);
      if (ids.length === 0) {
        setImportError('No ids found in file');
        return;
      }
      onImportIds?.(ids, 'merge');
      setImportMsg(`Imported ${ids.length} id(s) (merged)`);
    } catch (err) {
      setImportError(err instanceof Error ? err.message : 'Import failed');
    }
  };

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="bookmarks-drawer-title"
      className="fixed inset-y-0 right-0 z-50 w-full sm:w-[420px] bg-white dark:bg-[#131A29] border-l-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[8px_0_0_0_#1C1B18] dark:shadow-[8px_0_0_0_#D6DCE5] flex flex-col justify-between animate-in slide-in-from-right duration-300 font-sans"
    >
      {/* Drawer Header */}
      <div className="p-4 border-b border-[#D6D5CF] dark:border-slate-800 bg-[#F8F9F4] dark:bg-[#1A2336] flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-2xl bg-[#FF5A36]/15 text-[#FF5A36] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
            <Bookmark className="w-5 h-5" />
          </div>
          <div>
            <h3 id="bookmarks-drawer-title" className="text-base font-extrabold text-[#1C1B18] dark:text-white">
              {sharedMode ? 'Shared list (read-only)' : 'Saved Opportunities'}
            </h3>
            <p className="text-xs font-mono font-bold text-[#1C1B18] dark:text-[#B8C4D2]">
              {sharedMode
                ? `${sharedIds.length} id(s) from share link`
                : `${total} items in this browser`}
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="p-2 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-white hover:bg-[#FF5A36] hover:text-white transition-all font-bold"
          aria-label="Close"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Actions */}
      <div className="px-4 pt-3 flex flex-wrap gap-2 border-b border-[#D6D5CF] dark:border-slate-800 pb-3 bg-[#F8F9F4] dark:bg-[#1A2336]">
        {!sharedMode && (
          <>
            <button
              type="button"
              onClick={handleExport}
              disabled={uniqueIds.length === 0}
              className="btn-sharetopus-secondary text-[11px] py-1.5 px-2.5 flex items-center gap-1 disabled:opacity-40"
              title="Download JSON"
            >
              <Download className="w-3.5 h-3.5" />
              Export
            </button>
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="btn-sharetopus-secondary text-[11px] py-1.5 px-2.5 flex items-center gap-1"
              title="Import JSON"
            >
              <Upload className="w-3.5 h-3.5" />
              Import
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="application/json,.json"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void handleImportFile(f);
                e.target.value = '';
              }}
            />
          </>
        )}
        <button
          type="button"
          onClick={() => void handleShare()}
          disabled={uniqueIds.length === 0}
          className="btn-sharetopus-secondary text-[11px] py-1.5 px-2.5 flex items-center gap-1 disabled:opacity-40"
          title="Copy share link (?bm=ids)"
        >
          {shareCopied ? <Check className="w-3.5 h-3.5 text-green-600" /> : <Share2 className="w-3.5 h-3.5" />}
          {shareCopied ? 'Copied' : 'Share link'}
        </button>
        {sharedMode && (
          <>
            <button
              type="button"
              onClick={onSaveSharedToLocal}
              className="btn-sharetopus-primary text-[11px] py-1.5 px-2.5 flex items-center gap-1"
            >
              <Link2 className="w-3.5 h-3.5" />
              Save to my browser
            </button>
            <button
              type="button"
              onClick={onClearShared}
              className="btn-sharetopus-secondary text-[11px] py-1.5 px-2.5"
            >
              Dismiss share
            </button>
          </>
        )}
      </div>

      {(importMsg || importError) && (
        <div
          className={`mx-4 mt-2 text-[11px] font-bold rounded-xl px-3 py-2 border ${
            importError
              ? 'border-red-300 text-red-700 bg-red-50 dark:bg-red-900/20 dark:text-red-300'
              : 'border-emerald-300 text-emerald-800 bg-emerald-50 dark:bg-emerald-900/20 dark:text-emerald-300'
          }`}
        >
          {importError || importMsg}
        </div>
      )}

      {/* Drawer Body */}
      <div className="p-4 flex-1 overflow-y-auto space-y-4 text-xs">
        {total === 0 ? (
          <div className="py-12 text-center space-y-2">
            <Bookmark className="w-10 h-10 text-[#736F66] mx-auto" />
            <h4 className="font-extrabold text-[#1C1B18] dark:text-white text-sm">
              {sharedMode ? 'Shared ids not in current catalogue' : 'No Saved Opportunities'}
            </h4>
            <p className="text-xs text-[#1C1B18] dark:text-[#B8C4D2] font-bold">
              {sharedMode
                ? 'Ids are in the URL — open matching filters or save them locally. Some may be expired or not loaded.'
                : 'Click the bookmark icon on any card to save it for quick access. Export/import works offline.'}
            </p>
            {sharedMode && sharedIds.length > 0 && (
              <p className="text-[11px] font-mono text-[#736F66] break-all px-2">
                {sharedIds.slice(0, 8).join(', ')}
                {sharedIds.length > 8 ? ` +${sharedIds.length - 8} more` : ''}
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {bookmarkedHackathons.length > 0 && (
              <div className="space-y-2">
                <span className="font-mono text-[11px] font-extrabold text-[#FF5A36] uppercase">
                  {sharedMode ? 'SHARED' : 'SAVED'} HACKATHONS ({bookmarkedHackathons.length})
                </span>
                {bookmarkedHackathons.map((h) => (
                  <div
                    key={h.id}
                    className="sharetopus-card p-3 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-[#F8F9F4] dark:bg-[#1A2336] flex items-center justify-between gap-2"
                  >
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
                      <a
                        href={h.officialUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="p-1.5 rounded-full border border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#1A2336] text-[#1C1B18] dark:text-white hover:bg-[#FF5A36] hover:text-white"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                      {!sharedMode && (
                        <button
                          type="button"
                          onClick={() => onRemoveBookmark(h.id)}
                          className="p-1.5 rounded-full border border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#1A2336] text-[#FF5A36] hover:bg-[#FF5A36] hover:text-white"
                          aria-label="Remove bookmark"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {bookmarkedDeals.length > 0 && (
              <div className="space-y-2 pt-2">
                <span className="font-mono text-[11px] font-extrabold text-[#7C3AED] uppercase">
                  {sharedMode ? 'SHARED' : 'SAVED'} AI DEALS ({bookmarkedDeals.length})
                </span>
                {bookmarkedDeals.map((d) => (
                  <div
                    key={d.id}
                    className="sharetopus-card p-3 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-[#F8F9F4] dark:bg-[#1A2336] flex items-center justify-between gap-2"
                  >
                    <div className="space-y-0.5 min-w-0">
                      <div className="font-extrabold text-[#1C1B18] dark:text-white text-xs truncate flex items-center gap-1.5">
                        <Gift className="w-3.5 h-3.5 text-[#7C3AED] shrink-0" />
                        <span className="truncate">{d.productName}</span>
                      </div>
                      <div className="text-[11px] font-mono text-[#7C3AED] font-extrabold">
                        {d.offerValue}
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      <a
                        href={d.claimUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="p-1.5 rounded-full border border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#1A2336] text-[#1C1B18] dark:text-white hover:bg-[#7C3AED] hover:text-white"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                      {!sharedMode && (
                        <button
                          type="button"
                          onClick={() => onRemoveBookmark(d.id)}
                          className="p-1.5 rounded-full border border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#1A2336] text-[#FF5A36] hover:bg-[#FF5A36] hover:text-white"
                          aria-label="Remove bookmark"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Drawer Footer */}
      <div className="p-4 border-t border-[#D6D5CF] dark:border-slate-800 bg-[#F8F9F4] dark:bg-[#1A2336] text-[11px] font-mono font-extrabold text-[#1C1B18] dark:text-[#D6DCE5] flex items-center justify-between gap-2">
        <span className="truncate">{sharedMode ? 'Share link · no server account' : 'localStorage · no login'}</span>
        <button type="button" onClick={onClose} className="btn-sharetopus-secondary text-xs py-1 px-3 shrink-0">
          Close
        </button>
      </div>
    </div>
  );
};
