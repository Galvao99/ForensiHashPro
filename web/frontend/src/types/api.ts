export type ProcessingStatus =
  | 'success'
  | 'no_findings'
  | 'partial'
  | 'skipped'
  | 'unavailable'
  | 'failed'
  | 'cancelled'
  | 'limit_exceeded'

export interface ProcessingStep {
  step_id?: string
  code: string
  component?: string
  status: ProcessingStatus
  technical_message?: string
  user_message?: string
  duration_ms?: number
  [key: string]: unknown
}

export interface AnalysisContract {
  schema_version: string
  analysis_id: string
  evidence_id: string
  state: string
  file: Record<string, unknown>
  hashes: Record<string, string>
  declared_type: string | null
  detected_type: string | null
  metadata: Record<string, unknown>
  technical_structure: Record<string, unknown>
  native_text: Record<string, unknown> | null
  ocr: Record<string, unknown> | null
  signatures: Array<Record<string, unknown>>
  ip_addresses: Array<Record<string, unknown>> | null
  timeline: Array<Record<string, unknown>> | null
  biometrics: Record<string, unknown> | null
  facts: Array<Record<string, unknown>>
  findings: Array<Record<string, unknown>>
  limitations: Array<Record<string, unknown>>
  errors: Array<Record<string, unknown>>
  processing_steps: ProcessingStep[]
  execution: Record<string, unknown>
  [key: string]: unknown
}

export interface AnalysisSummary {
  analysisId: string
  filename: string
  detectedType: string | null
  sha256: string | null
  status: string
  createdAt: string | null
  durationMs: number | null
  findingsCount: number
  limitationsCount: number
}

export interface CapabilityState {
  available?: boolean
  available_in_individual_analysis?: boolean
  [key: string]: unknown
}

export type Capabilities = Record<string, CapabilityState>

export interface ApiErrorEnvelope {
  error?: {
    code?: string
    message?: string
    request_id?: string
  }
}

export type AnalysisProfileName = 'FREE' | 'PRO'
export interface WebUser { id: string; email: string; status?: 'ACTIVE' | 'DISABLED' | 'PENDING_VERIFICATION'; email_verified?: boolean; created_at: string; last_login_at: string | null; name?: string; role?: 'USER' | 'ADMIN'; analysis_profile?: AnalysisProfileName; is_active?: boolean }
export interface PrivacyPreferences { retention_mode: 'PRIVATE' | 'RESULT_ONLY' | 'FILE_AND_RESULT'; retain_analysis_results: boolean; retain_original_files: boolean; allow_external_services: boolean; updated_at: string }
export interface AuthResponse { user: WebUser; privacy?: PrivacyPreferences; csrf_token: string }

export type AnalysisJobStatus = 'QUEUED' | 'PROCESSING' | 'SUCCESS' | 'PARTIAL' | 'FAILED' | 'LIMIT_EXCEEDED' | 'CANCELLED'
export type AnalysisJobPublicState = 'queued' | 'running' | 'completed' | 'partial' | 'failed'
export interface AnalysisJobCreated {
  job_id: string
  analysis_id: string
  status: AnalysisJobStatus
  state: AnalysisJobPublicState
}
export interface AnalysisJobState extends AnalysisJobCreated {
  created_at: string
  started_at: string | null
  finished_at: string | null
  current_stage: string | null
  result_analysis_id: string | null
  error_code: string | null
  safe_error_message: string | null
}

export interface CorrelationFindingV2 {
  finding_id: string
  category: string
  severity: 'ok' | 'info' | 'warning' | 'critical'
  summary: string
  description: string
  rule_id: string
  source_engine: string
  confidence: number | null
  source_file?: string | null
  target_file?: string | null
  evidence: Array<Record<string, unknown>>
  entities: Array<Record<string, unknown>>
  limitations: string[]
  metadata: Record<string, unknown>
}

export interface AnalysisSetResult {
  set_id: string
  state: 'completed' | 'partial' | 'failed'
  created_at: string
  finished_at: string
  artifacts: Array<Record<string, unknown>>
  correlation_result: {
    summary: Record<string, number>
    findings: CorrelationFindingV2[]
  }
  timeline_result?: TimelineResult
  limitations: string[]
}

export interface TimelineResult {
  set_id?: string
  events: Array<Record<string, unknown>>
  temporal_events?: Array<Record<string, unknown>>
  structural_events?: Array<Record<string, unknown>>
  warnings: Array<Record<string, unknown>>
  limitations: string[]
  summary: Record<string, number>
}
