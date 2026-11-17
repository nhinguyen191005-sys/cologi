
import type { DSSScenario } from '../../types/dss'

export const demoScenarios: DSSScenario[] = [
  {
    id: 'SCN-001',
    name: 'Giao hàng đủ năng lực',
    description:
      'Nhiều nhu cầu mua hàng cùng ngày. ' +
      'Phương tiện và thời gian đáp ứng.',
    scenario_type: 'NORMAL',
    service_date: '2026-11-20',
    demand_count: 8,
    created_at: '2026-11-17T09:00:00+07:00',
    is_demo: true,
  },
  {
    id: 'SCN-002',
    name: 'Thiếu năng lực phương tiện',
    description:
      'Một số phương án không đủ xe hoặc tải trọng.',
    scenario_type: 'INSUFFICIENT_VEHICLES',
    service_date: '2026-11-21',
    demand_count: 12,
    created_at: '2026-11-17T09:10:00+07:00',
    is_demo: true,
  },
  {
    id: 'SCN-003',
    name: 'Xung đột thời gian giao nhận',
    description:
      'Khung giờ lấy hàng và nhận hàng không tương thích.',
    scenario_type: 'TIME_CONFLICT',
    service_date: '2026-11-22',
    demand_count: 6,
    created_at: '2026-11-17T09:20:00+07:00',
    is_demo: true,
  },
]