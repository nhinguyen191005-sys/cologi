
import {
  Navigate,
  Outlet,
  Route,
  Routes,
} from 'react-router-dom'

import { useAuth } from './contexts/useAuth'
import AppLayout from './components/layout/AppLayout'

// Common pages
import LoginPage from './pages/LoginPage'
import HomePage from './pages/HomePage'
import ProfilePage from './pages/ProfilePage'

// Purchasing pages
import DemandsPage from './pages/DemandsPage'
import DemandFormPage from './pages/DemandFormPage'
import DemandDetailPage from './pages/DemandDetailPage'

// Supplier pages
import SupplierInboxPage from './pages/SupplierInboxPage'
import SupplierRequestDetailPage from './pages/SupplierRequestDetailPage'
import SupplierCatalogPage from './pages/SupplierCatalogPage'

// Transport provider pages
import VehicleOffersPage from './pages/VehicleOffersPage'
import ProviderAvailabilityPage from './pages/ProviderAvailabilityPage'
import ProviderCapabilityPage from './pages/ProviderCapabilityPage'

// DSS pages - CP8
import DSSDashboardPage from './pages/dss/DSSDashboardPage'
import DSSScenarioPage from './pages/dss/DSSScenarioPage'
import DSSRunDetailPage from './pages/dss/DSSRunDetailPage'

/* =========================================
   AUTHENTICATION
========================================= */

function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <main className="loading-page">
        Đang kiểm tra phiên đăng nhập...
      </main>
    )
  }

  return isAuthenticated
    ? <Outlet />
    : <Navigate to="/login" replace />
}

/* =========================================
   ROLE GUARDS
========================================= */

function PurchasingRoute() {
  const { user } = useAuth()

  return user?.roles.some(
    (role) =>
      role === 'PURCHASING_STAFF' ||
      role === 'MANAGER'
  )
    ? <Outlet />
    : <Navigate to="/" replace />
}

function SupplierRoute() {
  const { user } = useAuth()

  return user?.roles.includes('SUPPLIER')
    ? <Outlet />
    : <Navigate to="/" replace />
}

function ProviderRoute() {
  const { user } = useAuth()

  return user?.roles.includes('TRANSPORT_PROVIDER')
    ? <Outlet />
    : <Navigate to="/" replace />
}

function ManagerRoute() {
  const { user } = useAuth()

  return user?.roles.includes('MANAGER')
    ? <Outlet />
    : <Navigate to="/" replace />
}

/* =========================================
   APP ROUTES
========================================= */

export default function App() {
  return (
    <Routes>
      {/* PUBLIC */}
      <Route
        path="/login"
        element={<LoginPage />}
      />

      {/* AUTHENTICATED */}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          {/* COMMON */}
          <Route
            path="/"
            element={<HomePage />}
          />

          <Route
            path="/profile"
            element={<ProfilePage />}
          />

          {/* PURCHASING + MANAGER */}
          <Route element={<PurchasingRoute />}>
            <Route
              path="/demands"
              element={<DemandsPage />}
            />

            <Route
              path="/demands/new"
              element={<DemandFormPage />}
            />

            <Route
              path="/demands/:id/edit"
              element={<DemandFormPage />}
            />

            <Route
              path="/demands/:id"
              element={<DemandDetailPage />}
            />
          </Route>

          {/* SUPPLIER */}
          <Route element={<SupplierRoute />}>
            <Route
              path="/supplier/requests"
              element={<SupplierInboxPage />}
            />

            <Route
              path="/supplier/requests/:id"
              element={<SupplierRequestDetailPage />}
            />

            <Route
              path="/supplier/items"
              element={<SupplierCatalogPage />}
            />
          </Route>

          {/* TRANSPORT PROVIDER */}
          <Route element={<ProviderRoute />}>
            <Route
              path="/provider/capability"
              element={<ProviderCapabilityPage />}
            />

            <Route
              path="/provider/vehicle-offers"
              element={<VehicleOffersPage />}
            />

            <Route
              path="/provider/availability"
              element={<ProviderAvailabilityPage />}
            />
          </Route>

          {/* MANAGER - DSS F1-F5 */}
          <Route element={<ManagerRoute />}>
            <Route
              path="/dss"
              element={<DSSDashboardPage />}
            />

            <Route
              path="/dss/scenarios/new"
              element={<DSSScenarioPage />}
            />

            <Route
              path="/dss/scenarios/:scenarioId"
              element={<DSSScenarioPage />}
            />

            <Route
              path="/dss/runs/:runId"
              element={<DSSRunDetailPage />}
            />
          </Route>

        </Route>
        {/* Đóng AppLayout */}

      </Route>
      {/* Đóng ProtectedRoute */}

      {/* FALLBACK */}
      <Route
        path="*"
        element={<Navigate to="/" replace />}
      />
    </Routes>
  )
}
