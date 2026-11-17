import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../services/api/client'
import { listSupplierRequests, respondToSupplierRequest } from '../services/api/suppliers'
import type {
  SupplierRequest,
  SupplierRequestResponse,
} from '../types/supplier'
import './SupplierRequestDetailPage.css'
import { SupplierLifecyclePanels } from './foundation/SupplierLifecyclePanels'
interface ItemResponse {
  confirmedWeight: string
  declineReason: string
}

const statusLabels: Record<string, string> = {
  WAITING: 'Chờ phản hồi',
  RESPONDED: 'Đã phản hồi',
  PENDING: 'Chờ xác nhận',
  CONFIRMED: 'Đã xác nhận',
  PARTIAL: 'Xác nhận một phần',
  DECLINED: 'Đã từ chối',
}

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat('vi-VN').format(new Date(value))
}

function formatWeight(value: string | number): string {
  return `${Number(value).toLocaleString('vi-VN', { maximumFractionDigits: 3 })} kg`
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'
    if (error.status === 403) return 'Bạn không có quyền truy cập yêu cầu này.'
    if (error.status === 404) return 'Không tìm thấy yêu cầu cung ứng.'
    if (typeof error.data === 'object' && error.data !== null) {
      const data = error.data as Record<string, unknown>
      const messages = Object.entries(data).flatMap(([field, value]) => {
        const values = Array.isArray(value) ? value : [value]
        return values.map((message) =>
          `${field === 'detail' ? '' : `${field}: `}${String(message)}`,
        )
      })
      if (messages.length) return messages.join(' ')
    }
    return error.message
  }
  return error instanceof Error ? error.message : 'Đã xảy ra lỗi. Vui lòng thử lại.'
}

function toInputDate(value: string | null): string {
  return value ?? ''
}

export default function SupplierRequestDetailPage() {
  const { id } = useParams<{ id: string }>()
  const requestId = Number(id)
  const [request, setRequest] = useState<SupplierRequest | null>(null)
  const [responses, setResponses] = useState<Record<number, ItemResponse>>({})
  const [readyDate, setReadyDate] = useState('')
  const [readyStartTime, setReadyStartTime] = useState('')
  const [readyEndTime, setReadyEndTime] = useState('')
  const [confirmationNote, setConfirmationNote] = useState('')
  const [result, setResult] = useState<SupplierRequestResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [responseBlocked, setResponseBlocked] = useState(false)
  const [error, setError] = useState('')
  const [validationError, setValidationError] = useState('')

  const loadRequest = useCallback(async () => {
    setIsLoading(true)
    setError('')
    setResponseBlocked(false)
    try {
      if (!Number.isInteger(requestId) || requestId < 1) {
        throw new Error('Mã yêu cầu không hợp lệ.')
      }
      const requests = await listSupplierRequests()
      const found = requests.find((item) => item.id === requestId)
      if (!found) {
        throw new Error('Không tìm thấy yêu cầu trong phạm vi tài khoản nhà cung cấp.')
      }
      setRequest(found)
      setResponses(Object.fromEntries(found.items.map((item) => [
        item.id,
        {
          confirmedWeight: item.confirmed_weight_kg,
          declineReason: item.decline_reason ?? '',
        },
      ])))
      setReadyDate(toInputDate(found.ready_date))
      setReadyStartTime(found.ready_start_time?.slice(0, 5) ?? '')
      setReadyEndTime(found.ready_end_time?.slice(0, 5) ?? '')
      setConfirmationNote(found.confirmation_note ?? '')
    } catch (loadError) {
      setError(getErrorMessage(loadError))
    } finally {
      setIsLoading(false)
    }
  }, [requestId])

  useEffect(() => {
    Promise.resolve().then(() => loadRequest())
  }, [loadRequest])

  const isEditable = Boolean(
    request?.request_status === 'WAITING' &&
    request?.confirmation_status === 'PENDING' &&
    !responseBlocked
  )
  const totalPromised = useMemo(
    () => request?.items.reduce((sum, item) => sum + Number(item.promised_weight_kg), 0) ?? 0,
    [request],
  )
  const totalConfirmed = useMemo(
    () => request?.items.reduce(
      (sum, item) => sum + Number(responses[item.id]?.confirmedWeight || 0), 0,
    ) ?? 0,
    [request, responses],
  )
  const hasPositiveQuantity = Object.values(responses).some(
    (item) => Number(item.confirmedWeight) > 0,
  )

  function updateResponse(
    promiseId: number,
    field: keyof ItemResponse,
    value: string,
  ) {
    setResponses((current) => ({
      ...current,
      [promiseId]: {
        ...current[promiseId],
        [field]: value,
        ...(field === 'confirmedWeight' && Number(value) > 0
          ? { declineReason: '' }
          : {}),
      },
    }))
    setValidationError('')
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!request || !isEditable || isSubmitting) return

    setValidationError('')
    setError('')

    for (const item of request.items) {
      const response = responses[item.id]
      const quantity = Number(response?.confirmedWeight)

if (
  !Number.isFinite(quantity) ||
  quantity < 0 ||
  !/^(?:\d+)(?:\.\d{1,3})?$/.test(
    response?.confirmedWeight ?? ''
  )
) {        setValidationError(`Số lượng xác nhận của "${item.item_name}" không hợp lệ.`)
        return
      }
      if (quantity > Number(item.promised_weight_kg)) {
        setValidationError(`Số lượng "${item.item_name}" không được vượt quá số lượng đã yêu cầu.`)
        return
      }
      if (quantity === 0 && !response?.declineReason.trim()) {
        setValidationError(`Vui lòng nhập lý do từ chối cho mặt hàng "${item.item_name}".`)
        return
      }
      if (quantity > 0 && response?.declineReason.trim()) {
        setValidationError(`Không nhập lý do từ chối khi xác nhận số lượng "${item.item_name}".`)
        return
      }
    }

    if (hasPositiveQuantity) {
if (!readyDate || !readyStartTime || !readyEndTime) {
  setValidationError(
    'Vui lòng nhập ngày sẵn sàng, giờ bắt đầu và giờ kết thúc.'
  )
  return
}
      if (readyStartTime >= readyEndTime) {
        setValidationError('Giờ kết thúc phải sau giờ bắt đầu.')
        return
      }
    }

    setIsSubmitting(true)
    try {
      const response = await respondToSupplierRequest(request.id, {
        items: request.items.map((item) => ({
          promise_id: item.id,
          confirmed_weight_kg: Number(responses[item.id].confirmedWeight).toFixed(3),
          decline_reason: responses[item.id].declineReason.trim(),
        })),
        ready_date: hasPositiveQuantity ? readyDate : null,
        ready_start_time: hasPositiveQuantity ? readyStartTime : null,
        ready_end_time: hasPositiveQuantity ? readyEndTime : null,
        confirmation_note: confirmationNote.trim(),
      })
      setResult(response)
      setRequest(response.request)
      setResponses(Object.fromEntries(response.request.items.map((item) => [
        item.id,
        {
          confirmedWeight: item.confirmed_weight_kg,
          declineReason: item.decline_reason ?? '',
        },
      ])))
    } catch (submitError) {
      if (submitError instanceof ApiError && submitError.status === 409) {
        await loadRequest()
        setResponseBlocked(true)
        setError(
          'Yêu cầu đã thay đổi trạng thái hoặc không còn đủ điều kiện phản hồi. '
          + 'Dữ liệu đã được tải lại; vui lòng quay lại danh sách yêu cầu.'
        )
      } else {
        setError(getErrorMessage(submitError))
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  if (isLoading) {
    return <div className="supplier-detail-loading">Đang tải chi tiết yêu cầu...</div>
  }

  if (error && !request) {
    return (
      <div className="supplier-detail-page">
        <div className="supplier-detail-alert" role="alert">{error}</div>
        <button type="button" className="supplier-detail-secondary" onClick={() => void loadRequest()}>
          Thử tải lại
        </button>
        <Link className="supplier-detail-back" to="/supplier/requests">← Quay lại danh sách</Link>
      </div>
    )
  }

  if (!request) return null

  return (
    <div className="supplier-detail-page">
      <Link className="supplier-detail-back" to="/supplier/requests">
        ← Danh sách yêu cầu
      </Link>

      <section className="supplier-detail-heading">
        <div>
          <p className="supplier-detail-eyebrow">SUPPLIER WORKSPACE / REQUEST DETAIL</p>
          <h1>{request.request_code}</h1>
          <p>Chi tiết yêu cầu cung ứng và xác nhận khả năng đáp ứng.</p>
        </div>
        <span className={`supplier-detail-status supplier-detail-status-${request.confirmation_status.toLowerCase()}`}>
          {statusLabels[request.confirmation_status] ?? request.confirmation_status}
        </span>
      </section>

      {result && (
        <section className="supplier-submit-success" role="status">
          <strong>Đã gửi phản hồi thành công</strong>
          <span>
            Trạng thái: {statusLabels[result.confirmation_status] ?? result.confirmation_status}
            {' · '}Số lượng còn thiếu: {formatWeight(result.missing_qty)}
          </span>
        </section>
      )}

      {error && <div className="supplier-detail-alert" role="alert">{error}</div>}

      <section className="supplier-detail-overview">
        <article>
          <span>MÃ NHU CẦU</span>
          <strong>{request.demand.demand_code}</strong>
        </article>
        <article>
          <span>CỬA HÀNG</span>
          <strong>{request.demand.outlet_name}</strong>
          <small>{request.demand.outlet_address}</small>
        </article>
        <article>
          <span>NGÀY GIAO DỰ KIẾN</span>
          <strong>{formatDate(request.demand.requested_date)}</strong>
          <small>
            {request.demand.requested_start_time?.slice(0, 5) ?? ''}
            {request.demand.requested_end_time
              ? ` – ${request.demand.requested_end_time.slice(0, 5)}`
              : ''}
          </small>
        </article>
        <article>
          <span>LẦN GỬI</span>
          <strong>#{request.attempt_no}</strong>
          <small>Ngày gửi {formatDate(request.sent_at)}</small>
        </article>
      </section>

      {request.demand.notes && (
        <section className="supplier-detail-note">
          <strong>Ghi chú từ bộ phận thu mua</strong>
          <p>{request.demand.notes}</p>
        </section>
      )}

      <form onSubmit={(event) => void handleSubmit(event)}>
        <section className="supplier-detail-section">
          <div className="supplier-detail-section-heading">
            <div>
              <h2>Danh sách mặt hàng</h2>
              <p>Nhập số lượng có thể cung ứng. Nhập 0 kg nếu cần từ chối mặt hàng.</p>
            </div>
            <span>{request.items.length} mặt hàng</span>
          </div>

          <div className="supplier-detail-table-wrap">
            <table className="supplier-detail-table">
              <thead>
                <tr>
                  <th>Mặt hàng</th>
                  <th>SL yêu cầu</th>
                  <th>SL đã hứa</th>
                  <th>SL xác nhận (kg)</th>
                  <th>Lý do từ chối</th>
                  <th>Trạng thái</th>
                </tr>
              </thead>
              <tbody>
                {request.items.map((item) => {
                  const response = responses[item.id] ?? {
                    confirmedWeight: '0',
                    declineReason: '',
                  }
                  const declined = Number(response.confirmedWeight) === 0

                  return (
                    <tr key={item.id}>
                      <td>
                        <strong>{item.item_name}</strong>
                        <small>{item.item_code}</small>
                        {item.item_note && <small>Ghi chú: {item.item_note}</small>}
                      </td>
                      <td>{formatWeight(item.required_weight_kg)}</td>
                      <td>{formatWeight(item.promised_weight_kg)}</td>
                      <td>
                        {isEditable ? (
                          <input
                            className="supplier-quantity-input"
                            type="number"
                            min="0"
                            max={item.promised_weight_kg}
                            step="0.001"
                            value={response.confirmedWeight}
                            onChange={(event) => updateResponse(item.id, 'confirmedWeight', event.target.value)}
                            aria-label={`Số lượng xác nhận ${item.item_name}`}
                            required
                          />
                        ) : (
                          <strong>{formatWeight(item.confirmed_weight_kg)}</strong>
                        )}
                      </td>
                      <td>
                        {isEditable ? (
                          <input
                            className="supplier-decline-input"
                            type="text"
                            value={response.declineReason}
                            onChange={(event) => updateResponse(item.id, 'declineReason', event.target.value)}
                            placeholder={declined ? 'Nhập lý do từ chối' : 'Không cần nhập'}
                            disabled={!declined}
                            aria-label={`Lý do từ chối ${item.item_name}`}
                            required={declined}
                          />
                        ) : (
                          item.decline_reason || '—'
                        )}
                      </td>
                      <td>
                        <span className={`supplier-line-status supplier-line-status-${item.line_status.toLowerCase()}`}>
                          {statusLabels[item.line_status] ?? item.line_status}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="supplier-detail-totals">
            <span>Tổng số lượng đã hứa: <strong>{formatWeight(totalPromised)}</strong></span>
            <span>Tổng số lượng xác nhận: <strong>{formatWeight(totalConfirmed)}</strong></span>
            <span>
                  Còn thiếu:{' '}
                  <strong>
                    {formatWeight(
                      Math.max(0, totalPromised - totalConfirmed)
                    )}
                  </strong>
                </span>
          </div>
        </section>

        <section className="supplier-detail-section">
          <div className="supplier-detail-section-heading">
            <div>
              <h2>Thông tin sẵn sàng giao hàng</h2>
              <p>Bắt buộc khi xác nhận toàn bộ hoặc một phần số lượng.</p>
            </div>
          </div>

          <div className="supplier-ready-grid">
            <label>
              <span>Ngày sẵn sàng</span>
              <input
                type="date"
                value={readyDate}
                onChange={(event) => setReadyDate(event.target.value)}
                disabled={!isEditable || !hasPositiveQuantity}
                required={isEditable && hasPositiveQuantity}
              />
            </label>
            <label>
              <span>Giờ bắt đầu</span>
              <input
                type="time"
                value={readyStartTime}
                onChange={(event) => setReadyStartTime(event.target.value)}
                disabled={!isEditable || !hasPositiveQuantity}
                required={isEditable && hasPositiveQuantity}
              />
            </label>
            <label>
              <span>Giờ kết thúc</span>
              <input
                type="time"
                value={readyEndTime}
                onChange={(event) => setReadyEndTime(event.target.value)}
                disabled={!isEditable || !hasPositiveQuantity}
                required={isEditable && hasPositiveQuantity}
              />
            </label>
          </div>

          <label className="supplier-confirmation-note">
            <span>Ghi chú phản hồi</span>
            <textarea
              value={confirmationNote}
              onChange={(event) => setConfirmationNote(event.target.value)}
              placeholder="Thông tin bổ sung gửi bộ phận thu mua..."
              rows={3}
              disabled={!isEditable}
            />
          </label>
        </section>

        {validationError && (
          <div className="supplier-detail-alert" role="alert">{validationError}</div>
        )}

        {isEditable ? (
          <div className="supplier-detail-actions">
            <Link to="/supplier/requests" className="supplier-detail-secondary">
              Quay lại
            </Link>
            <button type="submit" className="supplier-detail-submit" disabled={isSubmitting}>
              {isSubmitting ? 'Đang gửi phản hồi...' : 'Gửi xác nhận cung ứng'}
            </button>
          </div>
        ) : (
          <div className="supplier-readonly-notice">
            {responseBlocked
              ? 'Yêu cầu không còn đủ điều kiện phản hồi. Thông tin bên trên chỉ dùng để xem lại.'
              : 'Yêu cầu này đã được phản hồi. Thông tin bên trên chỉ dùng để xem lại.'}
          </div>
        )}
      </form>
            <SupplierLifecyclePanels request={request} />
    </div>
  )
}
