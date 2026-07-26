import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  X,
  ExternalLink,
  Calendar,
  Clock,
  Trophy,
  Users,
  Layers,
  Sparkles,
  CheckCircle2,
  Copy,
  Check,
  Bot,
  Terminal,
  ChevronDown,
  ChevronRight,
  FileText,
  Lightbulb,
  Rocket,
  Workflow,
  Flag,
  AlertTriangle,
  ShieldCheck,
  ArrowRight,
  Wallet,
} from 'lucide-react';
import type { Hackathon, AIDeal, VerificationAudit } from '../types';
import { buildReportIssueUrl } from '../utils/reportIssue';
import { formatPrizePool } from '../utils/formatPrize';
import { getDeadlineInfo } from '../utils/countdown';
import {
  downloadICS,
  buildGoogleCalendarUrl,
  hackathonRegDeadlineEvent,
  hackathonSubDeadlineEvent,
} from '../utils/calendar';
import { generateAIPrompt, getPromptMeta, isHackathonItem } from '../utils/aiPrompt';
import type { PromptSectionIcon } from '../utils/aiPrompt';
import { DEDUPE_THRESHOLD, compactDescription, dedupeHighlights } from '../utils/cardSummary';
import { useModalA11y } from '../hooks/useModalA11y';

/** Icon per prompt-section slot, keyed by the meta's semantic icon name. */
const PROMPT_SECTION_ICON: Record<PromptSectionIcon, React.ReactNode> = {
  brief: <FileText className="w-3.5 h-3.5 text-[#0369A1] dark:text-[#38BDF8] shrink-0" />,
  ideas: <Lightbulb className="w-3.5 h-3.5 text-[#C2410C] dark:text-[#FF8A6B] shrink-0" />,
  build: <Workflow className="w-3.5 h-3.5 text-[#6D28D9] dark:text-[#C4B5FD] shrink-0" />,
  timeline: <Calendar className="w-3.5 h-3.5 text-[#047857] dark:text-[#34D399] shrink-0" />,
  cost: <Wallet className="w-3.5 h-3.5 text-[#047857] dark:text-[#34D399] shrink-0" />,
};

interface DetailModalProps {
  item: Hackathon | AIDeal | null;
  onClose: () => void;
}

type DetailTab = 'overview' | 'audit' | 'prompt' | 'claim';

/**
 * Mirrors `MAX_*` in backend/app/ingestion/scoring.py. The maxima sum to 100,
 * which is what makes the scorecard total meaningful — keep the two in step.
 */
const SCORE_COMPONENTS = [
  { key: 'statusAndDeadline', label: 'Status & Deadline Active', max: 35, textClass: 'text-[#047857] dark:text-[#34D399]', barClass: 'bg-[#059669]' },
  { key: 'keywordMatch', label: 'Keyword & Developer Relevance', max: 25, textClass: 'text-[#0369A1] dark:text-[#38BDF8]', barClass: 'bg-[#0284C7]' },
  { key: 'sourceCredibility', label: 'Source Tier Credibility', max: 20, textClass: 'text-[#6D28D9] dark:text-[#C4B5FD]', barClass: 'bg-[#7C3AED]' },
  { key: 'freshness', label: 'Data Freshness', max: 15, textClass: 'text-[#C2410C] dark:text-[#FF8A6B]', barClass: 'bg-[#FF5A36]' },
  { key: 'completeness', label: 'Field Completeness', max: 5, textClass: 'text-[#B45309] dark:text-[#FBBF24]', barClass: 'bg-[#D97706]' },
] as const satisfies ReadonlyArray<{
  key: keyof VerificationAudit['scoreBreakdown'];
  label: string;
  max: number;
  textClass: string;
  barClass: string;
}>;

export const DetailModal: React.FC<DetailModalProps> = ({ item, onClose }) => {
  // Called before the `!item` early return below — hooks must run every render.
  const dialogRef = useModalA11y<HTMLDivElement>(!!item, onClose);
  const [activeTab, setActiveTab] = useState<DetailTab>('overview');
  const [copiedPrompt, setCopiedPrompt] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);
  const [showRawJson, setShowRawJson] = useState(false);

  // Reset tab-local UI when switching listings
  useEffect(() => {
    setActiveTab('overview');
    setCopiedPrompt(false);
    setCopyError(null);
    setShowRawJson(false);
  }, [item?.id]);

  const isHackathon = item ? isHackathonItem(item) : false;
  const hackathon = item && isHackathon ? (item as Hackathon) : null;
  const deal = item && !isHackathon ? (item as AIDeal) : null;

  const promptText = useMemo(
    () => (item ? generateAIPrompt(item) : ''),
    [item],
  );
  // Label, blurb and chips travel with the prompt itself, so a hackathon's
  // framing can never end up describing a deal's prompt.
  const promptMeta = useMemo(
    () => (item ? getPromptMeta(item) : null),
    [item],
  );

  const reportUrl = useMemo(
    () => (item ? buildReportIssueUrl(item) : null),
    [item],
  );

  // The prize/offer value has its own stat box above, so strip the sentence that
  // merely restates it. Unlike the cards, nothing is capped here — this is the
  // full-detail view, so only true restatements are dropped.
  const rewardLabel = hackathon ? hackathon.prizeLabel : (deal?.offerValue ?? '');
  const description = useMemo(
    () => compactDescription(item?.description ?? '', rewardLabel),
    [item?.description, rewardLabel],
  );
  const highlights = useMemo(
    () =>
      dedupeHighlights(
        item?.suitableReasons ?? [],
        {
          description: item?.description,
          prizeLabel: rewardLabel,
          mode: hackathon?.mode,
        },
        DEDUPE_THRESHOLD.detail,
      ),
    [item, rewardLabel, hackathon?.mode],
  );

  const scoreRows = useMemo(
    () =>
      SCORE_COMPONENTS.map((c) => ({
        ...c,
        value: item?.audit.scoreBreakdown[c.key] ?? 0,
      })),
    [item],
  );
  const scoreTotal = useMemo(
    () => scoreRows.reduce((sum, row) => sum + row.value, 0),
    [scoreRows],
  );
  // Allow a point of rounding slack; anything wider means the stored confidence
  // and the breakdown came from different places.
  const scoreMismatch =
    item != null && Math.abs(Math.round(item.confidenceScore * 100) - scoreTotal) > 1;

  const handleCopyPrompt = useCallback(async () => {
    if (!promptText) return;
    setCopyError(null);
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(promptText);
      } else {
        // Fallback for older browsers / non-secure contexts
        const ta = document.createElement('textarea');
        ta.value = promptText;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }
      setCopiedPrompt(true);
      window.setTimeout(() => setCopiedPrompt(false), 2000);
    } catch {
      setCopyError('Could not copy — select the text manually.');
    }
  }, [promptText]);

  if (!item) return null;

  // D1: Compute urgency info for deadlines
  const regDeadlineInfo = hackathon ? getDeadlineInfo(hackathon.registrationDeadline) : null;
  const subDeadlineInfo = hackathon
    ? getDeadlineInfo(hackathon.submissionDeadline, 'Submission closed')
    : null;
  const dealExpiresInfo = deal?.expiresAt ? getDeadlineInfo(deal.expiresAt, 'Expired') : null;

  const tabBtn = (tab: DetailTab, label: React.ReactNode) => (
    <button
      type="button"
      onClick={() => setActiveTab(tab)}
      className={`py-3 sm:py-3.5 border-b-2 transition-all whitespace-nowrap px-1 flex items-center gap-1.5 ${
        activeTab === tab
          ? 'border-[#FF5A36] text-[#C2410C] dark:text-[#FF8A6B] font-extrabold'
          : 'border-transparent text-[#4A4845] dark:text-[#B8C4D2] hover:text-[#C2410C] dark:hover:text-[#FF8A6B] font-semibold'
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/65 overflow-y-auto font-sans">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="detail-modal-title"
        className="sharetopus-card w-full max-w-4xl rounded-t-[28px] sm:rounded-[28px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[8px_8px_0_0_#1C1B18] dark:shadow-[8px_8px_0_0_#D6DCE5] overflow-hidden my-0 sm:my-8 max-h-[95vh] flex flex-col"
      >
        
        {/* Modal Header */}
        <div className="flex items-start sm:items-center justify-between gap-3 p-4 sm:p-6 border-b border-[#D6D5CF] dark:border-slate-800 bg-[#F8F9F4] dark:bg-[#1A2336] shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className={`p-2.5 sm:p-3 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shrink-0 ${isHackathon ? 'bg-[#FF5A36]/15 text-[#FF5A36]' : 'bg-[#7C3AED]/15 text-[#7C3AED]'}`}>
              {isHackathon ? <Trophy className="w-5 h-5 sm:w-6 sm:h-6" /> : <Sparkles className="w-5 h-5 sm:w-6 sm:h-6" />}
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[12px] font-mono font-semibold text-[#4A4845] dark:text-[#D6DCE5]">{isHackathon ? hackathon?.organizer : deal?.provider}</span>
                <span className="px-2.5 py-0.5 rounded-full bg-[#059669]/15 text-[#065F46] dark:text-[#34D399] border border-[#059669] text-[12px] font-semibold">
                  {item.verificationStatus.replace(/_/g, ' ').toUpperCase()}
                </span>
                {dealExpiresInfo && (
                  <span className={`urgency-badge urgency-${dealExpiresInfo.urgency}`}>
                    <Clock className="w-3.5 h-3.5" />
                    <span>{dealExpiresInfo.label}</span>
                  </span>
                )}
              </div>
              <h2 id="detail-modal-title" className="text-lg sm:text-xl font-extrabold text-[#1C1B18] dark:text-white tracking-tight leading-snug">
                {isHackathon ? hackathon?.title : deal?.productName}
              </h2>
            </div>
          </div>

          <button 
            onClick={onClose}
            className="p-2 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-white hover:bg-[#FF5A36] hover:text-white transition-all font-bold shrink-0"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation. Hackathons keep the "AI Agent Prompt" tab because
            the brainstorm/execution prompt is the useful angle there. Deals
            get a "How to Claim" tab instead — for a free-credits offer, what
            a reader actually wants is who qualifies, when it expires, and the
            claim link — not another AI-generated build plan. */}
        <div className="flex items-center gap-1 sm:gap-4 px-3 sm:px-6 border-b border-[#D6D5CF] dark:border-slate-800 bg-[#F3F4EF] dark:bg-[#131A29] text-[12px] sm:text-sm font-mono overflow-x-auto no-scrollbar shrink-0">
          {tabBtn('overview', 'Overview')}
          {tabBtn('audit', 'Provenance')}
          {isHackathon
            ? tabBtn(
                'prompt',
                <>
                  <Bot className="w-3.5 h-3.5 text-[#FF5A36]" />
                  <span>{promptMeta?.tabLabel}</span>
                  <span className="px-1.5 py-0.5 rounded-full bg-[#FF5A36]/15 text-[#9A3412] dark:text-[#FF8A6B] text-[10px] font-mono font-bold border border-[#FF5A36]">
                    NEW
                  </span>
                </>,
              )
            : tabBtn(
                'claim',
                <>
                  <ExternalLink className="w-3.5 h-3.5 text-[#7C3AED] dark:text-[#C4B5FD]" />
                  <span>How to Claim</span>
                </>,
              )}
        </div>

        {/* Modal Body Content. Body text stays at normal weight; emphasis is
            added explicitly below, so the eye has something to land on. */}
        <div className="p-4 sm:p-6 space-y-6 overflow-y-auto text-[#1C1B18] dark:text-white flex-1">
          
          {/* TAB 1: OVERVIEW */}
          {activeTab === 'overview' && (
            <div className="space-y-6 text-sm">
              
              {/* Summary Stats Grid — facts about the opportunity itself.
                  Confidence lives below instead: it describes how much DevRadar
                  trusts its own record, not anything about the hackathon, so it
                  should not compete with prize and deadline for attention. */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 font-mono">
                <div className="sharetopus-card p-3.5 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
                  <div className="text-[12px] text-[#4A4845] dark:text-[#B8C4D2] font-semibold">VALUE / REWARD</div>
                  <div className="text-base sm:text-lg font-extrabold text-[#047857] dark:text-[#34D399] leading-snug break-words">
                    {isHackathon && hackathon
                      ? formatPrizePool(hackathon)
                      : !isHackathon
                        ? deal?.offerValue
                        : '—'}
                  </div>
                </div>

                <div className="sharetopus-card p-3.5 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
                  <div className="text-[12px] text-[#4A4845] dark:text-[#B8C4D2] font-semibold">MODE / TYPE</div>
                  <div className="text-sm font-bold text-[#C2410C] dark:text-[#FF8A6B]">
                    {isHackathon ? hackathon?.mode.toUpperCase() : deal?.offerType.replace(/_/g, ' ').toUpperCase()}
                  </div>
                </div>

                <div className="sharetopus-card p-3.5 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
                  <div className="text-[12px] text-[#4A4845] dark:text-[#B8C4D2] font-semibold">LAST CHECKED</div>
                  <div className="text-[12px] sm:text-sm font-bold text-[#1C1B18] dark:text-white">
                    {new Date(item.lastCheckedAt).toLocaleString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </div>
                </div>
              </div>

              {/* Data-quality note, demoted out of the stat row but still one
                  click from the breakdown that justifies the number. */}
              <button
                type="button"
                onClick={() => setActiveTab('audit')}
                className="flex items-center gap-1.5 text-[12px] font-mono text-[#4A4845] dark:text-[#B8C4D2] hover:text-[#C2410C] dark:hover:text-[#FF8A6B] transition-colors"
              >
                <ShieldCheck className="w-3.5 h-3.5 shrink-0" />
                <span>
                  DevRadar confidence{' '}
                  <strong className="font-bold">{Math.round(item.confidenceScore * 100)}/100</strong>
                  {' '}· see how this was scored
                </span>
                <ArrowRight className="w-3.5 h-3.5 shrink-0" />
              </button>

              {/* Description */}
              <div className="space-y-2">
                <h4 className="font-bold text-[#1C1B18] dark:text-white text-base">Description</h4>
                <p className="text-[13px] sm:text-sm text-[#4A4845] dark:text-[#CBD5E1] leading-relaxed">{description}</p>
              </div>

              {/* Key Highlights — not personalized matching */}
              {highlights.length > 0 && (
              <div className="sharetopus-card p-4 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-[#F8F9F4] dark:bg-[#1A2336] space-y-2">
                <div className="flex items-center gap-2 font-semibold text-[#736F66] dark:text-[#94A3B8] text-[11px] font-mono uppercase tracking-wide">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Key highlights</span>
                </div>
                <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[13px] text-[#1C1B18] dark:text-[#E8ECF1]">
                  {highlights.map((reason, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-[#047857] dark:text-[#34D399] shrink-0 mt-0.5" />
                      <span>{reason}</span>
                    </li>
                  ))}
                </ul>
              </div>
              )}

              {/* Specific Metadata for Hackathon */}
              {isHackathon && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div className="sharetopus-card p-4 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] space-y-2">
                    <h5 className="font-bold text-[#1C1B18] dark:text-white text-sm flex items-center gap-2">
                      <Calendar className="w-4 h-4 text-[#0369A1] dark:text-[#38BDF8]" />
                      Key Dates &amp; Deadlines
                    </h5>
                    {/* Labels stay at normal weight so the dates beside them
                        are what the eye picks up. */}
                    <div className="space-y-2 text-[#4A4845] dark:text-[#CBD5E1]">
                      <div>Registration Opens: <strong className="text-[#1C1B18] dark:text-white font-bold">{new Date(hackathon!.registrationOpenAt).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })}</strong></div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span>Registration Deadline:</span>
                        <strong className="text-[#047857] dark:text-[#34D399] font-bold">{new Date(hackathon!.registrationDeadline).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })}</strong>
                        {regDeadlineInfo && (
                          <span className={`urgency-badge urgency-${regDeadlineInfo.urgency}`}>
                            <Clock className="w-3.5 h-3.5" />
                            <span>{regDeadlineInfo.label}</span>
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span>Submission Deadline:</span>
                        <strong className="text-[#C2410C] dark:text-[#FF8A6B] font-bold">{new Date(hackathon!.submissionDeadline).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })}</strong>
                        {subDeadlineInfo && (
                          <span className={`urgency-badge urgency-${subDeadlineInfo.urgency}`}>
                            <Clock className="w-3.5 h-3.5" />
                            <span>{subDeadlineInfo.label}</span>
                          </span>
                        )}
                      </div>
                    </div>

                    {/* D3 & D4: Calendar export buttons */}
                    <div className="pt-3 mt-2 border-t border-[#D6D5CF] dark:border-slate-700 space-y-2">
                      <div className="text-[11px] font-mono font-semibold text-[#736F66] dark:text-[#94A3B8] uppercase tracking-wide flex items-center gap-1.5">
                        <Calendar className="w-3.5 h-3.5" />
                        <span>Add to Calendar</span>
                      </div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <button
                          onClick={() => downloadICS([hackathonRegDeadlineEvent(hackathon!)])}
                          className="btn-calendar btn-calendar-ics"
                        >
                          <FileText className="w-3.5 h-3.5" />
                          <span>.ics (Reg)</span>
                        </button>
                        <button
                          onClick={() => downloadICS([hackathonSubDeadlineEvent(hackathon!)])}
                          className="btn-calendar btn-calendar-ics"
                        >
                          <Rocket className="w-3.5 h-3.5" />
                          <span>.ics (Submit)</span>
                        </button>
                        <button
                          onClick={() => downloadICS([hackathonRegDeadlineEvent(hackathon!), hackathonSubDeadlineEvent(hackathon!)])}
                          className="btn-calendar btn-calendar-ics"
                        >
                          <Calendar className="w-3.5 h-3.5" />
                          <span>.ics (All)</span>
                        </button>
                        <a
                          href={buildGoogleCalendarUrl(hackathonRegDeadlineEvent(hackathon!))}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn-calendar btn-calendar-google"
                        >
                          <Calendar className="w-3.5 h-3.5" />
                          <span>GCal (Reg)</span>
                        </a>
                        <a
                          href={buildGoogleCalendarUrl(hackathonSubDeadlineEvent(hackathon!))}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn-calendar btn-calendar-google"
                        >
                          <Rocket className="w-3.5 h-3.5" />
                          <span>GCal (Submit)</span>
                        </a>
                      </div>
                    </div>
                  </div>

                  <div className="sharetopus-card p-4 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] space-y-2">
                    <h5 className="font-bold text-[#1C1B18] dark:text-white text-sm flex items-center gap-2">
                      <Users className="w-4 h-4 text-[#6D28D9] dark:text-[#C4B5FD]" />
                      Eligibility &amp; Team Constraints
                    </h5>
                    <div className="space-y-1 text-[#4A4845] dark:text-[#CBD5E1]">
                      <div>Team Size: <strong className="text-[#1C1B18] dark:text-white font-bold">{hackathon!.teamMin} - {hackathon!.teamMax} members</strong></div>
                      <div>Eligible Roles: <strong className="text-[#1C1B18] dark:text-white font-bold">{hackathon!.eligibility.join(', ')}</strong></div>
                      <div>Region Restriction: <strong className="text-[#1C1B18] dark:text-white font-bold">{hackathon!.eligibleCountries.join(', ')}</strong></div>
                    </div>
                  </div>
                </div>
              )}

              {/* Technologies */}
              <div className="space-y-2">
                <h4 className="font-semibold text-[#736F66] dark:text-[#94A3B8] text-[11px] font-mono uppercase tracking-wide">Supported stack &amp; tags</h4>
                <div className="flex items-center gap-2 flex-wrap text-xs font-mono">
                  {(isHackathon ? hackathon!.technologies : deal!.tags).map((t, i) => (
                    <span key={i} className="px-3 py-1 rounded-full bg-[#F3F4EF] dark:bg-[#1A2336] border border-[#D6D5CF] dark:border-slate-700 text-[#4A4845] dark:text-[#CBD5E1] font-medium">
                      #{t}
                    </span>
                  ))}
                </div>
              </div>

            </div>
          )}

          {/* TAB 2: PROVENANCE (technical — secondary) */}
          {activeTab === 'audit' && (
            <div className="space-y-6 text-sm font-sans">
              <p className="text-[13px] text-[#4A4845] dark:text-[#B8C4D2]">
                Optional technical detail for operators. Most users can stay on Overview.
              </p>
              
              {/* Scorecard Visualizer */}
              <div className="sharetopus-card p-5 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-[#F8F9F4] dark:bg-[#1A2336] space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <h4 className="font-bold text-[#1C1B18] dark:text-white text-base">Verification scorecard</h4>
                    <p className="text-[#4A4845] dark:text-[#B8C4D2] text-[12px] sm:text-sm">
                      Five deterministic components, 100 points total. No LLM judgement is used.
                    </p>
                  </div>
                  <div className="text-left sm:text-right font-mono">
                    <div className="text-2xl font-extrabold text-[#C2410C] dark:text-[#FF8A6B]">{Math.round(item.confidenceScore * 100)}%</div>
                    <div className="text-[12px] text-[#4A4845] dark:text-[#B8C4D2] font-semibold">CONFIDENCE</div>
                  </div>
                </div>

                {/* Bars are driven off SCORE_COMPONENTS so every component the
                    scorer produces gets rendered. A hand-written list is what
                    let `completeness` go missing and made the card fail to add
                    up to the confidence it claimed to explain. */}
                {/* Labels read as prose; only the point figures are mono, so the
                    numbers line up in a column without the words shouting. */}
                <div className="space-y-3">
                  {scoreRows.map((row, i) => (
                    <div key={row.key}>
                      <div className="flex justify-between gap-3 text-[#4A4845] dark:text-[#CBD5E1] mb-1">
                        <span>{i + 1}. {row.label} <span className="text-[#736F66] dark:text-[#94A3B8]">(max {row.max})</span></span>
                        <span className={`${row.textClass} font-mono font-bold whitespace-nowrap`}>
                          {row.value} / {row.max} pts
                        </span>
                      </div>
                      <div className="h-2.5 bg-[#E5E6DF] dark:bg-slate-800 rounded-full border border-[#1C1B18] dark:border-[#D6DCE5] overflow-hidden">
                        <div
                          className={`h-full ${row.barClass} rounded-full`}
                          style={{ width: `${Math.min(100, (row.value / row.max) * 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}

                  {/* Explicit total, so a reader can check the bars by hand. */}
                  <div className="flex justify-between gap-3 pt-3 border-t border-[#D6D5CF] dark:border-slate-700 text-[#1C1B18] dark:text-white">
                    <span className="font-bold">Total</span>
                    <span className="font-mono font-extrabold whitespace-nowrap">{scoreTotal} / 100 pts</span>
                  </div>
                </div>

                {scoreMismatch && (
                  <p className="text-[12px] font-medium text-[#B45309] dark:text-[#FBBF24] leading-relaxed">
                    The stored confidence ({Math.round(item.confidenceScore * 100)}%) does not match the
                    sum of these components ({scoreTotal}%), so this listing was scored outside the
                    current pipeline. Trust the breakdown over the headline number.
                  </p>
                )}

              </div>

              {/* Provenance Tree */}
              <div className="space-y-3">
                <h4 className="font-bold text-[#1C1B18] dark:text-white text-sm flex items-center gap-2">
                  <Layers className="w-4 h-4 text-[#C2410C] dark:text-[#FF8A6B]" />
                  Discovery sources &amp; provenance tree
                </h4>

                <div className="space-y-2">
                  {item.discoverySources.map((source, i) => (
                    <div key={i} className="flex items-center justify-between p-3.5 rounded-2xl bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
                      <div className="flex items-center gap-3">
                        <span className="px-3 py-1 rounded-full bg-[#F3F4EF] dark:bg-[#1A2336] border border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white text-[12px] font-semibold whitespace-nowrap">
                          {source.tier}
                        </span>
                        <div className="min-w-0">
                          <div className="font-bold text-[#1C1B18] dark:text-white flex items-center gap-2 flex-wrap">
                            <span>{source.type.toUpperCase()}</span>
                          </div>
                          <div className="text-[12px] font-mono text-[#4A4845] dark:text-[#B8C4D2] truncate max-w-[min(100%,20rem)]">{source.url}</div>
                        </div>
                      </div>

                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-[#0369A1] dark:text-[#38BDF8] hover:underline font-mono text-xs font-semibold shrink-0"
                      >
                        <span>Visit source</span>
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  ))}
                </div>
              </div>

            </div>
          )}

          {/* TAB 3a: AI AGENT BRAINSTORM & EXECUTION PROMPT (hackathon only) */}
          {activeTab === 'prompt' && isHackathon && (
            <div className="space-y-4">
              <div className="sharetopus-card p-4 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2 font-bold text-[#1C1B18] dark:text-white text-sm">
                    <Bot className="w-4 h-4 text-[#C2410C] dark:text-[#FF8A6B] shrink-0" />
                    <span>{promptMeta?.title}</span>
                  </div>
                  <p className="text-[12px] text-[#4A4845] dark:text-[#B8C4D2] leading-relaxed">
                    {promptMeta?.blurb}
                  </p>
                  {copyError && (
                    <p className="text-[11px] font-semibold text-[#B91C1C] dark:text-[#F87171]">{copyError}</p>
                  )}
                </div>

                <button
                  type="button"
                  onClick={() => void handleCopyPrompt()}
                  className="btn-sharetopus-primary text-xs py-2.5 px-4 font-bold shrink-0 flex items-center justify-center gap-1.5 w-full sm:w-auto"
                  aria-label="Copy AI prompt to clipboard"
                >
                  {copiedPrompt ? (
                    <>
                      <Check className="w-4 h-4" />
                      <span>Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-4 h-4" />
                      <span>Copy AI Prompt</span>
                    </>
                  )}
                </button>
              </div>

              {/* What the prompt asks the agent to produce. Labels and icons both
                  come from the prompt's own metadata, so a deal never advertises
                  a hackathon's sections. */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono font-medium">
                {promptMeta?.sections.map((section) => (
                  <div
                    key={section.label}
                    className="sharetopus-card px-2.5 py-2 rounded-xl border-[1.5px] border-[#D6D5CF] dark:border-slate-700 bg-white dark:bg-[#090C15] flex items-center justify-center gap-1.5 text-[#4A4845] dark:text-[#CBD5E1]"
                  >
                    {PROMPT_SECTION_ICON[section.icon]}
                    <span>{section.label}</span>
                  </div>
                ))}
              </div>

              {/* Prompt preview */}
              <div className="relative">
                <pre
                  className="p-4 sm:p-5 rounded-2xl bg-[#090C15] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#34D399] dark:text-[#7DD3FC] font-mono text-[11px] sm:text-xs overflow-x-auto leading-relaxed whitespace-pre-wrap max-h-[min(50vh,420px)] select-text"
                  aria-label="Generated AI agent prompt"
                >
                  {promptText}
                </pre>
              </div>

              {/* Operator accordion — Raw JSON (secondary; not a primary tab) */}
              <div className="pt-1 border-t border-[#D6D5CF] dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowRawJson((v) => !v)}
                  className="w-full text-left text-[11px] font-mono font-semibold text-[#4A4845] dark:text-[#B8C4D2] hover:text-[#C2410C] dark:hover:text-[#FF8A6B] flex items-center gap-1.5 py-2"
                  aria-expanded={showRawJson}
                >
                  {showRawJson ? (
                    <ChevronDown className="w-3.5 h-3.5 shrink-0" />
                  ) : (
                    <ChevronRight className="w-3.5 h-3.5 shrink-0" />
                  )}
                  <Terminal className="w-3.5 h-3.5 shrink-0" />
                  <span>
                    {showRawJson
                      ? 'Operator View: Hide Raw JSON Record'
                      : 'Operator View: Show Raw JSON Record'}
                  </span>
                </button>

                {showRawJson && (
                  <div className="mt-1 space-y-2 animate-in fade-in duration-200">
                    <div className="flex items-center justify-between gap-2 text-[11px] font-mono font-semibold text-[#736F66] dark:text-[#94A3B8]">
                      <span>Normalized catalogue payload</span>
                      <span className="truncate">ID: {item.id}</span>
                    </div>
                    <pre className="p-4 rounded-2xl bg-[#090C15] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#C4B5FD] font-mono text-[11px] sm:text-xs overflow-x-auto max-h-64">
                      {JSON.stringify(item, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 3b: HOW TO CLAIM (AI deal only). Every fact here is data the
              catalogue already stores — nothing is invented. Written as an
              action checklist so a reader can decide "am I eligible?" and
              "when does this close?" without hunting through prose. */}
          {activeTab === 'claim' && deal && (
            <div className="space-y-5 text-sm">
              {/* Headline stats: eligibility summary + expiry with countdown */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 font-mono">
                <div className="sharetopus-card p-3.5 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] space-y-1">
                  <div className="text-[11px] text-[#4A4845] dark:text-[#B8C4D2] font-semibold uppercase tracking-wide">Who qualifies</div>
                  <div className="text-sm font-bold text-[#1C1B18] dark:text-white">
                    {deal.targetUsers.length > 0 ? deal.targetUsers.join(', ') : 'See official terms'}
                  </div>
                </div>
                <div className="sharetopus-card p-3.5 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] space-y-1">
                  <div className="text-[11px] text-[#4A4845] dark:text-[#B8C4D2] font-semibold uppercase tracking-wide">Expires</div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-bold text-[#C2410C] dark:text-[#FF8A6B]">
                      {deal.expiresAt
                        ? new Date(deal.expiresAt).toLocaleDateString(undefined, {
                            year: 'numeric', month: 'short', day: 'numeric',
                          })
                        : 'No fixed expiry'}
                    </span>
                    {dealExpiresInfo && (
                      <span className={`urgency-badge urgency-${dealExpiresInfo.urgency}`}>
                        <Clock className="w-3.5 h-3.5" />
                        <span>{dealExpiresInfo.label}</span>
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Numbered steps. The numbers are anchored to real data: 1 uses
                  requirements/targetUsers/regions, 2 links to the terms URL,
                  3 is the actual claim URL. Nothing generic. */}
              <ol className="space-y-3">
                {/* 1. Check eligibility */}
                <li className="sharetopus-card p-4 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-[#7C3AED]/15 text-[#6D28D9] dark:text-[#C4B5FD] border border-[#7C3AED] font-mono font-extrabold text-[12px] flex items-center justify-center shrink-0">
                      1
                    </span>
                    <h4 className="font-bold text-[#1C1B18] dark:text-white text-sm">Check you qualify</h4>
                  </div>

                  {deal.requirements.length > 0 ? (
                    <ul className="space-y-1.5 text-[13px] text-[#1C1B18] dark:text-[#E8ECF1]">
                      {deal.requirements.map((req, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                          <CheckCircle2 className="w-3.5 h-3.5 text-[#047857] dark:text-[#34D399] shrink-0 mt-0.5" />
                          <span>{req}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[12px] text-[#4A4845] dark:text-[#B8C4D2] italic">
                      No specific requirements listed by DevRadar — confirm on the official terms.
                    </p>
                  )}

                  <div className="pt-2 border-t border-[#D6D5CF] dark:border-slate-700 grid grid-cols-1 sm:grid-cols-2 gap-2 text-[12px]">
                    <div className="text-[#4A4845] dark:text-[#B8C4D2]">
                      <span className="font-semibold">Target users:</span>{' '}
                      <span className="text-[#1C1B18] dark:text-white font-bold">
                        {deal.targetUsers.length > 0 ? deal.targetUsers.join(', ') : '—'}
                      </span>
                    </div>
                    <div className="text-[#4A4845] dark:text-[#B8C4D2]">
                      <span className="font-semibold">Regions:</span>{' '}
                      <span className="text-[#1C1B18] dark:text-white font-bold">
                        {deal.supportedRegions.length > 0 ? deal.supportedRegions.join(', ') : 'See terms'}
                      </span>
                    </div>
                  </div>
                </li>

                {/* 2. Read the official terms */}
                <li className="sharetopus-card p-4 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-[#7C3AED]/15 text-[#6D28D9] dark:text-[#C4B5FD] border border-[#7C3AED] font-mono font-extrabold text-[12px] flex items-center justify-center shrink-0">
                      2
                    </span>
                    <h4 className="font-bold text-[#1C1B18] dark:text-white text-sm">Confirm the terms</h4>
                  </div>
                  <p className="text-[12px] text-[#4A4845] dark:text-[#B8C4D2]">
                    Quotas, pricing and eligibility change often — DevRadar last checked{' '}
                    <strong className="text-[#1C1B18] dark:text-white font-bold">
                      {new Date(deal.lastCheckedAt).toLocaleString(undefined, {
                        year: 'numeric', month: 'short', day: 'numeric',
                      })}
                    </strong>
                    . Read the official terms before you commit anything.
                  </p>
                  {deal.officialTermsUrl ? (
                    <a
                      href={deal.officialTermsUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#0369A1] dark:text-[#38BDF8] hover:underline font-mono break-all"
                    >
                      <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                      <span>{deal.officialTermsUrl}</span>
                    </a>
                  ) : (
                    <p className="text-[12px] text-[#B45309] dark:text-[#FBBF24] italic">
                      No terms URL on record — check the provider's site directly.
                    </p>
                  )}
                </li>

                {/* 3. Claim */}
                <li className="sharetopus-card p-4 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-[#7C3AED]/15 text-[#6D28D9] dark:text-[#C4B5FD] border border-[#7C3AED] font-mono font-extrabold text-[12px] flex items-center justify-center shrink-0">
                      3
                    </span>
                    <h4 className="font-bold text-[#1C1B18] dark:text-white text-sm">Claim the offer</h4>
                  </div>
                  <p className="text-[12px] text-[#4A4845] dark:text-[#B8C4D2]">
                    Opens {deal.provider} in a new tab. DevRadar is not affiliated with the provider
                    — you complete the claim on their site.
                  </p>
                  {deal.claimUrl && (
                    <a
                      href={deal.claimUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn-sharetopus-primary text-xs py-2 px-4 bg-[#6D28D9] hover:bg-[#5B21B6] font-bold inline-flex items-center gap-1.5"
                    >
                      <span>Claim on {deal.provider}</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  )}
                </li>
              </ol>
            </div>
          )}

        </div>

        {/* Modal Footer */}
        <div className="border-t border-[#D6D5CF] dark:border-slate-800 bg-[#F8F9F4] dark:bg-[#1A2336]">
          {/* DevRadar is an index, not the source — say so at the point of action.
              A hackathon has an organiser you register with; an AI offer has a
              provider you claim from. Using one word for both made the deal
              modal read as if it were describing a hackathon. */}
          <div className="px-6 pt-3 flex items-start gap-2 text-[11px] leading-relaxed text-[#4A4845] dark:text-[#94A3B8]">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-px text-[#D97706]" />
            <p>
              DevRadar is not affiliated with this {isHackathon ? 'organiser' : 'provider'}. Details
              can change after we last checked — confirm on the official page before you{' '}
              {isHackathon ? 'register' : 'claim this offer'} or share payment details.
            </p>
          </div>

          <div className="p-4 px-6 flex items-center justify-between gap-4 text-xs">
            <div className="text-[#4A4845] dark:text-[#B8C4D2] font-mono truncate">
              Official URL: <a href={isHackathon ? hackathon?.officialUrl : deal?.officialTermsUrl} target="_blank" rel="noreferrer" className="text-[#C2410C] dark:text-[#FF8A6B] hover:underline font-semibold">{isHackathon ? hackathon?.officialUrl : deal?.officialTermsUrl}</a>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {reportUrl && (
                <a
                  href={reportUrl}
                  target="_blank"
                  rel="noreferrer"
                  title="Report a dead link or wrong information"
                  className="flex items-center gap-1.5 text-[#4A4845] dark:text-[#94A3B8] hover:text-[#B45309] dark:hover:text-[#FBBF24] py-1.5 px-3 font-semibold"
                >
                  <Flag className="w-3.5 h-3.5" />
                  <span>Report issue</span>
                </a>
              )}
              <button
                onClick={onClose}
                className="btn-sharetopus-secondary text-xs py-1.5 px-4 font-bold"
              >
                Close
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};
