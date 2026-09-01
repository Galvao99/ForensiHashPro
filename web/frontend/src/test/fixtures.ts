import type { AuthResponse } from '../types/api'

export const authFixture: AuthResponse = {
  user: { id: 'user-test', email: 'person@example.test', status: 'ACTIVE', email_verified: false, created_at: '2026-08-08T12:00:00Z', last_login_at: null },
  csrf_token: 'csrf-test',
}
