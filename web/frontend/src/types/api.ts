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
