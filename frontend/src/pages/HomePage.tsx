import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../contexts/useAuth'
import { apiRequest } from '../services/api/client'
import { listDemands } from '../services/api/demands'
import { listSupplierRequests } from '../services/api/suppliers'
import type { BusinessRole } from '../types/auth'
import type { DeliveryDemand, DemandStatus } from '../types/demand'
import type { SupplierRequest } from '../types/supplier'
import './HomePage.css'
import RoleAnalytics, {
  DonutChart,
} from './foundation/RoleAnalytics'
type IconName = 'grid' | 'box' | 'truck' | 'clock' | 'check' | 'arrow' | 'chevron'
  | 'shield' | 'refresh' | 'calendar' | 'alert' | 'file' | 'layers' | 'spark' | 'user'

function Icon({ name, size = 19 }: { name: IconName; size?: number }) {
  const shapes: Record<IconName, ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1.4" /><rect x="14" y="3" width="7" height="7" rx="1.4" /><rect x="3" y="14" width="7" height="7" rx="1.4" /><rect x="14" y="14" width="7" height="7" rx="1.4" /></>,
    box: <><path d="m12 2 9 5-9 5-9-5 9-5ZM3 7v10l9 5 9-5V7M12 12v10" /></>,
    truck: <><path d="M2 6h12v11H2zM14 10h4l4 4v3h-8" /><circle cx="7" cy="18" r="2" /><circle cx="18" cy="18" r="2" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    check: <path d="m4 12 5 5L20 6" />,
    arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
    chevron: <path d="m9 6 6 6-6 6" />,
    shield: <><path d="m12 2 9 4v6c0 5-3.6 8-9 10-5.4-2-9-5-9-10V6z" /><path d="m8 12 3 3 5-5" /></>,
    refresh: <><path d="M20 7v5h-5M4 17v-5h5" /><path d="M5.5 9a7 7 0 0 1 12.5-2L20 12M4 12l2 5a7 7 0 0 0 12-2" /></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M7 3v4M17 3v4M3 10h18" /></>,
    alert: <><path d="m12 3 10 18H2L12 3Z" /><path d="M12 9v5m0 4h.01" /></>,
    file: <><rect x="5" y="3" width="14" height="18" rx="2" /><path d="M9 9h6m-6 4h6m-6 4h3" /></>,
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m3 12 9 5 9-5M3 16l9 5 9-5" /></>,
    spark: <path d="m12 2 2.2 7.8L22 12l-7.8 2.2L12 22l-2.2-7.8L2 12l7.8-2.2Z" />,
    user: <><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 3.6-6 8-6s8 2 8 6" /></>,
  }
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{shapes[name]}</svg>
}

type ProviderOffer = { id: number; is_active: boolean; available_vehicle_count: number }
type ProviderCoverage = { id: number; coverage_status: string; can_pickup: boolean }
type ProviderSlot = {
  id: number
  service_date: string
  start_time: string
  end_time: string
  availability_status: string
  available_vehicle_count: number
}
type ProviderProfile = { provider_name: string; service_region: string }
type TransportData = {
  offers: ProviderOffer[]
  coverages: ProviderCoverage[]
  slots: ProviderSlot[]
  profile: ProviderProfile
}
type Metric = { label: string; value: number; description: string; icon: IconName; tone: string }
type WorkItem = { id: string; title: string; detail: string; status: string; tone: string; to?: string }
type Step = { label: string; value: number; color: string }
type Shortcut = { label: string; description: string; to: string; icon: IconName }

const roleNames: Record<BusinessRole, string> = {
  MANAGER: 'Quản lý',
  PURCHASING_STAFF: 'Nhân viên mua hàng',
  SUPPLIER: 'Nhà cung cấp',
  TRANSPORT_PROVIDER: 'Đơn vị vận chuyển',
}
const roleOrder: BusinessRole[] = ['MANAGER', 'PURCHASING_STAFF', 'SUPPLIER', 'TRANSPORT_PROVIDER']
const demandLabels: Record<DemandStatus, string> = {
  DRAFT: 'Bản nháp', SUBMITTED: 'Đã gửi', PLANNING: 'Đang lập kế hoạch',
  PLANNED: 'Đã lập kế hoạch', CANCELLED: 'Đã hủy',
}
const numberFormat = new Intl.NumberFormat('vi-VN')

function localDay(offset = 0) {
  const day = new Date()
  day.setHours(12, 0, 0, 0)
  day.setDate(day.getDate() + offset)
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`
}
function shortDate(value?: string | null) {
  if (!value) return 'Chưa có ngày'
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
  return match ? `${match[3]}/${match[2]}/${match[1]}` : value
}
function dashboardError(error: unknown) {
  return error instanceof Error ? error.message : 'Không thể tải dữ liệu từ hệ thống.'
}
function countStatus(rows: DeliveryDemand[], status: DemandStatus) {
  return rows.filter((row) => row.status === status).length
}

type AccountNavItem = {
  label: string
  description: string
  to: string
}


function AccountMenu({
  activeRole,
  availableRoles,
  onRoleChange,
}: {
  activeRole: BusinessRole
  availableRoles: BusinessRole[]
  onRoleChange: (role: BusinessRole) => void
}) {
  const { user } = useAuth()
  const menuRef = useRef<HTMLDetailsElement>(null)
  const [showProfile, setShowProfile] = useState(false)

  useEffect(() => {
    function handleOutside(event: PointerEvent) {
      if (!menuRef.current?.contains(event.target as Node)) {
        menuRef.current?.removeAttribute('open')
        setShowProfile(false)
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        menuRef.current?.removeAttribute('open')
        setShowProfile(false)
      }
    }

    document.addEventListener('pointerdown', handleOutside)
    document.addEventListener('keydown', handleEscape)

    return () => {
      document.removeEventListener('pointerdown', handleOutside)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [])

  if (!user) return null

  const canCreateDemand =
    activeRole === 'PURCHASING_STAFF' &&
    !user.roles.includes('MANAGER')

  const navItems: AccountNavItem[] =
    activeRole === 'MANAGER'
      ? [
          {
            label: 'Danh sách nhu cầu',
            description: 'Chỉ xem và theo dõi',
            to: '/demands',
          },
        ]
      : activeRole === 'PURCHASING_STAFF'
        ? [
            {
              label: 'Danh sách nhu cầu',
              description: 'Theo dõi hồ sơ được phân quyền',
              to: '/demands',
            },
            ...(canCreateDemand
              ? [
                  {
                    label: 'Tạo demand mới',
                    description: 'Tạo yêu cầu giao hàng',
                    to: '/demands/new',
                  },
                ]
              : []),
          ]
        : activeRole === 'SUPPLIER'
          ? [
              {
                label: 'Yêu cầu cung ứng',
                description: 'Kiểm tra và phản hồi',
                to: '/supplier/requests',
              },
              {
                label: 'Danh mục mặt hàng',
                description: 'Thông tin cung ứng',
                to: '/supplier/items',
              },
            ]
          : []

  function closeMenu() {
    menuRef.current?.removeAttribute('open')
    setShowProfile(false)
  }

  return (
    <details className="clh-account-menu" ref={menuRef}>
      <summary
        className="clh-account-trigger"
        aria-label="Mở hồ sơ và chọn vai trò"
      >
        <Icon name="user" size={18} />

        <span className="clh-account-trigger-label">
          Hồ sơ &amp; vai trò
        </span>

        <Icon name="chevron" size={16} />
      </summary>

      <div className="clh-account-dropdown">
        {showProfile ? (
          <>
            <div className="clh-account-topline">
              <button
                type="button"
                className="clh-account-back"
                onClick={() => setShowProfile(false)}
              >
                ← Quay lại
              </button>

              <strong>Hồ sơ tài khoản</strong>
            </div>

            <div className="clh-account-profile-hero">
              <span className="clh-account-avatar large">
                {user.full_name.trim().charAt(0).toUpperCase() || 'C'}
              </span>

              <div>
                <strong>{user.full_name}</strong>
                <small>Thông tin tài khoản đang đăng nhập</small>
              </div>
            </div>

            <dl className="clh-account-details">
              <div>
                <dt>Họ tên</dt>
                <dd>{user.full_name}</dd>
              </div>
              <div>
                <dt>Email</dt>
                <dd>{user.email}</dd>
              </div>
              <div>
                <dt>Mã tài khoản</dt>
                <dd>#{user.id}</dd>
              </div>
              <div>
                <dt>Vai trò</dt>
                <dd>
                  {user.roles.map((r) => roleNames[r]).join(', ')}
                </dd>
              </div>
            </dl>

            <p className="clh-account-hint">
              Hồ sơ hiện chỉ xem; chưa có API chỉnh sửa
              thông tin tài khoản.
            </p>
          </>
        ) : (
          <>
            <button
              type="button"
              className="clh-account-profile-btn"
              onClick={() => setShowProfile(true)}
            >
              <Icon name="user" size={18} />
              Xem hồ sơ cá nhân
              <span>→</span>
            </button>

            <div className="clh-account-group">
              <p className="clh-account-label">
                KHÔNG GIAN LÀM VIỆC
              </p>

              <div className="clh-account-roles">
                {availableRoles.map((role) => (
                  <button
                    key={role}
                    type="button"
                    className={
                      role === activeRole ? 'selected' : ''
                    }
                    aria-pressed={role === activeRole}
                    onClick={() => {
                      onRoleChange(role)
                      closeMenu()
                    }}
                  >
                    {roleNames[role]}
                    {role === activeRole ? ' ✓' : ''}
                  </button>
                ))}
              </div>
            </div>

            <nav
              className="clh-account-group"
              aria-label="Điều hướng nghiệp vụ"
            >
              <p className="clh-account-label">
                TRUY CẬP NHANH · {roleNames[activeRole].toUpperCase()}
              </p>

              {navItems.length ? (
                navItems.map((item) => (
                  <Link
                    className="clh-account-navlink"
                    key={item.to}
                    to={item.to}
                    onClick={closeMenu}
                  >
                    <span>
                      <strong>{item.label}</strong>
                      <small>{item.description}</small>
                    </span>

                    <Icon name="arrow" size={16} />
                  </Link>
                ))
              ) : (
                <p className="clh-account-hint">
                  Chưa có route quản lý vận chuyển
                  trong App.tsx. Bạn vẫn có thể xem
                  dữ liệu từ Dashboard.
                </p>
              )}
            </nav>

            <p className="clh-account-hint">
              Đăng xuất bằng nút trên Header chung của CoLogi.
            </p>
          </>
        )}
      </div>
    </details>
  )
}

export default function HomePage() {
  const { user } = useAuth()
  const availableRoles = roleOrder.filter((role) => user?.roles.includes(role))
  const [chosenRole, setChosenRole] = useState<BusinessRole | null>(null)
  const activeRole = chosenRole && availableRoles.includes(chosenRole)
    ? chosenRole : availableRoles[0]
  const [demands, setDemands] = useState<DeliveryDemand[]>([])
  const [requests, setRequests] = useState<SupplierRequest[]>([])
  const [transport, setTransport] = useState<TransportData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  useEffect(() => {
    if (!activeRole) return
    let active = true

    async function loadOverview() {
      setLoading(true)
      setError('')
      try {
        if (activeRole === 'MANAGER' || activeRole === 'PURCHASING_STAFF') {
          const data = await listDemands()
          if (active) setDemands(data)
        } else if (activeRole === 'SUPPLIER') {
          const data = await listSupplierRequests()
          if (active) setRequests(data)
        } else {
          const [offers, slots, coverages, profile] = await Promise.all([
            apiRequest<ProviderOffer[]>('/providers/me/vehicle-offers/'),
            apiRequest<ProviderSlot[]>('/providers/me/availability/'),
            apiRequest<ProviderCoverage[]>('/providers/me/supplier-coverages/'),
            apiRequest<ProviderProfile>('/providers/me/'),
          ])
          if (active) setTransport({ offers, slots, coverages, profile })
        }
        if (active) setLastUpdated(new Date())
      } catch (requestError) {
        if (active) setError(dashboardError(requestError))
      } finally {
        if (active) setLoading(false)
      }
    }
    void loadOverview()
    return () => { active = false }
  }, [activeRole, reloadKey])

  if (!user) return null

  const isPurchasing = activeRole === 'MANAGER' || activeRole === 'PURCHASING_STAFF'
  // Backend policy: MANAGER is read-only, including dual-role accounts.
  const canModifyDemands =
  activeRole === 'PURCHASING_STAFF' &&
  !user.roles.includes('MANAGER')
  const isSupplier = activeRole === 'SUPPLIER'
  const isTransport = activeRole === 'TRANSPORT_PROVIDER'
  const firstName = user.full_name.trim().split(/\s+/).at(-1) || 'bạn'
  const today = localDay()
  const nearDay = localDay(2)
  const nextWeek = localDay(7)
  const openDemands = demands.filter((row) => row.status === 'SUBMITTED' || row.status === 'PLANNING')
  const nearDemands = openDemands.filter((row) => row.requested_date <= nearDay)
  const overdueDemands = nearDemands.filter((row) => row.requested_date < today)
  const waitingRequests = requests.filter((row) => row.request_status === 'WAITING')
  
const supplierResponseSlices = [
  {
    label: 'Chờ phản hồi',
    value: requests.filter(
      (row) => row.request_status === 'WAITING'
    ).length,
    color: '#D5B85A',
  },
  {
    label: 'Xác nhận đủ',
    value: requests.filter(
      (row) =>
        row.request_status === 'RESPONDED' &&
        row.confirmation_status === 'CONFIRMED'
    ).length,
    color: '#1E6B3A',
  },
  {
    label: 'Xác nhận một phần',
    value: requests.filter(
      (row) =>
        row.request_status === 'RESPONDED' &&
        row.confirmation_status === 'PARTIAL'
    ).length,
    color: '#6496AD',
  },
  {
    label: 'Từ chối',
    value: requests.filter(
      (row) =>
        row.request_status === 'RESPONDED' &&
        row.confirmation_status === 'DECLINED'
    ).length,
    color: '#BD756B',
  },
  {
    label: 'Khác',
    value: requests.filter(
      (row) =>
        row.request_status === 'RESPONDED' &&
        !['CONFIRMED', 'PARTIAL', 'DECLINED'].includes(
          row.confirmation_status
        )
    ).length,
    color: '#9BAE9F',
  },
]

const managerDemandSlices = [
  {
    label: 'Bản nháp',
    value: countStatus(demands, 'DRAFT'),
    color: '#1E6B3A',
  },
  {
    label: 'Đã gửi',
    value: countStatus(demands, 'SUBMITTED'),
    color: '#D5B85A',
  },
  {
    label: 'Đang lập kế hoạch',
    value: countStatus(demands, 'PLANNING'),
    color: '#4BB169',
  },
  {
    label: 'Đã lập kế hoạch',
    value: countStatus(demands, 'PLANNED'),
    color: '#6496AD',
  },
  {
    label: 'Đã hủy',
    value: countStatus(demands, 'CANCELLED'),
    color: '#9BAE9F',
  },
]

  const soonRequests = waitingRequests.filter((row) => row.demand.requested_date <= nearDay)
  const activeOffers = transport?.offers.filter((row) => row.is_active) ?? []
  const activeCoverage = transport?.coverages.filter((row) => row.coverage_status === 'ACTIVE' && row.can_pickup) ?? []
  const futureSlots = (transport?.slots ?? []).filter((slot) => slot.service_date >= today)
  const weekSlots = futureSlots.filter((slot) => slot.service_date <= nextWeek)
  const availableSlots = weekSlots.filter((slot) => slot.availability_status === 'AVAILABLE')

  let metrics: Metric[] = []
  let workflow: Step[] = []
  let workItems: WorkItem[] = []
  let shortcuts: Shortcut[] = []
  let alertText = ''
  let heroCaption = ''
  let heroTitle = ''
  let heroAccent = ''
  let heroDescription = ''

  if (isPurchasing) {
    metrics = [
      { label: 'Tổng nhu cầu', value: demands.length, description: 'Trong phạm vi được cấp quyền', icon: 'layers', tone: 'green' },
      { label: 'Bản nháp', value: countStatus(demands, 'DRAFT'), description: 'Cần hoàn thiện và gửi', icon: 'file', tone: 'gold' },
      { label: 'Chờ lập kế hoạch', value: openDemands.length, description: 'Đã gửi hoặc đang xử lý', icon: 'clock', tone: 'blue' },
      { label: 'Đã lập kế hoạch', value: countStatus(demands, 'PLANNED'), description: 'Theo trạng thái nhu cầu', icon: 'check', tone: 'mint' },
    ]
    workflow = [
      { label: 'Bản nháp', value: countStatus(demands, 'DRAFT'), color: 'gold' },
      { label: 'Đã gửi', value: countStatus(demands, 'SUBMITTED'), color: 'blue' },
      { label: 'Đang lập kế hoạch', value: countStatus(demands, 'PLANNING'), color: 'mint' },
      { label: 'Đã lập kế hoạch', value: countStatus(demands, 'PLANNED'), color: 'green' },
    ]
    
    if (activeRole === 'MANAGER') {
      // Manager giám sát tất cả demand trong phạm vi API cho phép.
      // Ưu tiên demand chưa được lập kế hoạch.
      const needsMonitoring = [...demands]
        .filter(
          (row) =>
            row.status === 'SUBMITTED' ||
            row.status === 'PLANNING'
        )
        .sort((a, b) =>
          a.requested_date.localeCompare(b.requested_date)
        )

      // Nếu không có hồ sơ đang chờ lập kế hoạch,
      // hiển thị những demand gần đây để Manager vẫn có
      // thông tin theo dõi, không tạo dữ liệu giả.
      const managerRows = needsMonitoring.length
        ? needsMonitoring.slice(0, 5)
        : [...demands]
            .filter((row) => row.status !== 'CANCELLED')
            .sort((a, b) => b.id - a.id)
            .slice(0, 5)

      workItems = managerRows.map((row) => ({
        id: `d-${row.id}`,
        title: `${row.demand_code} · ${row.outlet_name}`,
        detail:
          `Ngày nhận ${shortDate(row.requested_date)} · ${row.supplier_name}`,
        status: demandLabels[row.status],
        tone:
          row.status === 'DRAFT'
            ? 'gold'
            : row.status === 'PLANNED'
              ? 'green'
              : 'blue',
        // Manager chỉ được xem chi tiết, không được chỉnh sửa.
        to: `/demands/${row.id}`,
      }))
    } else {
      // Purchasing Staff chỉ thấy demand do chính mình tạo.
      workItems = [...demands]
        .filter((row) => row.created_by_id === user.id)
        .filter(
          (row) =>
            row.status === 'DRAFT' ||
            row.status === 'SUBMITTED' ||
            row.status === 'PLANNING'
        )
        .sort(
          (a, b) =>
            Number(a.status !== 'DRAFT') -
              Number(b.status !== 'DRAFT') ||
            a.requested_date.localeCompare(b.requested_date)
        )
        .slice(0, 5)
        .map((row) => ({
          id: `d-${row.id}`,
          title: `${row.demand_code} · ${row.outlet_name}`,
          detail:
            `Ngày nhận ${shortDate(row.requested_date)} · ${row.supplier_name}`,
          status: demandLabels[row.status],
          tone: row.status === 'DRAFT' ? 'gold' : 'blue',
          to:
            row.status === 'DRAFT' && canModifyDemands
              ? `/demands/${row.id}/edit`
              : `/demands/${row.id}`,
        }))
    }

    alertText = overdueDemands.length
      ? `${overdueDemands.length} nhu cầu chưa có trạng thái “Đã lập kế hoạch” và đã qua ngày nhận dự kiến.`
      : nearDemands.length
        ? `${nearDemands.length} nhu cầu có ngày nhận trong vòng 2 ngày tới nhưng chưa ở trạng thái “Đã lập kế hoạch”.`
        : ''
    heroCaption = activeRole === 'MANAGER' ? 'MANAGEMENT COMMAND CENTER' : 'PURCHASING WORKSPACE'
    heroTitle = activeRole === 'MANAGER' ? 'Nắm toàn cảnh.' : 'Rõ từng nhu cầu.'
    heroAccent = activeRole === 'MANAGER' ? 'Chủ động từng quyết định.' : 'Nhanh từng bước xử lý.'
    heroDescription = activeRole === 'MANAGER'
      ? 'Tổng hợp trạng thái nhu cầu, nhận diện việc cần theo dõi và đi đến các màn hình nghiệp vụ từ một nơi.'
      : 'Theo dõi từ bản nháp đến lúc lập kế hoạch, tập trung vào những nhu cầu cần xử lý tiếp.'
  } else if (isSupplier) {
    metrics = [
      { label: 'Tổng yêu cầu', value: requests.length, description: 'Yêu cầu gửi tới bạn', icon: 'layers', tone: 'green' },
      { label: 'Chờ phản hồi', value: waitingRequests.length, description: 'Cần xác nhận số lượng', icon: 'clock', tone: 'gold' },
      { label: 'Đã phản hồi', value: requests.filter((row) => row.request_status === 'RESPONDED').length, description: 'Đã ghi nhận phản hồi', icon: 'check', tone: 'mint' },
      { label: 'Xác nhận một phần', value: requests.filter((row) => row.confirmation_status === 'PARTIAL').length, description: 'Theo kết quả xác nhận', icon: 'box', tone: 'blue' },
    ]
    workflow = [
      { label: 'Chờ phản hồi', value: waitingRequests.length, color: 'gold' },
      { label: 'Đã phản hồi', value: requests.filter((row) => row.request_status === 'RESPONDED').length, color: 'green' },
    ]

const supplierWorkList =
  waitingRequests.length > 0
    ? [...waitingRequests].sort((a, b) =>
        a.demand.requested_date.localeCompare(
          b.demand.requested_date
        )
      )
    : [...requests]
        .filter(
          (row) => row.request_status === 'RESPONDED'
        )
        .sort((a, b) =>
          (b.responded_at ?? '').localeCompare(
            a.responded_at ?? ''
          )
        )

workItems = supplierWorkList
  .slice(0, 5)
  .map((row) => ({
    id: `s-${row.id}`,

    title:
      `${row.request_code} · ` +
      row.demand.outlet_name,

    detail:
      `Ngày nhận ${shortDate(row.demand.requested_date)}` +
      ` · ${row.items.length} mặt hàng`,

    status:
      row.request_status === 'WAITING'
        ? 'Chờ phản hồi'
        : 'Đã phản hồi',

    tone:
      row.request_status === 'WAITING'
        ? 'gold'
        : 'green',

    to: `/supplier/requests/${row.id}`,
  }))
    shortcuts = [
      { label: 'Hộp thư yêu cầu', description: 'Xác nhận yêu cầu cung ứng', to: '/supplier/requests', icon: 'file' },
      { label: 'Danh mục mặt hàng', description: 'Quản lý các mặt hàng của bạn', to: '/supplier/items', icon: 'box' },
    ]
    alertText = soonRequests.length
      ? `${soonRequests.length} yêu cầu chưa phản hồi có ngày nhận hàng trong vòng 2 ngày tới hoặc đã qua.` : ''
    heroCaption = 'SUPPLIER WORKSPACE'
    heroTitle = 'Phản hồi kịp thời.'
    heroAccent = 'Cung ứng rõ ràng.'
    heroDescription = 'Kiểm tra yêu cầu, xác nhận khả năng cung ứng và theo dõi phản hồi của bạn trên một màn hình.'
  } else if (isTransport) {
    metrics = [
      { label: 'Loại xe hoạt động', value: activeOffers.length, description: 'Báo giá đang kích hoạt', icon: 'truck', tone: 'green' },
      { label: 'Số xe theo báo giá', value: activeOffers.reduce((sum, row) => sum + row.available_vehicle_count, 0), description: 'Năng lực khai báo, không phải lịch ngày', icon: 'box', tone: 'blue' },
      { label: 'Khung lịch khả dụng', value: availableSlots.length, description: 'Trong 7 ngày tới', icon: 'calendar', tone: 'mint' },
      { label: 'NCC có thể lấy hàng', value: activeCoverage.length, description: 'Phạm vi phục vụ đang hoạt động', icon: 'layers', tone: 'gold' },
    ]
    workflow = [
      { label: 'Khung có xe', value: availableSlots.length, color: 'green' },
      { label: 'Khung không khả dụng', value: weekSlots.length - availableSlots.length, color: 'gold' },
    ]
    workItems = [...futureSlots]
      .sort((a, b) => `${a.service_date} ${a.start_time}`.localeCompare(`${b.service_date} ${b.start_time}`))
      .slice(0, 5)
      .map((slot) => ({
        id: `t-${slot.id}`, title: `Lịch xe · ${shortDate(slot.service_date)}`,
        detail: `${slot.start_time.slice(0, 5)}–${slot.end_time.slice(0, 5)} · ${slot.available_vehicle_count} xe khai báo`,
        status: slot.availability_status === 'AVAILABLE' ? 'Khả dụng' : 'Không khả dụng',
        tone: slot.availability_status === 'AVAILABLE' ? 'green' : 'gold',
      }))
    alertText = activeOffers.length === 0
      ? 'Chưa có báo giá phương tiện nào đang hoạt động trong hồ sơ.'
      : availableSlots.length === 0
        ? 'Chưa có khung lịch xe ở trạng thái khả dụng cho 7 ngày tới.' : ''
    heroCaption = 'TRANSPORT PROVIDER WORKSPACE'
    heroTitle = 'Năng lực sẵn sàng.'
    heroAccent = 'Lịch xe minh bạch.'
    heroDescription = 'Xem phương tiện, lịch xe và phạm vi lấy hàng từ dữ liệu đã khai báo cho đơn vị vận chuyển.'
  }

  const workflowTotal = workflow.reduce((sum, item) => sum + item.value, 0)
  const topAction = shortcuts[0]
  const dateLabel = new Intl.DateTimeFormat('vi-VN', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date())
  const updatedLabel = lastUpdated && !loading && !error
    ? `Cập nhật ${new Intl.DateTimeFormat('vi-VN', { hour: '2-digit', minute: '2-digit' }).format(lastUpdated)}`
    : loading ? 'Đang đồng bộ' : error ? 'Kết nối gián đoạn' : 'Chưa có dữ liệu'

  return (
    <main className="clh">
      <header className="clh-heading">
        <div>
          <p className="clh-overline"><span className="clh-pulse" /> COLOGI OPERATIONS <span className="clh-separator" /> {dateLabel}</p>
          <h1>Chào {firstName}<span className="clh-gold">.</span></h1>
          <p className="clh-subheading">Đây là những điều quan trọng trong không gian làm việc của bạn hôm nay.</p>
        </div>
        
<div className="clh-heading-actions">
  <button
    type="button"
    className="clh-refresh"
    onClick={() => setReloadKey((value) => value + 1)}
    disabled={loading}
  >
    <Icon name="refresh" size={17} />
    Làm mới dữ liệu
  </button>

  {activeRole && (
    <AccountMenu
      activeRole={activeRole}
      availableRoles={availableRoles}
      onRoleChange={setChosenRole}
    />
  )}
</div>

      </header>


      <section className="clh-hero">
        <div className="clh-hero-copy">
          <div className="clh-hero-eyebrow"><span /> {heroCaption || 'COLOGI WORKSPACE'}</div>
          <h2>{heroTitle || 'Điều hành tập trung.'}<br /><em>{heroAccent || 'Minh bạch dữ liệu.'}</em></h2>
          <p>{heroDescription || 'Dữ liệu và các thao tác được hiển thị theo quyền truy cập hiện tại.'}</p>
          <div className="clh-hero-actions">
            {topAction ? <Link className="clh-gold-button" to={topAction.to}>Bắt đầu làm việc <Icon name="arrow" size={18} /></Link>
              : <span className="clh-hero-feature">Dữ liệu phương tiện đã kết nối API</span>}
            <span className="clh-hero-role"><Icon name="shield" size={15} /> {activeRole ? roleNames[activeRole] : 'Chưa phân quyền'}</span>
          </div>
        </div>
        <div className="clh-hero-visual" aria-hidden="true">
          <div className="clh-visual-halo" />
          <div className="clh-visual-card"><div className="clh-visual-header"><span className="clh-pulse" /> OPERATIONS FLOW <span>01–03</span></div>
            <div className="clh-flow-node"><Icon name="file" /><span><b>Nhu cầu</b><small>Demand</small></span><i>01</i></div>
            <div className="clh-flow-connector" />
            <div className="clh-flow-node"><Icon name="box" /><span><b>Cung ứng</b><small>Supplier</small></span><i>02</i></div>
            <div className="clh-flow-connector" />
            <div className="clh-flow-node"><Icon name="truck" /><span><b>Vận chuyển</b><small>Transport</small></span><i>03</i></div>
          </div>
        </div>
      </section>

      {error && <div className="clh-alert clh-api-alert" role="alert"><Icon name="alert" size={20} /><div><strong>Không thể đồng bộ dữ liệu</strong><p>{error}. Kiểm tra Backend rồi chọn “Làm mới dữ liệu”.</p></div></div>}
      {!loading && !error && alertText && <div className="clh-alert" role="status"><Icon name="alert" size={20} /><div><strong>Điểm cần chú ý</strong><p>{alertText}</p></div></div>}

      <section className="clh-metrics" aria-label="Chỉ số theo vai trò">
        {metrics.length ? metrics.map((metric) => (
          <article className="clh-metric" key={metric.label}>
            <div className="clh-metric-top"><span>{metric.label}</span><span className={`clh-metric-icon ${metric.tone}`}><Icon name={metric.icon} size={19} /></span></div>
            {loading ? <div className="clh-skeleton clh-value-skeleton" /> : <strong className="clh-metric-value">{error ? '—' : numberFormat.format(metric.value)}</strong>}
            <p>{metric.description}</p>
          </article>
        )) : <article className="clh-metric clh-no-role">Tài khoản chưa có vai trò nghiệp vụ để hiển thị chỉ số.</article>}
      </section>

      <div className="clh-main-grid">
        <section className="clh-panel clh-tasks">
          <div className="clh-section-head"><div><span className="clh-section-eyebrow">
  {activeRole === 'MANAGER'
    ? 'MANAGEMENT WATCHLIST'
    : 'PRIORITY INBOX'}
</span>
<h3>
  {isTransport
    ? 'Lịch xe sắp tới'
    : isSupplier
      ? waitingRequests.length > 0
        ? 'Yêu cầu cần phản hồi'
        : 'Phản hồi gần đây'
      : activeRole === 'MANAGER'
        ? 'Nhu cầu cần theo dõi'
        : 'Công việc cần xử lý'}
</h3>

<p>
  {activeRole === 'MANAGER'
    ? 'Theo dõi nhu cầu của các nhân viên trong phạm vi quản lý · Chỉ xem'
    : activeRole === 'PURCHASING_STAFF'
      ? 'Chỉ hiển thị demand do chính tài khoản của bạn tạo'
      : activeRole === 'SUPPLIER'
        ? 'Các yêu cầu cung ứng đang cần phản hồi'
        : 'Các khung lịch xe sắp tới'}
</p>
</div><span className="clh-section-icon"><Icon name={isTransport ? 'calendar' : 'file'} /></span></div>
          {loading ? <div className="clh-task-loading"><div className="clh-skeleton" /><div className="clh-skeleton" /><div className="clh-skeleton" /></div>
            : error ? <div className="clh-empty"><Icon name="alert" size={23} /><strong>Chưa thể tải danh sách</strong><p>Vui lòng kiểm tra kết nối Backend.</p></div>
              : workItems.length ? <div className="clh-task-list">{workItems.map((item) => {
                const content = <><span className="clh-task-icon"><Icon name={isTransport ? 'truck' : 'file'} size={19} /></span><span className="clh-task-copy"><b>{item.title}</b><small>{item.detail}</small></span><span className={`clh-tag ${item.tone}`}>{item.status}</span>{item.to && <Icon name="chevron" size={17} />}</>
                return item.to
                  ? <Link className="clh-task-row" to={item.to} key={item.id}>{content}</Link>
                  : <div className="clh-task-row" key={item.id}>{content}</div>
              })}</div>
                : <div className="clh-empty"><Icon name="check" size={25} /><strong>{isTransport ? 'Chưa có lịch xe sắp tới' : 'Chưa có công việc trong danh sách ưu tiên'}</strong><p>{isTransport ? 'Lịch được lấy từ hồ sơ phương tiện của bạn.' : 'Khi có yêu cầu phù hợp, chúng sẽ xuất hiện tại đây.'}</p></div>}
          {topAction && <Link className="clh-panel-link" to={topAction.to}>Xem toàn bộ trong {topAction.label.toLocaleLowerCase('vi-VN')} <Icon name="arrow" size={17} /></Link>}
        </section>

<section className="clh-panel clh-progress">
 
<div className="clh-section-head">
  <div>
    <span className="clh-section-eyebrow">
      {activeRole === 'MANAGER' || isSupplier
        ? '03 · CƠ CẤU'
        : 'STATUS BREAKDOWN'}
    </span>

    <h3>
      {activeRole === 'MANAGER'
        ? 'Cơ cấu trạng thái nhu cầu'
        : isSupplier
          ? 'Kết quả phản hồi cung ứng'
          : isTransport
            ? 'Tình trạng lịch xe'
            : 'Tiến trình xử lý'}
    </h3>

    <p>
      {activeRole === 'MANAGER'
        ? 'Tổng hợp các nhu cầu trong phạm vi quản lý'
        : isSupplier
          ? 'Phân loại theo tình trạng phản hồi hiện tại'
          : 'Phân bổ theo trạng thái hiện tại'}
    </p>
  </div>

  <span className="clh-section-icon">
    <Icon name="grid" />
  </span>
</div>

  {loading ? (
    <div className="clh-task-loading">
      <div className="clh-skeleton" />
      <div className="clh-skeleton" />
    </div>
  ) : error ? (
    <p className="clh-muted">
      Chưa thể tải dữ liệu để phân tích.
    </p>

) : activeRole === 'MANAGER' ? (
  <DonutChart slices={managerDemandSlices} />
) : isSupplier ? (
  <DonutChart slices={supplierResponseSlices} />
) : workflowTotal === 0 ? (

    <div className="clh-empty compact">
      <Icon name="layers" />
      <strong>Chưa có dữ liệu thống kê</strong>
    </div>
  ) : (
    <div className="clh-progress-content">
      <div className="clh-progress-total">
        <strong>
          {numberFormat.format(workflowTotal)}
        </strong>
        <span>
          {isTransport
            ? 'khung lịch trong 7 ngày'
            : 'nhu cầu đang theo dõi'}
        </span>
      </div>

      <div
        className="clh-stacked-bar"
        aria-label="Tỷ trọng theo trạng thái"
      >
        {workflow
          .filter((step) => step.value > 0)
          .map((step) => (
            <div
              key={step.label}
              className={`clh-bar-segment ${step.color}`}
              style={{
                width: `${
                  (step.value / workflowTotal) * 100
                }%`,
              }}
              title={`${step.label}: ${step.value}`}
            />
          ))}
      </div>

      <div className="clh-progress-legend">
        {workflow.map((step) => (
          <div
            className="clh-legend-row"
            key={step.label}
          >
            <span
              className={`clh-legend-dot ${step.color}`}
            />
            <span>{step.label}</span>
            <b>{numberFormat.format(step.value)}</b>
          </div>
        ))}
      </div>
    </div>
  )}

  {isPurchasing && (
    <div className="clh-dss-note">
      <Icon name="spark" size={17} />
      <p>
        <strong>DSS Workspace</strong>
        {' '}
        So sánh phương án và tối ưu chi phí
        sẽ kết nối khi API DSS được triển khai.
      </p>
    </div>
  )}

  {isTransport && (
    <div className="clh-dss-note">
      <Icon name="shield" size={17} />
      <p>
        <strong>Phạm vi vận chuyển</strong>
        {' '}
        {loading || error
          ? 'Đang chờ dữ liệu.'
          : transport?.profile.service_region ||
            'Chưa khai báo vùng phục vụ.'}
      </p>
    </div>
  )}
</section>

      </div>

{activeRole && (
  <RoleAnalytics
    activeRole={activeRole}
    userId={user.id}
    demands={demands}
    requests={requests}
    transport={transport}
    loading={loading}
    error={error}
  />
)}
      <footer className="clh-footer"><span><Icon name="shield" size={16} /> CoLogi · Smart Operations Dashboard</span><span>{updatedLabel}</span></footer>
    </main>
  )
}
