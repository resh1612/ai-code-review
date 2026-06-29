export type ReviewStatus = 'pending' | 'processing' | 'completed' | 'failed'

export type FindingSeverity = 'critical' | 'warning' | 'info'

export type AgentTraceStatus = 'completed' | 'failed' | 'running'

export interface Review {
  id: string
  repo_name: string
  pr_number: number
  status: ReviewStatus
  findings_count: number
  created_at: string
}

export interface Finding {
  id: string
  line_number: number | null
  severity: FindingSeverity
  category: string
  message: string
  suggestion: string
}

export interface AgentTrace {
  agent_name: string
  started_at: string
  completed_at: string | null
  findings_count: number
  status: AgentTraceStatus
}

export interface ReviewDetail extends Review {
  findings: Finding[]
  final_summary?: string
}
