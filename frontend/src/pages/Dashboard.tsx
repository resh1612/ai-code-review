import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import api from '../lib/api'
import type { Review } from '../types/api'
import StatusBadge from '../components/StatusBadge'
import StatCard from '../components/StatCard'

async function fetchReviews(): Promise<Review[]> {
  const { data } = await api.get('/api/v1/reviews')
  return data
}

function formatDate(iso: string) {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  }).format(new Date(iso))
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { data: reviews = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['reviews'],
    queryFn: fetchReviews,
    refetchInterval: 15_000,
  })

  const total     = reviews.length
  const completed = reviews.filter(r => r.status === 'completed').length
  const pending   = reviews.filter(r => r.status === 'pending').length
  const failed    = reviews.filter(r => r.status === 'failed').length

  return (
    <div className="min-h-screen" style={{ background: 'var(--color-bg)' }}>
      {/* ── Top bar ─────────────────────────────────────────────────────── */}
      <header className="border-b border-white/10 sticky top-0 z-10 backdrop-blur-md bg-black/40">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center text-base">
              🤖
            </div>
            <div>
              <h1 className="text-base font-semibold text-white leading-none">AI Code Review</h1>
              <p className="text-xs text-slate-500 mt-0.5">Dashboard</p>
            </div>
          </div>
          <button
            onClick={() => refetch()}
            className="text-xs text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-lg border border-white/10 hover:border-white/20 hover:bg-white/5"
          >
            ↻ Refresh
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* ── Hero ──────────────────────────────────────────────────────── */}
        <div className="mb-8">
          <h2 className="text-3xl font-bold text-white">
            AI Code Review Dashboard
          </h2>
          <p className="text-slate-400 mt-1">
            {total} total review{total !== 1 ? 's' : ''} · automated PR analysis powered by Gemini
          </p>
        </div>

        {/* ── Stat cards ────────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          <StatCard label="Total Reviews"   value={total}     icon="📋" accent="text-indigo-400" />
          <StatCard label="Completed"       value={completed} icon="✅" accent="text-emerald-400" />
          <StatCard label="Pending"         value={pending}   icon="⏳" accent="text-yellow-400" />
          <StatCard label="Failed"          value={failed}    icon="❌" accent="text-red-400" />
        </div>

        {/* ── Table ─────────────────────────────────────────────────────── */}
        <div className="rounded-2xl border border-white/10 overflow-hidden bg-white/[0.02]">
          <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Recent Reviews</h3>
            {isLoading && <span className="text-xs text-slate-500 animate-pulse">Loading…</span>}
          </div>

          {isError ? (
            <div className="px-6 py-12 text-center">
              <p className="text-red-400 text-sm">Failed to load reviews.</p>
              <button onClick={() => refetch()} className="mt-3 text-xs text-slate-400 hover:text-white underline">
                Try again
              </button>
            </div>
          ) : isLoading ? (
            <div className="px-6 py-12 text-center">
              <div className="inline-block w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : reviews.length === 0 ? (
            <div className="px-6 py-12 text-center">
              <p className="text-slate-500 text-sm">No reviews yet. Merge a PR to get started!</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Repository</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">PR #</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Issues Found</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {reviews.map(review => (
                    <tr
                      key={review.id}
                      onClick={() => navigate(`/review/${review.id}`)}
                      className="cursor-pointer hover:bg-white/5 transition-colors group"
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <span className="text-base">📁</span>
                          <span className="font-medium text-white group-hover:text-indigo-300 transition-colors">
                            {review.repo_name}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="font-mono text-slate-300">#{review.pr_number}</span>
                      </td>
                      <td className="px-6 py-4">
                        <StatusBadge status={review.status} pulse />
                      </td>
                      <td className="px-6 py-4">
                        <span className={`font-semibold ${review.findings_count > 0 ? 'text-yellow-300' : 'text-emerald-300'}`}>
                          {review.findings_count}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-slate-500 text-xs">
                        {formatDate(review.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
