import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { AnalysisSessionProvider } from './context/AnalysisSessionContext'
import { PublicLayout } from './components/PublicLayout'
import { AnalysisPage } from './pages/AnalysisPage'
import { LoginPage, RegisterPage } from './pages/AuthPages'
import { DashboardPage } from './pages/DashboardPage'
import { DdnaPage } from './pages/DdnaPage'
import { HomePage } from './pages/HomePage'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { ProductPage } from './pages/ProductPage'
import { ReferencesPage } from './pages/ReferencesPage'
import { ResultPage } from './pages/ResultPage'
import { TechnologyPage } from './pages/TechnologyPage'
import { AuthProvider } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AccountPage } from './pages/AccountPage'
import { PrivacyPage, TermsPage } from './pages/LegalPages'
import { AdminUsersPage } from './pages/AdminUsersPage'
import { HistoryPage } from './pages/HistoryPage'

export function App() {
  return (
    <BrowserRouter><AuthProvider><ThemeProvider>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/forensihash" element={<ProductPage />} />
          <Route path="/ddna" element={<DdnaPage />} />
          <Route path="/technology" element={<TechnologyPage />} />
          <Route path="/references" element={<ReferencesPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/terms" element={<TermsPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
        </Route>
        <Route element={<ProtectedRoute />}><Route path="/app" element={<AnalysisSessionProvider><AppShell /></AnalysisSessionProvider>}>
          <Route index element={<DashboardPage />} />
          <Route path="analysis" element={<AnalysisPage />} />
          <Route path="result" element={<ResultPage />} />
          <Route path="result/:analysisId" element={<ResultPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="ddna" element={<PlaceholderPage title="DDNA" message="Tecnologia em desenvolvimento. Nenhum registro DDNA é criado nesta versão." />} />
          <Route path="account" element={<AccountPage />} />
          <Route path="assistant" element={<PlaceholderPage title="Assistente" message="Em desenvolvimento. Nenhum documento ou resultado é enviado a serviços de IA." />} />
        </Route></Route>
        <Route element={<ProtectedRoute admin />}><Route path="/admin/users" element={<AdminUsersPage />} /></Route>
        <Route path="*" element={<PlaceholderPage title="Página não encontrada" message="Verifique o endereço informado." />} />
      </Routes>
    </ThemeProvider></AuthProvider></BrowserRouter>
  )
}
