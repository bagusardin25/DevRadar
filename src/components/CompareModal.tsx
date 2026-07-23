import React from 'react';
import { X } from 'lucide-react';
import type { Hackathon } from '../types';

interface CompareModalProps {
  items: Hackathon[];
  onClose: () => void;
  onRemove: (id: string) => void;
}

export const CompareModal: React.FC<CompareModalProps> = ({
  items,
  onClose,
  onRemove
}) => {
  if (items.length === 0) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md overflow-y-auto">
      <div className="glass-panel w-full max-w-5xl rounded-2xl border-purple-500/30 bg-[#0b0f19] shadow-2xl overflow-hidden my-8 animate-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-800 bg-slate-900/50">
          <div>
            <h2 className="text-lg font-extrabold text-white">Side-by-Side Opportunity Comparison</h2>
            <p className="text-xs text-slate-400">Compare prize pools, effort estimates, deadlines, and requirements</p>
          </div>
          <button onClick={onClose} className="p-2 rounded-xl bg-slate-800 text-slate-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Comparison Table */}
        <div className="p-6 overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse font-mono">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400">
                <th className="p-3 w-40">METRIC</th>
                {items.map((item) => (
                  <th key={item.id} className="p-3 min-w-[240px] text-white font-bold text-sm">
                    <div className="flex items-center justify-between">
                      <span>{item.title}</span>
                      <button onClick={() => onRemove(item.id)} className="text-slate-400 hover:text-rose-400">
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                    <div className="text-[11px] text-slate-400 font-normal">{item.organizer}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              <tr>
                <td className="p-3 font-bold text-slate-400">Prize Pool</td>
                {items.map(item => (
                  <td key={item.id} className="p-3 font-bold text-emerald-400 text-sm">
                    ${item.prizeValue.toLocaleString()} {item.prizeCurrency}
                  </td>
                ))}
              </tr>

              <tr>
                <td className="p-3 font-bold text-slate-400">Effort Estimate</td>
                {items.map(item => (
                  <td key={item.id} className="p-3 text-sky-300">
                    {item.effortEstimate}
                  </td>
                ))}
              </tr>

              <tr>
                <td className="p-3 font-bold text-slate-400 font-mono">Registration Deadline</td>
                {items.map(item => (
                  <td key={item.id} className="p-3 text-amber-300">
                    {new Date(item.registrationDeadline).toLocaleDateString()}
                  </td>
                ))}
              </tr>

              <tr>
                <td className="p-3 font-bold text-slate-400">Participation Mode</td>
                {items.map(item => (
                  <td key={item.id} className="p-3 text-white uppercase font-bold">
                    {item.mode}
                  </td>
                ))}
              </tr>

              <tr>
                <td className="p-3 font-bold text-slate-400">Team Size</td>
                {items.map(item => (
                  <td key={item.id} className="p-3">
                    {item.teamMin} - {item.teamMax} Members
                  </td>
                ))}
              </tr>

              <tr>
                <td className="p-3 font-bold text-slate-400">Verification Match</td>
                {items.map(item => (
                  <td key={item.id} className="p-3 text-purple-300 font-bold">
                    {Math.round(item.confidenceScore * 100)}% Match
                  </td>
                ))}
              </tr>

              <tr>
                <td className="p-3 font-bold text-slate-400">Stack & Tools</td>
                {items.map(item => (
                  <td key={item.id} className="p-3">
                    {item.technologies.join(', ')}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>

      </div>
    </div>
  );
};
