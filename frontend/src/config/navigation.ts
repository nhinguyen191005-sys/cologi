
import type { BusinessRole } from '../types/auth'

export interface NavItem {
  label: string
  path: string
  icon: string
  roles?: BusinessRole[]
  description?: string
}

export interface NavSection {
  label: string
  items: NavItem[]
}

export const roleLabels: Record<BusinessRole, string> = {
  MANAGER: 'Quản lý',
  PURCHASING_STAFF: 'Nhân viên mua hàng',
  SUPPLIER: 'Nhà cung cấp',
  TRANSPORT_PROVIDER: 'Đơn vị vận chuyển',
}

export const sections: NavSection[] = [
  {
    label: 'TỔNG QUAN',
    items: [
      {
        label: 'Tổng quan',
        path: '/',
        icon: 'dashboard',
        description: 'Không gian làm việc',
      },
    ],
  },
  {
    label: 'NGHIỆP VỤ',
    items: [
      {
        label: 'Danh sách nhu cầu',
        path: '/demands',
        icon: 'clipboard',
        roles: ['MANAGER', 'PURCHASING_STAFF'],
        description: 'Theo dõi yêu cầu',
      },
      {
        label: 'Tạo nhu cầu',
        path: '/demands/new',
        icon: 'box',
        roles: ['PURCHASING_STAFF'],
        description: 'Tạo yêu cầu mới',
      },
      {
        label: 'Yêu cầu cung ứng',
        path: '/supplier/requests',
        icon: 'layers',
        roles: ['SUPPLIER'],
        description: 'Xử lý yêu cầu nhận được',
      },
      {
        label: 'Danh mục mặt hàng',
        path: '/supplier/items',
        icon: 'box',
        roles: ['SUPPLIER'],
        description: 'Mặt hàng cung ứng',
      },
      {
        label: 'Trung tâm vận chuyển',
        path: '/transport',
        icon: 'truck',
        roles: ['TRANSPORT_PROVIDER'],
        description: 'Thông tin đơn vị vận chuyển',
      },
    ],
  },
  {
    label: 'TÀI KHOẢN',
    items: [
      {
        label: 'Hồ sơ cá nhân',
        path: '/profile',
        icon: 'user',
        description: 'Thông tin và quyền truy cập',
      },
    ],
  },
]

export const hasRequiredRole = (
  roles: BusinessRole[],
  allowed?: BusinessRole[]
) => !allowed || allowed.some((role) => roles.includes(role))

export const visibleSections = (roles: BusinessRole[]) => {
  const isManager = roles.includes('MANAGER')

  return sections
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => {
        // Manager chỉ xem demand.
        // Bao gồm cả tài khoản có nhiều vai trò.
        if (
          isManager &&
          item.path === '/demands/new'
        ) {
          return false
        }

        return hasRequiredRole(roles, item.roles)
      }),
    }))
    .filter((section) => section.items.length > 0)
}
