import { useAuth } from '../contexts/useAuth'
import './HomePage.css'

const roleLabels: Record<string, string> = {
  PURCHASING_STAFF: 'Purchasing Staff',
  SUPPLIER: 'Supplier',
  TRANSPORT_PROVIDER: 'Transport Provider',
  MANAGER: 'Manager',
}

export default function HomePage() {
  const { user } = useAuth()

  if (!user) return null

  const roles = user.roles.map((role) => roleLabels[role] ?? role)

  return (
    <div className="dashboard-page">
      <section className="dashboard-welcome">
        <div>
          <p className="dashboard-eyebrow">OVERVIEW</p>
          <h1>Xin chào, {user.full_name}</h1>
          <p className="dashboard-description">
            Chào mừng bạn đến với hệ thống quản lý CoLogi.
          </p>
        </div>
        <div className="welcome-decoration">C</div>
      </section>

      <section className="dashboard-section">
        <div className="section-heading">
          <div>
            <h2>Tổng quan tài khoản</h2>
            <p>Thông tin tài khoản đang đăng nhập</p>
          </div>
        </div>

        <div className="account-grid">
          <article className="account-card">
            <span className="account-card-label">HỌ VÀ TÊN</span>
            <strong>{user.full_name}</strong>
          </article>

          <article className="account-card">
            <span className="account-card-label">EMAIL</span>
            <strong>{user.email}</strong>
          </article>

          <article className="account-card">
            <span className="account-card-label">USER ID</span>
            <strong>#{user.id}</strong>
          </article>

          <article className="account-card">
            <span className="account-card-label">BUSINESS ROLE</span>
            <strong>{roles.length ? roles.join(', ') : 'Chưa được gán'}</strong>
          </article>
        </div>
      </section>
    </div>
  )
}