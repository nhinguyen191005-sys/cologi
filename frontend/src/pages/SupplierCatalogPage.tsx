import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { ApiError } from '../services/api/client'
import {
  createSupplierCatalogItem,
  listSupplierAvailableItems,
  listSupplierCargoCategories,
  listSupplierCatalog,
  updateSupplierCatalogItem,
} from '../services/api/suppliers'
import type {
  SupplierAvailableItem,
  SupplierCargoCategory,
  SupplierCatalogCreateInput,
  SupplierCatalogItem,
  SupplierOfferStatus,
} from '../types/supplier'
import './SupplierCatalogPage.css'

type CatalogFilter = 'ALL' | SupplierOfferStatus
type FormMode = 'create' | 'edit'
type SelectionMode = 'existing' | 'new'

interface CatalogFormState {
  item_id: string
  item_name: string
  cargo_category_id: string
  weight_unit: string
  item_description: string
  unit_price_vnd_per_kg: string
  max_daily_supply_kg: string
  lead_time_hours: string
  minimum_order_kg: string
  offer_status: SupplierOfferStatus
}

const emptyForm: CatalogFormState = {
  item_id: '',
  item_name: '',
  cargo_category_id: '',
  weight_unit: 'KG',
  item_description: '',
  unit_price_vnd_per_kg: '',
  max_daily_supply_kg: '',
  lead_time_hours: '',
  minimum_order_kg: '',
  offer_status: 'ACTIVE',
}

const statusLabels: Record<SupplierOfferStatus, string> = {
  ACTIVE: 'Đang cung ứng',
  INACTIVE: 'Ngừng cung ứng',
}

function formatNumber(value: string | number | null, suffix = ''): string {
  if (value === null || value === '') return 'Chưa khai báo'
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return `${number.toLocaleString('vi-VN', { maximumFractionDigits: 3 })}${suffix}`
}

function formatPrice(value: string): string {
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return `${number.toLocaleString('vi-VN', { maximumFractionDigits: 2 })} ₫`
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'
    if (error.status === 403) return 'Tài khoản chưa có quyền truy cập danh mục cung ứng.'
    return error.message
  }
  return error instanceof Error ? error.message : 'Đã xảy ra lỗi. Vui lòng thử lại.'
}

function optionalNumber(value: string): string | null {
  return value.trim() === '' ? null : value.trim()
}

function optionalInteger(value: string): number | null {
  return value.trim() === '' ? null : Number(value)
}

export default function SupplierCatalogPage() {
  const [items, setItems] = useState<SupplierCatalogItem[]>([])
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<CatalogFilter>('ALL')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [isLoadingOptions, setIsLoadingOptions] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [formMode, setFormMode] = useState<FormMode>('create')
  const [selectionMode, setSelectionMode] = useState<SelectionMode>('existing')
  const [editingItem, setEditingItem] = useState<SupplierCatalogItem | null>(null)
  const [availableItems, setAvailableItems] = useState<SupplierAvailableItem[]>([])
  const [categories, setCategories] = useState<SupplierCargoCategory[]>([])
  const [form, setForm] = useState<CatalogFormState>(emptyForm)

  const loadCatalog = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      setItems(await listSupplierCatalog())
    } catch (loadError) {
      setError(getErrorMessage(loadError))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void Promise.resolve().then(() => loadCatalog())
  }, [loadCatalog])

  const filteredItems = useMemo(() => {
    const keyword = search.trim().toLocaleLowerCase('vi')
    return items.filter((item) => {
      const matchesStatus = filter === 'ALL' || item.offer_status === filter
      const searchable = `${item.item_code} ${item.item_name}`.toLocaleLowerCase('vi')
      return matchesStatus && (!keyword || searchable.includes(keyword))
    })
  }, [items, search, filter])

  const activeCount = items.filter((item) => item.offer_status === 'ACTIVE').length
  const inactiveCount = items.filter((item) => item.offer_status === 'INACTIVE').length

  const openCreateForm = async () => {
    setFormMode('create')
    setSelectionMode('existing')
    setEditingItem(null)
    setForm(emptyForm)
    setFormError('')
    setSuccessMessage('')
    setShowForm(true)
    setIsLoadingOptions(true)

    try {
      const [itemOptions, categoryOptions] = await Promise.all([
        listSupplierAvailableItems(),
        listSupplierCargoCategories(),
      ])
      setAvailableItems(itemOptions)
      setCategories(categoryOptions)
    } catch (loadError) {
      setFormError(getErrorMessage(loadError))
    } finally {
      setIsLoadingOptions(false)
    }
  }

  const openEditForm = (item: SupplierCatalogItem) => {
    setFormMode('edit')
    setEditingItem(item)
    setForm({
      ...emptyForm,
      unit_price_vnd_per_kg: item.unit_price_vnd_per_kg,
      max_daily_supply_kg: item.max_daily_supply_kg ?? '',
      lead_time_hours: item.lead_time_hours?.toString() ?? '',
      minimum_order_kg: item.minimum_order_kg ?? '',
      offer_status: item.offer_status,
    })
    setFormError('')
    setSuccessMessage('')
    setShowForm(true)
  }

  const closeForm = () => {
    if (isSaving) return
    setShowForm(false)
    setEditingItem(null)
    setFormError('')
  }

  const updateForm = (field: keyof CatalogFormState, value: string) => {
    setForm((current) => ({ ...current, [field]: value }))
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setFormError('')
    setSuccessMessage('')

    const price = Number(form.unit_price_vnd_per_kg)
    if (!Number.isFinite(price) || price < 0) {
      setFormError('Vui lòng nhập đơn giá hợp lệ, lớn hơn hoặc bằng 0.')
      return
    }

    if (form.max_daily_supply_kg.trim() !== '' &&
      (!Number.isFinite(Number(form.max_daily_supply_kg)) || Number(form.max_daily_supply_kg) < 0.001)) {
      setFormError('Sản lượng tối đa phải lớn hơn hoặc bằng 0,001 kg.')
      return
    }

    if (form.minimum_order_kg.trim() !== '' &&
      (!Number.isFinite(Number(form.minimum_order_kg)) || Number(form.minimum_order_kg) < 0)) {
      setFormError('Số lượng đặt tối thiểu không được âm.')
      return
    }

    if (form.lead_time_hours.trim() !== '' &&
      (!Number.isInteger(Number(form.lead_time_hours)) || Number(form.lead_time_hours) < 0)) {
      setFormError('Lead time phải là số nguyên không âm.')
      return
    }

    if (formMode === 'create' && selectionMode === 'new') {
      if (!form.item_name.trim() || !form.cargo_category_id || !form.weight_unit.trim()) {
        setFormError('Vui lòng nhập tên mặt hàng, danh mục và đơn vị tính.')
        return
      }
    }

    if (formMode === 'create' && selectionMode === 'existing' && !form.item_id) {
      setFormError('Vui lòng chọn mặt hàng có sẵn.')
      return
    }

    setIsSaving(true)
    try {
      if (formMode === 'create') {
        const payload: SupplierCatalogCreateInput = {
          unit_price_vnd_per_kg: form.unit_price_vnd_per_kg.trim(),
          max_daily_supply_kg: optionalNumber(form.max_daily_supply_kg),
          lead_time_hours: optionalInteger(form.lead_time_hours),
          minimum_order_kg: optionalNumber(form.minimum_order_kg),
          offer_status: 'ACTIVE',
        }

        if (selectionMode === 'existing') {
          payload.item_id = Number(form.item_id)
        } else {
          payload.item_name = form.item_name.trim()
          payload.cargo_category_id = Number(form.cargo_category_id)
          payload.weight_unit = form.weight_unit.trim()
          if (form.item_description.trim()) {
            payload.item_description = form.item_description.trim()
          }
        }

        await createSupplierCatalogItem(payload)
        setSuccessMessage('Đã thêm mặt hàng cung ứng thành công.')
      } else if (editingItem) {
        await updateSupplierCatalogItem(editingItem.id, {
          unit_price_vnd_per_kg: form.unit_price_vnd_per_kg.trim(),
          max_daily_supply_kg: optionalNumber(form.max_daily_supply_kg),
          lead_time_hours: optionalInteger(form.lead_time_hours),
          minimum_order_kg: optionalNumber(form.minimum_order_kg),
          offer_status: form.offer_status,
        })
        setSuccessMessage('Đã cập nhật điều kiện cung ứng.')
      }

      setShowForm(false)
      setEditingItem(null)
      await loadCatalog()
    } catch (saveError) {
      setFormError(getErrorMessage(saveError))
    } finally {
      setIsSaving(false)
    }
  }

  const toggleOfferStatus = async (item: SupplierCatalogItem) => {
    const nextStatus: SupplierOfferStatus =
      item.offer_status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'
    const actionLabel = nextStatus === 'ACTIVE' ? 'kích hoạt' : 'ngừng cung ứng'

    if (!window.confirm(`Bạn có chắc muốn ${actionLabel} mặt hàng "${item.item_name}"?`)) {
      return
    }

    setError('')
    setSuccessMessage('')
    try {
      await updateSupplierCatalogItem(item.id, { offer_status: nextStatus })
      setSuccessMessage(
        nextStatus === 'ACTIVE'
          ? `Đã kích hoạt cung ứng mặt hàng "${item.item_name}".`
          : `Đã ngừng cung ứng mặt hàng "${item.item_name}".`,
      )
      await loadCatalog()
    } catch (updateError) {
      setError(getErrorMessage(updateError))
    }
  }

  const offeredItemIds = new Set(items.map((item) => item.item_id))
  const selectableItems = availableItems.filter((item) => !offeredItemIds.has(item.id))

  return (
    <div className="supplier-catalog-page">
      <section className="supplier-catalog-heading">
        <div>
          <p className="supplier-catalog-eyebrow">SUPPLIER WORKSPACE</p>
          <h1>Danh mục cung ứng</h1>
          <p className="supplier-catalog-description">
            Theo dõi mặt hàng, đơn giá và năng lực cung ứng đã khai báo.
          </p>
        </div>
        <div className="supplier-catalog-heading-actions">
          <button
            type="button"
            className="supplier-catalog-primary"
            onClick={() => void openCreateForm()}
          >
            + Thêm mặt hàng
          </button>
          <button
            type="button"
            className="supplier-catalog-refresh"
            onClick={() => void loadCatalog()}
            disabled={isLoading}
          >
            ↻ Làm mới
          </button>
        </div>
      </section>

      {successMessage && (
        <div className="supplier-catalog-success" role="status">
          {successMessage}
          <button type="button" onClick={() => setSuccessMessage('')} aria-label="Đóng thông báo">×</button>
        </div>
      )}

      <section className="supplier-catalog-summary" aria-label="Tổng quan danh mục">
        <article className="supplier-catalog-summary-card">
          <span>TỔNG MẶT HÀNG</span>
          <strong>{isLoading ? '—' : items.length}</strong>
        </article>
        <article className="supplier-catalog-summary-card">
          <span>ĐANG CUNG ỨNG</span>
          <strong>{isLoading ? '—' : activeCount}</strong>
        </article>
        <article className="supplier-catalog-summary-card">
          <span>NGỪNG CUNG ỨNG</span>
          <strong>{isLoading ? '—' : inactiveCount}</strong>
        </article>
      </section>

      <section className="supplier-catalog-section">
        <div className="supplier-catalog-section-heading">
          <div>
            <h2>Thông tin mặt hàng</h2>
            <p>Danh mục chỉ hiển thị dữ liệu thuộc nhà cung cấp đang đăng nhập.</p>
          </div>
          <span className="supplier-catalog-count">
            {isLoading ? 'Đang tải...' : `${filteredItems.length} kết quả`}
          </span>
        </div>

        <div className="supplier-catalog-filters">
          <label className="supplier-catalog-search">
            <span aria-hidden="true">⌕</span>
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Tìm mã hàng hoặc tên mặt hàng..."
              aria-label="Tìm mặt hàng"
            />
          </label>
          <select
            value={filter}
            onChange={(event) => setFilter(event.target.value as CatalogFilter)}
            aria-label="Lọc trạng thái cung ứng"
          >
            <option value="ALL">Tất cả trạng thái</option>
            <option value="ACTIVE">Đang cung ứng</option>
            <option value="INACTIVE">Ngừng cung ứng</option>
          </select>
        </div>

        {error && (
          <div className="supplier-catalog-error" role="alert">
            <span>{error}</span>
            <button type="button" onClick={() => void loadCatalog()}>Thử lại</button>
          </div>
        )}

        {isLoading ? (
          <div className="supplier-catalog-empty">Đang tải danh mục cung ứng...</div>
        ) : !error && filteredItems.length === 0 ? (
          <div className="supplier-catalog-empty">
            <span className="supplier-catalog-empty-icon">▤</span>
            <strong>Chưa có mặt hàng phù hợp</strong>
            <p>Thử thay đổi từ khóa hoặc bộ lọc, hoặc thêm mặt hàng cung ứng mới.</p>
          </div>
        ) : (
          <div className="supplier-catalog-table-wrap">
            <table className="supplier-catalog-table">
              <thead>
                <tr>
                  <th>MẶT HÀNG</th>
                  <th>ĐƠN GIÁ</th>
                  <th>SẢN LƯỢNG TỐI ĐA / NGÀY</th>
                  <th>LEAD TIME</th>
                  <th>ĐƠN TỐI THIỂU</th>
                  <th>TRẠNG THÁI</th>
                  <th>THAO TÁC</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <strong>{item.item_name}</strong>
                      <small>{item.item_code}</small>
                    </td>
                    <td>{formatPrice(item.unit_price_vnd_per_kg)}<small>/ kg</small></td>
                    <td>{formatNumber(item.max_daily_supply_kg, ' kg')}</td>
                    <td>{formatNumber(item.lead_time_hours, ' giờ')}</td>
                    <td>{formatNumber(item.minimum_order_kg, ' kg')}</td>
                    <td>
                      <span className={`supplier-catalog-status supplier-catalog-status-${item.offer_status.toLowerCase()}`}>
                        {statusLabels[item.offer_status]}
                      </span>
                    </td>
                    <td>
                      <div className="supplier-catalog-row-actions">
                        <button type="button" onClick={() => openEditForm(item)}>
                          Sửa
                        </button>
                        <button
                          type="button"
                          className={item.offer_status === 'ACTIVE' ? 'is-danger' : 'is-activate'}
                          onClick={() => void toggleOfferStatus(item)}
                        >
                          {item.offer_status === 'ACTIVE' ? 'Ngừng' : 'Kích hoạt'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {showForm && (
        <div className="supplier-catalog-modal-backdrop" onMouseDown={(event) => {
          if (event.target === event.currentTarget) closeForm()
        }}>
          <section
            className="supplier-catalog-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="supplier-catalog-form-title"
          >
            <div className="supplier-catalog-modal-heading">
              <div>
                <p className="supplier-catalog-eyebrow">
                  {formMode === 'create' ? 'NEW SUPPLY OFFER' : 'EDIT SUPPLY OFFER'}
                </p>
                <h2 id="supplier-catalog-form-title">
                  {formMode === 'create' ? 'Thêm mặt hàng cung ứng' : 'Sửa điều kiện cung ứng'}
                </h2>
              </div>
              <button type="button" className="supplier-catalog-modal-close" onClick={closeForm} aria-label="Đóng">
                ×
              </button>
            </div>

            {formError && <div className="supplier-catalog-error" role="alert">{formError}</div>}

            {isLoadingOptions ? (
              <div className="supplier-catalog-empty">Đang tải danh mục mặt hàng...</div>
            ) : (
              <form className="supplier-catalog-form" onSubmit={(event) => void handleSubmit(event)}>
                {formMode === 'create' ? (
                  <>
                    <div className="supplier-catalog-form-field">
                      <span className="supplier-catalog-form-label">Nguồn mặt hàng</span>
                      <div className="supplier-catalog-choice">
                        <label>
                          <input
                            type="radio"
                            name="selectionMode"
                            checked={selectionMode === 'existing'}
                            onChange={() => setSelectionMode('existing')}
                          />
                          Chọn mặt hàng có sẵn
                        </label>
                        <label>
                          <input
                            type="radio"
                            name="selectionMode"
                            checked={selectionMode === 'new'}
                            onChange={() => setSelectionMode('new')}
                          />
                          Tạo mặt hàng mới
                        </label>
                      </div>
                    </div>

                    {selectionMode === 'existing' ? (
                      <label className="supplier-catalog-form-field">
                        <span className="supplier-catalog-form-label">Mặt hàng <b>*</b></span>
                        <select
                          required
                          value={form.item_id}
                          onChange={(event) => updateForm('item_id', event.target.value)}
                        >
                          <option value="">-- Chọn mặt hàng --</option>
                          {selectableItems.map((item) => (
                            <option key={item.id} value={item.id}>
                              {item.item_code} — {item.item_name}
                            </option>
                          ))}
                        </select>
                        {selectableItems.length === 0 && (
                          <small>Không còn mặt hàng có sẵn phù hợp. Bạn có thể tạo mặt hàng mới.</small>
                        )}
                      </label>
                    ) : (
                      <>
                        <label className="supplier-catalog-form-field">
                          <span className="supplier-catalog-form-label">Tên mặt hàng <b>*</b></span>
                          <input
                            required
                            value={form.item_name}
                            onChange={(event) => updateForm('item_name', event.target.value)}
                            placeholder="Nhập tên mặt hàng"
                          />
                        </label>
                        <div className="supplier-catalog-form-grid">
                          <label className="supplier-catalog-form-field">
                            <span className="supplier-catalog-form-label">Danh mục <b>*</b></span>
                            <select
                              required
                              value={form.cargo_category_id}
                              onChange={(event) => updateForm('cargo_category_id', event.target.value)}
                            >
                              <option value="">-- Chọn danh mục --</option>
                              {categories.map((category) => (
                                <option key={category.id} value={category.id}>
                                  {category.category_name}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className="supplier-catalog-form-field">
                            <span className="supplier-catalog-form-label">Đơn vị tính <b>*</b></span>
                            <input
                              required
                              value={form.weight_unit}
                              onChange={(event) => updateForm('weight_unit', event.target.value)}
                              placeholder="Ví dụ: KG"
                            />
                          </label>
                        </div>
                        <label className="supplier-catalog-form-field">
                          <span className="supplier-catalog-form-label">Mô tả mặt hàng</span>
                          <textarea
                            rows={2}
                            value={form.item_description}
                            onChange={(event) => updateForm('item_description', event.target.value)}
                            placeholder="Thông tin mô tả (không bắt buộc)"
                          />
                        </label>
                        <p className="supplier-catalog-form-note">
                          Mã mặt hàng sẽ được hệ thống tự động tạo. Thông tin mặt hàng mới sẽ được dùng chung trong CoLogi.
                        </p>
                      </>
                    )}
                  </>
                ) : (
                  <div className="supplier-catalog-locked-item">
                    <span>MẶT HÀNG</span>
                    <strong>{editingItem?.item_name}</strong>
                    <small>{editingItem?.item_code} · Thông tin mặt hàng dùng chung không thể chỉnh sửa tại đây.</small>
                  </div>
                )}

                <div className="supplier-catalog-form-divider">
                  <strong>Điều kiện cung ứng</strong>
                  <span>Thông tin riêng của nhà cung cấp</span>
                </div>

                <label className="supplier-catalog-form-field">
                  <span className="supplier-catalog-form-label">Đơn giá (VNĐ / kg) <b>*</b></span>
                  <input
                    required
                    type="number"
                    min="0"
                    step="0.01"
                    value={form.unit_price_vnd_per_kg}
                    onChange={(event) => updateForm('unit_price_vnd_per_kg', event.target.value)}
                    placeholder="Nhập đơn giá"
                  />
                </label>

                <div className="supplier-catalog-form-grid">
                  <label className="supplier-catalog-form-field">
                    <span className="supplier-catalog-form-label">Sản lượng tối đa / ngày (kg)</span>
                    <input
                      type="number"
                      min="0.001"
                      step="0.001"
                      value={form.max_daily_supply_kg}
                      onChange={(event) => updateForm('max_daily_supply_kg', event.target.value)}
                      placeholder="Không bắt buộc"
                    />
                  </label>
                  <label className="supplier-catalog-form-field">
                    <span className="supplier-catalog-form-label">Lead time (giờ)</span>
                    <input
                      type="number"
                      min="0"
                      step="1"
                      value={form.lead_time_hours}
                      onChange={(event) => updateForm('lead_time_hours', event.target.value)}
                      placeholder="Không bắt buộc"
                    />
                  </label>
                </div>

                <label className="supplier-catalog-form-field">
                  <span className="supplier-catalog-form-label">Số lượng đặt tối thiểu (kg)</span>
                  <input
                    type="number"
                    min="0"
                    step="0.001"
                    value={form.minimum_order_kg}
                    onChange={(event) => updateForm('minimum_order_kg', event.target.value)}
                    placeholder="Không bắt buộc"
                  />
                </label>

                {formMode === 'edit' && (
                  <label className="supplier-catalog-form-field">
                    <span className="supplier-catalog-form-label">Trạng thái cung ứng</span>
                    <select
                      value={form.offer_status}
                      onChange={(event) => updateForm('offer_status', event.target.value)}
                    >
                      <option value="ACTIVE">Đang cung ứng</option>
                      <option value="INACTIVE">Ngừng cung ứng</option>
                    </select>
                  </label>
                )}

                <div className="supplier-catalog-form-actions">
                  <button type="button" className="supplier-catalog-cancel" onClick={closeForm} disabled={isSaving}>
                    Hủy
                  </button>
                  <button type="submit" className="supplier-catalog-primary" disabled={isSaving}>
                    {isSaving ? 'Đang lưu...' : formMode === 'create' ? 'Thêm mặt hàng' : 'Lưu thay đổi'}
                  </button>
                </div>
              </form>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
