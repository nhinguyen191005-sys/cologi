
import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
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

type FormValues = {
  provider_vehicle_offer_id: string
  service_date: string
  start_time: string
  end_time: string
  available_vehicle_count: string
  availability_status: ProviderAvailabilityStatus
}

const initialForm: FormValues = {
  provider_vehicle_offer_id: '',
  service_date: '',
  start_time: '',
  end_time: '',
  available_vehicle_count: '1',
  availability_status: 'AVAILABLE',
}

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
      .flatMap((value) => Array.isArray(value) ? value : [value])
      .filter((value): value is string => typeof value === 'string')

    if (messages.length > 0) return messages.join(' ')
  }

  return apiError.message || 'Đã xảy ra lỗi. Vui lòng thử lại.'
}

function formatDate(date: string): string {
  if (!date) return '—'
  const [year, month, day] = date.split('-')
  return `${day}/${month}/${year}`
}

function formatTime(time: string): string {
  return time.slice(0, 5)
}


type AvailabilityTimeState =
  | 'PAST'
  | 'ENDED'
  | 'UPCOMING'
  | 'ONGOING'
  | 'FUTURE'

function getHoChiMinhDateTime(timestamp: number) {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Ho_Chi_Minh',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(timestamp))

  const values = Object.fromEntries(
    parts.map((part) => [part.type, part.value]),
  )

  return {
    date: `${values.year}-${values.month}-${values.day}`,
    time: `${values.hour}:${values.minute}:${values.second}`,
  }
}

function getAvailabilityTimeState(
  item: ProviderAvailability,
  timestamp: number,
): AvailabilityTimeState {
  const now = getHoChiMinhDateTime(timestamp)
  const startTime = formatTime(item.start_time)
  const endTime = formatTime(item.end_time)

  if (item.service_date < now.date) {
    return 'PAST'
  }

  if (item.service_date > now.date) {
    return 'FUTURE'
  }

  if (endTime <= now.time) {
    return 'ENDED'
  }

  if (startTime > now.time) {
    return 'UPCOMING'
  }

  return 'ONGOING'
}


export default function ProviderAvailabilityPage() {
  const [availability, setAvailability] = useState<ProviderAvailability[]>([])
  const [offers, setOffers] = useState<ProviderVehicleOffer[]>([])
  const [vehicleTypes, setVehicleTypes] = useState<ProviderVehicleType[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [search, setSearch] = useState('')
  const [dateFilter, setDateFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<ProviderAvailability | null>(null)
  const [form, setForm] = useState<FormValues>(initialForm)

  const [nowTimestamp, setNowTimestamp] = useState(() => Date.now())

  useEffect(() => {
    const timer = window.setInterval(() => {
      setNowTimestamp(Date.now())
    }, 1000)

    return () => window.clearInterval(timer)
  }, [])

  const loadData = useCallback(async () => {
    setLoading(true)
    setError('')

    try {
      const [availabilityData, offerData, vehicleTypeData] = await Promise.all([
        listProviderAvailability(),
        listProviderVehicleOffers(),
        listProviderVehicleTypes(),
      ])

      setAvailability(availabilityData)
      setOffers(offerData)
      setVehicleTypes(vehicleTypeData)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadData()
  }, [loadData])

  
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
    [offers],
  )


  const filteredAvailability = useMemo(() => {
    const keyword = search.trim().toLowerCase()

    return availability.filter((item) => {
      const offer = offers.find(
        (candidate) => candidate.id === item.provider_vehicle_offer_id,
      )

      const matchesSearch =
        !keyword ||
        String(item.id).includes(keyword) ||
        String(item.provider_vehicle_offer_id).includes(keyword) ||
        String(offer?.vehicle_type_id ?? '').includes(keyword)

      const matchesDate = !dateFilter || item.service_date === dateFilter

      const matchesStatus =
        statusFilter === 'ALL' ||
        item.availability_status === statusFilter

      return matchesSearch && matchesDate && matchesStatus
    })
  }, [availability, offers, search, dateFilter, statusFilter])

  const availableCount = availability.filter(
    (item) => item.availability_status === 'AVAILABLE',
  ).length

  const unavailableCount = availability.filter(
    (item) => item.availability_status === 'UNAVAILABLE',
  ).length

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
    setEditing(item)
    setForm({
      provider_vehicle_offer_id: String(item.provider_vehicle_offer_id),
      service_date: item.service_date,
      start_time: formatTime(item.start_time),
      end_time: formatTime(item.end_time),
      available_vehicle_count: String(item.available_vehicle_count),
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
  }

  function validateForm(): string | null {
    if (!editing && !form.provider_vehicle_offer_id) {
      return 'Vui lòng chọn phương tiện.'
    }

    if (!form.service_date || !form.start_time || !form.end_time) {
      return 'Vui lòng nhập đầy đủ ngày và khung giờ.'
    }

    if (form.start_time >= form.end_time) {
      return 'Giờ kết thúc phải sau giờ bắt đầu.'
    }

    const count = Number(form.available_vehicle_count)

    if (!Number.isInteger(count) || count < 0) {
      return 'Số lượng xe phải là số nguyên không âm.'
    }

    if (form.availability_status === 'AVAILABLE' && count <= 0) {
      return 'Lịch khả dụng phải có ít nhất một xe.'
    }

    if (form.availability_status === 'UNAVAILABLE' && count !== 0) {
      return 'Lịch không khả dụng phải có số lượng xe bằng 0.'
    }

    const selectedOffer = offers.find(
      (offer) =>
        offer.id === Number(form.provider_vehicle_offer_id),
    )

    if (
      selectedOffer &&
      count > selectedOffer.available_vehicle_count
    ) {
      return `Số lượng xe không được vượt quá năng lực khai báo (${selectedOffer.available_vehicle_count}).`
    }

    if (selectedOffer?.operating_start_time && selectedOffer.operating_end_time) {
      if (
        form.start_time < selectedOffer.operating_start_time.slice(0, 5) ||
        form.end_time > selectedOffer.operating_end_time.slice(0, 5)
      ) {
        return `Khung giờ phải nằm trong giờ hoạt động ${formatTime(selectedOffer.operating_start_time)}–${formatTime(selectedOffer.operating_end_time)}.`
      }
    }

    return null
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
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
      available_vehicle_count: Number(form.available_vehicle_count),
      availability_status: form.availability_status,
    }

    setSubmitting(true)

    try {
      if (editing) {
        await updateProviderAvailability(editing.id, payload)
        setSuccess('Đã cập nhật lịch khả dụng.')
      } else {
        await createProviderAvailability({
          ...payload,
          provider_vehicle_offer_id: Number(form.provider_vehicle_offer_id),
        })
        setSuccess('Đã tạo lịch khả dụng.')
      }

      setShowForm(false)
      setEditing(null)
      await loadData()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="provider-availability-page">
      <header className="provider-availability-heading">
        <div>
          <p className="provider-availability-eyebrow">TRANSPORTATION CAPABILITY</p>
          <h1>Lịch khả dụng</h1>
          <p className="provider-availability-description">
            Quản lý ngày hoạt động, khung giờ và số lượng phương tiện sẵn sàng phục vụ.
          </p>
        </div>

        <button
          type="button"
          className="provider-availability-primary"
          onClick={openCreateForm}
          disabled={activeOffers.length === 0}
        >
          + Tạo lịch khả dụng
        </button>
      </header>

      {error && !showForm && (
        <div className="provider-availability-alert is-error" role="alert">
          {error}
          <button type="button" onClick={() => void loadData()}>
            Thử lại
          </button>
        </div>
      )}

      {success && (
        <div className="provider-availability-alert is-success" role="status">
          {success}
        </div>
      )}

      <section className="provider-availability-summary">
        <article className="provider-availability-summary-card">
          <span>TỔNG LỊCH</span>
          <strong>{availability.length}</strong>
        </article>
        <article className="provider-availability-summary-card">
          <span>KHẢ DỤNG</span>
          <strong>{availableCount}</strong>
        </article>
        <article className="provider-availability-summary-card">
          <span>KHÔNG KHẢ DỤNG</span>
          <strong>{unavailableCount}</strong>
        </article>
      </section>

      <section className="provider-availability-section">
        <div className="provider-availability-section-heading">
          <div>
            <h2>Danh sách lịch</h2>
            <p>Các khung thời gian do đơn vị vận chuyển khai báo.</p>
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

        <div className="provider-availability-filters">
          <label>
            <span aria-hidden="true">⌕</span>
            <input
              type="search"
              placeholder="Tìm theo mã lịch hoặc phương tiện..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>

          <input
            type="date"
            aria-label="Lọc theo ngày"
            value={dateFilter}
            onChange={(event) => setDateFilter(event.target.value)}
          />

          <select
            aria-label="Lọc theo trạng thái"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="ALL">Tất cả trạng thái</option>
            <option value="AVAILABLE">Khả dụng</option>
            <option value="UNAVAILABLE">Không khả dụng</option>
          </select>
        </div>

        {loading ? (
          <div className="provider-availability-empty">
            Đang tải dữ liệu lịch khả dụng...
          </div>
        ) : filteredAvailability.length === 0 ? (
          <div className="provider-availability-empty">
            <strong>Chưa có lịch phù hợp</strong>
            <p>Thử thay đổi bộ lọc hoặc tạo lịch khả dụng mới.</p>
          </div>
        ) : (
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
                
                {filteredAvailability.map((item) => {
                  const offer = offers.find(
                    (candidate) =>
                      candidate.id === item.provider_vehicle_offer_id,
                  )

                  const vehicleType = vehicleTypes.find(
                    (type) => type.id === offer?.vehicle_type_id,
                  )

                  const timeState = getAvailabilityTimeState(item, nowTimestamp)
                  const isReadOnly =
                    timeState === 'PAST' ||
                    timeState === 'ENDED' ||
                    timeState === 'ONGOING'

                  return (
                    <tr
                      key={item.id}
                      className={
                        timeState === 'PAST' || timeState === 'ENDED'
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
                            (offer
                              ? `Loại xe #${offer.vehicle_type_id}`
                              : `Offer #${item.provider_vehicle_offer_id}`)}
                        </strong>

                        <small>
                          {vehicleType
                            ? `${vehicleType.vehicle_code} · Mã cấu hình: ${offer?.id} · Tải trọng: ${Number(vehicleType.capacity_kg).toLocaleString('vi-VN')} kg`
                            : `Offer #${item.provider_vehicle_offer_id}`}
                        </small>
                      </td>
                      <td>{formatDate(item.service_date)}</td>
                      <td>
                        {formatTime(item.start_time)} – {formatTime(item.end_time)}
                      </td>
                      <td>{item.available_vehicle_count}</td>
                      <td>
                        <span
                          className={`provider-availability-status ${
                            item.availability_status === 'AVAILABLE'
                              ? 'is-available'
                              : 'is-unavailable'
                          }`}
                        >
                          {item.availability_status === 'AVAILABLE'
                            ? 'Khả dụng'
                            : 'Không khả dụng'}
                        </span>
                      </td>
                      <td>
                        
                        {!isReadOnly ? (
                          <button
                            type="button"
                            className="provider-availability-edit"
                            onClick={() => openEditForm(item)}
                          >
                            Chỉnh sửa
                          </button>
                        ) : (
                          <span className="provider-availability-readonly-label">
                            {timeState === 'ONGOING' ? 'Đang diễn ra' : 'Chỉ xem'}
                          </span>
                        )}

                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {showForm && (
        <div className="provider-availability-modal-overlay">
          <section
            className="provider-availability-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="provider-availability-modal-title"
          >
            <h2 id="provider-availability-modal-title">
              {editing ? 'Chỉnh sửa lịch khả dụng' : 'Tạo lịch khả dụng'}
            </h2>
            <p className="provider-availability-modal-description">
              Khai báo ngày, giờ và số lượng phương tiện cho khung thời gian này.
            </p>

            {error && (
              <div className="provider-availability-alert is-error" role="alert">
                {error}
              </div>
            )}

            <form className="provider-availability-form" onSubmit={handleSubmit}>
              {!editing && (
                <label>
                  Phương tiện
                  <select
                    value={form.provider_vehicle_offer_id}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        provider_vehicle_offer_id: event.target.value,
                      }))
                    }
                    required
                  >
                    <option value="">Chọn loại phương tiện</option>
                    {activeOffers.map((offer) => {
                      const vehicleType = vehicleTypes.find(
                        (type) => type.id === offer.vehicle_type_id,
                      )

                      return (
                        <option key={offer.id} value={offer.id}>
                          {vehicleType
                            ? `${vehicleType.vehicle_name} (${vehicleType.vehicle_code}) · ${Number(vehicleType.capacity_kg).toLocaleString('vi-VN')} kg · Mã cấu hình: ${offer.id}`
                            : `Loại xe #${offer.vehicle_type_id} — Offer #${offer.id}`}
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
                    value={form.service_date}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        service_date: event.target.value,
                      }))
                    }
                    required
                  />
                </label>

                <label>
                  Số lượng xe
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={form.available_vehicle_count}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        available_vehicle_count: event.target.value,
                      }))
                    }
                    required
                  />
                </label>

                <label>
                  Giờ bắt đầu
                  <input
                    type="time"
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
                    value={form.end_time}
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
                    const nextStatus = event.target.value as ProviderAvailabilityStatus
                    setForm((current) => ({
                      ...current,
                      availability_status: nextStatus,
                      available_vehicle_count:
                        nextStatus === 'UNAVAILABLE'
                          ? '0'
                          : current.available_vehicle_count === '0'
                            ? '1'
                            : current.available_vehicle_count,
                    }))
                  }}
                >
                  <option value="AVAILABLE">Khả dụng</option>
                  <option value="UNAVAILABLE">Không khả dụng</option>
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
                <button type="submit" disabled={submitting}>
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
