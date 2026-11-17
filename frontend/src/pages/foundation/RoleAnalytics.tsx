
import { useState } from 'react'
import type { BusinessRole } from '../../types/auth'
import type { DeliveryDemand } from '../../types/demand'
import type { SupplierRequest } from '../../types/supplier'
import './RoleAnalytics.css'

type Slot = {
  service_date: string
  availability_status: string
  available_vehicle_count: number
}

type TransportOverview = {
  offers: {
    is_active: boolean
    available_vehicle_count: number
  }[]
  coverages: {
    coverage_status: string
    can_pickup: boolean
  }[]
  slots: Slot[]
}

type Props = {
  activeRole: BusinessRole
  userId: number
  demands: DeliveryDemand[]
  requests: SupplierRequest[]
  transport: TransportOverview | null
  loading: boolean
  error?: string
}

type BarRow = {
  label: string
  first: number
  second: number
}

type Point = {
  date: string
  label: string
  first: number
  second: number
}

type Slice = {
  label: string
  value: number
  color: string
}

type DashboardData = {
  barTitle: string
  barDescription: string
  barLegend: [string, string]
  bars: BarRow[]
  lineTitle: string
  lineDescription: string
  lineLegend: [string, string]
  lines: Point[]
  pieTitle: string
  pieDescription: string
  slices: Slice[]
  note: string
}

const palette = [
  '#1E6B3A',
  '#D5B85A',
  '#4BB169',
  '#6496AD',
  '#9BAE9F',
  '#BD756B',
]

const format = new Intl.NumberFormat('vi-VN', {
  maximumFractionDigits: 2,
})

const small = new Intl.NumberFormat('vi-VN', {
  notation: 'compact',
  maximumFractionDigits: 1,
})

function number(value: string | number | null | undefined) {
  const result = Number(value ?? 0)
  return Number.isFinite(result) ? Math.max(0, result) : 0
}

function ymd(date: Date) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-')
}

function dayKey(raw: string) {
  const parsed = new Date(raw)

  return Number.isNaN(parsed.getTime())
    ? raw.slice(0, 10)
    : ymd(parsed)
}

function rangeDates(days: number, future: boolean): Point[] {
  const today = new Date()
  today.setHours(12, 0, 0, 0)

  return Array.from({ length: days }, (_, i) => {
    const date = new Date(today)
    date.setDate(
      today.getDate() + (future ? i : i - days + 1)
    )

    return {
      date: ymd(date),
      label:
        `${String(date.getDate()).padStart(2, '0')}/` +
        `${String(date.getMonth() + 1).padStart(2, '0')}`,
      first: 0,
      second: 0,
    }
  })
}

function topGroups(rows: BarRow[], limit = 6): BarRow[] {
  const grouped = new Map<string, BarRow>()

  rows.forEach((row) => {
    const key = row.label || 'Chưa xác định'

    const current = grouped.get(key) ?? {
      label: key,
      first: 0,
      second: 0,
    }

    current.first += row.first
    current.second += row.second

    grouped.set(key, current)
  })

  return [...grouped.values()]
    .sort(
      (a, b) =>
        b.first - a.first ||
        a.label.localeCompare(b.label)
    )
    .slice(0, limit)
}

/* =========================================
   ANALYTICS DATA BY ROLE
========================================= */

function makeData(props: Props, days: number): DashboardData {
  const {
    activeRole,
    demands,
    requests,
    transport,
    userId,
  } = props

  if (
    activeRole === 'MANAGER' ||
    activeRole === 'PURCHASING_STAFF'
  ) {
    const manager = activeRole === 'MANAGER'

    const rows = manager
      ? demands
      : demands.filter(
          (row) => row.created_by_id === userId
        )

    const lines = rangeDates(days, false)
    const lineIndex = new Map(
      lines.map((row) => [row.date, row])
    )

    rows.forEach((row) => {
      const point = lineIndex.get(dayKey(row.created_at))

      if (point) {
        point.first += 1

        if (row.status === 'PLANNED') {
          point.second += 1
        }
      }
    })

    const statuses = [
      ['DRAFT', 'Bản nháp'],
      ['SUBMITTED', 'Đã gửi'],
      ['PLANNING', 'Đang lập kế hoạch'],
      ['PLANNED', 'Đã lập kế hoạch'],
      ['CANCELLED', 'Đã hủy'],
    ]

    return {
      barTitle: manager
        ? 'Nhu cầu theo cửa hàng'
        : 'Nhu cầu theo nhà cung cấp',

      barDescription: manager
        ? 'Tổng nhu cầu và nhu cầu đang chờ lập kế hoạch tại 6 cửa hàng có nhiều hồ sơ nhất'
        : 'Tổng nhu cầu và nhu cầu đã lập kế hoạch theo nhà cung cấp',

      barLegend: manager
        ? ['Tổng nhu cầu', 'Chưa lập kế hoạch']
        : ['Tổng nhu cầu', 'Đã lập kế hoạch'],

      bars: topGroups(
        rows.map((row) => ({
          label: manager
            ? row.outlet_name
            : row.supplier_name,

          first: 1,

          second: manager
            ? Number(
                row.status === 'SUBMITTED' ||
                row.status === 'PLANNING'
              )
            : Number(row.status === 'PLANNED'),
        }))
      ),

      lineTitle: manager
        ? 'Xu hướng nhu cầu được tạo'
        : 'Xu hướng nhu cầu của tôi',

      lineDescription:
        `Số nhu cầu tạo trong ${days} ngày gần nhất ` +
        'và số hồ sơ hiện đã lập kế hoạch',

      lineLegend: [
        'Nhu cầu tạo',
        'Hiện đã lập kế hoạch',
      ],

      lines,

      pieTitle: 'Cơ cấu trạng thái nhu cầu',

      pieDescription: manager
        ? 'Tổng hợp các nhu cầu trong phạm vi quản lý'
        : 'Chỉ thống kê nhu cầu do bạn tạo',

      slices: statuses.map(([status, label], i) => ({
        label,
        value: rows.filter(
          (row) => row.status === status
        ).length,
        color: palette[i],
      })),

      note: manager
        ? 'Dữ liệu được Backend cấp quyền cho Manager. Đây là thống kê chỉ xem.'
        : 'Thống kê được lọc theo created_by_id của tài khoản đang đăng nhập.',
    }
  }

  if (activeRole === 'SUPPLIER') {

const lines = rangeDates(days, false)

// Các ngày thuộc khoảng thời gian đang chọn
const visibleDates = new Set(
  lines.map((row) => row.date)
)

// Chỉ lấy yêu cầu được gửi trong 7/14/30 ngày
const filteredRequestsByDate = requests.filter((request) => {
  const sentAt = request.sent_at
  return sentAt !== null && sentAt !== undefined &&
    visibleDates.has(dayKey(sentAt))
})

const lineIndex = new Map(
  lines.map((row) => [row.date, row])
)



    requests.forEach((request) => {
      const sent = request.sent_at
        ? lineIndex.get(dayKey(request.sent_at))
        : undefined

      const responded = request.responded_at
        ? lineIndex.get(dayKey(request.responded_at))
        : undefined

      if (sent) sent.first += 1
      if (responded) responded.second += 1
    })

    return {
      barTitle: 'Số lượng cung ứng theo mặt hàng',

      barDescription:
  `So sánh khối lượng đã hứa và đã xác nhận (kg) ` +
  `của 6 mặt hàng lớn nhất trong ${days} ngày gần nhất`,
      barLegend: [
        'Đã hứa (kg)',
        'Đã xác nhận (kg)',
      ],


bars: topGroups(
  filteredRequestsByDate.flatMap((request) =>
    request.items.map((item) => ({
      label: item.item_name,
      first: number(item.promised_weight_kg),
      second: number(item.confirmed_weight_kg),
    }))
  )
),


      lineTitle: 'Yêu cầu và phản hồi theo ngày',

      lineDescription:
        `Số lần gửi yêu cầu và số lần phản hồi ` +
        `trong ${days} ngày gần nhất`,

      lineLegend: [
        'Yêu cầu gửi đến',
        'Đã phản hồi',
      ],

      lines,

      pieTitle: 'Kết quả phản hồi cung ứng',

      pieDescription:
        'Phân loại theo tình trạng phản hồi hiện tại',

      slices: [
        {
          label: 'Chờ phản hồi',
          value: requests.filter(
            (r) => r.request_status === 'WAITING'
          ).length,
          color: palette[1],
        },
        {
          label: 'Xác nhận đủ',
          value: requests.filter(
            (r) =>
              r.request_status === 'RESPONDED' &&
              r.confirmation_status === 'CONFIRMED'
          ).length,
          color: palette[0],
        },
        {
          label: 'Xác nhận một phần',
          value: requests.filter(
            (r) =>
              r.request_status === 'RESPONDED' &&
              r.confirmation_status === 'PARTIAL'
          ).length,
          color: palette[3],
        },
        {
          label: 'Từ chối',
          value: requests.filter(
            (r) =>
              r.request_status === 'RESPONDED' &&
              r.confirmation_status === 'DECLINED'
          ).length,
          color: palette[5],
        },
        {
          label: 'Khác',
          value: requests.filter(
            (r) =>
              r.request_status === 'RESPONDED' &&
              !['CONFIRMED', 'PARTIAL', 'DECLINED']
                .includes(r.confirmation_status)
          ).length,
          color: palette[4],
        },
      ],

      note:
        'Chỉ tính yêu cầu thuộc Supplier đang đăng nhập. ' +
        'Một demand có thể được gửi nhiều lần và mỗi lần gửi được tính riêng.',
    }
  }

  /* TRANSPORT PROVIDER */

  const slots = transport?.slots ?? []

  const lines = rangeDates(days, true)
  const lineIndex = new Map(
    lines.map((row) => [row.date, row])
  )

  slots.forEach((slot) => {
    const point = lineIndex.get(slot.service_date)

    if (point) {
      point.second += number(slot.available_vehicle_count)

      if (slot.availability_status === 'AVAILABLE') {
        point.first += number(slot.available_vehicle_count)
      }
    }
  })

  const sevenDays = rangeDates(7, true)
  const sevenIndex = new Map(
    sevenDays.map((row) => [row.date, row])
  )

  slots.forEach((slot) => {
    const point = sevenIndex.get(slot.service_date)

    if (point) {
      point.second += number(slot.available_vehicle_count)

      if (slot.availability_status === 'AVAILABLE') {
        point.first += number(slot.available_vehicle_count)
      }
    }
  })

  const futureKeys = new Set(
    lines.map((row) => row.date)
  )

  return {
    barTitle: 'Năng lực xe trong 7 ngày tới',

    barDescription:
      'So sánh lượt xe khả dụng và lượt xe khai báo theo ngày',

    barLegend: [
      'Lượt xe khả dụng',
      'Lượt xe khai báo',
    ],

    bars: sevenDays.map((row) => ({
      label: row.label,
      first: row.first,
      second: row.second,
    })),

    lineTitle: 'Xu hướng năng lực sắp tới',

    lineDescription:
      `Năng lực được khai báo trong ${days} ngày tới`,

    lineLegend: [
      'Khả dụng',
      'Đã khai báo',
    ],

    lines,

    pieTitle: 'Tình trạng khung lịch xe',

    pieDescription:
      `Phân loại các khung lịch trong ${days} ngày tới`,

    slices: [
      {
        label: 'Khả dụng',
        value: slots.filter(
          (s) =>
            futureKeys.has(s.service_date) &&
            s.availability_status === 'AVAILABLE'
        ).length,
        color: palette[0],
      },
      {
        label: 'Không khả dụng',
        value: slots.filter(
          (s) =>
            futureKeys.has(s.service_date) &&
            s.availability_status !== 'AVAILABLE'
        ).length,
        color: palette[1],
      },
    ],

    note:
      'Tổng lượt xe theo các khung lịch không đồng nghĩa với số xe ' +
      'duy nhất; một xe có thể xuất hiện ở nhiều khung giờ.',
  }
}

/* =========================================
   CHART STATES
========================================= */

function ChartEmpty({ label }: { label: string }) {
  return (
    <div className="cla-empty">
      {label}
    </div>
  )
}

/* =========================================
   BAR CHART
========================================= */

function BarChart({
  rows,
  legend,
}: {
  rows: BarRow[]
  legend: [string, string]
}) {
  const usable = rows.filter(
    (row) => row.first > 0 || row.second > 0
  )

  if (!usable.length) {
    return (
      <ChartEmpty label="Chưa có dữ liệu để so sánh." />
    )
  }

  const width = 660
  const height = 270
  const left = 43
  const right = 14
  const top = 18
  const bottom = 72

  const plotHeight = height - top - bottom
  const plotWidth = width - left - right

  const max = Math.max(
    1,
    ...usable.map(
      (row) => Math.max(row.first, row.second)
    )
  )

  const step = plotWidth / usable.length
  const barWidth = Math.min(26, step * 0.28)

  return (
    <>
      <div className="cla-legend">
        {legend.map((label, i) => (
          <span key={label}>
            <i style={{ background: palette[i] }} />
            {label}
          </span>
        ))}
      </div>

      <svg
        className="cla-svg"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Biểu đồ cột so sánh dữ liệu"
      >
        {[0, 1, 2, 3, 4].map((tick) => {
          const y = top + (plotHeight * tick) / 4

          return (
            <g key={tick}>
              <line
                x1={left}
                x2={width - right}
                y1={y}
                y2={y}
                stroke="#e4ede5"
              />

              <text
                x={left - 9}
                y={y + 4}
                textAnchor="end"
                fill="#8b9c91"
                fontSize="12"
              >
                {small.format(max * (1 - tick / 4))}
              </text>
            </g>
          )
        })}

        {usable.map((row, i) => {
          const center = left + (i + 0.5) * step

          return (
            <g key={row.label}>
              {[row.first, row.second].map((value, j) => {
                const barHeight =
                  (value / max) * plotHeight

                return (
                  <rect
                    key={j}
                    x={
                      center +
                      (j === 0 ? -barWidth - 2 : 2)
                    }
                    y={top + plotHeight - barHeight}
                    width={barWidth}
                    height={barHeight}
                    rx="5"
                    fill={palette[j]}
                  >
                    <title>
                      {row.label} · {legend[j]}:
                      {' '}{format.format(value)}
                    </title>
                  </rect>
                )
              })}

              <text
                x={center}
                y={height - bottom + 19}
                fill="#6c806f"
                fontSize="12"
                textAnchor="middle"
              >
                {row.label.length > 14
                  ? `${row.label.slice(0, 13)}…`
                  : row.label}
              </text>
            </g>
          )
        })}
      </svg>
    </>
  )
}

/* =========================================
   LINE CHART
========================================= */

function LineChart({
  rows,
  legend,
}: {
  rows: Point[]
  legend: [string, string]
}) {
  const total = rows.reduce(
    (sum, row) => sum + row.first + row.second,
    0
  )

  if (!total) {
    return (
      <ChartEmpty
        label="Chưa có hoạt động trong khoảng ngày đã chọn."
      />
    )
  }

  const width = 660
  const height = 270

  const left = 43
  const right = 15
  const top = 18
  const bottom = 45

  const plotWidth = width - left - right
  const plotHeight = height - top - bottom

  const max = Math.max(
    1,
    ...rows.map(
      (row) => Math.max(row.first, row.second)
    )
  )

  const xOf = (i: number) =>
    left +
    (i / Math.max(1, rows.length - 1)) *
      plotWidth

  const yOf = (value: number) =>
    top + plotHeight - (value / max) * plotHeight

  const points = (
    key: 'first' | 'second'
  ) =>
    rows
      .map(
        (row, i) =>
          `${xOf(i)},${yOf(row[key])}`
      )
      .join(' ')

  const visibleTicks = new Set([
    0,
    Math.floor((rows.length - 1) / 2),
    rows.length - 1,
  ])

  return (
    <>
      <div className="cla-legend">
        {legend.map((label, i) => (
          <span key={label}>
            <i style={{ background: palette[i] }} />
            {label}
          </span>
        ))}
      </div>

      <svg
        className="cla-svg"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Biểu đồ đường theo ngày"
      >
        {[0, 1, 2, 3, 4].map((tick) => {
          const y = top + (plotHeight * tick) / 4

          return (
            <g key={tick}>
              <line
                x1={left}
                x2={width - right}
                y1={y}
                y2={y}
                stroke="#e4ede5"
              />

              <text
                x={left - 9}
                y={y + 4}
                textAnchor="end"
                fill="#8b9c91"
                fontSize="12"
              >
                {small.format(max * (1 - tick / 4))}
              </text>
            </g>
          )
        })}

        {(['first', 'second'] as const).map(
          (key, j) => (
            <g key={key}>
              <polyline
                points={points(key)}
                fill="none"
                stroke={palette[j]}
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
              />

              {rows.map(
                (row, i) =>
                  (row[key] > 0 ||
                    i === rows.length - 1) && (
                    <circle
                      key={row.date}
                      cx={xOf(i)}
                      cy={yOf(row[key])}
                      r="3.7"
                      fill={palette[j]}
                      stroke="#fff"
                      strokeWidth="1.5"
                    >
                      <title>
                        {row.label} · {legend[j]}:
                        {' '}{format.format(row[key])}
                      </title>
                    </circle>
                  )
              )}
            </g>
          )
        )}

        {rows.map(
          (row, i) =>
            visibleTicks.has(i) && (
              <text
                key={row.date}
                x={xOf(i)}
                y={height - 17}
                textAnchor="middle"
                fill="#6c806f"
                fontSize="12"
              >
                {row.label}
              </text>
            )
        )}
      </svg>
    </>
  )
}

/* =========================================
   DONUT CHART
========================================= */

export function DonutChart({
  slices,
}: {
  slices: Slice[]
}) {
  const filtered = slices.filter(
    (slice) => slice.value > 0
  )

  const total = filtered.reduce(
    (sum, slice) => sum + slice.value,
    0
  )

  if (!total) {
    return (
      <ChartEmpty
        label="Chưa có bản ghi để phân tích tỷ trọng."
      />
    )
  }

  const radius = 75
  const circumference = 2 * Math.PI * radius

  let used = 0

  return (
    <div className="cla-donut-wrap">
      <svg
        viewBox="0 0 220 220"
        className="cla-donut"
        role="img"
        aria-label="Biểu đồ tròn phân bố trạng thái"
      >
        <circle
          cx="110"
          cy="110"
          r={radius}
          fill="none"
          stroke="#edf3ed"
          strokeWidth="25"
        />

        {filtered.map((slice) => {
          const length =
            (slice.value / total) * circumference

          const offset = used
          used += length

          return (
            <circle
              key={slice.label}
              cx="110"
              cy="110"
              r={radius}
              fill="none"
              stroke={slice.color}
              strokeWidth="25"
              strokeDasharray={
                `${length} ${circumference - length}`
              }
              strokeDashoffset={-offset}
              transform="rotate(-90 110 110)"
            >
              <title>
                {slice.label}:
                {' '}{format.format(slice.value)}
                {' '}(
                {Math.round((slice.value / total) * 100)}
                %)
              </title>
            </circle>
          )
        })}

        <text
          x="110"
          y="103"
          textAnchor="middle"
          fill="#193C29"
          fontSize="30"
          fontWeight="800"
        >
          {format.format(total)}
        </text>

        <text
          x="110"
          y="124"
          textAnchor="middle"
          fill="#8a9c8d"
          fontSize="12"
        >
          Tổng bản ghi
        </text>
      </svg>

      <div className="cla-donut-legend">
        {slices.map((slice) => (
          <div key={slice.label}>
            <span
              className="cla-dot"
              style={{ background: slice.color }}
            />

            <span>{slice.label}</span>

            <strong>
              {format.format(slice.value)}
            </strong>
          </div>
        ))}
      </div>
    </div>
  )
}


/* =========================================
   MAIN ANALYTICS COMPONENT
========================================= */

export default function RoleAnalytics(props: Props) {
  const [days, setDays] = useState<7 | 14 | 30>(14)
  const data = makeData(props, days)

  return (
    <section
      className="cla-section"
      aria-label="Phân tích vận hành theo vai trò"
    >
      <div className="cla-heading">
        <div>
          <span className="cla-kicker">
            OPERATIONS ANALYTICS
          </span>

          <h2>Phân tích vận hành</h2>

          <p>
            Biểu đồ lấy từ API và thay đổi theo
            vai trò đang chọn.
          </p>
        </div>

        <div
          className="cla-range"
          role="group"
          aria-label="Khoảng thời gian biểu đồ"
        >
          {([7, 14, 30] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setDays(value)}
              aria-pressed={days === value}
              className={
                days === value ? 'active' : ''
              }
            >
              {value} ngày
            </button>
          ))}
        </div>
      </div>

      {props.loading ? (
        <div
          className="cla-loading"
          role="status"
        >
          Đang tổng hợp dữ liệu biểu đồ...
        </div>
      ) : props.error ? (
        <div
          className="cla-loading cla-error"
          role="alert"
        >
          Không thể vẽ biểu đồ vì dữ liệu API
          chưa được tải. Hãy chọn Làm mới dữ liệu.
        </div>
      ) : (
        <>
          <div className="cla-grid">
            <article className="cla-card">
              <header>
                <span>01 · SO SÁNH</span>
                <h3>{data.barTitle}</h3>
                <p>{data.barDescription}</p>
              </header>

              <BarChart
                rows={data.bars}
                legend={data.barLegend}
              />
            </article>

            <article className="cla-card">
              <header>
                <span>02 · XU HƯỚNG</span>
                <h3>{data.lineTitle}</h3>
                <p>{data.lineDescription}</p>
              </header>

              <LineChart
                rows={data.lines}
                legend={data.lineLegend}
              />
            </article>

{props.activeRole !== 'SUPPLIER' &&
  props.activeRole !== 'MANAGER' && (
    <article className="cla-card cla-card--pie">
      <header>
        <span>03 · CƠ CẤU</span>
        <h3>{data.pieTitle}</h3>
        <p>{data.pieDescription}</p>
      </header>

      <DonutChart slices={data.slices} />
    </article>
)}

          </div>

          <p className="cla-note">
            {data.note}
          </p>
        </>
      )}
    </section>
  )
}