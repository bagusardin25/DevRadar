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
} from 'lucide-react';
import type { Hackathon, AIDeal } from '../types';
import { buildReportIssueUrl } from '../utils/reportIssue';
import { formatPrizePool } from '../utils/formatPrize';
import { getDeadlineInfo } from '../utils/countdown';
import {
  downloadICS,
  buildGoogleCalendarUrl,
  hackathonRegDeadlineEvent,
  hackathonSubDeadlineEvent,
} from '../utils/calendar';
import { generateAIPrompt } from '../utils/aiPrompt';

interface DetailModalProps {
  item: Hackathon | AIDeal | null;
  onClose: () => void;
}

type DetailTab = 'overview' | 'audit' | 'prompt';

export const DetailModal: React.FC<DetailModalProps> = ({ item, onClose }) => {
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

  const isHackathon = item ? 'prizeValue' in item : false;
  const hackathon = item && isHackathon ? (item as Hackathon) : null;
  const deal = item && !isHackathon ? (item as AIDeal) : null;

  const promptText = useMemo(
    () => (item ? generateAIPrompt(item) : ''),
    [item],
  );

  const reportUrl = useMemo(
    () => (item ? buildReportIssueUrl(item) : null),
    [item],
  );

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
      className={`py-3 sm:py-3.5 border-b-2 font-extrabold transition-all whitespace-nowrap px-1 flex items-center gap-1.5 ${
        activeTab === tab
          ? 'border-[#FF5A36] text-[#FF5A36]'
          : 'border-transparent text-[#1C1B18] dark:text-[#B8C4D2] hover:text-[#FF5A36]'
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/65 overflow-y-auto font-sans">
      <div className="sharetopus-card w-full max-w-4xl rounded-t-[28px] sm:rounded-[28px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[8px_8px_0_0_#1C1B18] dark:shadow-[8px_8px_0_0_#D6DCE5] overflow-hidden my-0 sm:my-8 max-h-[95vh] flex flex-col">
        
        {/* Modal Header */}
        <div className="flex items-start sm:items-center justify-between gap-3 p-4 sm:p-6 border-b border-[#D6D5CF] dark:border-slate-800 bg-[#F8F9F4] dark:bg-[#1A2336] shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className={`p-2.5 sm:p-3 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shrink-0 ${isHackathon ? 'bg-[#FF5A36]/15 text-[#FF5A36]' : 'bg-[#7C3AED]/15 text-[#7C3AED]'}`}>
              {isHackathon ? <Trophy className="w-5 h-5 sm:w-6 sm:h-6" /> : <Sparkles className="w-5 h-5 sm:w-6 sm:h-6" />}
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[12px] font-mono font-extrabold text-[#1C1B18] dark:text-[#D6DCE5]">{isHackathon ? hackathon?.organizer : deal?.provider}</span>
                <span className="px-2.5 py-0.5 rounded-full bg-[#059669]/15 text-[#059669] border border-[#059669] text-[12px] font-extrabold">
                  {item.verificationStatus.replace(/_/g, ' ').toUpperCase()}
                </span>
                {dealExpiresInfo && (
                  <span className={`urgency-badge urgency-${dealExpiresInfo.urgency}`}>
                    <Clock className="w-3.5 h-3.5" />
                    <span>{dealExpiresInfo.label}</span>
                  </span>
                )}
              </div>
              <h2 className="text-lg sm:text-xl font-extrabold text-[#1C1B18] dark:text-white tracking-tight leading-snug">
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

        {/* Tab Navigation: Overview · Provenance · AI Agent Prompt (Raw JSON is accordion inside Prompt) */}
        <div className="flex items-center gap-1 sm:gap-4 px-3 sm:px-6 border-b border-[#D6D5CF] dark:border-slate-800 bg-[#F3F4EF] dark:bg-[#131A29] text-[12px] sm:text-sm font-mono font-extrabold overflow-x-auto no-scrollbar shrink-0">
          {tabBtn('overview', 'Overview')}
          {tabBtn('audit', 'Provenance')}
          {tabBtn(
            'prompt',
            <>
              <Bot className="w-3.5 h-3.5 text-[#FF5A36]" />
              <span>AI Agent Prompt</span>
              <span className="px-1.5 py-0.5 rounded-full bg-[#FF5A36]/15 text-[#FF5A36] text-[10px] font-mono font-extrabold border border-[#FF5A36]">
                NEW
              </span>
            </>,
          )}
        </div>

        {/* Modal Body Content */}
        <div className="p-4 sm:p-6 space-y-6 overflow-y-auto text-[#1C1B18] dark:text-white font-bold flex-1">
          
          {/* TAB 1: OVERVIEW */}
          {activeTab === 'overview' && (
            <div className="space-y-6 text-sm">
              
              {/* Summary Stats Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono">
                <div className="sharetopus-card p-3.5 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
                  <div className="text-[12px] text-[#1C1B18] dark:text-[#B8C4D2] font-extrabold">VALUE / REWARD</div>
                  <div className="text-base sm:text-lg font-extrabold text-[#059669] leading-snug break-words">
                    {isHackathon && hackathon
                      ? formatPrizePool(hackathon)
                      : !isHackathon
                        ? deal?.offerValue
                        : '—'}
                  </div>
                </div>

                <div className="sharetopus-card p-3.5 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
                  <div className="text-[12px] text-[#1C1B18] dark:text-[#B8C4D2] font-extrabold">MODE / TYPE</div>
                  <div className="text-sm font-extrabold text-[#FF5A36]">
                    {isHackathon ? hackathon?.mode.toUpperCase() : deal?.offerType.replace(/_/g, ' ').toUpperCase()}
                  </div>
                </div>

                <div className="sharetopus-card p-3.5 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
                  <div className="text-[12px] text-[#1C1B18] dark:text-[#B8C4D2] font-extrabold">CONFIDENCE</div>
                  <div className="text-sm font-extrabold text-[#7C3AED] dark:text-[#C4B5FD]">
                    {Math.round(item.confidenceScore * 100)}%
                  </div>
                </div>

                <div className="sharetopus-card p-3.5 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
                  <div className="text-[12px] text-[#1C1B18] dark:text-[#B8C4D2] font-extrabold">LAST CHECKED</div>
                  <div className="text-[12px] sm:text-sm font-extrabold text-[#1C1B18] dark:text-white">
                    {new Date(item.lastCheckedAt).toLocaleString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </div>
                </div>
              </div>

              {/* Description */}
              <div className="space-y-2">
                <h4 className="font-extrabold text-[#1C1B18] dark:text-white text-base">Description</h4>
                <p className="text-[13px] sm:text-sm text-[#1C1B18] dark:text-[#D6DCE5] leading-relaxed font-bold">{item.description}</p>
              </div>

              {/* Key Highlights — not personalized matching */}
              {item.suitableReasons.length > 0 && (
              <div className="sharetopus-card p-4 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-[#F8F9F4] dark:bg-[#1A2336] space-y-2">
                <div className="flex items-center gap-2 font-extrabold text-[#FF5A36] text-[12px] font-mono uppercase tracking-wide">
                  <Sparkles className="w-4 h-4 text-[#FF5A36]" />
                  <span>Key highlights</span>
                </div>
                <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[13px] text-[#1C1B18] dark:text-[#E8ECF1] font-bold">
                  {item.suitableReasons.map((reason, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-[#059669] shrink-0 mt-0.5" />
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
                    <h5 className="font-extrabold text-[#1C1B18] dark:text-white font-mono flex items-center gap-2">
                      <Calendar className="w-4 h-4 text-[#0284C7]" />
                      Key Dates & Deadlines
                    </h5>
                    <div className="space-y-2 text-[#1C1B18] dark:text-[#D6DCE5] font-bold">
                      <div>Registration Opens: <strong className="text-[#1C1B18] dark:text-white font-extrabold">{new Date(hackathon!.registrationOpenAt).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })}</strong></div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span>Registration Deadline:</span>
                        <strong className="text-[#059669] dark:text-[#34D399] font-extrabold">{new Date(hackathon!.registrationDeadline).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })}</strong>
                        {regDeadlineInfo && (
                          <span className={`urgency-badge urgency-${regDeadlineInfo.urgency}`}>
                            <Clock className="w-3.5 h-3.5" />
                            <span>{regDeadlineInfo.label}</span>
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span>Submission Deadline:</span>
                        <strong className="text-[#FF5A36] dark:text-[#FF7A5C] font-extrabold">{new Date(hackathon!.submissionDeadline).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })}</strong>
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
                      <div className="text-[11px] font-mono font-extrabold text-[#1C1B18] dark:text-[#B8C4D2] uppercase tracking-wide flex items-center gap-1.5">
                        <Calendar className="w-3.5 h-3.5 text-[#0284C7]" />
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
                    <h5 className="font-extrabold text-[#1C1B18] dark:text-white font-mono flex items-center gap-2">
                      <Users className="w-4 h-4 text-[#7C3AED]" />
                      Eligibility & Team Constraints
                    </h5>
                    <div className="space-y-1 text-[#1C1B18] dark:text-[#D6DCE5] font-bold">
                      <div>Team Size: <strong className="text-[#1C1B18] dark:text-white font-extrabold">{hackathon!.teamMin} - {hackathon!.teamMax} members</strong></div>
                      <div>Eligible Roles: <strong className="text-[#1C1B18] dark:text-white font-extrabold">{hackathon!.eligibility.join(', ')}</strong></div>
                      <div>Region Restriction: <strong className="text-[#1C1B18] dark:text-white font-extrabold">{hackathon!.eligibleCountries.join(', ')}</strong></div>
                    </div>
                  </div>
                </div>
              )}

              {/* Technologies */}
              <div className="space-y-2">
                <h4 className="font-extrabold text-[#1C1B18] dark:text-white text-xs font-mono uppercase">SUPPORTED STACK & TAGS</h4>
                <div className="flex items-center gap-2 flex-wrap text-xs font-mono">
                  {(isHackathon ? hackathon!.technologies : deal!.tags).map((t, i) => (
                    <span key={i} className="px-3 py-1 rounded-full bg-[#F3F4EF] dark:bg-[#1A2336] border border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white font-extrabold">
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
              <p className="text-[13px] text-[#4A4845] dark:text-[#B8C4D2] font-bold">
                Optional technical detail for operators. Most users can stay on Overview.
              </p>
              
              {/* Scorecard Visualizer */}
              <div className="sharetopus-card p-5 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-[#F8F9F4] dark:bg-[#1A2336] space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <h4 className="font-extrabold text-[#1C1B18] dark:text-white text-base">Verification scorecard</h4>
                    <p className="text-[#1C1B18] dark:text-[#B8C4D2] text-[12px] sm:text-sm font-bold">How we weighted status, keywords, source tier, freshness, and completeness</p>
                  </div>
                  <div className="text-left sm:text-right font-mono">
                    <div className="text-2xl font-extrabold text-[#FF5A36]">{Math.round(item.confidenceScore * 100)}%</div>
                    <div className="text-[12px] text-[#1C1B18] dark:text-[#B8C4D2] font-extrabold">CONFIDENCE</div>
                  </div>
                </div>

                {/* Score breakdown bars */}
                <div className="space-y-3 font-mono font-bold">
                  <div>
                    <div className="flex justify-between text-[#1C1B18] dark:text-[#D6DCE5] mb-1">
                      <span>1. Status & Deadline Active (Max 35%)</span>
                      <span className="text-[#059669] font-extrabold">{item.audit.scoreBreakdown.statusAndDeadline} / 35 pts</span>
                    </div>
                    <div className="h-2.5 bg-[#E5E6DF] dark:bg-slate-800 rounded-full border border-[#1C1B18] dark:border-[#D6DCE5] overflow-hidden">
                      <div className="h-full bg-[#059669] rounded-full" style={{ width: `${(item.audit.scoreBreakdown.statusAndDeadline / 35) * 100}%` }} />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-[#1C1B18] dark:text-[#D6DCE5] mb-1">
                      <span>2. Keyword & Developer Relevance (Max 25%)</span>
                      <span className="text-[#0284C7] font-extrabold">{item.audit.scoreBreakdown.keywordMatch} / 25 pts</span>
                    </div>
                    <div className="h-2.5 bg-[#E5E6DF] dark:bg-slate-800 rounded-full border border-[#1C1B18] dark:border-[#D6DCE5] overflow-hidden">
                      <div className="h-full bg-[#0284C7] rounded-full" style={{ width: `${(item.audit.scoreBreakdown.keywordMatch / 25) * 100}%` }} />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-[#1C1B18] dark:text-[#D6DCE5] mb-1">
                      <span>3. Source Tier Credibility (Max 20%)</span>
                      <span className="text-[#7C3AED] font-extrabold">{item.audit.scoreBreakdown.sourceCredibility} / 20 pts</span>
                    </div>
                    <div className="h-2.5 bg-[#E5E6DF] dark:bg-slate-800 rounded-full border border-[#1C1B18] dark:border-[#D6DCE5] overflow-hidden">
                      <div className="h-full bg-[#7C3AED] rounded-full" style={{ width: `${(item.audit.scoreBreakdown.sourceCredibility / 20) * 100}%` }} />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-[#1C1B18] dark:text-[#D6DCE5] mb-1">
                      <span>4. Data Freshness (Max 15%)</span>
                      <span className="text-[#FF5A36] font-extrabold">{item.audit.scoreBreakdown.freshness} / 15 pts</span>
                    </div>
                    <div className="h-2.5 bg-[#E5E6DF] dark:bg-slate-800 rounded-full border border-[#1C1B18] dark:border-[#D6DCE5] overflow-hidden">
                      <div className="h-full bg-[#FF5A36] rounded-full" style={{ width: `${(item.audit.scoreBreakdown.freshness / 15) * 100}%` }} />
                    </div>
                  </div>
                </div>

              </div>

              {/* Provenance Tree */}
              <div className="space-y-3">
                <h4 className="font-extrabold text-[#1C1B18] dark:text-white text-sm font-mono flex items-center gap-2">
                  <Layers className="w-4 h-4 text-[#FF5A36]" />
                  Discovery Sources & Provenance Tree
                </h4>

                <div className="space-y-2">
                  {item.discoverySources.map((source, i) => (
                    <div key={i} className="flex items-center justify-between p-3.5 rounded-2xl bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
                      <div className="flex items-center gap-3">
                        <span className="px-3 py-1 rounded-full bg-[#F3F4EF] dark:bg-[#1A2336] border border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white text-[12px] font-extrabold">
                          {source.tier}
                        </span>
                        <div className="min-w-0">
                          <div className="font-extrabold text-[#1C1B18] dark:text-white flex items-center gap-2 flex-wrap">
                            <span>{source.type.toUpperCase()}</span>
                          </div>
                          <div className="text-[12px] font-mono text-[#1C1B18] dark:text-[#B8C4D2] font-bold truncate max-w-[min(100%,20rem)]">{source.url}</div>
                        </div>
                      </div>

                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-[#0284C7] hover:underline font-mono text-xs font-extrabold"
                      >
                        <span>Visit Source</span>
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  ))}
                </div>
              </div>

            </div>
          )}

          {/* TAB 3: AI AGENT BRAINSTORM & EXECUTION PROMPT */}
          {activeTab === 'prompt' && (
            <div className="space-y-4">
              <div className="sharetopus-card p-4 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2 font-extrabold text-[#1C1B18] dark:text-white text-sm">
                    <Bot className="w-4 h-4 text-[#FF5A36] shrink-0" />
                    <span>AI Brainstorm & Execution Prompt</span>
                  </div>
                  <p className="text-[12px] text-[#4A4845] dark:text-[#B8C4D2] font-bold leading-relaxed">
                    Auto-generated plan prompt: brief details, 3 project ideas, architecture, MVP
                    timeline, and demo/pitch tips. Paste into Cursor, Claude, ChatGPT, or Antigravity.
                  </p>
                  {copyError && (
                    <p className="text-[11px] font-extrabold text-red-600 dark:text-red-400">{copyError}</p>
                  )}
                </div>

                <button
                  type="button"
                  onClick={() => void handleCopyPrompt()}
                  className="btn-sharetopus-primary text-xs py-2.5 px-4 font-extrabold shrink-0 flex items-center justify-center gap-1.5 w-full sm:w-auto"
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

              {/* What the prompt asks the agent to produce */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono font-extrabold">
                {[
                  { icon: <FileText className="w-3.5 h-3.5 text-[#0284C7] shrink-0" />, label: 'Brief details' },
                  { icon: <Lightbulb className="w-3.5 h-3.5 text-[#FF5A36] shrink-0" />, label: '3 project ideas' },
                  { icon: <Workflow className="w-3.5 h-3.5 text-[#7C3AED] shrink-0" />, label: 'Architecture' },
                  { icon: <Calendar className="w-3.5 h-3.5 text-[#059669] shrink-0" />, label: 'MVP timeline' },
                ].map((chip) => (
                  <div
                    key={chip.label}
                    className="sharetopus-card px-2.5 py-2 rounded-xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#090C15] flex items-center justify-center gap-1.5 text-[#1C1B18] dark:text-[#D6DCE5]"
                  >
                    {chip.icon}
                    <span>{chip.label}</span>
                  </div>
                ))}
              </div>

              {/* Prompt preview */}
              <div className="relative">
                <pre
                  className="p-4 sm:p-5 rounded-2xl bg-[#090C15] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#34D399] dark:text-[#7DD3FC] font-mono text-[11px] sm:text-xs overflow-x-auto leading-relaxed whitespace-pre-wrap font-bold max-h-[min(50vh,420px)] select-text"
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
                  className="w-full text-left text-[11px] font-mono font-extrabold text-[#4A4845] dark:text-[#B8C4D2] hover:text-[#FF5A36] flex items-center gap-1.5 py-2"
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
                    <div className="flex items-center justify-between gap-2 text-[11px] font-mono font-extrabold text-[#736F66] dark:text-[#94A3B8]">
                      <span>Normalized catalogue payload</span>
                      <span className="truncate">ID: {item.id}</span>
                    </div>
                    <pre className="p-4 rounded-2xl bg-[#090C15] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#A78BFA] font-mono text-[11px] sm:text-xs overflow-x-auto font-bold max-h-64">
                      {JSON.stringify(item, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          )}

        </div>

        {/* Modal Footer */}
        <div className="border-t border-[#D6D5CF] dark:border-slate-800 bg-[#F8F9F4] dark:bg-[#1A2336]">
          {/* DevRadar is an index, not the organiser — say so at the point of action. */}
          <div className="px-6 pt-3 flex items-start gap-2 text-[11px] font-bold text-[#736F66] dark:text-[#94A3B8]">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-px text-[#D97706]" />
            <p>
              DevRadar is not affiliated with this organiser. Details can change after we last
              checked — confirm on the official page before you register or share payment details.
            </p>
          </div>

          <div className="p-4 px-6 flex items-center justify-between gap-4 text-xs font-bold">
            <div className="text-[#1C1B18] dark:text-[#B8C4D2] font-mono truncate font-bold">
              Official URL: <a href={isHackathon ? hackathon?.officialUrl : deal?.officialTermsUrl} target="_blank" rel="noreferrer" className="text-[#FF5A36] hover:underline font-extrabold">{isHackathon ? hackathon?.officialUrl : deal?.officialTermsUrl}</a>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {reportUrl && (
                <a
                  href={reportUrl}
                  target="_blank"
                  rel="noreferrer"
                  title="Report a dead link or wrong information"
                  className="flex items-center gap-1.5 text-[#736F66] dark:text-[#94A3B8] hover:text-[#D97706] py-1.5 px-3 font-extrabold"
                >
                  <Flag className="w-3.5 h-3.5" />
                  <span>Report issue</span>
                </a>
              )}
              <button
                onClick={onClose}
                className="btn-sharetopus-secondary text-xs py-1.5 px-4 font-extrabold"
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
