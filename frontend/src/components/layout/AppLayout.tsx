import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../../contexts/useAuth'
import './AppLayout.css'

const roleLabels: Record<string, string> = {
  PURCHASING_STAFF: 'Purchasing Staff',
  SUPPLIER: 'Supplier',
  TRANSPORT_PROVIDER: 'Transport Provider',
  MANAGER: 'Manager',
}

export default function AppLayout() {
  const { user, signOut, error } = useAuth()

  if (!user) return null

  const roleName = user.roles.length
    ? user.roles.map((role) => roleLabels[role] ?? role).join(', ')
    : 'Chưa được gán'

  async function handleSignOut() {
    try {
      await signOut()
    } catch {
      // AuthContext handles the error and clears the local session.
    }
  }

  return (
    <div className="app-layout">
      <aside className="app-sidebar">
        <NavLink to="/" className="sidebar-brand" aria-label="CoLogi trang chủ">
          <img src="/images/logo.png" alt="CoLogi" />
        </NavLink>

        <div className="sidebar-section-label">WORKSPACE</div>

        <nav className="sidebar-nav">
          <NavLink to="/" end className="sidebar-link">
            <span className="sidebar-link-icon">⌂</span>
            <span>Tổng quan</span>
          </NavLink>
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user-avatar">
            {user.full_name.charAt(0).toUpperCase()}
          </div>
          <div className="sidebar-user-info">
            <strong>{user.full_name}</strong>
            <span>{roleName}</span>
          </div>
        </div>
      </aside>

      <div className="app-main">
        <header className="app-header">
          <div>
            <span className="header-label">COLOGI WORKSPACE</span>
            <span className="header-page-title">Quản lý vận hành</span>
          </div>

          <div className="header-account">
            <div className="header-account-info">
              <strong>{user.full_name}</strong>
              <span>{roleName}</span>
            </div>
            <button
              type="button"
              className="header-logout-button"
              onClick={() => void handleSignOut()}
            >
              Đăng xuất
            </button>
          </div>
        </header>

        {error && (
          <div className="layout-error" role="alert">
            {error}
          </div>
        )}

        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
