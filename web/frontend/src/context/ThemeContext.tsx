import { createContext, ReactNode, useContext, useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'

export type ThemePreference = 'LIGHT' | 'DARK' | 'SYSTEM'
export type ResolvedTheme = 'LIGHT' | 'DARK'

const KEY = 'forensihash-theme'
const DARK_QUERY = '(prefers-color-scheme: dark)'

interface ThemeValue {
  preferredTheme: ThemePreference
  resolvedTheme: ResolvedTheme
  canUseThemePreference: boolean
  setPreferredTheme(value: ThemePreference): void
}

const ThemeContext = createContext<ThemeValue | null>(null)

function storedPreference(): ThemePreference {
  const stored = localStorage.getItem(KEY)
  return stored === 'LIGHT' || stored === 'DARK' || stored === 'SYSTEM' ? stored : 'SYSTEM'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const { pathname } = useLocation()
  const [preferredTheme, setPreferredTheme] = useState<ThemePreference>(storedPreference)
  const [systemDark, setSystemDark] = useState(() => matchMedia(DARK_QUERY).matches)
  const isProtectedArea = pathname === '/customer' || pathname.startsWith('/customer/')
  const canUseThemePreference = Boolean(user && isProtectedArea)
  const resolvedTheme: ResolvedTheme = canUseThemePreference && (
    preferredTheme === 'DARK' || (preferredTheme === 'SYSTEM' && systemDark)
  ) ? 'DARK' : 'LIGHT'

  useEffect(() => {
    const media = matchMedia(DARK_QUERY)
    const update = (event: MediaQueryListEvent) => setSystemDark(event.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = resolvedTheme.toLowerCase()
  }, [resolvedTheme])

  useEffect(() => {
    localStorage.setItem(KEY, preferredTheme)
  }, [preferredTheme])

  function updatePreference(value: ThemePreference) {
    setPreferredTheme(value)
  }

  return (
    <ThemeContext.Provider value={{ preferredTheme, resolvedTheme, canUseThemePreference, setPreferredTheme: updatePreference }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme(): ThemeValue {
  const value = useContext(ThemeContext)
  if (!value) throw new Error('ThemeProvider ausente')
  return value
}
