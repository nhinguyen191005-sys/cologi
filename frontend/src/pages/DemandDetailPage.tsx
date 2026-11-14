import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../contexts/useAuth'
import { ApiError } from '../services/api/client'
import {
  cancelDemand,
  getDemand,
  getDemandStatus,
  submitDemand,
} from '../services/api/demands'
import type {
  DeliveryDemand,
  DemandStatus,
  DemandStatusResponse,
} from '../types/demand'
import './DemandDetailPage.css'

const statusLabels: Record<DemandStatus, string> = {
  DRAFT: 'Bản nháp',
  SUBMITTED: 'Đã gửi',
  PLANNING: 'Đang lập kế hoạch',
  PLANNED: 'Đã lên kế hoạch',
  CANCELLED: 'Đã hủy',
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'
    if (error.status === 403) return 'Bạn không có quyền thực hiện thao tác này.'
    if (error.status === 404) return 'Không tìm thấy nhu cầu hoặc bạn không có quyền truy cập.'
    if (error.status === 409) return 'Trạng thái nhu cầu không còn phù hợp với thao tác này.'
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
  return error instanceof Error ? error.message : 'Đã xảy ra lỗi. Vui lòng thử lại.'
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(date)
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export default function DemandDetailPage() {
  const { id } = useParams()
  const { user } = useAuth()
  const demandId = Number(id)

  const [demand, setDemand] = useState<DeliveryDemand | null>(null)
  const [statusInfo, setStatusInfo] = useState<DemandStatusResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [busyAction, setBusyAction] = useState<'submit' | 'cancel' | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let active = true

    async function loadDetail() {
      if (!Number.isInteger(demandId) || demandId <= 0) {
        setError('Mã nhu cầu không hợp lệ.')
        setIsLoading(false)
        return
      }

      setIsLoading(true)
      setError('')
      try {
        const detail = await getDemand(demandId)
        if (!active) return
        setDemand(detail)

        try {
          const currentStatus = await getDemandStatus(demandId)
          if (active) setStatusInfo(currentStatus)
        } catch {
          if (active) setStatusInfo(null)
        }
      } catch (loadError) {
        if (active) setError(getErrorMessage(loadError))
      } finally {
        if (active) setIsLoading(false)
      }
    }

    void loadDetail()
    return () => {
      active = false
    }
  }, [demandId, reloadKey])

  const isCreator = Boolean(user && demand && user.id === demand.created_by_id)
  const isDraft = demand?.status === 'DRAFT'
  const canEdit = isCreator && isDraft
  const canSubmit = isCreator && isDraft
  const canCancel = isCreator && (demand?.status === 'DRAFT' || demand?.status === 'SUBMITTED')
  const currentStatus = statusInfo?.status ?? demand?.status

  async function handleSubmitDemand() {
    if (!demand || busyAction) return
    const confirmed = window.confirm(
      `Gửi nhu cầu ${demand.demand_code} để bắt đầu quy trình lập kế hoạch?`,
    )
    if (!confirmed) return

    setBusyAction('submit')
    setError('')
    setNotice('')
    try {
      const result = await submitDemand(demand.id)
      setNotice(`Đã gửi nhu cầu thành công. Mã yêu cầu nhà cung cấp: ${result.supplier_request_id}.`)
      setReloadKey((value) => value + 1)
    } catch (actionError) {
      setError(getErrorMessage(actionError))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleCancelDemand() {
    if (!demand || busyAction) return
    const confirmed = window.confirm(
      `Bạn có chắc muốn hủy nhu cầu ${demand.demand_code}? Thao tác này không thể hoàn tác.`,
    )
    if (!confirmed) return

    setBusyAction('cancel')
    setError('')
    setNotice('')
    try {
      await cancelDemand(demand.id)
      setNotice('Nhu cầu đã được hủy thành công.')
      setReloadKey((value) => value + 1)
    } catch (actionError) {
      setError(getErrorMessage(actionError))
    } finally {
      setBusyAction(null)
    }
  }

  if (isLoading) {
    return <div className="demand-detail-state">Đang tải chi tiết nhu cầu...</div>
  }

  if (!demand) {
    return (
      <section className="demand-detail-page">
        <div className="demand-detail-error" role="alert">
          {error || 'Không thể tải thông tin nhu cầu.'}
        </div>
        <div className="demand-detail-toolbar">
          <Link className="demand-detail-secondary" to="/demands">Quay lại danh sách</Link>
          <button type="button" className="demand-detail-primary" onClick={() => setReloadKey((value) => value + 1)}>
            Thử tải lại
          </button>
        </div>
      </section>
    )
  }

  return (
    <section className="demand-detail-page">
      <div className="demand-detail-heading">
        <div>
          <p className="demands-eyebrow">PURCHASING WORKSPACE</p>
          <div className="demand-detail-title-row">
            <h1>{demand.demand_code}</h1>
            <span className={`demand-detail-status status-${demand.status.toLowerCase()}`}>
              {statusLabels[demand.status]}
            </span>
          </div>
          <p>Chi tiết nhu cầu mua hàng và giao hàng.</p>
        </div>
        <Link className="demand-detail-secondary" to="/demands">← Danh sách nhu cầu</Link>
      </div>

      {error && <div className="demand-detail-error" role="alert">{error}</div>}
      {notice && <div className="demand-detail-notice" role="status">{notice}</div>}

      <div className="demand-detail-toolbar">
        <div className="demand-detail-toolbar-meta">
          <span>Mã nhu cầu</span>
          <strong>{demand.demand_code}</strong>
          <span className="demand-detail-meta-divider">•</span>
          <span>Tạo lúc {formatDateTime(demand.created_at)}</span>
        </div>
        <div className="demand-detail-actions">
          {canEdit && (
            <Link className="demand-detail-secondary" to={`/demands/${demand.id}/edit`}>
              Chỉnh sửa
            </Link>
          )}
          {canSubmit && (
            <button
              type="button"
              className="demand-detail-primary"
              onClick={() => void handleSubmitDemand()}
              disabled={busyAction !== null}
            >
              {busyAction === 'submit' ? 'Đang gửi...' : 'Gửi nhu cầu'}
            </button>
          )}
          {canCancel && (
            <button
              type="button"
              className="demand-detail-danger"
              onClick={() => void handleCancelDemand()}
              disabled={busyAction !== null}
            >
              {busyAction === 'cancel' ? 'Đang hủy...' : 'Hủy nhu cầu'}
            </button>
          )}
        </div>
      </div>

      <div className="demand-detail-grid">
        <article className="demand-detail-card">
          <div className="demand-detail-card-heading">
            <h2>Thông tin giao hàng</h2>
          </div>
          <dl className="demand-detail-info-grid">
            <div>
              <dt>Nhà cung cấp</dt>
              <dd>{demand.supplier_code} — {demand.supplier_name}</dd>
            </div>
            <div>
              <dt>Cửa hàng nhận</dt>
              <dd>{demand.outlet_code} — {demand.outlet_name}</dd>
            </div>
            <div>
              <dt>Ngày yêu cầu</dt>
              <dd>{formatDate(demand.requested_date)}</dd>
            </div>
            <div>
              <dt>Khung giờ nhận hàng</dt>
              <dd>
                {demand.requested_start_time || demand.requested_end_time
                  ? `${demand.requested_start_time?.slice(0, 5) ?? '—'} – ${demand.requested_end_time?.slice(0, 5) ?? '—'}`
                  : 'Chưa xác định'}
              </dd>
            </div>
            <div>
              <dt>Cargo Category</dt>
              <dd>{demand.cargo_category_code} — {demand.cargo_category_name}</dd>
            </div>
            <div>
              <dt>Tổng khối lượng</dt>
              <dd className="demand-detail-weight">
                {Number(demand.quantity_kg).toLocaleString('vi-VN', { maximumFractionDigits: 3 })} kg
              </dd>
            </div>
          </dl>
          <div className="demand-detail-notes">
            <span>Ghi chú chung</span>
            <p>{demand.notes?.trim() || 'Không có ghi chú.'}</p>
          </div>
        </article>

        <article className="demand-detail-card demand-detail-status-card">
          <div className="demand-detail-card-heading">
            <h2>Trạng thái xử lý</h2>
          </div>
          <div className="demand-status-current">
            <span className={`demand-detail-status status-${(currentStatus ?? demand.status).toLowerCase()}`}>
              {statusLabels[currentStatus ?? demand.status]}
            </span>
            <p>Mốc trạng thái hiện tại của nhu cầu.</p>
          </div>
          <div className="demand-status-timeline">
            <div className="demand-timeline-item">
              <span className="demand-timeline-marker" />
              <div>
                <strong>Khởi tạo nhu cầu</strong>
                <time>{formatDateTime(demand.created_at)}</time>
              </div>
            </div>
            <div className="demand-timeline-item is-current">
              <span className="demand-timeline-marker" />
              <div>
                <strong>{statusLabels[currentStatus ?? demand.status]}</strong>
                <time>Cập nhật gần nhất: {formatDateTime(statusInfo?.updated_at ?? demand.updated_at)}</time>
              </div>
            </div>
          </div>
          <p className="demand-timeline-disclaimer">
            API hiện chỉ cung cấp trạng thái hiện tại và thời điểm cập nhật gần nhất,
            chưa có lịch sử chi tiết từng lần chuyển trạng thái.
          </p>
        </article>
      </div>

      <article className="demand-detail-card demand-detail-items-card">
        <div className="demand-detail-card-heading">
          <div>
            <h2>Danh sách hàng hóa</h2>
            <p>{demand.items.length} dòng hàng trong nhu cầu</p>
          </div>
          <strong>
            {Number(demand.quantity_kg).toLocaleString('vi-VN', { maximumFractionDigits: 3 })} kg
          </strong>
        </div>

        {demand.items.length ? (
          <div className="demand-detail-table-wrap">
            <table className="demand-detail-table">
              <thead>
                <tr>
                  <th>SKU</th>
                  <th>Tên sản phẩm</th>
                  <th>Khối lượng yêu cầu</th>
                  <th>Đơn vị</th>
                  <th>Ghi chú</th>
                </tr>
              </thead>
              <tbody>
                {demand.items.map((item) => (
                  <tr key={item.id}>
                    <td className="demand-detail-item-code">{item.item_code}</td>
                    <td>{item.item_name}</td>
                    <td className="demand-detail-number">
                      {Number(item.required_weight_kg).toLocaleString('vi-VN', { maximumFractionDigits: 3 })}
                    </td>
                    <td>{item.unit_of_measure}</td>
                    <td>{item.item_note?.trim() || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="demand-detail-empty">Nhu cầu chưa có dòng hàng.</div>
        )}
      </article>

      <div className="demand-detail-footer">
        <span>Cập nhật lần cuối: {formatDateTime(demand.updated_at)}</span>
        <button type="button" className="demand-detail-secondary" onClick={() => setReloadKey((value) => value + 1)}>
          Làm mới dữ liệu
        </button>
      </div>
    </section>
  )
}
