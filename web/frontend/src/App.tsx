import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
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

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/forensihash" element={<ProductPage />} />
          <Route path="/ddna" element={<DdnaPage />} />
          <Route path="/technology" element={<TechnologyPage />} />
          <Route path="/references" element={<ReferencesPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
        </Route>
        <Route path="/app" element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="analysis" element={<AnalysisPage />} />
          <Route path="result" element={<ResultPage />} />
          <Route path="history" element={<PlaceholderPage title="Histórico" message="O histórico depende de persistência e será implementado em fase posterior." />} />
          <Route path="ddna" element={<PlaceholderPage title="DDNA" message="Tecnologia em desenvolvimento. Nenhum registro DDNA é criado nesta versão." />} />
          <Route path="account" element={<PlaceholderPage title="Conta" message="Contas e autenticação ainda não estão disponíveis." />} />
        </Route>
        <Route path="*" element={<PlaceholderPage title="Página não encontrada" message="Verifique o endereço informado." />} />
      </Routes>
    </BrowserRouter>
  )
}
