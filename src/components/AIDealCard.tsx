import React from 'react';
import { 
  ShieldCheck, 
  Gift, 
  ExternalLink, 
  Bookmark, 
  Clock, 
  CreditCard,
  ArrowUpRight,
  CheckCircle2
} from 'lucide-react';
import type { AIDeal } from '../types';

interface AIDealCardProps {
  deal: AIDeal;
  onSelect: (deal: AIDeal) => void;
  onToggleBookmark: (id: string) => void;
  onToggleAlert: (id: string) => void;
  viewLayout?: 'grid' | 'compact';
}

export const AIDealCard: React.FC<AIDealCardProps> = ({
  deal,
  onSelect,
  onToggleBookmark,
  viewLayout = 'grid'
}) => {
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
              <span className={`px-2 py-0.2 rounded-full text-[10px] font-extrabold border ${getOfferBadgeStyle(deal.offerType)}`}>
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
      
      {/* Top Provenance & Offer Type */}
      <div className="flex items-center justify-between gap-2 text-xs font-sans">
        <div className="flex items-center gap-2 flex-wrap">
          {/* Status Badge */}
          <span className="px-3 py-1 rounded-full bg-[#059669]/15 text-[#059669] border border-[#059669] text-[11px] font-extrabold flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#059669]" />
            Verified Active
          </span>

          {/* Offer Type Pill */}
          <span className={`px-3 py-1 rounded-full text-[11px] font-extrabold border ${getOfferBadgeStyle(deal.offerType)}`}>
            {deal.offerType.replace('_', ' ').toUpperCase()}
          </span>
        </div>

        {/* Confidence Score Gauge */}
        <div className="flex items-center gap-1.5 font-mono text-[11px] bg-[#F3F4EF] dark:bg-[#1A2336] px-3 py-1 rounded-full border border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold">
          <ShieldCheck className="w-3.5 h-3.5 text-[#1C1B18] dark:text-[#F8FAF9]" />
          <span>{Math.round(deal.confidenceScore * 100)}% Match</span>
        </div>
      </div>

      {/* Main Info */}
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-3">
          <div>
            <span className="text-xs text-[#1C1B18] dark:text-[#B8C4D2] font-extrabold uppercase tracking-wider">{deal.provider}</span>
            <h3 
              onClick={() => onSelect(deal)}
              className="text-xl font-extrabold text-[#1C1B18] dark:text-white hover:text-[#FF5A36] cursor-pointer transition-colors line-clamp-1 tracking-tight"
            >
              {deal.productName}
            </h3>
          </div>

          {/* Value Badge */}
          <div className="text-right shrink-0 bg-[#F8F9F4] dark:bg-[#1A2336] p-2.5 rounded-2xl border border-[#1C1B18] dark:border-[#D6DCE5]">
            <div className="text-[10px] text-[#1C1B18] dark:text-[#F8FAF9] font-mono font-extrabold tracking-wider">VALUE</div>
            <div className="text-lg font-extrabold text-[#FF5A36] font-mono flex items-center gap-1 justify-end">
              <Gift className="w-4 h-4 text-[#FF5A36]" />
              <span>{deal.offerValue}</span>
            </div>
          </div>
        </div>

        <p className="text-xs text-[#1C1B18] dark:text-[#D6DCE5] line-clamp-2 leading-relaxed font-bold">
          {deal.description}
        </p>
      </div>

      {/* Value Proposition Box */}
      <div className="bg-[#F8F9F4] dark:bg-[#1A2336] border border-[#1C1B18] dark:border-[#D6DCE5] rounded-2xl p-3.5 space-y-2 text-xs">
        <div className="flex items-center justify-between text-[11px] font-extrabold text-[#FF5A36] font-mono">
          <span className="flex items-center gap-1.5">
            <CreditCard className="w-3.5 h-3.5 text-[#FF5A36]" />
            DEAL IMPACT:
          </span>
          <span className="text-[#1C1B18] dark:text-[#B8C4D2] font-sans font-bold">Target: {deal.targetUsers.join(', ')}</span>
        </div>
        <ul className="space-y-1 text-[#1C1B18] dark:text-[#E8ECF1] font-extrabold">
          {deal.requirements.map((req, idx) => (
            <li key={idx} className="flex items-center gap-1.5 text-[11px]">
              <CheckCircle2 className="w-3.5 h-3.5 text-[#059669] shrink-0" />
              <span>{req}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Tags */}
      <div className="flex items-center gap-1.5 flex-wrap text-[11px] font-mono">
        {deal.tags.map((tag, i) => (
          <span key={i} className="px-3 py-1 rounded-full bg-[#F3F4EF] dark:bg-[#1A2336] border border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white font-extrabold">
            #{tag}
          </span>
        ))}
      </div>

      {/* Footer & Action Buttons */}
      <div className="pt-3 border-t border-[#D6D5CF] dark:border-slate-800 flex items-center justify-between gap-3 text-xs">
        <div className="text-[11px] font-mono text-[#1C1B18] dark:text-[#D6DCE5] font-extrabold flex items-center gap-1">
          <Clock className="w-3.5 h-3.5 text-[#FF5A36]" />
          <span>Checked {new Date(deal.lastCheckedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
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
};
