import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { useAuth } from './contexts/useAuth'
import AppLayout from './components/layout/AppLayout'
import DemandsPage from './pages/DemandsPage'
import DemandFormPage from './pages/DemandFormPage'
import DemandDetailPage from './pages/DemandDetailPage'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import SupplierInboxPage from './pages/SupplierInboxPage'
import SupplierRequestDetailPage from './pages/SupplierRequestDetailPage'
import SupplierCatalogPage from './pages/SupplierCatalogPage'

function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <main className="loading-page">Đang kiểm tra phiên đăng nhập...</main>
  }

  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />
}

function PurchasingRoute() {
  const { user } = useAuth()

  return user?.roles.some((role) => role === 'PURCHASING_STAFF' || role === 'MANAGER')
    ? <Outlet />
    : <Navigate to="/" replace />
}

function SupplierRoute() {
  const { user } = useAuth()

  return user?.roles.includes('SUPPLIER')
    ? <Outlet />
    : <Navigate to="/" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<HomePage />} />

          <Route element={<PurchasingRoute />}>
            <Route path="/demands" element={<DemandsPage />} />
            <Route path="/demands/new" element={<DemandFormPage />} />
            <Route path="/demands/:id/edit" element={<DemandFormPage />} />
            <Route path="/demands/:id" element={<DemandDetailPage />} />
          </Route>

          <Route element={<SupplierRoute />}>
            <Route path="/supplier/requests" element={<SupplierInboxPage />} />
            <Route path="/supplier/requests/:id" element={<SupplierRequestDetailPage />} />
            <Route path="/supplier/items" element={<SupplierCatalogPage />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
