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
import { ListingBadges } from './ListingBadges';

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

  const getOfferBadgeStyle = (type: string) => {
    switch (type) {
      case 'free_credits':
        return 'bg-[#ECFDF5] dark:bg-[#059669]/15 text-[#059669] border-[#059669]';
      case 'free_model':
        return 'bg-[#F0F9FF] dark:bg-[#FF5A36]/15 text-[#FF5A36] border-[#FF5A36]';
      case 'credit_grant':
        return 'bg-[#F5F3FF] dark:bg-[#FF5A36]/15 text-[#FF5A36] border-[#FF5A36]';
      case 'early_access':
        return 'bg-[#FFFBEB] dark:bg-[#D97706]/15 text-[#D97706] border-[#D97706]';
      default:
        return 'bg-[#F3F4EF] dark:bg-[#1A2336] text-[#1C1B18] dark:text-white border-[#1C1B18] dark:border-[#D6DCE5]';
    }
  };

  if (viewLayout === 'compact') {
    return (
      <div className="sharetopus-card p-4 rounded-[20px] bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-[3px_3px_0_0_#1C1B18] dark:shadow-[3px_3px_0_0_#D6DCE5]">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-2xl bg-[#FF5A36]/15 border border-[#1C1B18] dark:border-[#D6DCE5] flex items-center justify-center text-[#FF5A36] font-bold shrink-0">
            <Gift className="w-5 h-5 text-[#FF5A36]" />
          </div>
          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-[#1C1B18] dark:text-[#D6DCE5] font-extrabold">{deal.provider}</span>
              <span className={`px-2 py-0.5 rounded-full text-[12px] font-extrabold border ${getOfferBadgeStyle(deal.offerType)}`}>
                {deal.offerType.replace('_', ' ').toUpperCase()}
              </span>
            </div>
            <h4 
              onClick={() => onSelect(deal)}
              className="text-base font-extrabold text-[#1C1B18] dark:text-white hover:text-[#FF5A36] cursor-pointer transition-colors"
            >
              {deal.productName}
            </h4>
            <div className="flex items-center gap-3 text-xs font-mono text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold">
              <span className="text-[#FF5A36] font-extrabold">{deal.offerValue}</span>
              <span>•</span>
              <span className="text-[#1C1B18] dark:text-[#D6DCE5] font-extrabold">Target: {deal.targetUsers.join(', ')}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 justify-end shrink-0">
          <button
            onClick={() => onToggleBookmark(deal.id)}
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
            className="btn-sharetopus-primary text-xs py-1.5 px-4 font-extrabold"
          >
            <span>Claim Offer</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </button>
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

      {/* Main Info */}
      <div className="space-y-2">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
          <div className="min-w-0">
            <span className="text-[12px] text-[#1C1B18] dark:text-[#B8C4D2] font-extrabold uppercase tracking-wider">{deal.provider}</span>
            <h3 
              onClick={() => onSelect(deal)}
              className="text-lg sm:text-xl font-extrabold text-[#1C1B18] dark:text-white hover:text-[#FF5A36] cursor-pointer transition-colors line-clamp-2 sm:line-clamp-1 tracking-tight"
            >
              {deal.productName}
            </h3>
          </div>

          {/* Value Badge */}
          <div className="text-left sm:text-right shrink-0 bg-[#F8F9F4] dark:bg-[#1A2336] p-2.5 rounded-2xl border border-[#1C1B18] dark:border-[#D6DCE5] w-full sm:w-auto max-w-full">
            <div className="text-[12px] text-[#1C1B18] dark:text-[#F8FAF9] font-mono font-extrabold tracking-wider">VALUE</div>
            <div className="text-sm sm:text-base font-extrabold text-[#FF5A36] font-mono flex items-start gap-1 sm:justify-end leading-tight">
              <Gift className="w-4 h-4 text-[#FF5A36] shrink-0 mt-0.5" />
              <span className="break-words">{deal.offerValue}</span>
            </div>
          </div>
        </div>

        <p className="text-[13px] sm:text-sm text-[#1C1B18] dark:text-[#D6DCE5] line-clamp-2 leading-relaxed font-bold">
          {deal.description}
        </p>
      </div>

      {/* Key Highlights */}
      <div className="bg-[#F8F9F4] dark:bg-[#1A2336] border border-[#1C1B18] dark:border-[#D6DCE5] rounded-2xl p-3.5 space-y-2 text-sm">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 text-[12px] font-extrabold text-[#FF5A36] font-mono uppercase tracking-wide">
          <span className="flex items-center gap-1.5">
            <CreditCard className="w-3.5 h-3.5 text-[#FF5A36]" />
            Key highlights
          </span>
          <span className="text-[#1C1B18] dark:text-[#B8C4D2] font-sans font-bold normal-case tracking-normal">
            For: {deal.targetUsers.join(', ')}
          </span>
        </div>
        <ul className="space-y-1 text-[#1C1B18] dark:text-[#E8ECF1] font-bold">
          {(deal.suitableReasons.length > 0 ? deal.suitableReasons : deal.requirements)
            .slice(0, 4)
            .map((req, idx) => (
            <li key={idx} className="flex items-start gap-1.5 text-[12px] sm:text-[13px]">
              <CheckCircle2 className="w-3.5 h-3.5 text-[#059669] shrink-0 mt-0.5" />
              <span>{req}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Tags */}
      <div className="flex items-center gap-1.5 flex-wrap text-[12px] font-mono">
        {deal.tags.map((tag, i) => (
          <span key={i} className="px-3 py-1 rounded-full bg-[#F3F4EF] dark:bg-[#1A2336] border border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white font-extrabold">
            #{tag}
          </span>
        ))}
      </div>

      {/* Footer & Action Buttons */}
      <div className="pt-3 border-t border-[#D6D5CF] dark:border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2">
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
          <span className="text-[12px] font-mono text-[#1C1B18] dark:text-[#D6DCE5] font-extrabold flex items-center gap-1">
            <Clock className="w-3.5 h-3.5 text-[#FF5A36]" />
            Checked {new Date(deal.lastCheckedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Bookmark */}
          <button
            onClick={() => onToggleBookmark(deal.id)}
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
            className="btn-sharetopus-secondary text-xs py-2 px-4 font-extrabold"
          >
            <span>Audit</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>

          {/* Claim / View Details */}
          <a
            href={deal.claimUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-sharetopus-primary text-xs py-2 px-4 bg-[#7C3AED] hover:bg-[#6D28D9] font-extrabold"
          >
            <span>Claim Offer</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>

    </div>
  );
});
