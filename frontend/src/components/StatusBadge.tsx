import type { Review } from '../types/api'

const STATUS_STYLES: Record<Review['status'], string> = {
  pending:    'bg-yellow-400/15 text-yellow-300 ring-1 ring-yellow-400/30',
  processing: 'bg-blue-400/15 text-blue-300 ring-1 ring-blue-400/30',
  completed:  'bg-emerald-400/15 text-emerald-300 ring-1 ring-emerald-400/30',
  failed:     'bg-red-400/15 text-red-300 ring-1 ring-red-400/30',
}

const STATUS_DOT: Record<Review['status'], string> = {
  pending:    'bg-yellow-400',
  processing: 'bg-blue-400',
  completed:  'bg-emerald-400',
  failed:     'bg-red-400',
}

interface Props {
  status: Review['status']
  pulse?: boolean
}

export default function StatusBadge({ status, pulse = false }: Props) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[status]}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[status]} ${pulse && (status === 'pending' || status === 'processing') ? 'animate-pulse' : ''}`} />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  )
}
