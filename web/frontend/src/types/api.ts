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

export interface WebUser { id: string; name: string; email: string; role: 'USER' | 'ADMIN'; is_active: boolean; created_at: string; last_login_at: string | null }
export interface PrivacyPreferences { retention_mode: 'PRIVATE' | 'RESULT_ONLY' | 'FILE_AND_RESULT'; retain_analysis_results: boolean; retain_original_files: boolean; allow_external_services: boolean; updated_at: string }
export interface AuthResponse { user: WebUser; privacy: PrivacyPreferences; csrf_token: string }

export type AnalysisJobStatus = 'QUEUED' | 'PROCESSING' | 'SUCCESS' | 'PARTIAL' | 'FAILED' | 'LIMIT_EXCEEDED' | 'CANCELLED'
export interface AnalysisJobCreated { job_id: string; status: AnalysisJobStatus }
export interface AnalysisJobState extends AnalysisJobCreated {
  created_at: string
  started_at: string | null
  finished_at: string | null
  current_stage: string | null
  analysis_id: string | null
  error_code: string | null
  safe_error_message: string | null
}
