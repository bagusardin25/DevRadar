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
  ExternalLink,
} from 'lucide-react';
import type { Hackathon } from '../types';
import { formatPrizePool } from '../utils/formatPrize';
import { getDeadlineInfo } from '../utils/countdown';
import { downloadICS, buildGoogleCalendarUrl, hackathonRegDeadlineEvent } from '../utils/calendar';
import { compactDescription, dedupeHighlights } from '../utils/cardSummary';
import { formatAppDateTime } from '../utils/dateTime';
import { ListingBadges } from './ListingBadges';

/** Cards trade completeness for scannability; the modal carries the full lists. */
const MAX_CARD_TAGS = 3;
const MAX_CARD_HIGHLIGHTS = 2;

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

  // The prize, mode and deadline get dedicated slots on the card, so strip them
  // back out of the prose that would otherwise repeat them.
  const description = compactDescription(hackathon.description, hackathon.prizeLabel);
  const highlights = dedupeHighlights(hackathon.suitableReasons, {
    description: hackathon.description,
    prizeLabel: hackathon.prizeLabel,
    mode: hackathon.mode,
  }).slice(0, MAX_CARD_HIGHLIGHTS);
  const visibleTags = hackathon.technologies.slice(0, MAX_CARD_TAGS);
  const hiddenTagCount = hackathon.technologies.length - visibleTags.length;

  const handleDownloadMD = (e: React.MouseEvent, hackathon: Hackathon) => {
    e.stopPropagation();
    const dateOptions: Intl.DateTimeFormatOptions = {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZoneName: 'short',
    };
    const mdContent = `# ${hackathon.title}\n\n**Organizer:** ${hackathon.organizer}\n**Prize Pool:** ${formatPrizePool(hackathon)}\n**Registration Deadline:** ${formatAppDateTime(hackathon.registrationDeadline, dateOptions)}\n**Submission Deadline:** ${formatAppDateTime(hackathon.submissionDeadline, dateOptions)}\n\n## Description\n${hackathon.description}\n\n## Technologies\n${hackathon.technologies.join(', ')}\n\n## Official Link\n[${hackathon.officialUrl}](${hackathon.officialUrl})\n\n## Verification\n**Status:** ${hackathon.verificationStatus}\n**Confidence:** ${Math.round((hackathon.confidenceScore ?? 0) * 100)}%\n**Last checked:** ${hackathon.audit?.lastCheckedAt ? formatAppDateTime(hackathon.audit.lastCheckedAt, dateOptions) : 'Unknown'}\n\n> Always confirm details on the official page before relying on them.\n`;
    
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
            <Trophy className="w-5 h-5 text-[#C2410C] dark:text-[#FF8A6B]" />
          </div>

          <div className="min-w-0 space-y-2">
            {/* Status comes from the same source as the grid card. The row used
                to hard-code a VERIFIED pill, which claimed verification for
                listings the pipeline had never verified. */}
            <div className="flex items-center gap-1.5 flex-wrap text-xs font-sans">
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
              <span className="inline-flex items-center gap-1.5 font-mono text-[12px] bg-[#F3F4EF] dark:bg-[#1A2336] px-3 py-1 rounded-full border border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold shrink-0">
                <ShieldCheck className="w-3.5 h-3.5 text-[#1C1B18] dark:text-[#F8FAF9]" />
                <span>{Math.round(hackathon.confidenceScore * 100)}%</span>
              </span>
            </div>

            <div className="min-w-0">
              <span className="block text-[12px] text-[#4A4845] dark:text-[#CBD5E1] font-semibold uppercase tracking-wider truncate">{hackathon.organizer}</span>
              {/* The heading carries the click target, so the button inside it
                  is what makes the title reachable by keyboard as well. */}
              <h3 className="text-base lg:text-lg font-extrabold tracking-tight">
                <button
                  type="button"
                  onClick={() => onSelect(hackathon)}
                  className="text-left w-full text-[#1C1B18] dark:text-white hover:text-[#C2410C] dark:hover:text-[#FF8A6B] cursor-pointer transition-colors line-clamp-2 lg:line-clamp-1 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#C2410C] dark:focus-visible:outline-[#FF8A6B] rounded-sm"
                >
                  {hackathon.title}
                </button>
              </h3>
            </div>

            {/* Scan strip + tags share a wrapping row here; separate rows in the
                grid card only because the card is narrow. */}
            <div className="flex items-center gap-1.5 flex-wrap text-[12px] font-mono">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#F8F9F4] dark:bg-[#1A2336] border border-[#1C1B18] dark:border-[#D6DCE5] text-[#047857] dark:text-[#34D399] font-extrabold">
                <Trophy className="w-3.5 h-3.5 text-[#C2410C] dark:text-[#FF8A6B] shrink-0" />
                {formatPrizePool(hackathon, { compact: true })}
              </span>
              <span className="px-3 py-1 rounded-full bg-[#FFF1EE] dark:bg-[#FF5A36]/20 border border-[#FF5A36] text-[#C2410C] dark:text-[#FF8A6B] font-bold">
                {hackathon.mode.toUpperCase()}
              </span>
              {deadlineInfo && (
                <span className={`urgency-badge urgency-${deadlineInfo.urgency}`}>
                  <Clock className="w-3.5 h-3.5" />
                  <span>{deadlineInfo.shortLabel}</span>
                </span>
              )}
              {visibleTags.map((tech) => (
                <span key={tech} className="px-3 py-1 rounded-full bg-[#F3F4EF] dark:bg-[#1A2336] border border-[#D6D5CF] dark:border-slate-700 text-[#4A4845] dark:text-[#CBD5E1] font-medium">
                  #{tech}
                </span>
              ))}
              {hiddenTagCount > 0 && (
                <span
                  className="px-1.5 py-1 text-[#736F66] dark:text-[#94A3B8] font-medium"
                  title={hackathon.technologies.join(', ')}
                >
                  +{hiddenTagCount} more
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Same actions and same order as the grid card; wraps so the primary
            button can never overflow the row. */}
        <div className="flex items-center gap-2 flex-wrap lg:justify-end lg:shrink-0">
          <button
            onClick={() => onToggleCompare(hackathon)}
            className={`px-3.5 py-1.5 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[12px] font-bold transition-all ${
              isCompared
                ? 'bg-[#1C1B18] text-white dark:bg-white dark:text-[#1C1B18]'
                : 'bg-white dark:bg-[#1A2336] text-[#1C1B18] dark:text-white hover:bg-[#1C1B18] hover:text-white'
            }`}
          >
            {isCompared ? '✓ Comparing' : '+ Compare'}
          </button>

          <button
            onClick={() => onToggleBookmark(hackathon.id)}
            aria-pressed={hackathon.bookmarked}
            aria-label={hackathon.bookmarked ? `Remove bookmark for ${hackathon.title}` : `Bookmark ${hackathon.title}`}
            title={hackathon.bookmarked ? 'Remove bookmark' : 'Bookmark'}
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
            aria-label={`Download AI agent context for ${hackathon.title} (.md)`}
            title="Download Context for AI Agent (.md)"
            className="p-2 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] transition-all font-bold bg-white dark:bg-[#1A2336] text-[#1C1B18] dark:text-white hover:bg-[#1C1B18] hover:text-white"
          >
            <Download className="w-4 h-4" />
          </button>

          <button
            onClick={() => onSelect(hackathon)}
            className="btn-sharetopus-secondary text-xs py-2 px-4 font-bold"
          >
            <span>Details</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>

          <a
            href={hackathon.officialUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-sharetopus-primary text-xs py-2 px-4 font-bold"
          >
            <span>Official site</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>
    );
  }

  return (
    // @container: the action row adapts to the card's own width, which in a
    // 3-column grid is narrow even on a wide viewport — so media queries would
    // measure the wrong thing.
    <div className="@container sharetopus-card p-6 rounded-[24px] bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] hover:shadow-[6px_6px_0_0_#1C1B18] dark:hover:shadow-[6px_6px_0_0_#D6DCE5] flex flex-col justify-between gap-4 relative overflow-hidden transition-all duration-300">
      
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

      {/* Main Info — the title owns the full card width. Anything laid out
          beside it wins the space fight and truncates the listing name, which
          is the one field a reader cannot afford to lose. */}
      <div className="space-y-3">
        <div className="min-w-0">
          <span className="text-[12px] text-[#4A4845] dark:text-[#CBD5E1] font-semibold uppercase tracking-wider">{hackathon.organizer}</span>
          {/* The heading carries the click target, so the button inside it is
              what makes the title reachable by keyboard as well as mouse. */}
          <h3 className="text-lg sm:text-xl font-extrabold tracking-tight">
            <button
              type="button"
              onClick={() => onSelect(hackathon)}
              className="text-left w-full text-[#1C1B18] dark:text-white hover:text-[#C2410C] dark:hover:text-[#FF8A6B] cursor-pointer transition-colors line-clamp-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#C2410C] dark:focus-visible:outline-[#FF8A6B] rounded-sm"
            >
              {hackathon.title}
            </button>
          </h3>
        </div>

        {/* Scan strip — prize, mode and deadline: the three facts that decide
            whether the reader keeps going. */}
        <div className="flex items-center gap-2 flex-wrap text-[12px] font-mono">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#F8F9F4] dark:bg-[#1A2336] border border-[#1C1B18] dark:border-[#D6DCE5] text-[#047857] dark:text-[#34D399] font-extrabold">
            <Trophy className="w-3.5 h-3.5 text-[#C2410C] dark:text-[#FF8A6B] shrink-0" />
            {formatPrizePool(hackathon, { compact: true })}
          </span>
          <span className="px-3 py-1 rounded-full bg-[#FFF1EE] dark:bg-[#FF5A36]/20 border border-[#FF5A36] text-[#C2410C] dark:text-[#FF8A6B] font-bold">
            {hackathon.mode.toUpperCase()}
          </span>
          {deadlineInfo && (
            <span className={`urgency-badge urgency-${deadlineInfo.urgency}`}>
              <Clock className="w-3.5 h-3.5" />
              {deadlineInfo.label}
            </span>
          )}
        </div>

        <p className="text-[13px] sm:text-sm text-[#4A4845] dark:text-[#CBD5E1] line-clamp-2 leading-relaxed">
          {description}
        </p>
      </div>

      {/* Technology Tags — capped, and lighter-bordered than the card itself so
          they read as secondary rather than competing with the title. */}
      {visibleTags.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap text-[12px] font-mono">
          {visibleTags.map((tech) => (
            <span key={tech} className="px-3 py-1 rounded-full bg-[#F3F4EF] dark:bg-[#1A2336] border border-[#D6D5CF] dark:border-slate-700 text-[#4A4845] dark:text-[#CBD5E1] font-medium">
              #{tech}
            </span>
          ))}
          {hiddenTagCount > 0 && (
            <span
              className="px-1.5 py-1 text-[#736F66] dark:text-[#94A3B8] font-medium"
              title={hackathon.technologies.join(', ')}
            >
              +{hiddenTagCount} more
            </span>
          )}
        </div>
      )}

      {/* Key Highlights (static listing reasons — not personalized) */}
      {highlights.length > 0 && (
      <div className="bg-[#F8F9F4] dark:bg-[#1A2336] border border-[#D6D5CF] dark:border-slate-700 rounded-2xl p-3.5 space-y-2">
        <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[#736F66] dark:text-[#94A3B8] font-mono uppercase tracking-wide">
          <Sparkles className="w-3.5 h-3.5" />
          Key highlights
        </div>
        <ul className="space-y-1.5 text-[#1C1B18] dark:text-[#F8FAF9]">
          {highlights.map((reason, idx) => (
            <li key={idx} className="flex items-start gap-1.5 text-[12px] sm:text-[13px]">
              <CheckCircle2 className="w-3.5 h-3.5 text-[#047857] dark:text-[#34D399] shrink-0 mt-0.5" />
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      </div>
      )}

      {/* D3/D4: Calendar buttons + actions. The row wraps: without it the
          "Audit & Detail" button overflowed the card and got clipped by the
          card's own overflow-hidden. */}
      <div className="pt-3 border-t border-[#D6D5CF] dark:border-slate-800 flex items-center justify-between gap-x-3 gap-y-2 flex-wrap text-xs">
        {/* Hidden on narrow cards to keep the actions on one line; the detail
            modal offers the same exports (plus submit/all-dates variants). */}
        <div className="hidden @[26rem]:flex items-center gap-2">
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
        <div className="flex items-center gap-2 ml-auto flex-wrap justify-end">

          {/* Compare Toggle */}
          <button
            onClick={() => onToggleCompare(hackathon)}
            className={`px-3.5 py-1.5 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[12px] font-bold transition-all ${
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
            aria-pressed={hackathon.bookmarked}
            aria-label={hackathon.bookmarked ? `Remove bookmark for ${hackathon.title}` : `Bookmark ${hackathon.title}`}
            title={hackathon.bookmarked ? 'Remove bookmark' : 'Bookmark'}
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
            aria-label={`Download AI agent context for ${hackathon.title} (.md)`}
            title="Download Context for AI Agent (.md)"
            className="p-2 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] transition-all font-bold bg-white dark:bg-[#1A2336] text-[#1C1B18] dark:text-white hover:bg-[#1C1B18] hover:text-white"
          >
            <Download className="w-4 h-4" />
          </button>

          {/* View Details */}
          <button
            onClick={() => onSelect(hackathon)}
            className="btn-sharetopus-secondary text-xs py-2 px-4 font-bold"
          >
            <span>Details</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>

          <a
            href={hackathon.officialUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-sharetopus-primary text-xs py-2 px-4 font-bold"
          >
            <span>Official site</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>

      </div>

    </div>
  );
});
