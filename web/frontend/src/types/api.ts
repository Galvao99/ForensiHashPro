export interface ApiErrorEnvelope { error?: { code?: string; message?: string; request_id?: string } }
export interface WebUser { id: string; email: string; status: 'ACTIVE' | 'DISABLED' | 'PENDING_VERIFICATION'; email_verified: boolean; created_at: string; last_login_at: string | null }
export interface AuthResponse { user: WebUser; csrf_token: string }
