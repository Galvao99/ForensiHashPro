import type { AnalysisContract } from '../types/api'
import type { AuthResponse } from '../types/api'

export const authFixture: AuthResponse = {
  user: { id: 'user-test', name: 'Pessoa Teste', email: 'person@example.test', role: 'USER', is_active: true, created_at: '2026-08-08T12:00:00Z', last_login_at: null },
  privacy: { retention_mode: 'PRIVATE', retain_analysis_results: false, retain_original_files: false, allow_external_services: false, updated_at: '2026-08-08T12:00:00Z' },
  csrf_token: 'csrf-test',
}

export const analysisFixture: AnalysisContract = {
  schema_version: '1.0.0',
  analysis_id: 'analysis-test',
  evidence_id: 'evidence-test',
  state: 'completed',
  file: { name: 'synthetic.txt', size_bytes: 9 },
  hashes: { sha256: 'abc123', md5: 'def456' },
  declared_type: '.txt',
  detected_type: 'TEXT',
  metadata: { Producer: 'Synthetic' },
  technical_structure: { integrity: { hash_verified: true } },
  native_text: { text: 'synthetic', source: 'native' },
  ocr: null,
  signatures: [],
  ip_addresses: null,
  timeline: [],
  biometrics: null,
  facts: [{ kind: 'hashes' }],
  findings: [],
  limitations: [],
  errors: [],
  processing_steps: [
    { code: 'metadata_extraction', component: 'metadata', status: 'success' },
    { code: 'timeline', component: 'timeline', status: 'no_findings' },
    { code: 'ip_context', component: 'ip_context', status: 'skipped' },
    { code: 'biometric_analysis', component: 'biometric', status: 'unavailable' },
  ],
  execution: { runtime: 'python', started_at: '2026-08-08T14:31:58Z', finished_at: '2026-08-08T14:32:00.400Z' },
}
