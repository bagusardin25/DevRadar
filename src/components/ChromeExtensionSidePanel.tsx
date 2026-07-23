import React, { useState } from 'react';
import { 
  Globe, 
  X, 
  Sparkles, 
  Calendar, 
  Bookmark,
  Zap,
  Wrench
} from 'lucide-react';

interface ChromeExtensionSidePanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ChromeExtensionSidePanel: React.FC<ChromeExtensionSidePanelProps> = ({
  isOpen,
  onClose
}) => {
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzed, setAnalyzed] = useState(false);

  if (!isOpen) return null;

  const handleAnalyze = () => {
    setAnalyzing(true);
    setTimeout(() => {
      setAnalyzing(false);
      setAnalyzed(true);
    }, 1200);
  };

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[420px] bg-[#F3F4EF] dark:bg-[#090C15] border-l-[3px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[-8px_0_0_0_rgba(28,27,24,0.1)] dark:shadow-[-8px_0_0_0_rgba(56,189,248,0.1)] flex flex-col justify-between animate-in slide-in-from-right duration-300 font-sans">
      
      {/* Side Panel Top Bar */}
      <div className="p-4 border-b-[2.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-[#FF5A36] text-white border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5]">
            <Globe className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-extrabold text-[#1C1B18] dark:text-white">DevRadar Extension</h3>
            <p className="text-[10px] font-mono text-[#4A4845] dark:text-[#B8C4D2] font-bold">Side Panel API v1.4 • Active Tab</p>
          </div>
        </div>

        <button 
          onClick={onClose}
          className="p-1.5 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white hover:bg-[#FF5A36] hover:text-white bg-white dark:bg-[#1A2336] transition-colors shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5]"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Main Body */}
      <div className="p-5 flex-1 overflow-y-auto space-y-5 text-xs">
        
        {/* Active Tab Preview */}
        <div className="p-3.5 rounded-2xl bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] space-y-2">
          <div className="flex items-center justify-between text-[11px] font-mono font-extrabold text-[#4A4845] dark:text-[#B8C4D2]">
            <span>CURRENT BROWSER TAB:</span>
            <span className="text-[#059669] dark:text-[#34D399]">Active</span>
          </div>
          <div className="font-extrabold text-[#1C1B18] dark:text-white text-xs truncate">
            https://anthropic.com/hackathon-2026
          </div>
          <p className="text-[#4A4845] dark:text-[#B8C4D2] text-[11px] font-bold">
            Global AI Agents Developer Challenge — Build multi-agent AI systems with Claude 4.5.
          </p>
        </div>

        {/* Action Button */}
        {!analyzed ? (
          <button
            onClick={handleAnalyze}
            disabled={analyzing}
            className="w-full btn-sharetopus-primary justify-center text-xs py-3 rounded-full font-extrabold shadow-[3px_3px_0_0_#1C1B18] dark:shadow-[3px_3px_0_0_#D6DCE5]"
          >
            <Sparkles className={`w-4 h-4 ${analyzing ? 'animate-spin' : ''}`} />
            <span>{analyzing ? 'Extracting Page DOM & Dates...' : 'Analyze This Page'}</span>
          </button>
        ) : (
          <div className="space-y-4 animate-in fade-in duration-300">
            
            {/* Extraction Results */}
            <div className="p-4 rounded-2xl bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] space-y-3">
              <div className="flex items-center justify-between">
                <span className="px-3 py-1 rounded-full bg-[#059669]/15 text-[#059669] dark:text-[#34D399] border border-[#059669] text-[10px] font-extrabold">
                  VERIFIED TARGET
                </span>
                <span className="font-mono text-[#1C1B18] dark:text-[#F8FAF9] font-extrabold bg-[#F3F4EF] dark:bg-[#1A2336] px-2.5 py-0.5 rounded-full border border-[#1C1B18] dark:border-[#D6DCE5]">
                  98% Match
                </span>
              </div>

              <div className="space-y-1">
                <div className="font-extrabold text-[#1C1B18] dark:text-white text-sm">Global AI Agents Developer Challenge</div>
                <div className="text-[#059669] dark:text-[#34D399] font-mono font-extrabold">$50,000 USD Prize Pool</div>
              </div>

              <div className="p-3 bg-[#F8F9F4] dark:bg-[#1A2336] rounded-xl space-y-1.5 font-mono text-[11px] text-[#1C1B18] dark:text-[#F8FAF9] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] font-bold">
                <div className="flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-[#FF5A36]" />
                  <span>Reg Deadline: <strong>Aug 10, 2026</strong></span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Zap className="w-3.5 h-3.5 text-[#FF5A36]" />
                  <span>Submission: <strong>Aug 25, 2026</strong></span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Wrench className="w-3.5 h-3.5 text-[#FF5A36]" />
                  <span>Technologies: <strong>Anthropic, Next.js, Python</strong></span>
                </div>
              </div>

              {/* Quick Actions */}
              <div className="grid grid-cols-2 gap-2 pt-1">
                <button 
                  onClick={() => alert('Deadline exported to Google Calendar / iCal!')}
                  className="flex items-center justify-center gap-1.5 p-2 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#1A2336] text-[#1C1B18] dark:text-white font-extrabold shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5] hover:translate-x-[-1px] transition-all"
                >
                  <Calendar className="w-3.5 h-3.5 text-[#1C1B18] dark:text-[#F8FAF9]" />
                  <span>Export Cal</span>
                </button>

                <button 
                  onClick={() => alert('Saved to your DevRadar bookmarks!')}
                  className="flex items-center justify-center gap-1.5 p-2 rounded-full border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-[#FF5A36] text-white font-extrabold shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5] hover:translate-x-[-1px] transition-all"
                >
                  <Bookmark className="w-3.5 h-3.5" />
                  <span>Save Info</span>
                </button>
              </div>
            </div>

            {/* Check Similar Opportunities */}
            <div className="p-3.5 rounded-2xl bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] shadow-[4px_4px_0_0_#1C1B18] dark:shadow-[4px_4px_0_0_#D6DCE5] space-y-3">
              <div className="font-extrabold text-[#1C1B18] dark:text-white text-[10px] font-mono tracking-wider">3 SIMILAR ACTIVE OPPORTUNITIES:</div>
              <div className="space-y-2 text-[11px]">
                <div className="p-2.5 rounded-xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white font-extrabold flex items-center justify-between shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5]">
                  <span>Open Source AI Infra Hackathon</span>
                  <span className="text-[#059669] dark:text-[#34D399] font-mono">$25k</span>
                </div>
                <div className="p-2.5 rounded-xl bg-[#F8F9F4] dark:bg-[#1A2336] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] text-[#1C1B18] dark:text-white font-extrabold flex items-center justify-between shadow-[2px_2px_0_0_#1C1B18] dark:shadow-[2px_2px_0_0_#D6DCE5]">
                  <span>Claude 4.5 $100 Free Credits</span>
                  <span className="text-[#1C1B18] dark:text-[#F8FAF9] font-mono">Free</span>
                </div>
              </div>
            </div>

          </div>
        )}

      </div>

      {/* Side Panel Footer */}
      <div className="p-4 border-t-[2.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] text-[11px] font-mono font-bold text-[#4A4845] dark:text-[#B8C4D2] flex items-center justify-between">
        <span>DevRadar Helper v1.4</span>
        <button onClick={() => setAnalyzed(false)} className="text-[#FF5A36] font-extrabold hover:underline">
          Reset Simulator
        </button>
      </div>

    </div>
  );
};
