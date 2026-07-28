import React from 'react';
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';

interface PaginationProps {
  currentPage: number;
  totalItems: number;
  totalAvailable?: number;
  rowsPerPage: number; // 0 or Infinity means 'All'
  onPageChange: (page: number) => void;
  onRowsPerPageChange: (rows: number) => void;
  hasMore?: boolean;
  isLoadingMore?: boolean;
  loadMoreError?: string | null;
  onLoadMore?: () => void;
  options?: number[];
  className?: string;
}

export const Pagination: React.FC<PaginationProps> = ({
  currentPage,
  totalItems,
  totalAvailable = totalItems,
  rowsPerPage,
  onPageChange,
  onRowsPerPageChange,
  hasMore = false,
  isLoadingMore = false,
  loadMoreError = null,
  onLoadMore,
  options = [6, 12, 24, 48],
  className = '',
}) => {
  if (totalItems === 0) return null;

  const isAll = rowsPerPage >= totalItems || rowsPerPage === 0;
  const totalPages = isAll ? 1 : Math.ceil(totalItems / rowsPerPage);

  const startItem = isAll ? 1 : (currentPage - 1) * rowsPerPage + 1;
  const endItem = isAll ? totalItems : Math.min(currentPage * rowsPerPage, totalItems);

  const handlePrev = () => {
    if (currentPage > 1) onPageChange(currentPage - 1);
  };

  const handleNext = () => {
    if (currentPage < totalPages) onPageChange(currentPage + 1);
  };

  return (
    <div
      className={`sharetopus-card p-4 rounded-[20px] bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] flex flex-col sm:flex-row items-center justify-between gap-4 font-mono text-xs text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold ${className}`}
    >
      {/* Rows per page selector */}
      <div className="flex items-center gap-2">
        <label htmlFor="rows-per-page-select" className="text-[12px] text-[#4A4845] dark:text-[#B8C4D2]">
          Rows per page:
        </label>
        <select
          id="rows-per-page-select"
          aria-label="Rows per page"
          value={isAll ? 'all' : rowsPerPage}
          onChange={(e) => {
            const val = e.target.value;
            if (val === 'all') {
              onRowsPerPageChange(0); // 0 represents 'All'
            } else {
              onRowsPerPageChange(Number(val));
            }
          }}
          className="bg-[#F3F4EF] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white rounded-xl px-3 py-1.5 outline-none font-bold text-xs cursor-pointer"
        >
          {options.map((opt) => (
            <option key={opt} value={opt}>
              {opt} items
            </option>
          ))}
          <option value="all">All loaded ({totalItems})</option>
        </select>
      </div>

      {/* Item count summary */}
      <div className="text-[12px] font-bold text-[#1C1B18] dark:text-[#D6DCE5]">
        Showing <strong className="text-[#C2410C] dark:text-[#FF8A6B] font-extrabold">{startItem}–{endItem}</strong> of{' '}
        <strong className="text-[#047857] dark:text-[#34D399] font-extrabold">{totalItems}</strong> loaded
        {totalAvailable > totalItems && (
          <span className="text-[#736F66] dark:text-[#94A3B8]"> · {totalAvailable} available</span>
        )}
      </div>

      {/* Page navigation controls */}
      {!isAll && totalPages > 1 && (
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handlePrev}
            disabled={currentPage === 1}
            title="Previous page"
            className="p-1.5 rounded-xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#1A2336] text-[#1C1B18] dark:text-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[#D23B14] hover:text-white transition-all font-bold"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          {/* Page numbers */}
          <div className="flex items-center gap-1">
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => {
              // Show limited page numbers if totalPages is large
              if (
                totalPages > 6 &&
                page !== 1 &&
                page !== totalPages &&
                Math.abs(page - currentPage) > 1
              ) {
                if (page === 2 && currentPage > 3) {
                  return <span key="dots1" className="px-1 text-slate-400">…</span>;
                }
                if (page === totalPages - 1 && currentPage < totalPages - 2) {
                  return <span key="dots2" className="px-1 text-slate-400">…</span>;
                }
                return null;
              }

              return (
                <button
                  key={page}
                  type="button"
                  onClick={() => onPageChange(page)}
                  className={`px-3 py-1.5 rounded-xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] font-extrabold text-xs transition-all ${
                    currentPage === page
                      ? 'bg-[#D23B14] text-white shadow-sm'
                      : 'bg-white dark:bg-[#1A2336] text-[#1C1B18] dark:text-white hover:bg-[#1C1B18] hover:text-white'
                  }`}
                >
                  {page}
                </button>
              );
            })}
          </div>

          <button
            type="button"
            onClick={handleNext}
            disabled={currentPage === totalPages}
            title="Next page"
            className="p-1.5 rounded-xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#1A2336] text-[#1C1B18] dark:text-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[#D23B14] hover:text-white transition-all font-bold"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {(hasMore || loadMoreError) && onLoadMore && (
        <div className="flex flex-col items-center sm:items-end gap-1.5 sm:ml-auto">
          <button
            type="button"
            onClick={onLoadMore}
            disabled={isLoadingMore}
            className="btn-sharetopus-secondary justify-center text-xs py-2 px-4 font-bold disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {isLoadingMore && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            <span>{isLoadingMore ? 'Loading more…' : 'Load more opportunities'}</span>
          </button>
          {loadMoreError && (
            <span role="alert" className="max-w-xs text-center sm:text-right text-[11px] text-[#B91C1C] dark:text-[#F87171]">
              {loadMoreError}
            </span>
          )}
        </div>
      )}
    </div>
  );
};
