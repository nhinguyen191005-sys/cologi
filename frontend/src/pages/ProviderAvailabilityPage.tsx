
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from 'react'

import {
  createProviderAvailability,
  listProviderAvailability,
  listProviderVehicleOffers,
  listProviderVehicleTypes,
  updateProviderAvailability,
} from '../services/api/providers'

import type {
  ProviderAvailability,
  ProviderAvailabilityInput,
  ProviderAvailabilityStatus,
  ProviderVehicleOffer,
  ProviderVehicleType,
} from '../types/provider'

import './ProviderAvailabilityPage.css'

/* =========================================
   TYPES
========================================= */

type FormValues = {
  provider_vehicle_offer_id: string
  service_date: string
  start_time: string
  end_time: string
  available_vehicle_count: string
  availability_status: ProviderAvailabilityStatus
}

type TimeStatus = 'ONGOING' | 'UPCOMING' | 'PAST'
type TimeFilter = 'ALL' | TimeStatus

type VietnamNow = {
  date: string
  time: string
}

const PAGE_SIZE = 10

const initialForm: FormValues = {
  provider_vehicle_offer_id: '',
  service_date: '',
  start_time: '',
  end_time: '',
  available_vehicle_count: '1',
  availability_status: 'AVAILABLE',
}

/* =========================================
   TIME HELPERS
========================================= */

function getVietnamNow(timestamp = Date.now()): VietnamNow {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Ho_Chi_Minh',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(timestamp))

  const get = (type: string) =>
    parts.find((part) => part.type === type)?.value ?? ''

  return {
    date: `${get('year')}-${get('month')}-${get('day')}`,
    time: `${get('hour')}:${get('minute')}`,
  }
}

function formatDate(date: string): string {
  if (!date) return '—'

  const [year, month, day] = date.split('-')

  return `${day}/${month}/${year}`
}

function formatTime(time: string): string {
  return time.slice(0, 5)
}

function getTimeStatus(
  item: ProviderAvailability,
  now: VietnamNow
): TimeStatus {
  const start = formatTime(item.start_time)
  const end = formatTime(item.end_time)

  if (item.service_date < now.date) {
    return 'PAST'
  }

  if (item.service_date > now.date) {
    return 'UPCOMING'
  }

  if (end <= now.time) {
    return 'PAST'
  }

  if (start <= now.time && end > now.time) {
    return 'ONGOING'
  }

  return 'UPCOMING'
}

function sortAvailability(
  rows: ProviderAvailability[],
  now: VietnamNow
): ProviderAvailability[] {
  const priority: Record<TimeStatus, number> = {
    ONGOING: 0,
    UPCOMING: 1,
    PAST: 2,
  }

  return [...rows].sort((a, b) => {
    const statusA = getTimeStatus(a, now)
    const statusB = getTimeStatus(b, now)

    if (statusA !== statusB) {
      return priority[statusA] - priority[statusB]
    }

    const startA =
      `${a.service_date}T${formatTime(a.start_time)}`

    const startB =
      `${b.service_date}T${formatTime(b.start_time)}`

    if (statusA === 'PAST') {
      const endA =
        `${a.service_date}T${formatTime(a.end_time)}`

      const endB =
        `${b.service_date}T${formatTime(b.end_time)}`

      return endB.localeCompare(endA) || b.id - a.id
    }

    return startA.localeCompare(startB) || a.id - b.id
  })
}

/* =========================================
   ERROR HANDLING
========================================= */

function getErrorMessage(error: unknown): string {
  const apiError = error as {
    message?: string
    status?: number
    data?: Record<string, unknown>
  }

  if (apiError.status === 401) {
    return 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'
  }

  if (apiError.status === 403) {
    return 'Bạn không có quyền truy cập lịch khả dụng của đơn vị vận chuyển.'
  }

  if (apiError.data) {
    const messages = Object.values(apiError.data)
      .flatMap((value) =>
        Array.isArray(value) ? value : [value]
      )
      .filter(
        (value): value is string =>
          typeof value === 'string'
      )

    if (messages.length > 0) {
      return messages.join(' ')
    }
  }

  return (
    apiError.message ||
    'Đã xảy ra lỗi. Vui lòng thử lại.'
  )
}

/* =========================================
   MAIN COMPONENT
========================================= */

export default function ProviderAvailabilityPage() {
  const [availability, setAvailability] =
    useState<ProviderAvailability[]>([])

  const [offers, setOffers] =
    useState<ProviderVehicleOffer[]>([])

  const [vehicleTypes, setVehicleTypes] =
    useState<ProviderVehicleType[]>([])

  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [search, setSearch] = useState('')
  const [dateFilter, setDateFilter] = useState('')
  const [statusFilter, setStatusFilter] =
    useState('ALL')

  const [timeFilter, setTimeFilter] =
    useState<TimeFilter>('ALL')

  const [currentPage, setCurrentPage] = useState(1)

  const [nowTimestamp, setNowTimestamp] = useState(
    () => Date.now()
  )

  const [showForm, setShowForm] = useState(false)

  const [editing, setEditing] =
    useState<ProviderAvailability | null>(null)

  const [form, setForm] = useState<FormValues>(initialForm)

  const now = useMemo(
    () => getVietnamNow(nowTimestamp),
    [nowTimestamp]
  )

  /* =========================================
     CLOCK UPDATE
  ========================================= */

  useEffect(() => {
    const timer = window.setInterval(() => {
      setNowTimestamp(Date.now())
    }, 30000)

    return () => window.clearInterval(timer)
  }, [])

  /* =========================================
     LOAD DATA
  ========================================= */

  const loadData = useCallback(async () => {
    setLoading(true)
    setError('')

    try {
      const [
        availabilityData,
        offerData,
        vehicleTypeData,
      ] = await Promise.all([
        listProviderAvailability(),
        listProviderVehicleOffers(),
        listProviderVehicleTypes(),
      ])

      setAvailability(availabilityData)
      setOffers(offerData)
      setVehicleTypes(vehicleTypeData)

      setNowTimestamp(Date.now())
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadData()
  }, [loadData])

  /* =========================================
     VEHICLE LOOKUPS
  ========================================= */

  const offerMap = useMemo(
    () =>
      new Map(
        offers.map((offer) => [offer.id, offer])
      ),
    [offers]
  )

  const vehicleTypeMap = useMemo(
    () =>
      new Map(
        vehicleTypes.map((type) => [type.id, type])
      ),
    [vehicleTypes]
  )

  const activeOffers = useMemo(
    () =>
      offers.filter((offer) => {
        if (
          !offer.is_active ||
          !offer.operating_start_time ||
          !offer.operating_end_time
        ) {
          return false
        }

        return (
          formatTime(offer.operating_start_time) <
          formatTime(offer.operating_end_time)
        )
      }),
    [offers]
  )

  /* =========================================
     TIME COUNTS
  ========================================= */

  const timeCounts = useMemo(() => {
    const counts = {
      upcoming: 0,
      ongoing: 0,
      past: 0,
    }

    availability.forEach((item) => {
      const status = getTimeStatus(item, now)

      if (status === 'UPCOMING') {
        counts.upcoming += 1
      } else if (status === 'ONGOING') {
        counts.ongoing += 1
      } else {
        counts.past += 1
      }
    })

    return counts
  }, [availability, now])

  /* =========================================
     SEARCH + FILTER + SORT
  ========================================= */

  const filteredAvailability = useMemo(() => {
    const keyword = search.trim().toLowerCase()

    const filtered = availability.filter((item) => {
      const offer = offerMap.get(
        item.provider_vehicle_offer_id
      )

      const vehicleType = offer
        ? vehicleTypeMap.get(offer.vehicle_type_id)
        : undefined

      const searchableText = [
        `AV-${item.id}`,
        String(item.id),
        String(item.provider_vehicle_offer_id),
        String(offer?.vehicle_type_id ?? ''),
        vehicleType?.vehicle_name ?? '',
        vehicleType?.vehicle_code ?? '',
      ]
        .join(' ')
        .toLowerCase()

      const matchesSearch =
        !keyword || searchableText.includes(keyword)

      const matchesDate =
        !dateFilter ||
        item.service_date === dateFilter

      const matchesStatus =
        statusFilter === 'ALL' ||
        item.availability_status === statusFilter

      const matchesTime =
        timeFilter === 'ALL' ||
        getTimeStatus(item, now) === timeFilter

      return (
        matchesSearch &&
        matchesDate &&
        matchesStatus &&
        matchesTime
      )
    })

    return sortAvailability(filtered, now)
  }, [
    availability,
    offerMap,
    vehicleTypeMap,
    search,
    dateFilter,
    statusFilter,
    timeFilter,
    now,
  ])

  /* =========================================
     PAGINATION
  ========================================= */

  const totalPages = Math.max(
    1,
    Math.ceil(filteredAvailability.length / PAGE_SIZE)
  )

  const safePage = Math.min(currentPage, totalPages)

  const paginatedAvailability = useMemo(
    () =>
      filteredAvailability.slice(
        (safePage - 1) * PAGE_SIZE,
        safePage * PAGE_SIZE
      ),
    [filteredAvailability, safePage]
  )

  const firstItem =
    filteredAvailability.length === 0
      ? 0
      : (safePage - 1) * PAGE_SIZE + 1

  const lastItem = Math.min(
    safePage * PAGE_SIZE,
    filteredAvailability.length
  )

  function changeTimeFilter(value: TimeFilter) {
    setTimeFilter(value)
    setCurrentPage(1)
    setNowTimestamp(Date.now())
  }

  function resetFilters() {
    setSearch('')
    setDateFilter('')
    setStatusFilter('ALL')
    setTimeFilter('ALL')
    setCurrentPage(1)
    setNowTimestamp(Date.now())
  }

  /* =========================================
     FORM
  ========================================= */

  function openCreateForm() {
    setEditing(null)

    setForm({
      ...initialForm,
      provider_vehicle_offer_id: activeOffers[0]
        ? String(activeOffers[0].id)
        : '',
    })

    setError('')
    setSuccess('')
    setShowForm(true)
  }

  function openEditForm(item: ProviderAvailability) {
    const timeStatus = getTimeStatus(
      item,
      getVietnamNow()
    )

    if (timeStatus !== 'UPCOMING') {
      setError(
        'Không thể chỉnh sửa lịch đã bắt đầu hoặc đã qua.'
      )
      return
    }

    setEditing(item)

    setForm({
      provider_vehicle_offer_id:
        String(item.provider_vehicle_offer_id),
      service_date: item.service_date,
      start_time: formatTime(item.start_time),
      end_time: formatTime(item.end_time),
      available_vehicle_count:
        String(item.available_vehicle_count),
      availability_status: item.availability_status,
    })

    setError('')
    setSuccess('')
    setShowForm(true)
  }

  function closeForm() {
    if (submitting) return

    setShowForm(false)
    setEditing(null)
    setForm(initialForm)
    setError('')
  }

  function validateForm(): string | null {
    if (!form.provider_vehicle_offer_id) {
      return 'Vui lòng chọn phương tiện.'
    }

    if (
      !form.service_date ||
      !form.start_time ||
      !form.end_time
    ) {
      return 'Vui lòng nhập đầy đủ ngày và khung giờ.'
    }

    const start = formatTime(form.start_time)
    const end = formatTime(form.end_time)

    if (start >= end) {
      return 'Giờ kết thúc phải sau giờ bắt đầu.'
    }

    const currentTime = getVietnamNow()

    if (
      form.service_date < currentTime.date ||
      (
        form.service_date === currentTime.date &&
        start <= currentTime.time
      )
    ) {
      return 'Lịch mới hoặc lịch chỉnh sửa phải bắt đầu sau thời điểm hiện tại.'
    }

    const count = Number(form.available_vehicle_count)

    if (
      form.available_vehicle_count.trim() === '' ||
      !Number.isInteger(count) ||
      count < 0
    ) {
      return 'Số lượng xe phải là số nguyên không âm.'
    }

    if (
      form.availability_status === 'AVAILABLE' &&
      count <= 0
    ) {
      return 'Lịch khả dụng phải có ít nhất một xe.'
    }

    if (
      form.availability_status === 'UNAVAILABLE' &&
      count !== 0
    ) {
      return 'Lịch không khả dụng phải có số lượng xe bằng 0.'
    }

    const selectedOffer = offerMap.get(
      Number(form.provider_vehicle_offer_id)
    )

    if (!selectedOffer) {
      return 'Cấu hình phương tiện không tồn tại.'
    }

    if (
      !editing &&
      !selectedOffer.is_active
    ) {
      return 'Không thể tạo lịch cho cấu hình xe đã ngừng hoạt động.'
    }

    if (
      count > selectedOffer.available_vehicle_count
    ) {
      return (
        `Số xe không được vượt quá năng lực khai báo ` +
        `(${selectedOffer.available_vehicle_count} xe).`
      )
    }

    if (
      selectedOffer.operating_start_time &&
      selectedOffer.operating_end_time
    ) {
      const operatingStart = formatTime(
        selectedOffer.operating_start_time
      )

      const operatingEnd = formatTime(
        selectedOffer.operating_end_time
      )

      if (
        start < operatingStart ||
        end > operatingEnd
      ) {
        return (
          `Khung giờ phải nằm trong giờ hoạt động ` +
          `${operatingStart}–${operatingEnd}.`
        )
      }
    }

    return null
  }

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault()

    if (submitting) return

    setError('')
    setSuccess('')

    const validationError = validateForm()

    if (validationError) {
      setError(validationError)
      return
    }

    const payload: ProviderAvailabilityInput = {
      service_date: form.service_date,
      start_time: form.start_time,
      end_time: form.end_time,
      available_vehicle_count:
        Number(form.available_vehicle_count),
      availability_status: form.availability_status,
    }

    setSubmitting(true)

    try {
      if (editing) {
        await updateProviderAvailability(
          editing.id,
          payload
        )

        setSuccess('Đã cập nhật lịch khả dụng.')
      } else {
        await createProviderAvailability({
          ...payload,
          provider_vehicle_offer_id: Number(
            form.provider_vehicle_offer_id
          ),
        })

        setSuccess('Đã tạo lịch khả dụng.')
      }

      setShowForm(false)
      setEditing(null)
      setForm(initialForm)
      setCurrentPage(1)

      await loadData()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  /* =========================================
     RENDER
  ========================================= */

  return (
    <main className="provider-availability-page">
      {/* HEADER */}
      <header className="provider-availability-heading">
        <div>
          <p className="provider-availability-eyebrow">
            TRANSPORTATION CAPABILITY
          </p>

          <h1>Lịch khả dụng</h1>

          <p className="provider-availability-description">
            Theo dõi lịch xe, ưu tiên khung giờ sắp tới
            và quản lý năng lực phương tiện.
          </p>
        </div>

        <button
          type="button"
          className="provider-availability-primary"
          onClick={openCreateForm}
          disabled={
            activeOffers.length === 0 ||
            loading
          }
        >
          + Tạo lịch khả dụng
        </button>
      </header>

      {/* ALERTS */}
      {error && !showForm && (
        <div
          className="provider-availability-alert is-error"
          role="alert"
        >
          {error}

          <button
            type="button"
            onClick={() => void loadData()}
          >
            Thử lại
          </button>
        </div>
      )}

      {success && (
        <div
          className="provider-availability-alert is-success"
          role="status"
        >
          {success}
        </div>
      )}

      {/* SUMMARY */}
      <section className="provider-availability-summary">
        <article className="provider-availability-summary-card">
          <span>SẮP TỚI</span>
          <strong>{timeCounts.upcoming}</strong>
        </article>

        <article className="provider-availability-summary-card">
          <span>ĐANG TRONG KHUNG GIỜ</span>
          <strong>{timeCounts.ongoing}</strong>
        </article>

        <article className="provider-availability-summary-card">
          <span>ĐÃ QUA</span>
          <strong>{timeCounts.past}</strong>
        </article>
      </section>

      {/* LIST */}
      <section className="provider-availability-section">
        <div className="provider-availability-section-heading">
          <div>
            <h2>Danh sách lịch khả dụng</h2>
            <p>
              Lịch đang trong khung giờ và sắp tới
              được ưu tiên hiển thị.
              Mỗi trang tối đa {PAGE_SIZE} bản ghi.
            </p>
          </div>

          <button
            type="button"
            className="provider-availability-refresh"
            onClick={() => void loadData()}
            disabled={loading}
          >
            {loading ? 'Đang tải...' : '↻ Làm mới'}
          </button>
        </div>

        {/* EXISTING FILTERS */}
        <div className="provider-availability-filters">
          <label>
            <span aria-hidden="true">⌕</span>

            <input
              type="search"
              placeholder="Tìm mã lịch hoặc phương tiện..."
              value={search}
              onChange={(event) => {
                setSearch(event.target.value)
                setCurrentPage(1)
              }}
            />
          </label>

          <input
            type="date"
            aria-label="Lọc theo ngày"
            value={dateFilter}
            onChange={(event) => {
              setDateFilter(event.target.value)
              setCurrentPage(1)
            }}
          />

          <select
            aria-label="Lọc theo trạng thái khả dụng"
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value)
              setCurrentPage(1)
            }}
          >
            <option value="ALL">Tất cả trạng thái</option>
            <option value="AVAILABLE">Khả dụng</option>
            <option value="UNAVAILABLE">
              Không khả dụng
            </option>
          </select>
        </div>

        {/* TIME FILTERS */}
        <div className="availability-time-toolbar">
          <div className="availability-time-filters">
            {([
              {
                value: 'ALL',
                label: 'Tất cả',
                count: availability.length,
              },
              {
                value: 'ONGOING',
                label: 'Đang trong khung giờ',
                count: timeCounts.ongoing,
              },
              {
                value: 'UPCOMING',
                label: 'Sắp tới',
                count: timeCounts.upcoming,
              },
              {
                value: 'PAST',
                label: 'Đã qua',
                count: timeCounts.past,
              },
            ] as const).map((option) => (
              <button
                key={option.value}
                type="button"
                className={
                  timeFilter === option.value
                    ? 'active'
                    : ''
                }
                onClick={() =>
                  changeTimeFilter(option.value)
                }
                aria-pressed={
                  timeFilter === option.value
                }
              >
                {option.label}
                <span>{option.count}</span>
              </button>
            ))}
          </div>

          <button
            type="button"
            className="availability-reset-button"
            onClick={resetFilters}
          >
            Xóa bộ lọc
          </button>
        </div>

        {/* TABLE */}
        {loading ? (
          <div className="provider-availability-empty">
            Đang tải dữ liệu lịch khả dụng...
          </div>
        ) : filteredAvailability.length === 0 ? (
          <div className="provider-availability-empty">
            <strong>Chưa có lịch phù hợp</strong>
            <p>
              Thử thay đổi bộ lọc hoặc tạo lịch khả dụng mới.
            </p>
          </div>
        ) : (
          <>
            <div className="provider-availability-table-wrap">
              <table className="provider-availability-table">
                <thead>
                  <tr>
                    <th>MÃ LỊCH</th>
                    <th>PHƯƠNG TIỆN</th>
                    <th>NGÀY PHỤC VỤ</th>
                    <th>KHUNG GIỜ</th>
                    <th>SỐ LƯỢNG XE</th>
                    <th>TRẠNG THÁI</th>
                    <th>THAO TÁC</th>
                  </tr>
                </thead>

                <tbody>
                  {paginatedAvailability.map((item) => {
                    const offer = offerMap.get(
                      item.provider_vehicle_offer_id
                    )

                    const vehicleType = offer
                      ? vehicleTypeMap.get(
                          offer.vehicle_type_id
                        )
                      : undefined

                    const timeState = getTimeStatus(
                      item,
                      now
                    )

                    const isReadOnly =
                      timeState !== 'UPCOMING'

                    return (
                      <tr
                        key={item.id}
                        className={
                          timeState === 'PAST'
                            ? 'is-time-expired'
                            : ''
                        }
                      >
                        <td>
                          <strong>AV-{item.id}</strong>
                        </td>

                        <td>
                          <strong>
                            {vehicleType?.vehicle_name ||
                              (
                                offer
                                  ? `Loại xe #${offer.vehicle_type_id}`
                                  : `Offer #${item.provider_vehicle_offer_id}`
                              )}
                          </strong>

                          <small>
                            {vehicleType
                              ? (
                                `${vehicleType.vehicle_code} · ` +
                                `Mã cấu hình: ${offer?.id} · ` +
                                `Tải trọng: ${Number(
                                  vehicleType.capacity_kg
                                ).toLocaleString('vi-VN')} kg`
                              )
                              : `Offer #${item.provider_vehicle_offer_id}`
                            }
                          </small>
                        </td>

                        <td>
                          {formatDate(item.service_date)}
                        </td>

                        <td>
                          {formatTime(item.start_time)}
                          {' – '}
                          {formatTime(item.end_time)}
                        </td>

                        <td>
                          {item.available_vehicle_count}
                        </td>

                        <td>
                          <div className="availability-status-stack">
                            <span
                              className={`provider-availability-status ${
                                item.availability_status ===
                                'AVAILABLE'
                                  ? 'is-available'
                                  : 'is-unavailable'
                              }`}
                            >
                              {item.availability_status ===
                              'AVAILABLE'
                                ? 'Khả dụng'
                                : 'Không khả dụng'}
                            </span>

                            {timeState === 'ONGOING' && (
                              <small className="availability-time-label is-ongoing">
                                Đang trong khung giờ
                              </small>
                            )}

                            {timeState === 'PAST' && (
                              <small className="availability-time-label is-past">
                                Đã qua
                              </small>
                            )}
                          </div>
                        </td>

                        <td>
                          {!isReadOnly ? (
                            <button
                              type="button"
                              className="provider-availability-edit"
                              onClick={() =>
                                openEditForm(item)
                              }
                            >
                              Chỉnh sửa
                            </button>
                          ) : (
                            <span className="provider-availability-readonly-label">
                              Chỉ xem
                            </span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* PAGINATION */}
            <div className="availability-pagination">
              <span className="availability-pagination-info">
                Hiển thị {firstItem}–{lastItem}
                {' / '}
                {filteredAvailability.length} lịch
              </span>

              <div className="availability-pagination-actions">
                <button
                  type="button"
                  disabled={safePage <= 1}
                  onClick={() =>
                    setCurrentPage(
                      Math.max(1, safePage - 1)
                    )
                  }
                >
                  ‹ Trước
                </button>

                <span className="availability-page-current">
                  Trang {safePage}/{totalPages}
                </span>

                <button
                  type="button"
                  disabled={safePage >= totalPages}
                  onClick={() =>
                    setCurrentPage(
                      Math.min(
                        totalPages,
                        safePage + 1
                      )
                    )
                  }
                >
                  Sau ›
                </button>
              </div>
            </div>
          </>
        )}
      </section>

      {/* CREATE / EDIT MODAL */}
      {showForm && (
        <div className="provider-availability-modal-overlay">
          <section
            className="provider-availability-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="provider-availability-modal-title"
          >
            <h2 id="provider-availability-modal-title">
              {editing
                ? 'Chỉnh sửa lịch khả dụng'
                : 'Tạo lịch khả dụng'}
            </h2>

            <p className="provider-availability-modal-description">
              Khai báo ngày, giờ và số lượng phương tiện
              cho khung thời gian này.
            </p>

            {error && (
              <div
                className="provider-availability-alert is-error"
                role="alert"
              >
                {error}
              </div>
            )}

            <form
              className="provider-availability-form"
              onSubmit={handleSubmit}
            >
              {!editing && (
                <label>
                  Phương tiện

                  <select
                    value={form.provider_vehicle_offer_id}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        provider_vehicle_offer_id:
                          event.target.value,
                      }))
                    }
                    required
                  >
                    <option value="">
                      Chọn loại phương tiện
                    </option>

                    {activeOffers.map((offer) => {
                      const vehicleType =
                        vehicleTypeMap.get(
                          offer.vehicle_type_id
                        )

                      return (
                        <option
                          key={offer.id}
                          value={offer.id}
                        >
                          {vehicleType
                            ? (
                              `${vehicleType.vehicle_name} ` +
                              `(${vehicleType.vehicle_code}) · ` +
                              `${Number(
                                vehicleType.capacity_kg
                              ).toLocaleString('vi-VN')} kg · ` +
                              `Mã cấu hình: ${offer.id}`
                            )
                            : `Loại xe #${offer.vehicle_type_id} · Offer #${offer.id}`
                          }
                        </option>
                      )
                    })}
                  </select>
                </label>
              )}

              <div className="provider-availability-form-grid">
                <label>
                  Ngày phục vụ

                  <input
                    type="date"
                    min={getVietnamNow().date}
                    value={form.service_date}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        service_date:
                          event.target.value,
                      }))
                    }
                    required
                  />
                </label>

                <label>
                  Số lượng xe

                  <input
                    type="number"
                    min={
                      form.availability_status ===
                      'AVAILABLE'
                        ? 1
                        : 0
                    }
                    step="1"
                    value={form.available_vehicle_count}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        available_vehicle_count:
                          event.target.value,
                      }))
                    }
                    required
                  />
                </label>

                <label>
                  Giờ bắt đầu

                  <input
                    type="time"
                    step={60}
                    value={form.start_time}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        start_time: event.target.value,
                      }))
                    }
                    required
                  />
                </label>

                <label>
                  Giờ kết thúc

                  <input
                    type="time"
                    step={60}
                    value={form.end_time}
                    min={form.start_time || undefined}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        end_time: event.target.value,
                      }))
                    }
                    required
                  />
                </label>
              </div>

              <label>
                Trạng thái

                <select
                  value={form.availability_status}
                  onChange={(event) => {
                    const nextStatus =
                      event.target.value as ProviderAvailabilityStatus

                    setForm((current) => ({
                      ...current,
                      availability_status: nextStatus,

                      available_vehicle_count:
                        nextStatus === 'UNAVAILABLE'
                          ? '0'
                          : current.available_vehicle_count ===
                            '0'
                            ? '1'
                            : current.available_vehicle_count,
                    }))
                  }}
                >
                  <option value="AVAILABLE">
                    Khả dụng
                  </option>

                  <option value="UNAVAILABLE">
                    Không khả dụng
                  </option>
                </select>
              </label>

              <div className="provider-availability-form-actions">
                <button
                  type="button"
                  onClick={closeForm}
                  disabled={submitting}
                >
                  Hủy
                </button>

                <button
                  type="submit"
                  disabled={submitting}
                >
                  {submitting
                    ? 'Đang lưu...'
                    : editing
                      ? 'Lưu thay đổi'
                      : 'Tạo lịch'}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </main>
  )
}
