import { useQuery } from '@tanstack/react-query'
import { useParams, useNavigate, Link } from 'react-router-dom'
import api from '../lib/api'
import type { Finding, ReviewDetail } from '../types/api'
import StatusBadge from '../components/StatusBadge'
import FindingsTable from '../components/FindingsTable'

async function fetchReview(id: string): Promise<ReviewDetail> {
  const { data } = await api.get(`/api/v1/reviews/${id}`)
  return data
}

function SeverityCount({ findings, severity, emoji, accent }: {
  findings: Finding[]
  severity: Finding['severity']
  emoji: string
  accent: string
}) {
  const count = findings.filter(f => f.severity === severity).length
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 border border-white/10">
      <span>{emoji}</span>
      <div>
        <p className={`text-lg font-bold leading-none ${accent}`}>{count}</p>
        <p className="text-xs text-slate-500 capitalize mt-0.5">{severity}</p>
      </div>
    </div>
  )
}

export default function ReviewDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const { data: review, isLoading, isError } = useQuery({
    queryKey: ['review', id],
    queryFn: () => fetchReview(id!),
    enabled: !!id,
    refetchInterval: (query) =>
      query.state.data?.status === 'pending' ? 5_000 : false,
  })

  return (
    <div className="min-h-screen" style={{ background: 'var(--color-bg)' }}>
      {/* ── Top bar ─────────────────────────────────────────────────────── */}
      <header className="border-b border-white/10 sticky top-0 z-10 backdrop-blur-md bg-black/40">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center gap-4">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-lg border border-white/10 hover:border-white/20 hover:bg-white/5"
          >
            ← Back
          </button>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center text-base">
              🤖
            </div>
            <span className="text-sm font-semibold text-white">AI Code Review</span>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8">
        {isLoading && (
          <div className="flex items-center justify-center py-24">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {isError && (
          <div className="text-center py-24">
            <p className="text-red-400">Failed to load review.</p>
            <button onClick={() => navigate('/')} className="mt-3 text-sm text-slate-400 hover:text-white underline">
              Go back
            </button>
          </div>
        )}

        {review && (
          <>
            {/* ── Review header ─────────────────────────────────────────── */}
            <div className="mb-8 rounded-2xl border border-white/10 bg-white/[0.02] p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-2xl">📦</span>
                    <h2 className="text-2xl font-bold text-white">{review.repo_name}</h2>
                    <StatusBadge status={review.status} pulse />
                  </div>
                  <p className="text-slate-400 text-sm">
                    Pull Request <span className="font-mono text-white">#{review.pr_number}</span>
                    {' · '}
                    <span className="text-slate-500 font-mono text-xs">{review.id}</span>
                  </p>
                </div>

                <Link
                  to={`/review/${id}/trace`}
                  className="flex items-center gap-2 text-sm text-indigo-400 hover:text-indigo-300 transition-colors px-4 py-2 rounded-lg border border-indigo-500/30 hover:border-indigo-500/50 bg-indigo-500/10 hover:bg-indigo-500/20"
                >
                  🔍 Agent Trace
                </Link>
              </div>

              {/* ── Severity counters ────────────────────────────────────── */}
              <div className="flex flex-wrap gap-3 mt-6">
                <SeverityCount findings={review.findings} severity="critical" emoji="🔴" accent="text-red-400" />
                <SeverityCount findings={review.findings} severity="warning"  emoji="🟡" accent="text-yellow-400" />
                <SeverityCount findings={review.findings} severity="info"     emoji="🔵" accent="text-indigo-400" />
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 border border-white/10">
                  <span>📊</span>
                  <div>
                    <p className="text-lg font-bold leading-none text-white">{review.findings.length}</p>
                    <p className="text-xs text-slate-500 mt-0.5">Total</p>
                  </div>
                </div>
              </div>
            </div>

            {/* ── Final summary ────────────────────────────────────────── */}
            {review.final_summary && (
              <div className="mb-6 rounded-xl border border-white/10 bg-white/[0.02] p-5">
                <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">
                  AI Summary
                </h3>
                <pre className="text-sm text-slate-300 whitespace-pre-wrap font-sans leading-relaxed">
                  {review.final_summary}
                </pre>
              </div>
            )}

            {/* ── Findings ─────────────────────────────────────────────── */}
            <div>
              <h3 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">
                Findings
              </h3>
              <FindingsTable findings={review.findings} />
            </div>
          </>
        )}
      </main>
    </div>
  )
}
