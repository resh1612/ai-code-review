import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../lib/api'
import type { AgentTrace } from '../types/api'

async function fetchTrace(id: string): Promise<AgentTrace[]> {
  const { data } = await api.get(`/reviews/${id}/trace`)
  return data
}

function mergeTraceUpdate(traces: AgentTrace[], update: AgentTrace): AgentTrace[] {
  const index = traces.findIndex((trace) => trace.agent_name === update.agent_name)
  if (index >= 0) {
    const next = [...traces]
    next[index] = { ...next[index], ...update }
    return next
  }
  return [...traces, update]
}

function duration(started: string, completed: string | null): string {
  if (!completed) return '—'
  const ms = new Date(completed).getTime() - new Date(started).getTime()
  if (ms < 0) return '—'
  const s = (ms / 1000).toFixed(1)
  return `${s}s`
}

const STATUS_CONFIG = {
  completed: { icon: '✅', class: 'text-emerald-400', bg: 'bg-emerald-400/10 border-emerald-500/30' },
  failed:    { icon: '❌', class: 'text-red-400',     bg: 'bg-red-400/10 border-red-500/30' },
  running:   { icon: '⏳', class: 'text-yellow-400',  bg: 'bg-yellow-400/10 border-yellow-500/30' },
}

const AGENT_ICONS: Record<string, string> = {
  planner_node:       '🗺️',
  code_quality_node:  '🔍',
  security_node:      '🔒',
  aggregator_node:    '📊',
}

export default function AgentTrace() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [traces, setTraces] = useState<AgentTrace[]>([])

  const { isLoading, isError } = useQuery({
    queryKey: ['trace', id],
    queryFn: () => fetchTrace(id!),
    enabled: !!id,
  })

  useEffect(() => {
    if (!id) return

    const ws = new WebSocket(`ws://localhost:8000/ws/review/${id}`)

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data) as
        | { type: 'snapshot'; traces: AgentTrace[] }
        | { type: 'update'; trace: AgentTrace }

      if (message.type === 'snapshot') {
        setTraces(message.traces)
        return
      }

      if (message.type === 'update') {
        setTraces((current) => mergeTraceUpdate(current, message.trace))
      }
    }

    return () => {
      ws.close()
    }
  }, [id])

  return (
    <div className="min-h-screen" style={{ background: 'var(--color-bg)' }}>
      {/* ── Top bar ─────────────────────────────────────────────────────── */}
      <header className="border-b border-white/10 sticky top-0 z-10 backdrop-blur-md bg-black/40">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center gap-4">
          <button
            onClick={() => navigate(`/review/${id}`)}
            className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-lg border border-white/10 hover:border-white/20 hover:bg-white/5"
          >
            ← Back to Review
          </button>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center">
              🔍
            </div>
            <div>
              <span className="text-sm font-semibold text-white">Agent Trace</span>
              <p className="text-xs text-slate-500 font-mono">Review {id?.slice(0, 8)}…</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-white">Agent Execution Trace</h2>
          <p className="text-slate-400 text-sm mt-1">
            Step-by-step breakdown of how each agent processed this PR
          </p>
        </div>

        {isLoading && traces.length === 0 && (
          <div className="flex items-center justify-center py-24">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {isError && traces.length === 0 && (
          <div className="text-center py-24">
            <p className="text-red-400 text-sm">Failed to load agent trace.</p>
          </div>
        )}

        {!isLoading && !isError && traces.length === 0 && (
          <div className="text-center py-24">
            <p className="text-slate-500 text-sm">No trace data available for this review.</p>
          </div>
        )}

        {traces.length > 0 && (
          <>
            {/* ── Timeline ─────────────────────────────────────────────── */}
            <div className="space-y-4 mb-8">
              {traces.map((trace, idx) => {
                const cfg = STATUS_CONFIG[trace.status] ?? STATUS_CONFIG.completed
                const agentIcon = AGENT_ICONS[trace.agent_name] ?? '🤖'
                const label = trace.agent_name.replace(/_/g, ' ').replace(/\bnode\b/g, '').trim()

                return (
                  <div key={trace.agent_name} className="relative flex gap-4">
                    {/* Timeline line */}
                    {idx < traces.length - 1 && (
                      <div className="absolute left-5 top-12 bottom-0 w-px bg-white/10" />
                    )}

                    {/* Icon bubble */}
                    <div className={`flex-shrink-0 w-10 h-10 rounded-full border flex items-center justify-center text-lg z-10 ${cfg.bg}`}>
                      {agentIcon}
                    </div>

                    {/* Card */}
                    <div className="flex-1 rounded-xl border border-white/10 bg-white/[0.02] p-5 hover:bg-white/[0.04] transition-colors">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="font-semibold text-white capitalize text-sm">{label}</p>
                            {trace.status === 'running' && (
                              <span
                                className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"
                                title="Running"
                              />
                            )}
                          </div>
                          <p className="text-xs text-slate-500 font-mono mt-0.5">{trace.agent_name}</p>
                        </div>
                        <div className="flex items-center gap-3">
                          {/* Duration */}
                          <div className="text-right">
                            <p className="text-xs text-slate-500">Duration</p>
                            <p className="text-sm font-mono font-semibold text-slate-200">
                              {duration(trace.started_at, trace.completed_at)}
                            </p>
                          </div>
                          {/* Findings */}
                          <div className="text-right">
                            <p className="text-xs text-slate-500">Findings</p>
                            <p className={`text-sm font-bold ${trace.findings_count > 0 ? 'text-yellow-300' : 'text-emerald-300'}`}>
                              {trace.findings_count}
                            </p>
                          </div>
                          {/* Status */}
                          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border ${cfg.bg} ${cfg.class}`}>
                            {cfg.icon} {trace.status}
                          </div>
                        </div>
                      </div>

                      {/* Timestamps */}
                      <div className="flex gap-6 mt-3 pt-3 border-t border-white/5 text-xs text-slate-600">
                        <span>
                          Started:{' '}
                          <span className="text-slate-400 font-mono">
                            {new Date(trace.started_at).toLocaleTimeString()}
                          </span>
                        </span>
                        <span>
                          Completed:{' '}
                          <span className="text-slate-400 font-mono">
                            {trace.completed_at
                              ? new Date(trace.completed_at).toLocaleTimeString()
                              : '—'}
                          </span>
                        </span>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* ── Summary table ────────────────────────────────────────── */}
            <div className="rounded-2xl border border-white/10 overflow-hidden bg-white/[0.02]">
              <div className="px-6 py-4 border-b border-white/10">
                <h3 className="text-sm font-semibold text-white">Summary</h3>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Agent</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Duration</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Findings</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {traces.map((trace) => {
                    const cfg = STATUS_CONFIG[trace.status] ?? STATUS_CONFIG.completed
                    return (
                      <tr key={trace.agent_name} className="hover:bg-white/5 transition-colors">
                        <td className="px-6 py-3">
                          <div className="flex items-center gap-2 font-mono text-xs text-slate-300">
                            {trace.status === 'running' && (
                              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                            )}
                            {trace.agent_name}
                          </div>
                        </td>
                        <td className="px-6 py-3 font-mono text-sm text-slate-200">
                          {duration(trace.started_at, trace.completed_at)}
                        </td>
                        <td className="px-6 py-3">
                          <span className={`font-semibold ${trace.findings_count > 0 ? 'text-yellow-300' : 'text-emerald-300'}`}>
                            {trace.findings_count}
                          </span>
                        </td>
                        <td className="px-6 py-3">
                          <span className={`text-sm ${cfg.class}`}>{cfg.icon} {trace.status}</span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </main>
    </div>
  )
}
