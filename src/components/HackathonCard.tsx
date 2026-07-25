import React, { memo } from 'react';
import {
  Trophy,
  ShieldCheck,
  Bookmark,
  Clock,
  ArrowUpRight,
  Sparkles,
  CheckCircle2,
  Download,
  Calendar,
} from 'lucide-react';
import type { Hackathon } from '../types';
import { formatPrizePool } from '../utils/formatPrize';
import { getDeadlineInfo } from '../utils/countdown';
import { downloadICS, buildGoogleCalendarUrl, hackathonRegDeadlineEvent } from '../utils/calendar';
import { ListingBadges } from './ListingBadges';

interface HackathonCardProps {
  hackathon: Hackathon;
  onSelect: (hackathon: Hackathon) => void;
  onToggleBookmark: (id: string) => void;
  onToggleAlert: (id: string) => void;
  onToggleCompare: (hackathon: Hackathon) => void;
  isCompared: boolean;
  viewLayout?: 'grid' | 'compact';
}

export const HackathonCard = memo(function HackathonCard({
  hackathon,
  onSelect,
  onToggleBookmark,
  onToggleCompare,
  isCompared,
  viewLayout = 'grid'
}: HackathonCardProps) {
  // D1: Urgency-aware deadline info
  const deadlineRaw = hackathon.registrationDeadline || hackathon.submissionDeadline;
  const deadlineInfo = getDeadlineInfo(deadlineRaw);

  const primarySource = hackathon.discoverySources[0];

  const handleDownloadMD = (e: React.MouseEvent, hackathon: Hackathon) => {
    e.stopPropagation();
    const mdContent = `# ${hackathon.title}\n\n**Organizer:** ${hackathon.organizer}\n**Prize Pool:** ${formatPrizePool(hackathon)}\n**Registration Deadline:** ${new Date(hackathon.registrationDeadline).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })}\n**Submission Deadline:** ${new Date(hackathon.submissionDeadline).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })}\n\n## Description\n${hackathon.description}\n\n## Technologies\n${hackathon.technologies.join(', ')}\n\n## Official Link\n[${hackathon.officialUrl}](${hackathon.officialUrl})\n\n## Verification Notes\n${hackathon.audit?.verifierNotes || 'N/A'}\n`;
    
    const blob = new Blob([mdContent], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${hackathon.title.replace(/[^a-z0-9]/gi, '-').toLowerCase()}-rules.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (viewLayout === 'compact') {
    return (
      <div className="sharetopus-card p-4 rounded-[20px] bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-[3px_3px_0_0_#1C1B18] dark:shadow-[3px_3px_0_0_#D6DCE5]">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-2xl bg-[#FF5A36]/15 border border-[#1C1B18] dark:border-[#D6DCE5] flex items-center justify-center text-[#FF5A36] font-bold shrink-0">
            <Trophy className="w-5 h-5 text-[#FF5A36]" />
          </div>
          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold">{hackathon.organizer}</span>
              <span className="px-2 py-0.5 rounded-full bg-[#059669]/15 text-[#059669] dark:text-[#34D399] border border-[#059669] text-[12px] font-extrabold">VERIFIED</span>
            </div>
            <h4 
              onClick={() => onSelect(hackathon)}
              className="text-base font-extrabold text-[#1C1B18] dark:text-white hover:text-[#FF5A36] cursor-pointer transition-colors"
            >
              {hackathon.title}
            </h4>
            <div className="flex items-center gap-3 text-xs font-mono text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold">
              <span className="text-[#059669] dark:text-[#34D399] font-extrabold">{formatPrizePool(hackathon, { compact: true })}</span>
              <span>•</span>
              {deadlineInfo && (
                <span className={`urgency-badge urgency-${deadlineInfo.urgency}`}>
                  <Clock className="w-3.5 h-3.5" />
                  <span>{deadlineInfo.shortLabel}</span>
                </span>
              )}
              <span>•</span>
              <span className="text-[#1C1B18] dark:text-[#F8FAF9] font-bold">{hackathon.technologies.slice(0, 3).join(', ')}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 justify-end shrink-0">
          <button
            onClick={() => onToggleCompare(hackathon)}
            className={`px-3.5 py-1.5 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-xs font-extrabold transition-all ${
              isCompared
                ? 'bg-[#1C1B18] text-white dark:bg-white dark:text-[#1C1B18]'
                : 'bg-white dark:bg-[#1A2336] text-[#1C1B18] dark:text-white hover:bg-[#1C1B18] hover:text-white'
            }`}
          >
            {isCompared ? '✓ Comparing' : '+ Compare'}
          </button>

          <button
            onClick={() => onToggleBookmark(hackathon.id)}
            className={`p-2 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] transition-all font-bold ${
              hackathon.bookmarked
                ? 'bg-[#FF5A36] text-white'
                : 'bg-white dark:bg-[#1A2336] text-[#1C1B18] dark:text-white hover:bg-[#FF5A36] hover:text-white'
            }`}
          >
            <Bookmark className="w-4 h-4" />
          </button>

          <button
            onClick={(e) => handleDownloadMD(e, hackathon)}
            title="Download Context for AI Agent (.md)"
            className="p-2 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] transition-all font-bold bg-white dark:bg-[#1A2336] text-[#1C1B18] dark:text-white hover:bg-[#1C1B18] hover:text-white"
          >
            <Download className="w-4 h-4" />
          </button>

          <button
            onClick={() => onSelect(hackathon)}
            className="btn-sharetopus-primary text-xs py-1.5 px-4 font-extrabold"
          >
            <span>View Details</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="sharetopus-card p-6 rounded-[24px] bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] hover:shadow-[6px_6px_0_0_#1C1B18] dark:hover:shadow-[6px_6px_0_0_#D6DCE5] flex flex-col justify-between gap-5 relative overflow-hidden transition-all duration-300">
      
      {/* Card Header: status + completeness + provenance */}
      <div className="flex items-center justify-between gap-2 text-xs font-sans">
        <ListingBadges
          status={hackathon.verificationStatus}
          completeness={hackathon.completeness}
          extra={[
            {
              key: 'tier',
              label: primarySource?.tier || 'Tier ?',
              tone: 'slate',
              title: 'Source trust tier',
            },
          ]}
        />

        <div className="flex items-center gap-1.5 font-mono text-[12px] bg-[#F3F4EF] dark:bg-[#1A2336] px-3 py-1 rounded-full border border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold shrink-0">
          <ShieldCheck className="w-3.5 h-3.5 text-[#1C1B18] dark:text-[#F8FAF9]" />
          <span>{Math.round(hackathon.confidenceScore * 100)}%</span>
        </div>
      </div>

      {/* Main Info */}
      <div className="space-y-2">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
          <div className="min-w-0">
            <span className="text-[12px] text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold uppercase tracking-wider">{hackathon.organizer}</span>
            <h3 
              onClick={() => onSelect(hackathon)}
              className="text-lg sm:text-xl font-extrabold text-[#1C1B18] dark:text-white hover:text-[#FF5A36] cursor-pointer transition-colors line-clamp-2 sm:line-clamp-1 tracking-tight"
            >
              {hackathon.title}
            </h3>
          </div>

          {/* Prize Value Pill */}
          <div className="text-left sm:text-right shrink-0 bg-[#F8F9F4] dark:bg-[#1A2336] p-2.5 rounded-2xl border border-[#1C1B18] dark:border-[#D6DCE5] w-full sm:w-auto">
            <div className="text-[12px] text-[#1C1B18] dark:text-[#F8FAF9] font-mono font-extrabold tracking-wider">PRIZE POOL</div>
            <div className="text-sm sm:text-base font-extrabold text-[#059669] dark:text-[#34D399] font-mono flex items-center gap-1 sm:justify-end max-w-none sm:max-w-[12rem] leading-tight">
              <Trophy className="w-4 h-4 text-[#FF5A36] shrink-0" />
              <span>{formatPrizePool(hackathon, { compact: true })}</span>
            </div>
          </div>
        </div>

        <p className="text-[13px] sm:text-sm text-[#1C1B18] dark:text-[#F8FAF9] line-clamp-2 leading-relaxed font-bold">
          {hackathon.description}
        </p>
      </div>

      {/* Technology Tags */}
      <div className="flex items-center gap-1.5 flex-wrap text-[12px] font-mono">
        {hackathon.technologies.map((tech, i) => (
          <span key={i} className="px-3 py-1 rounded-full bg-[#F3F4EF] dark:bg-[#1A2336] border border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold">
            #{tech}
          </span>
        ))}
        <span className="px-3 py-1 rounded-full bg-[#FFF1EE] dark:bg-[#FF5A36]/20 border border-[#FF5A36] text-[#FF5A36] font-extrabold">
          {hackathon.mode.toUpperCase()}
        </span>
      </div>

      {/* Key Highlights (static listing reasons — not personalized) */}
      {hackathon.suitableReasons.length > 0 && (
      <div className="bg-[#F8F9F4] dark:bg-[#1A2336] border border-[#1C1B18] dark:border-[#D6DCE5] rounded-2xl p-3.5 space-y-2 text-sm">
        <div className="flex items-center gap-1.5 text-[12px] font-extrabold text-[#FF5A36] font-mono uppercase tracking-wide">
          <Sparkles className="w-3.5 h-3.5 text-[#FF5A36]" />
          Key highlights
        </div>
        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-[#1C1B18] dark:text-[#F8FAF9] font-bold">
          {hackathon.suitableReasons.slice(0, 4).map((reason, idx) => (
            <li key={idx} className="flex items-start gap-1.5 text-[12px] sm:text-[13px]">
              <CheckCircle2 className="w-3.5 h-3.5 text-[#059669] dark:text-[#34D399] shrink-0 mt-0.5" />
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      </div>
      )}

      {/* D1: Urgency countdown badge + D3/D4: Calendar buttons */}
      <div className="pt-3 border-t border-[#D6D5CF] dark:border-slate-800 flex items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2">
          {deadlineInfo && (
            <span className={`urgency-badge urgency-${deadlineInfo.urgency}`}>
              <Clock className="w-3.5 h-3.5" />
              {deadlineInfo.label}
            </span>
          )}
          {/* D3 & D4: Calendar export buttons (only when still open) */}
          {deadlineInfo && deadlineInfo.urgency !== 'closed' && (
            <>
              <button
                onClick={(e) => { e.stopPropagation(); downloadICS([hackathonRegDeadlineEvent(hackathon)]); }}
                className="btn-calendar btn-calendar-ics"
                title="Download .ics calendar file"
              >
                <Calendar className="w-3.5 h-3.5" />
                <span>.ics</span>
              </button>
              <a
                href={buildGoogleCalendarUrl(hackathonRegDeadlineEvent(hackathon))}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="btn-calendar btn-calendar-google"
                title="Add to Google Calendar"
              >
                <Calendar className="w-3.5 h-3.5" />
                <span>GCal</span>
              </a>
            </>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          
          {/* Compare Toggle */}
          <button
            onClick={() => onToggleCompare(hackathon)}
            className={`px-3.5 py-1.5 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[12px] font-extrabold transition-all ${
              isCompared
                ? 'bg-[#1C1B18] text-white dark:bg-white dark:text-[#1C1B18]'
                : 'bg-white dark:bg-[#1A2336] text-[#1C1B18] dark:text-white hover:bg-[#1C1B18] hover:text-white'
            }`}
          >
            {isCompared ? '✓ Comparing' : '+ Compare'}
          </button>

          {/* Bookmark */}
          <button
            onClick={() => onToggleBookmark(hackathon.id)}
            className={`p-2 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] transition-all font-bold ${
              hackathon.bookmarked
                ? 'bg-[#FF5A36] text-white'
                : 'bg-white dark:bg-[#1A2336] text-[#1C1B18] dark:text-white hover:bg-[#FF5A36] hover:text-white'
            }`}
          >
            <Bookmark className="w-4 h-4" />
          </button>

          {/* Download MD */}
          <button
            onClick={(e) => handleDownloadMD(e, hackathon)}
            title="Download Context for AI Agent (.md)"
            className="p-2 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] transition-all font-bold bg-white dark:bg-[#1A2336] text-[#1C1B18] dark:text-white hover:bg-[#1C1B18] hover:text-white"
          >
            <Download className="w-4 h-4" />
          </button>

          {/* View Details */}
          <button
            onClick={() => onSelect(hackathon)}
            className="btn-sharetopus-primary text-xs py-2 px-4 font-extrabold"
          >
            <span>Audit & Detail</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        </div>

      </div>

    </div>
  );
});
