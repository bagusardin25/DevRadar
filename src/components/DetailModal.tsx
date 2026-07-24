import React, { useState } from 'react';
import { 
  X, 
  ExternalLink, 
  Calendar, 
  Trophy, 
  Users, 
  Layers, 
  Sparkles,
  CheckCircle2
} from 'lucide-react';
import type { Hackathon, AIDeal } from '../types';

interface DetailModalProps {
  item: Hackathon | AIDeal | null;
  onClose: () => void;
}

export const DetailModal: React.FC<DetailModalProps> = ({ item, onClose }) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'audit' | 'json'>('overview');

  if (!item) return null;

  const isHackathon = 'prizeValue' in item;
  const hackathon = isHackathon ? (item as Hackathon) : null;
  const deal = !isHackathon ? (item as AIDeal) : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-md overflow-y-auto font-sans">
      <div className="sharetopus-card w-full max-w-4xl rounded-[28px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] shadow-[8px_8px_0_0_#1C1B18] dark:shadow-[8px_8px_0_0_#D6DCE5] overflow-hidden my-8 animate-in zoom-in-95 duration-200">
        
        {/* Modal Header */}
        <div className="flex items-center justify-between p-6 border-b border-[#D6D5CF] dark:border-slate-800 bg-[#F8F9F4] dark:bg-[#1A2336]">
          <div className="flex items-center gap-3">
            <div className={`p-3 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] ${isHackathon ? 'bg-[#FF5A36]/15 text-[#FF5A36]' : 'bg-[#7C3AED]/15 text-[#7C3AED]'}`}>
              {isHackathon ? <Trophy className="w-6 h-6" /> : <Sparkles className="w-6 h-6" />}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono font-extrabold text-[#1C1B18] dark:text-[#D6DCE5]">{isHackathon ? hackathon?.organizer : deal?.provider}</span>
                <span className="px-2.5 py-0.5 rounded-full bg-[#059669]/15 text-[#059669] border border-[#059669] text-[10px] font-extrabold">VERIFIED LISTING</span>
              </div>
              <h2 className="text-xl font-extrabold text-[#1C1B18] dark:text-white tracking-tight">{isHackathon ? hackathon?.title : deal?.productName}</h2>
            </div>
          </div>

          <button 
            onClick={onClose}
            className="p-2 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-white hover:bg-[#FF5A36] hover:text-white transition-all font-bold"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-4 px-6 border-b border-[#D6D5CF] dark:border-slate-800 bg-[#F3F4EF] dark:bg-[#131A29] text-xs font-mono font-extrabold">
          <button
            onClick={() => setActiveTab('overview')}
            className={`py-3.5 border-b-2 font-extrabold transition-all ${
              activeTab === 'overview' ? 'border-[#FF5A36] text-[#FF5A36]' : 'border-transparent text-[#1C1B18] dark:text-[#B8C4D2] hover:text-[#FF5A36]'
            }`}
          >
            1. Overview & Requirements
          </button>
          <button
            onClick={() => setActiveTab('audit')}
            className={`py-3.5 border-b-2 font-extrabold transition-all ${
              activeTab === 'audit' ? 'border-[#FF5A36] text-[#FF5A36]' : 'border-transparent text-[#1C1B18] dark:text-[#B8C4D2] hover:text-[#FF5A36]'
            }`}
          >
            2. Provenance Scorecard ({Math.round(item.confidenceScore * 100)}%)
          </button>
          <button
            onClick={() => setActiveTab('json')}
            className={`py-3.5 border-b-2 font-extrabold transition-all ${
              activeTab === 'json' ? 'border-[#FF5A36] text-[#FF5A36]' : 'border-transparent text-[#1C1B18] dark:text-[#B8C4D2] hover:text-[#FF5A36]'
            }`}
          >
            3. Normalized JSON
          </button>
        </div>

        {/* Modal Body Content */}
        <div className="p-6 space-y-6 max-h-[70vh] overflow-y-auto text-[#1C1B18] dark:text-white font-bold">
          
          {/* TAB 1: OVERVIEW */}
          {activeTab === 'overview' && (
            <div className="space-y-6 text-sm">
              
              {/* Summary Stats Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono">
                <div className="sharetopus-card p-3.5 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
                  <div className="text-[11px] text-[#1C1B18] dark:text-[#B8C4D2] font-extrabold">VALUE / REWARD</div>
                  <div className="text-lg font-extrabold text-[#059669]">
                    {isHackathon ? `$${hackathon?.prizeValue.toLocaleString()} USD` : deal?.offerValue}
                  </div>
                </div>

                <div className="sharetopus-card p-3.5 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
                  <div className="text-[11px] text-[#1C1B18] dark:text-[#B8C4D2] font-extrabold">PARTICIPATION MODE</div>
                  <div className="text-sm font-extrabold text-[#FF5A36]">
                    {isHackathon ? hackathon?.mode.toUpperCase() : deal?.offerType.toUpperCase()}
                  </div>
                </div>

                <div className="sharetopus-card p-3.5 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
                  <div className="text-[11px] text-[#1C1B18] dark:text-[#B8C4D2] font-extrabold">CONFIDENCE SCORE</div>
                  <div className="text-sm font-extrabold text-[#7C3AED]">
                    {Math.round(item.confidenceScore * 100)}% Verified
                  </div>
                </div>

                <div className="sharetopus-card p-3.5 rounded-2xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5]">
                  <div className="text-[11px] text-[#1C1B18] dark:text-[#B8C4D2] font-extrabold">LAST CHECKED</div>
                  <div className="text-xs font-extrabold text-[#1C1B18] dark:text-white">
                    {new Date(item.lastCheckedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
              </div>

              {/* Description */}
              <div className="space-y-2">
                <h4 className="font-extrabold text-[#1C1B18] dark:text-white text-base">Description</h4>
                <p className="text-[#1C1B18] dark:text-[#D6DCE5] leading-relaxed font-bold">{item.description}</p>
              </div>

              {/* Suitable For You Because (AI Matcher) */}
              <div className="sharetopus-card p-4 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-[#F8F9F4] dark:bg-[#1A2336] space-y-2">
                <div className="flex items-center gap-2 font-extrabold text-[#FF5A36] text-xs font-mono">
                  <Sparkles className="w-4 h-4 text-[#FF5A36]" />
                  <span>SUITABLE FOR YOU BECAUSE (AUTOMATED MATCH REASONING):</span>
                </div>
                <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-[#1C1B18] dark:text-[#E8ECF1] font-extrabold">
                  {item.suitableReasons.map((reason, idx) => (
                    <li key={idx} className="flex items-center gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-[#059669] shrink-0" />
                      <span>{reason}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Specific Metadata for Hackathon */}
              {isHackathon && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div className="sharetopus-card p-4 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] space-y-2">
                    <h5 className="font-extrabold text-[#1C1B18] dark:text-white font-mono flex items-center gap-2">
                      <Calendar className="w-4 h-4 text-[#0284C7]" />
                      Key Dates & Deadlines
                    </h5>
                    <div className="space-y-1 text-[#1C1B18] dark:text-[#D6DCE5] font-bold">
                      <div>Registration Opens: <strong className="text-[#1C1B18] dark:text-white font-extrabold">{new Date(hackathon!.registrationOpenAt).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })}</strong></div>
                      <div>Registration Deadline: <strong className="text-[#059669] font-extrabold">{new Date(hackathon!.registrationDeadline).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })}</strong></div>
                      <div>Submission Deadline: <strong className="text-[#FF5A36] font-extrabold">{new Date(hackathon!.submissionDeadline).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })}</strong></div>
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

          {/* TAB 2: AUDIT & PROVENANCE SCORECARD */}
          {activeTab === 'audit' && (
            <div className="space-y-6 text-xs font-sans">
              
              {/* Scorecard Visualizer */}
              <div className="sharetopus-card p-5 rounded-2xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-[#F8F9F4] dark:bg-[#1A2336] space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-extrabold text-[#1C1B18] dark:text-white text-base">Deterministic Confidence Scorecard</h4>
                    <p className="text-[#1C1B18] dark:text-[#B8C4D2] text-xs font-bold">Weighted formula score calculated by DevRadar Verification Engine</p>
                  </div>
                  <div className="text-right font-mono">
                    <div className="text-2xl font-extrabold text-[#FF5A36]">{Math.round(item.confidenceScore * 100)} / 100</div>
                    <div className="text-[10px] text-[#1C1B18] dark:text-[#B8C4D2] font-extrabold">HIGH CONFIDENCE</div>
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

                <div className="p-3.5 bg-white dark:bg-[#131A29] rounded-xl text-[#1C1B18] dark:text-[#E8ECF1] text-xs border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] font-bold">
                  <strong className="text-[#FF5A36] font-mono font-extrabold">Verifier Notes:</strong> {item.audit.verifierNotes}
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
                        <span className="px-3 py-1 rounded-full bg-[#F3F4EF] dark:bg-[#1A2336] border border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white text-[11px] font-extrabold">
                          {source.tier}
                        </span>
                        <div>
                          <div className="font-extrabold text-[#1C1B18] dark:text-white flex items-center gap-2">
                            <span>{source.type.toUpperCase()}</span>
                            {source.author && <span className="text-[#1C1B18] dark:text-[#B8C4D2] font-mono text-[11px]">{source.author}</span>}
                          </div>
                          <div className="text-[11px] font-mono text-[#1C1B18] dark:text-[#B8C4D2] font-bold truncate max-w-md">{source.url}</div>
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

          {/* TAB 3: NORMALIZED JSON SCHEMA */}
          {activeTab === 'json' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs font-mono font-extrabold text-[#1C1B18] dark:text-[#D6DCE5]">
                <span>Normalized Database Record (PostgreSQL target)</span>
                <span>Type: {isHackathon ? 'hackathon' : 'ai_offer'}</span>
              </div>
              <pre className="p-4 rounded-2xl bg-[#090C15] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#34D399] font-mono text-xs overflow-x-auto font-bold">
                {JSON.stringify(item, null, 2)}
              </pre>
            </div>
          )}

        </div>

        {/* Modal Footer */}
        <div className="p-4 px-6 border-t border-[#D6D5CF] dark:border-slate-800 bg-[#F8F9F4] dark:bg-[#1A2336] flex items-center justify-between text-xs font-bold">
          <div className="text-[#1C1B18] dark:text-[#B8C4D2] font-mono truncate max-w-md font-bold">
            Official URL: <a href={isHackathon ? hackathon?.officialUrl : deal?.officialTermsUrl} target="_blank" rel="noreferrer" className="text-[#FF5A36] hover:underline font-extrabold">{isHackathon ? hackathon?.officialUrl : deal?.officialTermsUrl}</a>
          </div>
          <button
            onClick={onClose}
            className="btn-sharetopus-secondary text-xs py-1.5 px-4 font-extrabold"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  );
};
