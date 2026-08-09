import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
export function ProtectedRoute({ admin = false }: { admin?: boolean }) { const { user, loading } = useAuth(); const location = useLocation(); if (loading) return <p className="route-loading">Verificando sessão…</p>; if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />; if (admin && user.role !== 'ADMIN') return <Navigate to="/app" replace />; return <Outlet /> }
