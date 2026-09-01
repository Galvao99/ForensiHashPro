import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { PublicLayout } from './components/PublicLayout'
import { ForgotPasswordPage, LoginPage, RegisterPage, ResetPasswordPage } from './pages/AuthPages'
import { CustomerAreaPage } from './pages/CustomerAreaPage'
import { DdnaPage } from './pages/DdnaPage'
import { HomePage } from './pages/HomePage'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { ProductPage } from './pages/ProductPage'
import { ReferencesPage } from './pages/ReferencesPage'
import { AuthProvider } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import { PrivacyPage, TermsPage } from './pages/LegalPages'

export function App() {
  return (
    <BrowserRouter><AuthProvider><ThemeProvider>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/forensihash" element={<ProductPage />} />
          <Route path="/ddna" element={<DdnaPage />} />
          <Route path="/references" element={<ReferencesPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/terms" element={<TermsPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
        </Route>
        <Route element={<ProtectedRoute />}>
          <Route path="/customer" element={<CustomerAreaPage />} />
          <Route path="/app/*" element={<Navigate to="/customer" replace />} />
          <Route path="/analysis/*" element={<Navigate to="/customer" replace />} />
        </Route>
        <Route path="*" element={<PlaceholderPage title="Página não encontrada" message="Verifique o endereço informado." />} />
      </Routes>
    </ThemeProvider></AuthProvider></BrowserRouter>
  )
}
