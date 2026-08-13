export type AnalysisDiagnosticEvent =
  | 'provider.mounted'
  | 'provider.unmounted'
  | 'upload.created'
  | 'upload.transition'
  | 'submit.attempt'
  | 'submit.claimed'
  | 'submit.blocked'
  | 'job.created'
  | 'poller.created'
  | 'poller.disposed'

interface AnalysisDiagnosticDetails {
  providerInstanceId: string
  clientUploadId?: string
  filename?: string
  currentState?: string
  jobId?: string | null
  submissionAttemptId?: string
  source?: string
  reason?: string
}

let providerSequence = 0
let attemptSequence = 0

function diagnosticEnabled(): boolean {
  return (import.meta.env.DEV && import.meta.env.MODE !== 'test') || import.meta.env.VITE_ANALYSIS_DIAGNOSTICS === 'true'
}

export function nextProviderInstanceId(): string {
  providerSequence += 1
  return `P-${String(providerSequence).padStart(3, '0')}`
}

export function nextSubmissionAttemptId(): string {
  attemptSequence += 1
  return `SUB-${String(attemptSequence).padStart(3, '0')}`
}

export function analysisDiagnostic(event: AnalysisDiagnosticEvent, details: AnalysisDiagnosticDetails): void {
  if (!diagnosticEnabled()) return
  console.info('[analysis-lifecycle]', {
    event,
    ...details,
    buildId: import.meta.env.VITE_BUILD_ID ?? 'local',
    timestamp: new Date().toISOString(),
  })
}
