import type { Finding } from '../types/api'

const SEVERITY_CONFIG: Record<Finding['severity'], { emoji: string; label: string; rowClass: string; badgeClass: string }> = {
  critical: {
    emoji: '🔴',
    label: 'Critical',
    rowClass: 'bg-red-950/20 hover:bg-red-950/30 border-l-2 border-red-500/50',
    badgeClass: 'bg-red-400/15 text-red-300 ring-1 ring-red-400/30',
  },
  warning: {
    emoji: '🟡',
    label: 'Warning',
    rowClass: 'bg-yellow-950/10 hover:bg-yellow-950/20 border-l-2 border-yellow-500/40',
    badgeClass: 'bg-yellow-400/15 text-yellow-300 ring-1 ring-yellow-400/30',
  },
  info: {
    emoji: '🔵',
    label: 'Info',
    rowClass: 'hover:bg-white/5 border-l-2 border-indigo-500/30',
    badgeClass: 'bg-indigo-400/15 text-indigo-300 ring-1 ring-indigo-400/30',
  },
}

interface Props { findings: Finding[] }

export default function FindingsTable({ findings }: Props) {
  const SEVERITY_ORDER: Finding['severity'][] = ['critical', 'warning', 'info']
  const sorted = [...findings].sort(
    (a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity)
  )

  if (sorted.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="text-5xl mb-4">✅</div>
        <p className="text-lg font-medium text-emerald-300">No issues found</p>
        <p className="text-sm text-slate-500 mt-1">This pull request looks clean!</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-white/10">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/10 bg-white/5">
            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider w-28">Severity</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider w-28">Category</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider w-16">Line</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Message</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Suggestion</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {sorted.map((f, i) => {
            const cfg = SEVERITY_CONFIG[f.severity]
            return (
              <tr key={i} className={`transition-colors ${cfg.rowClass}`}>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.badgeClass}`}>
                    {cfg.emoji} {cfg.label}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-400 capitalize">{f.category}</td>
                <td className="px-4 py-3 text-slate-500 font-mono text-xs">
                  {f.line_number ?? '—'}
                </td>
                <td className="px-4 py-3 text-slate-200 leading-relaxed">{f.message}</td>
                <td className="px-4 py-3 text-slate-400 leading-relaxed">{f.suggestion}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
