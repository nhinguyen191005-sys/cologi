
import { useState, type ReactNode } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../../contexts/useAuth'
import type { BusinessRole } from '../../types/auth'
import './AppLayout.css'
type MenuIcon =
  | 'home' | 'clipboard' | 'plus' | 'box' | 'truck'
  | 'calendar' | 'layers' | 'shield' | 'user' | 'menu'
  | 'chevron' | 'check' | 'route' | 'chart' | 'clock'

const iconArt: Record<MenuIcon, ReactNode> = {
  home: <>
    <path d="m3 10 9-7 9 7v10H3z" />
    <path d="M9 20v-7h6v7" />
  </>,
  clipboard: <>
    <rect x="5" y="5" width="14" height="17" rx="2" />
    <path d="M9 5V3h6v2M9 12h6m-6 4h6" />
  </>,
  plus: <path d="M12 4v16M4 12h16" />,
  box: <>
    <path d="m12 3 9 5-9 5-9-5 9-5Z" />
    <path d="M3 8v8l9 5 9-5V8M12 13v8" />
  </>,
  truck: <>
    <path d="M3 6h11v11H3zM14 10h4l3 4v3h-7" />
    <circle cx="7" cy="18" r="2" />
    <circle cx="18" cy="18" r="2" />
  </>,
  calendar: <>
    <rect x="3" y="5" width="18" height="16" rx="2" />
    <path d="M7 3v4M17 3v4M3 10h18" />
  </>,
  layers: <>
    <path d="m12 3 9 5-9 5-9-5 9-5Z" />
    <path d="m3 12 9 5 9-5M3 16l9 5 9-5" />
  </>,
  shield: <>
    <path d="m12 2 9 4v6c0 5-3.6 8-9 10-5.4-2-9-5-9-10V6z" />
    <path d="m8 12 3 3 5-5" />
  </>,
  user: <>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21c0-4 3.6-6 8-6s8 2 8 6" />
  </>,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  chevron: <path d="m6 9 6 6 6-6" />,
  check: <path d="m4 12 5 5L20 6" />,
  route: <>
    <circle cx="5" cy="5" r="2" />
    <circle cx="19" cy="19" r="2" />
    <path d="M7 5h9a4 4 0 0 1 0 8H8a4 4 0 0 0 0 6h9" />
  </>,
  chart: <>
    <path d="M3 3v18h18" />
    <path d="m7 16 4-5 4 2 5-7" />
  </>,
  clock: <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </>,
}

function SideIcon({
  name,
  size = 19,
}: {
  name: MenuIcon
  size?: number
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {iconArt[name]}
    </svg>
  )
}

const roleLabels: Record<BusinessRole, string> = {
  MANAGER: 'Quản lý',
  PURCHASING_STAFF: 'Nhân viên mua hàng',
  SUPPLIER: 'Nhà cung cấp',
  TRANSPORT_PROVIDER: 'Đơn vị vận chuyển',
}

type MenuLink = {
  path: string
  label: string
  detail: string
  icon: MenuIcon
}

type MenuSection = {
  heading: string
  links: MenuLink[]
}

/* Năm chức năng DSS theo báo cáo */
const dssSteps = [
  {
    code: 'F1',
    label: 'Phối hợp nhu cầu',
    detail: 'Kiểm tra điều kiện gom hàng',
  },
  {
    code: 'F2',
    label: 'Xây dựng phương án',
    detail: 'Giao trực tiếp / qua Hub',
  },
  {
    code: 'F3',
    label: 'Phân bổ phương tiện',
    detail: 'Tải trọng và khả dụng',
  },
  {
    code: 'F4',
    label: 'Kiểm tra thời gian',
    detail: 'Khung giờ lấy và nhận hàng',
  },
  {
    code: 'F5',
    label: 'Đánh giá kinh tế',
    detail: 'So sánh chi phí phương án',
  },
]

/* Điều hướng theo quyền và route đang có */
function buildSections(
  roles: BusinessRole[],
): MenuSection[] {
  const isManager = roles.includes('MANAGER')
  const isStaff = roles.includes('PURCHASING_STAFF')
  const isSupplier = roles.includes('SUPPLIER')
  const isTransport = roles.includes('TRANSPORT_PROVIDER')

  const sections: MenuSection[] = [
    {
      heading: 'TỔNG QUAN',
      links: [
        {
          path: '/',
          label: 'Bảng điều khiển',
          detail: 'Tổng quan vận hành',
          icon: 'home',
        },
      ],
    },
  ]

  if (isManager || isStaff) {
    sections.push({
      heading: '01 · NHU CẦU MUA HÀNG',
      links: [
        {
          path: '/demands',
          label: 'Danh sách nhu cầu',
          detail: isManager
            ? 'Giám sát · chỉ xem'
            : 'Theo dõi và quản lý',
          icon: 'clipboard',
        },
        ...(!isManager && isStaff
          ? [
              {
                path: '/demands/new',
                label: 'Tạo nhu cầu mới',
                detail: 'Nhập yêu cầu giao hàng',
                icon: 'plus' as const,
              },
            ]
          : []),
      ],
    })
  }

  if (isSupplier) {
    sections.push({
      heading: '02 · NGUỒN CUNG',
      links: [
        {
          path: '/supplier/requests',
          label: 'Yêu cầu cung ứng',
          detail: 'Xác nhận hàng & giờ lấy',
          icon: 'layers',
        },
        {
          path: '/supplier/items',
          label: 'Danh mục mặt hàng',
          detail: 'Thông tin hàng cung ứng',
          icon: 'box',
        },
      ],
    })
  }


if (isTransport) {
  sections.push({
    heading: '03 · VẬN CHUYỂN',
    links: [
      {
        path: '/provider/capability',
        label: 'Năng lực vận chuyển',
        detail: 'Tổng quan phương tiện & phục vụ',
        icon: 'truck',
      },
      {
        path: '/provider/vehicle-offers',
        label: 'Cấu hình xe & báo giá',
        detail: 'Số lượng, loại xe và chi phí',
        icon: 'box',
      },
      {
        path: '/provider/availability',
        label: 'Lịch khả dụng',
        detail: 'Ngày, giờ và năng lực xe',
        icon: 'calendar',
      },
    ],
  })
}

  return sections
}

export default function AppLayout() {
  const { user, signOut, error } = useAuth()

  const [mobileOpen, setMobileOpen] = useState(false)
  const [dssOpen, setDssOpen] = useState(true)

  if (!user) return null

  const isManager = user.roles.includes('MANAGER')
  const isPurchasing = user.roles.includes('PURCHASING_STAFF')
  const isTransport = user.roles.includes('TRANSPORT_PROVIDER')


  const sections = buildSections(user.roles)

  const roleName = user.roles.length
    ? user.roles
        .map((role) => roleLabels[role])
        .join(' · ')
    : 'Chưa được gán vai trò'

  const accessNote = isManager
    ? 'Theo dõi nhu cầu; xem xét và phê duyệt phương án khi chức năng được tích hợp.'
    : isPurchasing
      ? 'Tạo và theo dõi nhu cầu theo phân quyền.'
      : isTransport
        ? 'Cập nhật năng lực, tiếp nhận kế hoạch được duyệt.'
        : 'Xác nhận cung ứng và điều kiện lấy hàng.'

  async function handleSignOut() {
    try {
      await signOut()
    } catch {
      // AuthContext chịu trách nhiệm xử lý lỗi đăng xuất.
    }
  }

  return (
    <div className="app-layout">

      {mobileOpen && (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-label="Đóng menu"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* SIDEBAR */}
      <aside
        className={
          `app-sidebar${mobileOpen ? ' app-sidebar--open' : ''}`
        }
      >

        {/* BRAND */}
        <NavLink
          to="/"
          className="sidebar-brand"
          aria-label="CoLogi - Trang chủ"
          onClick={() => setMobileOpen(false)}
        >
          <span className="sidebar-brand-mark">
            <img src="/images/logo.png" alt="" />
          </span>

          <span className="sidebar-brand-copy">
            <strong>
              CoLogi<span>.</span>
            </strong>
            <small>LOGISTICS WORKSPACE</small>
          </span>
        </NavLink>

        {/* WORKSPACE */}
        <div className="sidebar-workspace-card">
          <span className="sidebar-workspace-kicker">
            KHÔNG GIAN LÀM VIỆC
          </span>

          <strong>
            {isManager
              ? 'Quản lý điều phối'
              : isPurchasing
                ? 'Mua hàng'
                : isTransport
                  ? 'Vận chuyển'
                  : 'Cung ứng'}
          </strong>

          <small>
            {isManager
              ? 'Giám sát và phê duyệt'
              : roleName}
          </small>
        </div>

        {/* MENU CÓ THỂ CUỘN */}
        <div className="sidebar-scroll">

          <nav
            className="sidebar-nav"
            aria-label="Điều hướng chính"
          >
            {sections.map((section) => (
              <section
                className="sidebar-section"
                key={section.heading}
              >
                <p className="sidebar-section-label">
                  {section.heading}
                </p>

                {section.links.map((item) => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    end={
                      item.path === '/' ||
                      item.path === '/demands'
                    }
                    onClick={() => setMobileOpen(false)}
                    className={({ isActive }) =>
                      `sidebar-link${isActive ? ' active' : ''}`
                    }
                  >
                    <span className="sidebar-link-icon">
                      <SideIcon name={item.icon} />
                    </span>

                    <span className="sidebar-link-label">
                      <strong>{item.label}</strong>
                      <small>{item.detail}</small>
                    </span>
                  </NavLink>
                ))}
              </section>
            ))}
          
          </nav>

          {/* HỖ TRỢ LẬP KẾ HOẠCH */}
          {isManager && (
            <section className="sidebar-section sidebar-dss-section">
              <button
                type="button"
                className="sidebar-section-toggle"
                aria-expanded={dssOpen}
                aria-controls="cologi-dss-steps"
                onClick={() =>
                  setDssOpen((value) => !value)
                }
              >
                <span>04 · HỖ TRỢ LẬP KẾ HOẠCH</span>
                <SideIcon name="chevron" size={15} />
              </button>

              {dssOpen && (
                <div id="cologi-dss-steps">
                  <NavLink
                    to="/dss"
                    onClick={() => setMobileOpen(false)}
                    className={({ isActive }) =>
                      `sidebar-link${isActive ? ' active' : ''}`
                    }
                  >
                    <span className="sidebar-link-icon">
                      <SideIcon name="chart" />
                    </span>

                    <span className="sidebar-link-label">
                      <strong>Tổng quan lập kế hoạch</strong>
                      <small>
                        Kịch bản & kết quả mô phỏng
                      </small>
                    </span>
                  </NavLink>

                  <ol
                    className="sidebar-dss-list"
                    aria-label="Năm bước hỗ trợ lập kế hoạch"
                  >
                    {dssSteps.map((step) => (
                      <li
                        key={step.code}
                        className="sidebar-dss-step"
                      >
                        <span className="sidebar-dss-number">
                          {step.code}
                        </span>

                        <span className="sidebar-dss-copy">
                          <strong>{step.label}</strong>
                          <small>{step.detail}</small>
                        </span>
                      </li>
                    ))}
                  </ol>

                  <p className="sidebar-dss-note">
                    Chức năng F1–F5 đang được mô phỏng
                    trong trang tổng quan lập kế hoạch.
                  </p>
                </div>
              )}
            </section>
          )}

          {/* QUYẾT ĐỊNH VÀ KẾ HOẠCH */}
          {isManager && (
            <section className="sidebar-section">
              <p className="sidebar-section-label">
                05 · QUYẾT ĐỊNH & KẾ HOẠCH
              </p>

              <div
                className="sidebar-coming"
                aria-disabled="true"
              >
                <span className="sidebar-link-icon">
                  <SideIcon name="shield" />
                </span>
                <span className="sidebar-link-label">
                  <strong>Phê duyệt phương án</strong>
                  <small>Chờ tích hợp module</small>
                </span>
              </div>

              <div
                className="sidebar-coming"
                aria-disabled="true"
              >
                <span className="sidebar-link-icon">
                  <SideIcon name="route" />
                </span>
                <span className="sidebar-link-label">
                  <strong>Kế hoạch cuối cùng</strong>
                  <small>Bàn giao vận chuyển</small>
                </span>
              </div>

              <div
                className="sidebar-coming"
                aria-disabled="true"
              >
                <span className="sidebar-link-icon">
                  <SideIcon name="clock" />
                </span>
                <span className="sidebar-link-label">
                  <strong>Lịch sử quyết định</strong>
                  <small>Nhật ký và phiên bản</small>
                </span>
              </div>
            </section>
          )}

          {/* XÁC NHẬN CHUYẾN */}
          {isTransport && (
            <section className="sidebar-section">
              <p className="sidebar-section-label">
                KẾ HOẠCH ĐƯỢC DUYỆT
              </p>

              <div
                className="sidebar-coming"
                aria-disabled="true"
              >
                <span className="sidebar-link-icon">
                  <SideIcon name="check" />
                </span>
                <span className="sidebar-link-label">
                  <strong>Xác nhận chuyến</strong>
                  <small>Chờ tích hợp module</small>
                </span>
              </div>
            </section>
          )}

          {/* TÀI KHOẢN */}
          <section className="sidebar-section">
            <p className="sidebar-section-label">
              TÀI KHOẢN
            </p>

            <NavLink
              to="/profile"
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                `sidebar-link${isActive ? ' active' : ''}`
              }
            >
              <span className="sidebar-link-icon">
                <SideIcon name="user" />
              </span>

              <span className="sidebar-link-label">
                <strong>Hồ sơ cá nhân</strong>
                <small>Thông tin & vai trò</small>
              </span>
            </NavLink>
          </section>

        </div>
        {/* KẾT THÚC sidebar-scroll */}

        {/* SIDEBAR FOOTER */}
        <div className="sidebar-footer">
          <div className="sidebar-access-card">
            <SideIcon name="shield" size={18} />

            <div>
              <strong>Quyền truy cập</strong>
              <small>{accessNote}</small>
            </div>
          </div>

          <span className="sidebar-version">
            COLOGI DSS · MVP 2026
          </span>
        </div>

      </aside>

      {/* MAIN LAYOUT */}
      <div className="app-main">
        <header className="app-header">
          <div className="app-header-left">
            <button
              type="button"
              className="sidebar-mobile-button"
              aria-label="Mở thanh điều hướng"
              onClick={() => setMobileOpen(true)}
            >
              <SideIcon name="menu" size={22} />
            </button>

            <div>
              <span className="header-label">
                COLOGI WORKSPACE
              </span>

              <span className="header-page-title">
                Quản lý vận hành
              </span>
            </div>
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
