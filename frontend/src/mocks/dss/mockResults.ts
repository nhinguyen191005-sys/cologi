
import type {
  DSSCandidate,
  DSSModuleResult,
  DSSOption,
  DSSReason,
  DSSRun,
  DSSScenario,
  DSSScenarioType,
} from '../../types/dss'

const SIMULATION_VERSION = 'demo-1.0'

function reason(
  code: string,
  module: DSSReason['module'],
  message: string
): DSSReason {
  return { code, module, message }
}

function createCandidates(
  scenario: DSSScenario
): DSSCandidate[] {
  const blocked =
    scenario.scenario_type === 'TIME_CONFLICT'

  return [
    {
      id: 'GRP-001',
      demand_ids: ['DM-001', 'DM-002'],
      supplier_names: ['NCC A', 'NCC B'],
      total_quantity_kg: 800,
      status: 'ELIGIBLE',
      reasons: [],
    },
    {
      id: 'GRP-002',
      demand_ids: ['DM-003', 'DM-004'],
      supplier_names: ['NCC C'],
      total_quantity_kg: 1200,
      status: 'ELIGIBLE',
      reasons: [],
    },
    {
      id: 'GRP-003',
      demand_ids: ['DM-005'],
      supplier_names: ['NCC D'],
      total_quantity_kg: 2500,
      status: blocked ? 'EXCLUDED' : 'ELIGIBLE',
      reasons: blocked
        ? [
            reason(
              'F1_PICKUP_WINDOW_CONFLICT',
              'F1',
              'Nhu cầu mẫu không phù hợp với điều kiện ' +
                'phối hợp đã giả định trong kịch bản.'
            ),
          ]
        : [],
    },
  ]
}

function createOptions(
  type: DSSScenarioType
): DSSOption[] {
  const insufficient =
    type === 'INSUFFICIENT_VEHICLES'

  const timeConflict =
    type === 'TIME_CONFLICT'

  const directBlocked = timeConflict

  const hubBlocked =
    insufficient || timeConflict

  return [
    {
      id: 'OPT-DIRECT-01',
      name: 'Phương án giao trực tiếp',
      mode: 'DIRECT',
      status: directBlocked
        ? 'BLOCKED'
        : 'FEASIBLE',

      demand_ids: ['DM-001', 'DM-002', 'DM-003'],
      vehicle_name: 'Xe tải 2 tấn',
      vehicle_count: 2,
      capacity_kg: 2000,
      total_quantity_kg: 1800,

      estimated_cost_vnd: directBlocked
        ? null
        : 1450000,

      estimated_distance_km: 32,

      stops: [
        {
          sequence: 1,
          location_name: 'Nhà cung cấp A',
          stop_type: 'PICKUP',
          arrival_time: '08:00',
          departure_time: '08:20',
        },
        {
          sequence: 2,
          location_name: 'Nhà cung cấp B',
          stop_type: 'PICKUP',
          arrival_time: '08:40',
          departure_time: '09:00',
        },
        {
          sequence: 3,
          location_name: 'Điểm nhận hàng',
          stop_type: 'DELIVERY',
          arrival_time: '09:40',
          departure_time: '10:00',
        },
      ],

      reasons: directBlocked
        ? [
            reason(
              'F4_DELIVERY_WINDOW_MISSED',
              'F4',
              'Thời gian giao dự kiến vượt khung giờ ' +
                'nhận hàng của kịch bản mẫu.'
            ),
          ]
        : [],
    },

    {
      id: 'OPT-HUB-01',
      name: 'Phương án qua điểm trung chuyển',
      mode: 'HUB',
      status: hubBlocked
        ? 'BLOCKED'
        : 'FEASIBLE',

      demand_ids: [
        'DM-001',
        'DM-002',
        'DM-003',
        'DM-004',
      ],

      vehicle_name: 'Xe tải 1,5 tấn',
      vehicle_count: 2,
      capacity_kg: 1500,
      total_quantity_kg: 2400,

      estimated_cost_vnd: hubBlocked
        ? null
        : 1180000,

      estimated_distance_km: 28,

      stops: [
        {
          sequence: 1,
          location_name: 'Nhà cung cấp A',
          stop_type: 'PICKUP',
          arrival_time: '07:30',
          departure_time: '07:50',
        },
        {
          sequence: 2,
          location_name: 'Điểm trung chuyển Hub',
          stop_type: 'HUB',
          arrival_time: '08:20',
          departure_time: '08:50',
        },
        {
          sequence: 3,
          location_name: 'Điểm nhận hàng',
          stop_type: 'DELIVERY',
          arrival_time: '09:30',
          departure_time: '09:50',
        },
      ],

      reasons: insufficient
        ? [
            reason(
              'F3_INSUFFICIENT_VEHICLES',
              'F3',
              'Số phương tiện khả dụng trong dữ liệu ' +
                'giả lập không đáp ứng phương án Hub.'
            ),
          ]
        : timeConflict
          ? [
              reason(
                'F4_PICKUP_DELIVERY_CONFLICT',
                'F4',
                'Không thể đáp ứng đồng thời thời gian ' +
                  'lấy hàng và nhận hàng giả định.'
              ),
            ]
          : [],
    },
  ]
}

function createModules(
  scenario: DSSScenario,
  options: DSSOption[],
  candidates: DSSCandidate[]
): DSSModuleResult[] {
  const hasFeasible = options.some(
    (item) => item.status === 'FEASIBLE'
  )

  const hasBlocked = options.some(
    (item) => item.status === 'BLOCKED'
  )

  const f3Blocked = options.some((option) =>
    option.reasons.some(
      (item) => item.module === 'F3'
    )
  )

  const f4Blocked = options.some((option) =>
    option.reasons.some(
      (item) => item.module === 'F4'
    )
  )

  return [
    {
      module: 'F1',
      title: 'Phối hợp nhu cầu',
      status: 'COMPLETED',
      summary:
        'Mô phỏng phân nhóm các nhu cầu mua hàng.',
      details: [
        `${scenario.demand_count} nhu cầu đầu vào theo kịch bản.`,
        `${candidates.length} nhóm ứng viên minh họa.`,
        'Dữ liệu nhóm không được tính từ đơn hàng thật.',
      ],
    },
    {
      module: 'F2',
      title: 'Xây dựng phương án',
      status: 'COMPLETED',
      summary:
        'Tạo phương án Direct và Hub minh họa.',
      details: [
        'Direct: nhận hàng và giao đến điểm đích.',
        'Hub: đưa hàng qua điểm trung chuyển.',
      ],
    },
    {
      module: 'F3',
      title: 'Phân bổ phương tiện',
      status: f3Blocked ? 'BLOCKED' : 'COMPLETED',
      summary: f3Blocked
        ? 'Có phương án bị chặn do thiếu phương tiện.'
        : 'Không phát hiện chặn phương tiện trong fixture.',
      details: [
        'Xe và tải trọng chỉ là giá trị minh họa.',
        'Không sử dụng lịch xe thực tế từ backend.',
      ],
    },
    {
      module: 'F4',
      title: 'Kiểm tra thời gian',
      status: f4Blocked ? 'BLOCKED' : 'COMPLETED',
      summary: f4Blocked
        ? 'Có phương án không đáp ứng điều kiện giờ.'
        : 'Fixture không đặt ra xung đột thời gian.',
      details: [
        'Giờ lấy và giao trong demo được thiết lập sẵn.',
        'Chưa tính thời gian di chuyển thực tế.',
      ],
    },
    {
      module: 'F5',
      title: 'Đánh giá kinh tế',
      status: !hasFeasible
        ? 'SKIPPED'
        : 'COMPLETED',
      summary: hasFeasible
        ? 'So sánh chi phí của phương án khả thi.'
        : 'Không có phương án khả thi để so sánh.',
      details: [
        'Giá trị chi phí là số liệu mô phỏng.',
        hasBlocked
          ? 'Phương án bị chặn không tham gia xếp hạng.'
          : 'Các phương án minh họa đều khả thi.',
      ],
    },
  ]
}

export function buildMockRun(
  scenario: DSSScenario,
  runId: string,
  startedAt: string
): DSSRun {
  const candidates = createCandidates(scenario)
  const options = createOptions(
    scenario.scenario_type
  )

  const modules = createModules(
    scenario,
    options,
    candidates
  )

  const feasibleCount = options.filter(
    (option) => option.status === 'FEASIBLE'
  ).length

  const blockedCount = options.filter(
    (option) => option.status !== 'FEASIBLE'
  ).length

  return {
    id: runId,
    scenario_id: scenario.id,
    scenario_name: scenario.name,

    status: 'COMPLETED',
    started_at: startedAt,
    completed_at: startedAt,

    is_demo: true,
    simulation_version: SIMULATION_VERSION,

    modules,
    candidates,
    options,

    snapshot: {
      captured_at: startedAt,
      source: 'DEMO_FIXTURE',
      scenario_id: scenario.id,

      input: {
        service_date: scenario.service_date,
        demand_count: scenario.demand_count,
        scenario_type: scenario.scenario_type,
        note:
          'Snapshot minh họa từ dữ liệu cố định. ' +
          'Không phải dữ liệu từ backend F1–F5.',
      },

      output: {
        candidate_count: candidates.length,
        option_count: options.length,
        feasible_count: feasibleCount,
        blocked_count: blockedCount,
      },
    },
  }
}