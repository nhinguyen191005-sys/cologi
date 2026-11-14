import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError } from '../services/api/client'
import {
  createDemand,
  getDemand,
  listItems,
  listOutlets,
  listSuppliers,
  updateDemand,
} from '../services/api/demands'
import type {
  DemandCreateInput,
  DemandItemInput,
  DeliveryDemand,
  Item,
  Outlet,
  Supplier,
} from '../types/demand'
import './DemandFormPage.css'

interface ItemRow {
  key: number
  item_id: string
  required_weight_kg: string
  item_note: string
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'
    if (error.status === 403) return 'Bạn không có quyền thực hiện thao tác này.'
    if (error.status === 404) return 'Không tìm thấy nhu cầu hoặc dữ liệu liên quan.'
    if (error.status === 409) return 'Nhu cầu đã thay đổi trạng thái và không thể thực hiện thao tác này.'
    if (typeof error.data === 'object' && error.data !== null) {
      const messages: string[] = []
      const collect = (value: unknown) => {
        if (typeof value === 'string') messages.push(value)
        else if (Array.isArray(value)) value.forEach(collect)
        else if (typeof value === 'object' && value !== null) {
          Object.values(value).forEach(collect)
        }
      }
      collect(error.data)
      if (messages.length) return messages.join(' ')
    }
    return error.message
  }
  return error instanceof Error ? error.message : 'Không thể lưu nhu cầu. Vui lòng thử lại.'
}

function toDateInput(value: string): string {
  return value ? value.slice(0, 10) : ''
}

export default function DemandFormPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isEdit = Boolean(id)
  const demandId = Number(id)

  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [outlets, setOutlets] = useState<Outlet[]>([])
  const [items, setItems] = useState<Item[]>([])
  const [supplierId, setSupplierId] = useState('')
  const [outletId, setOutletId] = useState('')
  const [requestedDate, setRequestedDate] = useState('')
  const [startTime, setStartTime] = useState('')
  const [endTime, setEndTime] = useState('')
  const [notes, setNotes] = useState('')
  const [rows, setRows] = useState<ItemRow[]>([
    { key: 1, item_id: '', required_weight_kg: '', item_note: '' },
  ])
  const [nextKey, setNextKey] = useState(2)
  const [originalDemand, setOriginalDemand] = useState<DeliveryDemand | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    async function loadForm() {
      setIsLoading(true)
      setError('')
      try {
        const [supplierData, outletData, itemData, demand] = await Promise.all([
          listSuppliers(),
          listOutlets(),
          listItems(),
          isEdit ? getDemand(demandId) : Promise.resolve(null),
        ])

        if (!active) return

        setSuppliers(supplierData.filter((entry) => entry.is_active))
        setOutlets(outletData.filter((entry) => entry.is_active))
        setItems(itemData.filter((entry) => entry.is_active))

        if (demand) {
          setOriginalDemand(demand)
          setSupplierId(String(demand.supplier_id))
          setOutletId(String(demand.outlet_id))
          setRequestedDate(toDateInput(demand.requested_date))
          setStartTime(demand.requested_start_time?.slice(0, 5) ?? '')
          setEndTime(demand.requested_end_time?.slice(0, 5) ?? '')
          setNotes(demand.notes ?? '')
          const demandRows = demand.items.map((item, index) => ({
            key: index + 1,
            item_id: String(item.item_id),
            required_weight_kg: item.required_weight_kg,
            item_note: item.item_note ?? '',
          }))
          setRows(demandRows.length ? demandRows : [
            { key: 1, item_id: '', required_weight_kg: '', item_note: '' },
          ])
          setNextKey(demandRows.length + 1)
        }
      } catch (loadError) {
        if (active) setError(getErrorMessage(loadError))
      } finally {
        if (active) setIsLoading(false)
      }
    }

    void loadForm()
    return () => {
      active = false
    }
  }, [demandId, isEdit])

  const selectedItems = rows.map((row) =>
    items.find((item) => String(item.id) === row.item_id),
  )
  const selectedCategoryId = selectedItems.find(Boolean)?.cargo_category_id

  const availableItems = useMemo(
    () => items.filter((item) =>
      selectedCategoryId === undefined ||
      item.cargo_category_id === selectedCategoryId,
    ),
    [items, selectedCategoryId],
  )

  const totalWeight = rows.reduce(
    (total, row) => total + (Number(row.required_weight_kg) || 0),
    0,
  )

  function updateRow(key: number, changes: Partial<ItemRow>) {
    setRows((current) => current.map((row) =>
      row.key === key ? { ...row, ...changes } : row,
    ))
  }

  function addRow() {
    setRows((current) => [
      ...current,
      { key: nextKey, item_id: '', required_weight_kg: '', item_note: '' },
    ])
    setNextKey((current) => current + 1)
  }

  function removeRow(key: number) {
    setRows((current) => current.length > 1
      ? current.filter((row) => row.key !== key)
      : current)
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')

    if (!supplierId || !requestedDate) {
      setError('Vui lòng chọn nhà cung cấp và ngày yêu cầu.')
      return
    }

    if (!isEdit && !outletId) {
      setError('Vui lòng chọn cửa hàng nhận hàng.')
      return
    }

    if (startTime && endTime && endTime <= startTime) {
      setError('Giờ kết thúc phải sau giờ bắt đầu.')
      return
    }

    if (rows.some((row) => !row.item_id || !row.required_weight_kg)) {
      setError('Vui lòng chọn SKU và nhập khối lượng cho tất cả dòng hàng.')
      return
    }

    if (rows.some((row) => !Number.isFinite(Number(row.required_weight_kg)) || Number(row.required_weight_kg) < 0.001)) {
      setError('Khối lượng mỗi SKU phải lớn hơn hoặc bằng 0.001 kg.')
      return
    }

    const itemIds = rows.map((row) => row.item_id)
    if (new Set(itemIds).size !== itemIds.length) {
      setError('Mỗi SKU chỉ được xuất hiện một lần trong nhu cầu.')
      return
    }

    const categoryIds = new Set(
      selectedItems.filter((item): item is Item => Boolean(item))
        .map((item) => item.cargo_category_id),
    )
    if (categoryIds.size !== 1) {
      setError('Tất cả SKU trong một nhu cầu phải thuộc cùng Cargo Category.')
      return
    }

    const demandItems: DemandItemInput[] = rows.map((row) => ({
      item_id: Number(row.item_id),
      required_weight_kg: row.required_weight_kg,
      item_note: row.item_note.trim() || null,
    }))

    const payload: DemandCreateInput = {
      supplier_id: Number(supplierId),
      outlet_id: Number(outletId),
      requested_date: requestedDate,
      requested_start_time: startTime || null,
      requested_end_time: endTime || null,
      notes: notes.trim() || null,
      items: demandItems,
    }

    setIsSaving(true)
    try {
      if (isEdit) {
        const updatePayload = {
          supplier_id: payload.supplier_id,
          requested_date: payload.requested_date,
          requested_start_time: payload.requested_start_time,
          requested_end_time: payload.requested_end_time,
          notes: payload.notes,
          items: demandItems,
        }
        await updateDemand(demandId, updatePayload)
        navigate(`/demands/${demandId}`)
      } else {
        const created = await createDemand(payload)
        navigate(`/demands/${created.id}`)
      }
    } catch (saveError) {
      setError(getErrorMessage(saveError))
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading) {
    return <div className="demand-form-state">Đang tải dữ liệu biểu mẫu...</div>
  }

  if (error && isEdit && !originalDemand) {
    return (
      <section className="demand-form-page">
        <div className="demand-form-error" role="alert">{error}</div>
        <Link className="demand-secondary-button" to="/demands">Quay lại danh sách</Link>
      </section>
    )
  }

  if (isEdit && originalDemand?.status !== 'DRAFT') {
    return (
      <section className="demand-form-page">
        <div className="demand-form-error" role="alert">
          Chỉ nhu cầu ở trạng thái Bản nháp mới có thể chỉnh sửa.
        </div>
        <Link className="demand-secondary-button" to={`/demands/${demandId}`}>
          Quay lại chi tiết
        </Link>
      </section>
    )
  }

  return (
    <section className="demand-form-page">
      <div className="demand-form-heading">
        <div>
          <p className="demands-eyebrow">PURCHASING WORKSPACE</p>
          <h1>{isEdit ? 'Chỉnh sửa nhu cầu' : 'Tạo nhu cầu mới'}</h1>
          <p>
            {isEdit
              ? `Cập nhật thông tin ${originalDemand?.demand_code ?? ''}.`
              : 'Khai báo nhà cung cấp, cửa hàng nhận và danh sách hàng hóa cần giao.'}
          </p>
        </div>
        <Link className="demand-secondary-button" to={isEdit ? `/demands/${demandId}` : '/demands'}>
          Quay lại
        </Link>
      </div>

      {error && <div className="demand-form-error" role="alert">{error}</div>}

      <form className="demand-form-card" onSubmit={(event) => void handleSubmit(event)}>
        <section className="demand-form-section">
          <div className="demand-form-section-heading">
            <h2>Thông tin nhu cầu</h2>
            <span>Thông tin bắt buộc <b>*</b></span>
          </div>

          <div className="demand-form-grid">
            <label className="demand-field">
              <span>Nhà cung cấp <b>*</b></span>
              <select value={supplierId} onChange={(event) => setSupplierId(event.target.value)} required>
                <option value="">Chọn nhà cung cấp</option>
                {suppliers.map((supplier) => (
                  <option key={supplier.id} value={supplier.id}>
                    {supplier.supplier_code} — {supplier.supplier_name}
                  </option>
                ))}
              </select>
            </label>

            <label className="demand-field">
              <span>Cửa hàng nhận <b>*</b></span>
              {isEdit ? (
                <input value={originalDemand?.outlet_name ?? ''} disabled />
              ) : (
                <select value={outletId} onChange={(event) => setOutletId(event.target.value)} required>
                  <option value="">Chọn cửa hàng</option>
                  {outlets.map((outlet) => (
                    <option key={outlet.id} value={outlet.id}>
                      {outlet.outlet_code} — {outlet.outlet_name}
                    </option>
                  ))}
                </select>
              )}
              {isEdit && <small>Cửa hàng nhận không thể thay đổi sau khi tạo.</small>}
            </label>

            <label className="demand-field">
              <span>Ngày yêu cầu <b>*</b></span>
              <input type="date" value={requestedDate} onChange={(event) => setRequestedDate(event.target.value)} required />
            </label>

            <label className="demand-field">
              <span>Giờ bắt đầu nhận</span>
              <input type="time" value={startTime} onChange={(event) => setStartTime(event.target.value)} />
            </label>

            <label className="demand-field">
              <span>Giờ kết thúc nhận</span>
              <input type="time" value={endTime} onChange={(event) => setEndTime(event.target.value)} />
            </label>
          </div>
        </section>

        <section className="demand-form-section">
          <div className="demand-form-section-heading">
            <div>
              <h2>Danh sách hàng hóa</h2>
              <p>Chọn các SKU thuộc cùng một Cargo Category.</p>
            </div>
            <button type="button" className="demand-add-line-button" onClick={addRow}>
              + Thêm SKU
            </button>
          </div>

          {selectedCategoryId !== undefined && (
            <div className="demand-category-hint">
              Cargo Category: {items.find((item) => item.cargo_category_id === selectedCategoryId)?.category_name}
            </div>
          )}

          <div className="demand-item-list">
            {rows.map((row, index) => (
              <div className="demand-item-row" key={row.key}>
                <div className="demand-item-row-heading">
                  <strong>Dòng hàng {index + 1}</strong>
                  <button
                    type="button"
                    className="demand-remove-line-button"
                    onClick={() => removeRow(row.key)}
                    disabled={rows.length === 1}
                  >
                    Xóa dòng
                  </button>
                </div>

                <div className="demand-form-grid demand-item-grid">
                  <label className="demand-field">
                    <span>Sản phẩm / SKU <b>*</b></span>
                    <select
                      value={row.item_id}
                      onChange={(event) => updateRow(row.key, { item_id: event.target.value })}
                      required
                    >
                      <option value="">Chọn SKU</option>
                      {availableItems.map((item) => (
                        <option
                          key={item.id}
                          value={item.id}
                          disabled={rows.some((other) => other.key !== row.key && other.item_id === String(item.id))}
                        >
                          {item.item_code} — {item.item_name} ({item.weight_unit})
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="demand-field">
                    <span>Khối lượng (kg) <b>*</b></span>
                    <input
                      type="number"
                      min="0.001"
                      max="999999999"
                      step="0.001"
                      value={row.required_weight_kg}
                      onChange={(event) => updateRow(row.key, { required_weight_kg: event.target.value })}
                      placeholder="Ví dụ: 120.500"
                      required
                    />
                  </label>

                  <label className="demand-field demand-item-note">
                    <span>Ghi chú dòng hàng</span>
                    <input
                      value={row.item_note}
                      onChange={(event) => updateRow(row.key, { item_note: event.target.value })}
                      placeholder="Ghi chú tùy chọn"
                    />
                  </label>
                </div>
              </div>
            ))}
          </div>

          <div className="demand-total-row">
            <span>Tổng khối lượng dự kiến</span>
            <strong>{totalWeight.toLocaleString('vi-VN', { maximumFractionDigits: 3 })} kg</strong>
          </div>
        </section>

        <section className="demand-form-section">
          <label className="demand-field">
            <span>Ghi chú chung</span>
            <textarea
              rows={4}
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Thông tin bổ sung cho nhu cầu giao hàng..."
            />
          </label>
        </section>

        <div className="demand-form-actions">
          <Link className="demand-secondary-button" to={isEdit ? `/demands/${demandId}` : '/demands'}>
            Hủy
          </Link>
          <button type="submit" className="demand-primary-button" disabled={isSaving}>
            {isSaving ? 'Đang lưu...' : isEdit ? 'Lưu thay đổi' : 'Tạo bản nháp'}
          </button>
        </div>
      </form>
    </section>
  )
}
