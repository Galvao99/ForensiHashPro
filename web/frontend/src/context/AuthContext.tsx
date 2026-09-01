import { createContext, ReactNode, useContext, useEffect, useRef, useState } from 'react'
import { authApi } from '../lib/api'
import type { AuthResponse, PrivacyPreferences, WebUser } from '../types/api'

export interface RegisterPayload {
  email: string
  password: string
  password_confirmation: string
}

type AuthStage = 'IDLE' | 'SUBMITTING' | 'VALIDATING'

interface AuthValue {
  user: WebUser | null
  privacy: PrivacyPreferences | null
  csrfToken: string
  loading: boolean
  authStage: AuthStage
  login(email: string, password: string): Promise<void>
  register(payload: RegisterPayload): Promise<void>
  logout(): Promise<void>
  updatePrivacy(payload: object): Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<AuthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [authStage, setAuthStage] = useState<AuthStage>('IDLE')
  const requestVersion = useRef(0)

  useEffect(() => {
    const version = ++requestVersion.current
    authApi.me()
      .then((current) => {
        if (requestVersion.current === version) setAuth(current)
      })
      .catch(() => {
        if (requestVersion.current === version) setAuth(null)
      })
      .finally(() => {
        if (requestVersion.current === version) setLoading(false)
      })
  }, [])

  async function authenticate(action: () => Promise<AuthResponse>) {
    const version = ++requestVersion.current
    setLoading(true)
    setAuthStage('SUBMITTING')
    try {
      await action()
      setAuthStage('VALIDATING')
      const verified = await authApi.me()
      if (requestVersion.current === version) {
        setAuth(verified)
      }
    } finally {
      if (requestVersion.current === version) {
        setLoading(false)
        setAuthStage('IDLE')
      }
    }
  }

  return (
    <AuthContext.Provider value={{
      user: auth?.user ?? null,
      privacy: auth?.privacy ?? null,
      csrfToken: auth?.csrf_token ?? '',
      loading,
      authStage,
      login: (email, password) => authenticate(() => authApi.login(email, password)),
      register: (payload) => authenticate(() => authApi.register(payload)),
      async logout() {
        if (auth) await authApi.logout(auth.csrf_token)
        requestVersion.current += 1
        setAuth(null)
        setLoading(false)
        setAuthStage('IDLE')
      },
      async updatePrivacy(payload) {
        if (!auth) return
        const privacy = await authApi.updatePrivacy(payload, auth.csrf_token)
        setAuth({ ...auth, privacy })
      },
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('AuthProvider ausente')
  return value
}
