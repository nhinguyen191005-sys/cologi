
import { useAuth } from '../contexts/useAuth'
import './ProfilePage.css'
const roleLabels: Record<string, string> = {
  PURCHASING_STAFF: 'Nhân viên mua hàng',
  SUPPLIER: 'Nhà cung cấp',
  TRANSPORT_PROVIDER: 'Đơn vị vận chuyển',
  MANAGER: 'Quản lý',
}

export default function ProfilePage() {
  const { user } = useAuth()

  if (!user) return null

  const initials = user.full_name
    .trim()
    .split(/\s+/)
    .slice(-2)
    .map((name) => name.charAt(0).toUpperCase())
    .join('')

  return (
    <div className="profile-page">
      <div className="profile-heading">
        <p>ACCOUNT SETTINGS</p>
        <h1>Hồ sơ cá nhân</h1>
        <span>
          Xem thông tin tài khoản và quyền truy cập CoLogi.
        </span>
      </div>

      <section className="profile-card">
        <div className="profile-banner" />

        <div className="profile-identity">
          <div className="profile-avatar">
            {initials || '?'}
          </div>

          <div>
            <h2>{user.full_name}</h2>
            <p>{user.email}</p>
            <span className="profile-active">
              Tài khoản đang hoạt động
            </span>
          </div>
        </div>

        <div className="profile-section-title">
          <h3>Thông tin cá nhân</h3>
          <p>Thông tin được lấy từ tài khoản đăng nhập.</p>
        </div>

        <div className="profile-info-grid">
          <div className="profile-info-item">
            <label>Họ và tên</label>
            <strong>{user.full_name}</strong>
          </div>

          <div className="profile-info-item">
            <label>Email</label>
            <strong>{user.email}</strong>
          </div>

          <div className="profile-info-item">
            <label>Mã tài khoản</label>
            <strong>#{user.id}</strong>
          </div>

          <div className="profile-info-item">
            <label>Trạng thái</label>
            <strong>Đang đăng nhập</strong>
          </div>
        </div>

        <div className="profile-section-title">
          <h3>Vai trò và phân quyền</h3>
          <p>
            Các quyền được cấp cho tài khoản trong hệ thống.
          </p>
        </div>

        <div className="profile-roles">
          {user.roles.length ? (
            user.roles.map((role) => (
              <span key={role} className="profile-role-badge">
                {roleLabels[role] ?? role}
              </span>
            ))
          ) : (
            <span>Chưa được phân quyền</span>
          )}
        </div>
      </section>
    </div>
  )
}
