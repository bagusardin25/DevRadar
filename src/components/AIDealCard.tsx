import { memo } from 'react';
import { 
  ShieldCheck, 
  Gift, 
  ExternalLink, 
  Bookmark, 
  Clock, 
  CreditCard,
  ArrowUpRight,
  CheckCircle2,
  RefreshCw
} from 'lucide-react';
import type { AIDeal } from '../types';
import { getDeadlineInfo } from '../utils/countdown';
import { compactDescription, dedupeHighlights } from '../utils/cardSummary';
import { formatAppDateTime } from '../utils/dateTime';
import { ListingBadges } from './ListingBadges';

/** Cards trade completeness for scannability; the modal carries the full lists. */
const MAX_CARD_TAGS = 3;
const MAX_CARD_HIGHLIGHTS = 2;

interface AIDealCardProps {
  deal: AIDeal;
  onSelect: (deal: AIDeal) => void;
  onToggleBookmark: (id: string) => void;
  onToggleAlert: (id: string) => void;
  viewLayout?: 'grid' | 'compact';
}

export const AIDealCard = memo(function AIDealCard({
  deal,
  onSelect,
  onToggleBookmark,
  viewLayout = 'grid'
}: AIDealCardProps) {
  // D1: Urgency countdown for deals with expiry
  const deadlineInfo = deal.expiresAt ? getDeadlineInfo(deal.expiresAt, 'Expired') : null;

  // The offer value gets its own slot, so drop the prose that restates it.
  const description = compactDescription(deal.description, deal.offerValue);
  const highlights = dedupeHighlights(
    deal.suitableReasons.length > 0 ? deal.suitableReasons : deal.requirements,
    { description: deal.description, prizeLabel: deal.offerValue },
  ).slice(0, MAX_CARD_HIGHLIGHTS);
  const visibleTags = deal.tags.slice(0, MAX_CARD_TAGS);
  const hiddenTagCount = deal.tags.length - visibleTags.length;

  if (viewLayout === 'compact') {
    // The compact row is the grid card minus the prose: same badges, same scan
    // strip, same action set — only the description and highlights are dropped,
    // because those are what make the grid card tall.
    return (
      // Viewport breakpoints, not the grid card's container queries: a compact
      // row always spans the full content column, so the viewport is an honest
      // proxy for its width.
      <div className="sharetopus-card p-4 rounded-[20px] bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[3px_3px_0_0_#1C1B18] dark:shadow-[3px_3px_0_0_#D6DCE5] hover:shadow-[5px_5px_0_0_#1C1B18] dark:hover:shadow-[5px_5px_0_0_#D6DCE5] flex flex-col lg:flex-row lg:items-center justify-between gap-4 transition-all duration-300">
        <div className="flex items-start gap-3.5 min-w-0">
          <div className="w-10 h-10 rounded-2xl bg-[#FFF1EE] dark:bg-[#FF5A36]/20 border border-[#1C1B18] dark:border-[#D6DCE5] flex items-center justify-center shrink-0">
            <Gift className="w-5 h-5 text-[#C2410C] dark:text-[#FF8A6B]" />
          </div>

          <div className="min-w-0 space-y-2">
            {/* Verification status was missing from this row entirely; it now
                reads from the same source as the grid card. */}
            <div className="flex items-center gap-1.5 flex-wrap text-xs font-sans">
              <ListingBadges
                status={deal.verificationStatus}
                completeness={deal.completeness}
                extra={[
                  {
                    key: 'offer_type',
                    label: deal.offerType.replace(/_/g, ' ').toUpperCase(),
                    tone: 'purple',
                  },
                ]}
              />
              <span className="inline-flex items-center gap-1.5 font-mono text-[12px] bg-[#F3F4EF] dark:bg-[#1A2336] px-3 py-1 rounded-full border border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold shrink-0">
                <ShieldCheck className="w-3.5 h-3.5 text-[#1C1B18] dark:text-[#F8FAF9]" />
                <span>{Math.round(deal.confidenceScore * 100)}%</span>
              </span>
            </div>

            <div className="min-w-0">
              <span className="block text-[12px] text-[#4A4845] dark:text-[#B8C4D2] font-semibold uppercase tracking-wider truncate">{deal.provider}</span>
              {/* The heading carries the click target, so the button inside it
                  is what makes the title reachable by keyboard as well. */}
              <h3 className="text-base lg:text-lg font-extrabold tracking-tight">
                <button
                  type="button"
                  onClick={() => onSelect(deal)}
                  className="text-left w-full text-[#1C1B18] dark:text-white hover:text-[#C2410C] dark:hover:text-[#FF8A6B] cursor-pointer transition-colors line-clamp-2 lg:line-clamp-1 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#C2410C] dark:focus-visible:outline-[#FF8A6B] rounded-sm"
                >
                  {deal.productName}
                </button>
              </h3>
            </div>

            {/* Scan strip + tags share a wrapping row here; separate rows in the
                grid card only because the card is narrow. */}
            <div className="flex items-center gap-1.5 flex-wrap text-[12px] font-mono">
              <span className="inline-flex items-start gap-1.5 px-3 py-1 rounded-full bg-[#F8F9F4] dark:bg-[#1A2336] border border-[#1C1B18] dark:border-[#D6DCE5] text-[#C2410C] dark:text-[#FF8A6B] font-extrabold">
                <Gift className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                <span className="break-words">{deal.offerValue}</span>
              </span>
              {deadlineInfo ? (
                <span className={`urgency-badge urgency-${deadlineInfo.urgency}`}>
                  <Clock className="w-3.5 h-3.5" />
                  <span>{deadlineInfo.shortLabel}</span>
                </span>
              ) : (
                <span className="urgency-badge urgency-normal">
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Ongoing</span>
                </span>
              )}
              {visibleTags.map((tag) => (
                <span key={tag} className="px-3 py-1 rounded-full bg-[#F3F4EF] dark:bg-[#1A2336] border border-[#D6D5CF] dark:border-slate-700 text-[#4A4845] dark:text-[#CBD5E1] font-medium">
                  #{tag}
                </span>
              ))}
              {hiddenTagCount > 0 && (
                <span
                  className="px-1.5 py-1 text-[#736F66] dark:text-[#94A3B8] font-medium"
                  title={deal.tags.join(', ')}
                >
                  +{hiddenTagCount} more
                </span>
              )}
              <span className="px-1.5 py-1 font-sans font-medium text-[#736F66] dark:text-[#94A3B8]">
                For: {deal.targetUsers.join(', ')}
              </span>
            </div>
          </div>
        </div>

        {/* Same actions and same order as the grid card; wraps so the primary
            button can never overflow the row. */}
        <div className="flex items-center gap-2 flex-wrap lg:justify-end lg:shrink-0">
          <button
            onClick={() => onToggleBookmark(deal.id)}
            aria-pressed={deal.bookmarked}
            aria-label={deal.bookmarked ? `Remove bookmark for ${deal.productName}` : `Bookmark ${deal.productName}`}
            title={deal.bookmarked ? 'Remove bookmark' : 'Bookmark'}
            className={`p-2 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] transition-all font-bold ${
              deal.bookmarked
                ? 'bg-[#1C1B18] text-white'
                : 'bg-white dark:bg-[#1A2336] text-[#1C1B18] dark:text-white hover:bg-[#1C1B18] hover:text-white'
            }`}
          >
            <Bookmark className="w-4 h-4" />
          </button>

          <button
            onClick={() => onSelect(deal)}
            className="btn-sharetopus-secondary text-xs py-2 px-4 font-bold"
          >
            <span>Details</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>

          {/* An anchor, like the grid card: the label and the external-link icon
              promise the offer page, but this used to just open the modal. */}
          <a
            href={deal.claimUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-sharetopus-primary text-xs py-2 px-4 bg-[#6D28D9] hover:bg-[#5B21B6] font-bold"
          >
            <span>Claim Offer</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="sharetopus-card p-6 rounded-[24px] bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] hover:shadow-[6px_6px_0_0_#1C1B18] dark:hover:shadow-[6px_6px_0_0_#D6DCE5] flex flex-col justify-between gap-5 relative overflow-hidden transition-all duration-300">
      
      {/* Status + completeness + offer type */}
      <div className="flex items-center justify-between gap-2 text-xs font-sans">
        <ListingBadges
          status={deal.verificationStatus}
          completeness={deal.completeness}
          extra={[
            {
              key: 'offer_type',
              label: deal.offerType.replace(/_/g, ' ').toUpperCase(),
              tone: 'purple',
            },
          ]}
        />

        <div className="flex items-center gap-1.5 font-mono text-[12px] bg-[#F3F4EF] dark:bg-[#1A2336] px-3 py-1 rounded-full border border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold shrink-0">
          <ShieldCheck className="w-3.5 h-3.5 text-[#1C1B18] dark:text-[#F8FAF9]" />
          <span>{Math.round(deal.confidenceScore * 100)}%</span>
        </div>
      </div>

      {/* Main Info — the product name owns the full card width so it never
          loses a space fight with the value badge and truncates. */}
      <div className="space-y-3">
        <div className="min-w-0">
          <span className="text-[12px] text-[#4A4845] dark:text-[#B8C4D2] font-semibold uppercase tracking-wider">{deal.provider}</span>
          {/* The heading carries the click target, so the button inside it is
              what makes the title reachable by keyboard as well as mouse. */}
          <h3 className="text-lg sm:text-xl font-extrabold tracking-tight">
            <button
              type="button"
              onClick={() => onSelect(deal)}
              className="text-left w-full text-[#1C1B18] dark:text-white hover:text-[#C2410C] dark:hover:text-[#FF8A6B] cursor-pointer transition-colors line-clamp-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#C2410C] dark:focus-visible:outline-[#FF8A6B] rounded-sm"
            >
              {deal.productName}
            </button>
          </h3>
        </div>

        {/* Scan strip — what you get, and whether it is still live. */}
        <div className="flex items-center gap-2 flex-wrap text-[12px] font-mono">
          <span className="inline-flex items-start gap-1.5 px-3 py-1 rounded-full bg-[#F8F9F4] dark:bg-[#1A2336] border border-[#1C1B18] dark:border-[#D6DCE5] text-[#C2410C] dark:text-[#FF8A6B] font-extrabold">
            <Gift className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            <span className="break-words">{deal.offerValue}</span>
          </span>
          {deadlineInfo ? (
            <span className={`urgency-badge urgency-${deadlineInfo.urgency}`}>
              <Clock className="w-3.5 h-3.5" />
              <span>{deadlineInfo.shortLabel}</span>
            </span>
          ) : (
            <span className="urgency-badge urgency-normal">
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Ongoing</span>
            </span>
          )}
        </div>

        <p className="text-[13px] sm:text-sm text-[#4A4845] dark:text-[#CBD5E1] line-clamp-2 leading-relaxed">
          {description}
        </p>
      </div>

      {/* Key Highlights */}
      {highlights.length > 0 && (
      <div className="bg-[#F8F9F4] dark:bg-[#1A2336] border border-[#D6D5CF] dark:border-slate-700 rounded-2xl p-3.5 space-y-2">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 text-[11px] font-semibold text-[#736F66] dark:text-[#94A3B8] font-mono uppercase tracking-wide">
          <span className="flex items-center gap-1.5">
            <CreditCard className="w-3.5 h-3.5" />
            Key highlights
          </span>
          <span className="font-sans normal-case tracking-normal">
            For: {deal.targetUsers.join(', ')}
          </span>
        </div>
        <ul className="space-y-1.5 text-[#1C1B18] dark:text-[#E8ECF1]">
          {highlights.map((req, idx) => (
            <li key={idx} className="flex items-start gap-1.5 text-[12px] sm:text-[13px]">
              <CheckCircle2 className="w-3.5 h-3.5 text-[#047857] dark:text-[#34D399] shrink-0 mt-0.5" />
              <span>{req}</span>
            </li>
          ))}
        </ul>
      </div>
      )}

      {/* Tags — capped, and lighter-bordered than the card so they read as
          secondary rather than competing with the product name. */}
      {visibleTags.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap text-[12px] font-mono">
          {visibleTags.map((tag) => (
            <span key={tag} className="px-3 py-1 rounded-full bg-[#F3F4EF] dark:bg-[#1A2336] border border-[#D6D5CF] dark:border-slate-700 text-[#4A4845] dark:text-[#CBD5E1] font-medium">
              #{tag}
            </span>
          ))}
          {hiddenTagCount > 0 && (
            <span
              className="px-1.5 py-1 text-[#736F66] dark:text-[#94A3B8] font-medium"
              title={deal.tags.join(', ')}
            >
              +{hiddenTagCount} more
            </span>
          )}
        </div>
      )}

      {/* Footer & Action Buttons. The row wraps so the primary button can never
          overflow the card and get clipped by its overflow-hidden. */}
      <div className="pt-3 border-t border-[#D6D5CF] dark:border-slate-800 flex items-center justify-between gap-x-3 gap-y-2 flex-wrap text-xs">
        <span className="text-[12px] font-mono text-[#736F66] dark:text-[#94A3B8] font-medium flex items-center gap-1">
          <Clock className="w-3.5 h-3.5" />
          Checked {formatAppDateTime(deal.lastCheckedAt, { hour: '2-digit', minute: '2-digit' })}
        </span>

        <div className="flex items-center gap-2 ml-auto">
          {/* Bookmark */}
          <button
            onClick={() => onToggleBookmark(deal.id)}
            aria-pressed={deal.bookmarked}
            aria-label={deal.bookmarked ? `Remove bookmark for ${deal.productName}` : `Bookmark ${deal.productName}`}
            title={deal.bookmarked ? 'Remove bookmark' : 'Bookmark'}
            className={`p-2 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] transition-all font-bold ${
              deal.bookmarked
                ? 'bg-[#1C1B18] text-white'
                : 'bg-white dark:bg-[#1A2336] text-[#1C1B18] dark:text-white hover:bg-[#1C1B18] hover:text-white'
            }`}
          >
            <Bookmark className="w-4 h-4" />
          </button>

          {/* Details */}
          <button
            onClick={() => onSelect(deal)}
            className="btn-sharetopus-secondary text-xs py-2 px-4 font-bold"
          >
            <span>Details</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>

          {/* Claim / View Details */}
          <a
            href={deal.claimUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-sharetopus-primary text-xs py-2 px-4 bg-[#6D28D9] hover:bg-[#5B21B6] font-bold"
          >
            <span>Claim Offer</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>

    </div>
  );
});
