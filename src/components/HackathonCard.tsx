import React from 'react';
import { 
  Trophy, 
  ShieldCheck, 
  Bookmark, 
  Layers, 
  Clock, 
  ArrowUpRight,
  Sparkles,
  CheckCircle2,
  Download
} from 'lucide-react';
import type { Hackathon } from '../types';

interface HackathonCardProps {
  hackathon: Hackathon;
  onSelect: (hackathon: Hackathon) => void;
  onToggleBookmark: (id: string) => void;
  onToggleAlert: (id: string) => void;
  onToggleCompare: (hackathon: Hackathon) => void;
  isCompared: boolean;
  viewLayout?: 'grid' | 'compact';
}

export const HackathonCard: React.FC<HackathonCardProps> = ({
  hackathon,
  onSelect,
  onToggleBookmark,
  onToggleCompare,
  isCompared,
  viewLayout = 'grid'
}) => {
  // Calculate remaining registration days accurately
  const deadlineRaw = hackathon.registrationDeadline || hackathon.submissionDeadline;
  const deadlineDate = deadlineRaw ? new Date(deadlineRaw) : null;
  const now = new Date();
  const diffTime =
    deadlineDate && !Number.isNaN(deadlineDate.getTime())
      ? deadlineDate.getTime() - now.getTime()
      : 0;
  const daysLeft = Math.max(0, Math.ceil(diffTime / (1000 * 60 * 60 * 24)));

  const primarySource = hackathon.discoverySources[0];

  const handleDownloadMD = (e: React.MouseEvent, hackathon: Hackathon) => {
    e.stopPropagation();
    const mdContent = `# ${hackathon.title}\n\n**Organizer:** ${hackathon.organizer}\n**Prize Pool:** $${hackathon.prizeValue.toLocaleString()} ${hackathon.prizeCurrency}\n**Registration Deadline:** ${new Date(hackathon.registrationDeadline).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })}\n**Submission Deadline:** ${new Date(hackathon.submissionDeadline).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })}\n\n## Description\n${hackathon.description}\n\n## Technologies\n${hackathon.technologies.join(', ')}\n\n## Official Link\n[${hackathon.officialUrl}](${hackathon.officialUrl})\n\n## Verification Notes\n${hackathon.audit?.verifierNotes || 'N/A'}\n`;
    
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
              <span className="px-2 py-0.2 rounded-full bg-[#059669]/15 text-[#059669] dark:text-[#34D399] border border-[#059669] text-[10px] font-extrabold">VERIFIED</span>
            </div>
            <h4 
              onClick={() => onSelect(hackathon)}
              className="text-base font-extrabold text-[#1C1B18] dark:text-white hover:text-[#FF5A36] cursor-pointer transition-colors"
            >
              {hackathon.title}
            </h4>
            <div className="flex items-center gap-3 text-xs font-mono text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold">
              <span className="text-[#059669] dark:text-[#34D399] font-extrabold">${hackathon.prizeValue.toLocaleString()} {hackathon.prizeCurrency}</span>
              <span>•</span>
              <span className="flex items-center gap-1 text-[#1C1B18] dark:text-[#F8FAF9]">
                <span>Reg closes in:</span>
                <strong className="text-[#FF5A36] dark:text-[#D6DCE5] font-extrabold">{daysLeft} days</strong>
              </span>
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
      
      {/* Card Header: Provenance Tier & Verification Pulse */}
      <div className="flex items-center justify-between gap-2 text-xs font-sans">
        <div className="flex items-center gap-2 flex-wrap">
          {/* Status Badge */}
          <span className="px-3 py-1 rounded-full bg-[#059669]/15 text-[#059669] dark:text-[#34D399] border border-[#059669] text-[11px] font-extrabold flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#059669] dark:bg-[#34D399]" />
            {hackathon.verificationStatus.replace('_', ' ').toUpperCase()}
          </span>

          {/* Tier Provenance Badge */}
          <span className="px-3 py-1 rounded-full bg-[#F3F4EF] dark:bg-[#1A2336] border border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-[#F8FAF9] text-[11px] font-extrabold flex items-center gap-1">
            <Layers className="w-3 h-3 text-[#FF5A36]" />
            {primarySource?.tier || 'Tier 1'}
          </span>
        </div>

        {/* Confidence Score Gauge */}
        <div className="flex items-center gap-1.5 font-mono text-[11px] bg-[#F3F4EF] dark:bg-[#1A2336] px-3 py-1 rounded-full border border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold">
          <ShieldCheck className="w-3.5 h-3.5 text-[#1C1B18] dark:text-[#F8FAF9]" />
          <span>{Math.round(hackathon.confidenceScore * 100)}% Match</span>
        </div>
      </div>

      {/* Main Info */}
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-3">
          <div>
            <span className="text-xs text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold uppercase tracking-wider">{hackathon.organizer}</span>
            <h3 
              onClick={() => onSelect(hackathon)}
              className="text-xl font-extrabold text-[#1C1B18] dark:text-white hover:text-[#FF5A36] cursor-pointer transition-colors line-clamp-1 tracking-tight"
            >
              {hackathon.title}
            </h3>
          </div>

          {/* Prize Value Pill */}
          <div className="text-right shrink-0 bg-[#F8F9F4] dark:bg-[#1A2336] p-2.5 rounded-2xl border border-[#1C1B18] dark:border-[#D6DCE5]">
            <div className="text-[10px] text-[#1C1B18] dark:text-[#F8FAF9] font-mono font-extrabold tracking-wider">PRIZE POOL</div>
            <div className="text-lg font-extrabold text-[#059669] dark:text-[#34D399] font-mono flex items-center gap-1 justify-end">
              <Trophy className="w-4 h-4 text-[#FF5A36]" />
              <span>${hackathon.prizeValue.toLocaleString()} {hackathon.prizeCurrency}</span>
            </div>
          </div>
        </div>

        {/* Issue 1 Fix: Hackathon Description - 100% Crisp Visible Text in Light & Dark Mode */}
        <p className="text-xs text-[#1C1B18] dark:text-[#F8FAF9] line-clamp-2 leading-relaxed font-extrabold">
          {hackathon.description}
        </p>
      </div>

      {/* Technology Tags */}
      <div className="flex items-center gap-1.5 flex-wrap text-[11px] font-mono">
        {hackathon.technologies.map((tech, i) => (
          <span key={i} className="px-3 py-1 rounded-full bg-[#F3F4EF] dark:bg-[#1A2336] border border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold">
            #{tech}
          </span>
        ))}
        <span className="px-3 py-1 rounded-full bg-[#FFF1EE] dark:bg-[#FF5A36]/20 border border-[#FF5A36] text-[#FF5A36] font-extrabold">
          {hackathon.mode.toUpperCase()}
        </span>
      </div>

      {/* "Suitable For You Because" AI Matcher Box */}
      <div className="bg-[#F8F9F4] dark:bg-[#1A2336] border border-[#1C1B18] dark:border-[#D6DCE5] rounded-2xl p-3.5 space-y-2 text-xs">
        <div className="flex items-center justify-between text-[11px] font-extrabold text-[#FF5A36] font-mono">
          <span className="flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-[#FF5A36]" />
            SUITABLE FOR YOU BECAUSE:
          </span>
          <span className="text-[#1C1B18] dark:text-[#F8FAF9] font-sans font-extrabold">AI Matcher</span>
        </div>
        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold">
          {hackathon.suitableReasons.slice(0, 4).map((reason, idx) => (
            <li key={idx} className="flex items-center gap-1.5 text-[11px]">
              <CheckCircle2 className="w-3.5 h-3.5 text-[#059669] dark:text-[#34D399] shrink-0" />
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Issue 2 Fix: Footer Countdown Text - 100% Crisp Visible Countdown */}
      <div className="pt-3 border-t border-[#D6D5CF] dark:border-slate-800 flex items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-1.5 font-mono text-[#1C1B18] dark:text-[#F8FAF9] text-[11px] font-extrabold">
          <Clock className="w-4 h-4 text-[#FF5A36] shrink-0" />
          <span className="flex items-center gap-1">
            <span>Reg. closes in:</span>
            <strong className="text-[#FF5A36] dark:text-[#D6DCE5] font-extrabold text-xs">{daysLeft} days</strong>
          </span>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          
          {/* Compare Toggle */}
          <button
            onClick={() => onToggleCompare(hackathon)}
            className={`px-3.5 py-1.5 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[11px] font-extrabold transition-all ${
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
};
