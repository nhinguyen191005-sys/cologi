
import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { ApiError } from '../services/api/client'
import {
  createProviderVehicleOffer,
  listProviderVehicleOffers,
  listProviderVehicleTypes,
  updateProviderVehicleOffer,
} from '../services/api/providers'
import type {
  ProviderFuelType,
  ProviderVehicleOffer,
  ProviderVehicleOfferCreateInput,
  ProviderVehicleOfferUpdateInput,
  ProviderVehicleType,
  ProviderVehicleTypeCreateInput,
} from '../types/provider'
import './VehicleOffersPage.css'

type OfferFilter = 'ALL' | 'ACTIVE' | 'INACTIVE'

interface OfferFormState {
  available_vehicle_count: string
  fuel_type: ProviderFuelType
  operating_start_time: string
  operating_end_time: string
  fixed_quote_vnd: string
  estimated_cost_per_km_vnd: string
  is_active: boolean
  vehicle_note: string
}

const emptyForm: OfferFormState = {
  available_vehicle_count: '',
  fuel_type: 'DIESEL',
  operating_start_time: '',
  operating_end_time: '',
  fixed_quote_vnd: '',
  estimated_cost_per_km_vnd: '',
  is_active: true,
  vehicle_note: '',
}

const fuelLabels: Record<ProviderFuelType, string> = {
  ELECTRIC: 'Điện',
  GASOLINE: 'Xăng',
  DIESEL: 'Dầu diesel',
}

function formatNumber(value: string | number | null, suffix = ''): string {
  if (value === null || value === '') return 'Chưa thiết lập'
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return `${number.toLocaleString('vi-VN', { maximumFractionDigits: 2 })}${suffix}`
}

function formatPrice(value: string | null): string {
  if (value === null || value === '') return 'Chưa thiết lập'
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return `${number.toLocaleString('vi-VN', { maximumFractionDigits: 2 })} ₫`
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'
    if (error.status === 403) return 'Tài khoản chưa có quyền truy cập năng lực vận tải.'
    return error.message
  }
  return error instanceof Error ? error.message : 'Đã xảy ra lỗi. Vui lòng thử lại.'
}

function toForm(offer: ProviderVehicleOffer): OfferFormState {
  return {
    available_vehicle_count: String(offer.available_vehicle_count),
    fuel_type: offer.fuel_type,
    operating_start_time: offer.operating_start_time?.slice(0, 5) ?? '',
    operating_end_time: offer.operating_end_time?.slice(0, 5) ?? '',
    fixed_quote_vnd: offer.fixed_quote_vnd ?? '',
    estimated_cost_per_km_vnd: offer.estimated_cost_per_km_vnd ?? '',
    is_active: offer.is_active,
    vehicle_note: offer.vehicle_note ?? '',
  }
}

export default function VehicleOffersPage() {
  const [offers, setOffers] = useState<ProviderVehicleOffer[]>([])
  const [vehicleTypes, setVehicleTypes] = useState<ProviderVehicleType[]>([])

  const [vehicleTypeMode, setVehicleTypeMode] = useState<'EXISTING' | 'NEW'>('EXISTING')
  const [selectedVehicleTypeId, setSelectedVehicleTypeId] = useState('')

  const [newVehicleType, setNewVehicleType] = useState<ProviderVehicleTypeCreateInput>({
    vehicle_name: '',
    capacity_kg: '',
    description: '',
  })
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<OfferFilter>('ALL')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editingOffer, setEditingOffer] = useState<ProviderVehicleOffer | null>(null)
  const [form, setForm] = useState<OfferFormState>(emptyForm)

  const loadOffers = useCallback(async () => {
    setIsLoading(true)
    setError('')

    try {
      const [offerData, vehicleTypeData] = await Promise.all([
        listProviderVehicleOffers(),
        listProviderVehicleTypes(),
      ])

      setOffers(offerData)
      setVehicleTypes(vehicleTypeData)
    } catch (loadError) {
      setError(getErrorMessage(loadError))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadOffers()
  }, [loadOffers])

  const vehicleTypeById = useMemo(
    () => new Map(vehicleTypes.map((item) => [item.id, item])),
    [vehicleTypes],
  )

  const filteredOffers = useMemo(() => {
    const keyword = search.trim().toLocaleLowerCase('vi')

    return offers.filter((offer) => {
      const matchesStatus =
        filter === 'ALL' ||
        (filter === 'ACTIVE' && offer.is_active) ||
        (filter === 'INACTIVE' && !offer.is_active)

      const vehicleType = vehicleTypeById.get(offer.vehicle_type_id)
      const searchable = [
        `xe ${offer.vehicle_type_id}`,
        `#${offer.id}`,
        offer.id,
        vehicleType?.vehicle_code ?? '',
        vehicleType?.vehicle_name ?? '',
      ].join(' ').toLocaleLowerCase('vi')

      return matchesStatus && (!keyword || searchable.includes(keyword))
    })
  }, [offers, search, filter, vehicleTypeById])

  const activeCount = offers.filter((offer) => offer.is_active).length
  const inactiveCount = offers.length - activeCount

  const updateForm = (field: keyof OfferFormState, value: string | boolean) => {
    setForm((current) => ({ ...current, [field]: value }))
  }

  const openCreateForm = () => {
    setEditingOffer(null)
    setForm(emptyForm)

    setVehicleTypeMode('EXISTING')
    setSelectedVehicleTypeId(vehicleTypes[0] ? String(vehicleTypes[0].id) : '')

    setNewVehicleType({
      vehicle_name: '',
      capacity_kg: '',
      description: '',
    })

    setFormError('')
    setSuccessMessage('')
    setShowForm(true)
  }

  const openEditForm = (offer: ProviderVehicleOffer) => {
    setEditingOffer(offer)
    setSelectedVehicleTypeId(String(offer.vehicle_type_id))
    setForm(toForm(offer))
    setFormError('')
    setSuccessMessage('')
    setShowForm(true)
  }

  const closeForm = () => {
    if (isSaving) return
    setShowForm(false)
    setEditingOffer(null)
    setSelectedVehicleTypeId('')
    setFormError('')
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    setFormError('')
    setSuccessMessage('')

    if (!editingOffer) {
      if (vehicleTypeMode === 'EXISTING' && !selectedVehicleTypeId) {
        setFormError('Vui lòng chọn loại phương tiện có sẵn.')
        return
      }

      if (vehicleTypeMode === 'NEW') {
        const vehicleName = newVehicleType.vehicle_name.trim()
        const capacityKg = newVehicleType.capacity_kg.trim()
        const capacityValue = Number(capacityKg)

        if (!vehicleName) {
          setFormError('Vui lòng nhập tên loại phương tiện.')
          return
        }

        if (
          !capacityKg ||
          !Number.isFinite(capacityValue) ||
          capacityValue <= 0
        ) {
          setFormError('Tải trọng phải là số lớn hơn 0.')
          return
        }

        if (!/^\d+(\.\d{1,3})?$/.test(capacityKg)) {
          setFormError('Tải trọng chỉ được có tối đa 3 chữ số thập phân.')
          return
        }
      }
    }

    const capacity = Number(form.available_vehicle_count)

    if (!Number.isInteger(capacity) || capacity < 0) {
      setFormError('Số lượng phương tiện phải là số nguyên không âm.')
      return
    }

    if (form.is_active && capacity <= 0) {
      setFormError('Phương tiện đang hoạt động phải có số lượng lớn hơn 0.')
      return
    }

    const start = form.operating_start_time.trim()
    const end = form.operating_end_time.trim()

    if (Boolean(start) !== Boolean(end)) {
      setFormError('Vui lòng khai báo cả giờ bắt đầu và giờ kết thúc, hoặc để trống cả hai.')
      return
    }

    if (start && end && start >= end) {
      setFormError('Giờ kết thúc phải sau giờ bắt đầu.')
      return
    }

    const validateRate = (value: string, label: string) => {
      if (value.trim() === '') return ''
      const number = Number(value)
      return Number.isFinite(number) && number >= 0
        ? ''
        : `${label} phải là số không âm.`
    }

    const rateError =
      validateRate(form.fixed_quote_vnd, 'Giá cố định') ||
      validateRate(form.estimated_cost_per_km_vnd, 'Chi phí mỗi km')

    if (rateError) {
      setFormError(rateError)
      return
    }

    const commonPayload = {
      available_vehicle_count: capacity,
      fuel_type: form.fuel_type,
      operating_start_time: start || null,
      operating_end_time: end || null,
      fixed_quote_vnd: form.fixed_quote_vnd.trim() || null,
      estimated_cost_per_km_vnd: form.estimated_cost_per_km_vnd.trim() || null,
      is_active: form.is_active,
      vehicle_note: form.vehicle_note.trim(),
    }

    setIsSaving(true)

    try {
      if (editingOffer) {
        const payload: ProviderVehicleOfferUpdateInput = commonPayload
        await updateProviderVehicleOffer(editingOffer.id, payload)
        setSuccessMessage(`Đã cập nhật cấu hình phương tiện #${editingOffer.id}.`)
      } else {
        const vehicleTypePayload =
          vehicleTypeMode === 'NEW'
            ? {
                new_vehicle_type: {
                  vehicle_name: newVehicleType.vehicle_name.trim(),
                  capacity_kg: newVehicleType.capacity_kg.trim(),
                  description: newVehicleType.description?.trim() || '',
                },
              }
            : {
                vehicle_type_id: Number(selectedVehicleTypeId),
              }

        const payload: ProviderVehicleOfferCreateInput = {
          ...commonPayload,
          ...vehicleTypePayload,
        }

        const createdOffer = await createProviderVehicleOffer(payload)

        setSuccessMessage(
          vehicleTypeMode === 'NEW'
            ? `Đã tạo loại phương tiện mới và cấu hình #${createdOffer.id}.`
            : `Đã tạo cấu hình phương tiện #${createdOffer.id}.`,
        )
      }

      setShowForm(false)
      setEditingOffer(null)
      setSelectedVehicleTypeId('')
      await loadOffers()
    } catch (saveError) {
      setFormError(getErrorMessage(saveError))
    } finally {
      setIsSaving(false)
    }
  }

  const toggleOfferStatus = async (offer: ProviderVehicleOffer) => {
    const nextStatus = !offer.is_active

    if (nextStatus && offer.available_vehicle_count <= 0) {
      setError('Không thể kích hoạt phương tiện khi số lượng khả dụng bằng 0.')
      return
    }

    if (!window.confirm(
      `Bạn có chắc muốn ${nextStatus ? 'kích hoạt' : 'ngừng hoạt động'} cấu hình phương tiện #${offer.id}?`,
    )) return

    setError('')
    setSuccessMessage('')

    try {
      await updateProviderVehicleOffer(offer.id, { is_active: nextStatus })
      setSuccessMessage(
        `Đã ${nextStatus ? 'kích hoạt' : 'ngừng hoạt động'} cấu hình phương tiện #${offer.id}.`,
      )
      await loadOffers()
    } catch (updateError) {
      setError(getErrorMessage(updateError))
    }
  }

  return (
    <div className="provider-offers-page">
      <section className="provider-offers-heading">
        <div>
          <p className="provider-offers-eyebrow">TRANSPORT PROVIDER WORKSPACE</p>
          <h1>Đội xe và năng lực vận tải</h1>
          <p className="provider-offers-description">
            Theo dõi số lượng phương tiện, nhiên liệu, giờ hoạt động và cấu hình báo giá.
          </p>
        </div>

        <div className="provider-offers-heading-actions">
          <button
            type="button"
            className="provider-offers-refresh"
            onClick={openCreateForm}
            disabled={isLoading}
          >
            + Thêm phương tiện
          </button>
          <button
            type="button"
            className="provider-offers-refresh"
            onClick={() => void loadOffers()}
            disabled={isLoading}
          >
            ↻ Làm mới
          </button>
        </div>
      </section>

      {successMessage && (
        <div className="provider-offers-success" role="status">
          {successMessage}
          <button
            type="button"
            onClick={() => setSuccessMessage('')}
            aria-label="Đóng thông báo"
          >
            ×
          </button>
        </div>
      )}

      <section className="provider-offers-summary" aria-label="Tổng quan đội xe">
        <article className="provider-offers-summary-card">
          <span>TỔNG CẤU HÌNH</span>
          <strong>{isLoading ? '—' : offers.length}</strong>
        </article>
        <article className="provider-offers-summary-card">
          <span>ĐANG HOẠT ĐỘNG</span>
          <strong>{isLoading ? '—' : activeCount}</strong>
        </article>
        <article className="provider-offers-summary-card">
          <span>NGỪNG HOẠT ĐỘNG</span>
          <strong>{isLoading ? '—' : inactiveCount}</strong>
        </article>
      </section>

      <section className="provider-offers-section">
        <div className="provider-offers-section-heading">
          <div>
            <h2>Cấu hình phương tiện</h2>
            <p>Dữ liệu được giới hạn theo nhà vận tải đang đăng nhập.</p>
          </div>
          <span>{isLoading ? 'Đang tải...' : `${filteredOffers.length} kết quả`}</span>
        </div>

        <div className="provider-offers-filters">
          <label>
            <span aria-hidden="true">⌕</span>
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Tìm mã cấu hình hoặc mã loại xe..."
              aria-label="Tìm cấu hình phương tiện"
            />
          </label>
          <select
            value={filter}
            onChange={(event) => setFilter(event.target.value as OfferFilter)}
            aria-label="Lọc trạng thái phương tiện"
          >
            <option value="ALL">Tất cả trạng thái</option>
            <option value="ACTIVE">Đang hoạt động</option>
            <option value="INACTIVE">Ngừng hoạt động</option>
          </select>
        </div>

        {error && (
          <div className="provider-offers-error" role="alert">
            <span>{error}</span>
            <button type="button" onClick={() => void loadOffers()}>Thử lại</button>
          </div>
        )}

        {isLoading ? (
          <div className="provider-offers-empty">Đang tải cấu hình phương tiện...</div>
        ) : !error && filteredOffers.length === 0 ? (
          <div className="provider-offers-empty">
            <strong>Chưa có cấu hình phương tiện phù hợp</strong>
            <p>Thử thay đổi từ khóa hoặc bộ lọc, hoặc tạo cấu hình mới.</p>
          </div>
        ) : (
          <div className="provider-offers-table-wrap">
            <table className="provider-offers-table">
              <thead>
                <tr>
                  <th>CẤU HÌNH</th>
                  <th>SỐ LƯỢNG</th>
                  <th>NHIÊN LIỆU</th>
                  <th>GIỜ HOẠT ĐỘNG</th>
                  <th>GIÁ CỐ ĐỊNH</th>
                  <th>CHI PHÍ / KM</th>
                  <th>TRẠNG THÁI</th>
                  <th>THAO TÁC</th>
                </tr>
              </thead>
              <tbody>
                {filteredOffers.map((offer) => {
                  const vehicleType = vehicleTypeById.get(offer.vehicle_type_id)

                  return (
                    <tr key={offer.id}>
                      <td>
                        <strong>{vehicleType?.vehicle_name ?? `Loại xe #${offer.vehicle_type_id}`}</strong>
                        <small>
                          {vehicleType?.vehicle_code ?? `VehicleType #${offer.vehicle_type_id}`}
                          {' · '}Mã cấu hình: {offer.id}
                        </small>
                        {vehicleType && (
                          <small>Tải trọng: {formatNumber(vehicleType.capacity_kg, ' kg')}</small>
                        )}
                      </td>
                      <td>{formatNumber(offer.available_vehicle_count, ' xe')}</td>
                      <td>{fuelLabels[offer.fuel_type]}</td>
                      <td>
                        {offer.operating_start_time && offer.operating_end_time
                          ? `${offer.operating_start_time.slice(0, 5)} – ${offer.operating_end_time.slice(0, 5)}`
                          : 'Chưa thiết lập'}
                      </td>
                      <td>{formatPrice(offer.fixed_quote_vnd)}</td>
                      <td>{formatPrice(offer.estimated_cost_per_km_vnd)}</td>
                      <td>
                        <span className={`provider-offers-status ${offer.is_active ? 'is-active' : 'is-inactive'}`}>
                          {offer.is_active ? 'Đang hoạt động' : 'Ngừng hoạt động'}
                        </span>
                      </td>
                      <td>
                        <div className="provider-offers-actions">
                          <button type="button" onClick={() => openEditForm(offer)}>Sửa</button>
                          <button
                            type="button"
                            className={offer.is_active ? 'is-danger' : 'is-activate'}
                            onClick={() => void toggleOfferStatus(offer)}
                          >
                            {offer.is_active ? 'Ngừng' : 'Kích hoạt'}
                          </button>
                        </div>
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
        <div
          className="provider-offers-modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeForm()
          }}
        >
          <section
            className="provider-offers-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="provider-offers-form-title"
          >
            <div className="provider-offers-modal-heading">
              <div>
                <p className="provider-offers-eyebrow">
                  {editingOffer ? 'EDIT VEHICLE OFFER' : 'NEW VEHICLE OFFER'}
                </p>
                <h2 id="provider-offers-form-title">
                  {editingOffer
                    ? `Cập nhật phương tiện #${editingOffer.id}`
                    : 'Tạo cấu hình phương tiện'}
                </h2>
                <p>
                  {editingOffer
                    ? `Loại xe #${editingOffer.vehicle_type_id} · Không thể thay đổi loại xe tại đây.`
                    : 'Chọn loại xe và khai báo năng lực vận tải của nhà cung cấp.'}
                </p>
              </div>
              <button
                type="button"
                onClick={closeForm}
                disabled={isSaving}
                aria-label="Đóng"
              >
                ×
              </button>
            </div>

            {formError && <div className="provider-offers-error" role="alert">{formError}</div>}

            <form className="provider-offers-form" onSubmit={(event) => void handleSubmit(event)}>
              {!editingOffer && (
                <>
                  <label>
                    <span>Cách khai báo loại phương tiện <b>*</b></span>
                    <select
                      value={vehicleTypeMode}
                      onChange={(event) =>
                        setVehicleTypeMode(event.target.value as 'EXISTING' | 'NEW')
                      }
                    >
                      <option value="EXISTING">Chọn loại phương tiện có sẵn</option>
                      <option value="NEW">Tạo mới loại phương tiện</option>
                    </select>
                  </label>

                  {vehicleTypeMode === 'EXISTING' ? (
                    <label>
                      <span>Loại phương tiện <b>*</b></span>
                      <select
                        required
                        value={selectedVehicleTypeId}
                        onChange={(event) => setSelectedVehicleTypeId(event.target.value)}
                      >
                        <option value="">-- Chọn loại phương tiện --</option>
                        {vehicleTypes.map((vehicleType) => (
                          <option key={vehicleType.id} value={vehicleType.id}>
                            {vehicleType.vehicle_name} ({vehicleType.vehicle_code}) ·
                            {' '}{formatNumber(vehicleType.capacity_kg, ' kg')}
                          </option>
                        ))}
                      </select>
                    </label>
                  ) : (
                    <>
                      <label>
                        <span>Tên loại phương tiện <b>*</b></span>
                        <input
                          required
                          type="text"
                          maxLength={255}
                          value={newVehicleType.vehicle_name}
                          onChange={(event) =>
                            setNewVehicleType((current) => ({
                              ...current,
                              vehicle_name: event.target.value,
                            }))
                          }
                          placeholder="Ví dụ: Xe tải đông lạnh 5 tấn"
                        />
                      </label>

                      <label>
                        <span>Tải trọng (kg) <b>*</b></span>
                        <input
                          required
                          type="number"
                          min="0.001"
                          step="0.001"
                          value={newVehicleType.capacity_kg}
                          onChange={(event) =>
                            setNewVehicleType((current) => ({
                              ...current,
                              capacity_kg: event.target.value,
                            }))
                          }
                          placeholder="Ví dụ: 5000"
                        />
                      </label>

                      <label>
                        <span>Mô tả loại phương tiện</span>
                        <textarea
                          rows={2}
                          value={newVehicleType.description ?? ''}
                          onChange={(event) =>
                            setNewVehicleType((current) => ({
                              ...current,
                              description: event.target.value,
                            }))
                          }
                          placeholder="Mô tả bổ sung (không bắt buộc)"
                        />
                      </label>

                      <p className="provider-offers-note">
                        Mã loại phương tiện sẽ được hệ thống tự động tạo sau khi lưu.
                      </p>
                    </>
                  )}
                </>
              )}

              <label>
                <span>Số lượng phương tiện <b>*</b></span>
                <input
                  required
                  type="number"
                  min="0"
                  step="1"
                  value={form.available_vehicle_count}
                  onChange={(event) => updateForm('available_vehicle_count', event.target.value)}
                />
              </label>

              <label>
                <span>Loại nhiên liệu <b>*</b></span>
                <select
                  value={form.fuel_type}
                  onChange={(event) => updateForm('fuel_type', event.target.value as ProviderFuelType)}
                >
                  <option value="ELECTRIC">Điện</option>
                  <option value="GASOLINE">Xăng</option>
                  <option value="DIESEL">Dầu diesel</option>
                </select>
              </label>

              <div className="provider-offers-form-grid">
                <label>
                  <span>Giờ bắt đầu hoạt động</span>
                  <input
                    type="time"
                    value={form.operating_start_time}
                    onChange={(event) => updateForm('operating_start_time', event.target.value)}
                  />
                </label>
                <label>
                  <span>Giờ kết thúc hoạt động</span>
                  <input
                    type="time"
                    value={form.operating_end_time}
                    onChange={(event) => updateForm('operating_end_time', event.target.value)}
                  />
                </label>
              </div>

              <div className="provider-offers-form-grid">
                <label>
                  <span>Giá cố định (VNĐ)</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={form.fixed_quote_vnd}
                    onChange={(event) => updateForm('fixed_quote_vnd', event.target.value)}
                    placeholder="Để trống nếu chưa thiết lập"
                  />
                </label>
                <label>
                  <span>Chi phí ước tính / km (VNĐ)</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={form.estimated_cost_per_km_vnd}
                    onChange={(event) => updateForm('estimated_cost_per_km_vnd', event.target.value)}
                    placeholder="Để trống nếu chưa thiết lập"
                  />
                </label>
              </div>

              <label>
                <span>Ghi chú phương tiện</span>
                <textarea
                  rows={3}
                  value={form.vehicle_note}
                  onChange={(event) => updateForm('vehicle_note', event.target.value)}
                  placeholder="Thông tin bổ sung (không bắt buộc)"
                />
              </label>

              <label className="provider-offers-checkbox">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(event) => updateForm('is_active', event.target.checked)}
                />
                Cấu hình phương tiện đang hoạt động
              </label>

              <p className="provider-offers-note">
                Để trống đơn giá nghĩa là chưa thiết lập; giá trị 0 là mức giá bằng 0, không phải dữ liệu thiếu.
              </p>

              <div className="provider-offers-form-actions">
                <button type="button" onClick={closeForm} disabled={isSaving}>Hủy</button>
                <button type="submit" disabled={isSaving}>
                  {isSaving
                    ? 'Đang lưu...'
                    : editingOffer
                      ? 'Lưu thay đổi'
                      : 'Tạo cấu hình'}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  )
}
