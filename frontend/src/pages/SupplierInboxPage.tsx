import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../services/api/client'
import { listSupplierRequests } from '../services/api/suppliers'
import type { SupplierRequest } from '../types/supplier'
import './SupplierInboxPage.css'

type FilterStatus = 'ALL' | 'WAITING' | 'RESPONDED'

const statusLabels: Record<string, string> = {
  WAITING: 'Chờ phản hồi',
  RESPONDED: 'Đã phản hồi',
  PENDING: 'Chờ xác nhận',
  CONFIRMED: 'Đã xác nhận',
  PARTIAL: 'Xác nhận một phần',
  DECLINED: 'Đã từ chối',
}

const statusClasses: Record<string, string> = {
  WAITING: 'waiting',
  RESPONDED: 'responded',
  PENDING: 'pending',
  CONFIRMED: 'confirmed',
  PARTIAL: 'partial',
  DECLINED: 'declined',
}

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat('vi-VN').format(new Date(value))
}

function formatTime(value: string | null): string {
  return value ? value.slice(0, 5) : ''
}

function formatWeight(value: string): string {
  return `${Number(value).toLocaleString('vi-VN', { maximumFractionDigits: 3 })} kg`
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'
    if (error.status === 403) return 'Tài khoản chưa có quyền truy cập khu vực nhà cung cấp.'
    return error.message
  }
  return error instanceof Error ? error.message : 'Không thể tải danh sách yêu cầu.'
}

export default function SupplierInboxPage() {
  const [requests, setRequests] = useState<SupplierRequest[]>([])
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<FilterStatus>('ALL')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  const loadRequests = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      setRequests(await listSupplierRequests())
    } catch (loadError) {
      setError(getErrorMessage(loadError))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void Promise.resolve().then(() => loadRequests())
  }, [loadRequests])

  const filteredRequests = useMemo(() => {
    const keyword = search.trim().toLocaleLowerCase('vi')
    return requests.filter((request) => {
      const matchesStatus = filter === 'ALL' || request.request_status === filter
      const searchable = [
        request.request_code,
        request.demand.demand_code,
        request.demand.outlet_name,
        request.demand.outlet_address,
      ].join(' ').toLocaleLowerCase('vi')
      return matchesStatus && (!keyword || searchable.includes(keyword))
    })
  }, [requests, search, filter])

  const waitingCount = requests.filter((item) => item.request_status === 'WAITING').length
  const respondedCount = requests.filter((item) => item.request_status === 'RESPONDED').length

  return (
    <div className="supplier-inbox-page">
      <section className="supplier-inbox-heading">
        <div>
          <p className="supplier-inbox-eyebrow">SUPPLIER WORKSPACE</p>
          <h1>Yêu cầu cung ứng</h1>
          <p className="supplier-inbox-description">
            Theo dõi yêu cầu đặt hàng và phản hồi số lượng có thể cung ứng.
          </p>
        </div>
        <button
          type="button"
          className="supplier-refresh-button"
          onClick={() => void loadRequests()}
          disabled={isLoading}
        >
          ↻ Làm mới
        </button>
      </section>

      <section className="supplier-summary-grid" aria-label="Tổng quan yêu cầu">
        <article className="supplier-summary-card">
          <span>TỔNG YÊU CẦU</span>
          <strong>{isLoading ? '—' : requests.length}</strong>
        </article>
        <article className="supplier-summary-card">
          <span>CHỜ PHẢN HỒI</span>
          <strong>{isLoading ? '—' : waitingCount}</strong>
        </article>
        <article className="supplier-summary-card">
          <span>ĐÃ PHẢN HỒI</span>
          <strong>{isLoading ? '—' : respondedCount}</strong>
        </article>
      </section>

      <section className="supplier-request-section">
        <div className="supplier-request-section-heading">
          <div>
            <h2>Danh sách yêu cầu</h2>
            <p>Các yêu cầu được gửi đến nhà cung cấp của bạn.</p>
          </div>
          <span className="supplier-result-count">
            {isLoading ? 'Đang tải...' : `${filteredRequests.length} kết quả`}
          </span>
        </div>

        <div className="supplier-inbox-filters">
          <label className="supplier-search">
            <span aria-hidden="true">⌕</span>
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Tìm mã yêu cầu, nhu cầu, cửa hàng..."
              aria-label="Tìm kiếm yêu cầu"
            />
          </label>
          <select
            value={filter}
            onChange={(event) => setFilter(event.target.value as FilterStatus)}
            aria-label="Lọc trạng thái yêu cầu"
          >
            <option value="ALL">Tất cả trạng thái</option>
            <option value="WAITING">Chờ phản hồi</option>
            <option value="RESPONDED">Đã phản hồi</option>
          </select>
        </div>

        {error && (
          <div className="supplier-inbox-error" role="alert">
            <span>{error}</span>
            <button type="button" onClick={() => void loadRequests()}>Thử lại</button>
          </div>
        )}

        {isLoading ? (
          <div className="supplier-inbox-empty">Đang tải danh sách yêu cầu...</div>
        ) : !error && filteredRequests.length === 0 ? (
          <div className="supplier-inbox-empty">
            <span className="supplier-empty-icon">◈</span>
            <strong>Chưa có yêu cầu phù hợp</strong>
            <p>Thử thay đổi từ khóa hoặc bộ lọc trạng thái.</p>
          </div>
        ) : (
          <div className="supplier-request-list">
            {filteredRequests.map((request) => {
              const totalPromised = request.items.reduce(
                (sum, item) => sum + Number(item.promised_weight_kg), 0,
              )
              const totalConfirmed = request.items.reduce(
                (sum, item) => sum + Number(item.confirmed_weight_kg), 0,
              )

              return (
                <article className="supplier-request-card" key={request.id}>
                  <div className="supplier-request-card-top">
                    <div>
                      <span className="supplier-request-code">{request.request_code}</span>
                      <span className={`supplier-status supplier-status-${statusClasses[request.request_status] ?? 'pending'}`}>
                        {statusLabels[request.request_status] ?? request.request_status}
                      </span>
                    </div>
                    <span className="supplier-request-date">
                      Gửi ngày {formatDate(request.sent_at)}
                    </span>
                  </div>

                  <div className="supplier-request-main">
                    <div>
                      <span className="supplier-field-label">MÃ NHU CẦU</span>
                      <strong>{request.demand.demand_code}</strong>
                    </div>
                    <div>
                      <span className="supplier-field-label">CỬA HÀNG</span>
                      <strong>{request.demand.outlet_name}</strong>
                      <small>{request.demand.outlet_address}</small>
                    </div>
                    <div>
                      <span className="supplier-field-label">NGÀY GIAO DỰ KIẾN</span>
                      <strong>{formatDate(request.demand.requested_date)}</strong>
                      <small>
                        {formatTime(request.demand.requested_start_time)}
                        {request.demand.requested_end_time
                          ? ` – ${formatTime(request.demand.requested_end_time)}`
                          : ''}
                      </small>
                    </div>
                    <div>
                      <span className="supplier-field-label">SỐ MẶT HÀNG</span>
                      <strong>{request.items.length} mặt hàng</strong>
                      <small>{formatWeight(String(totalPromised))} đã được yêu cầu</small>
                    </div>
                  </div>

                  {request.request_status === 'RESPONDED' && (
                    <div className="supplier-request-response">
                      <span className={`supplier-status supplier-status-${statusClasses[request.confirmation_status] ?? 'pending'}`}>
                        {statusLabels[request.confirmation_status] ?? request.confirmation_status}
                      </span>
                      <span>
                        Đã xác nhận {formatWeight(String(totalConfirmed))}
                        {' / '}
                        {formatWeight(String(totalPromised))}
                      </span>
                    </div>
                  )}

                  <div className="supplier-request-card-footer">
                    <span>Lần gửi thứ {request.attempt_no}</span>
                    <Link to={`/supplier/requests/${request.id}`}>
                      {request.request_status === 'WAITING' ? 'Xem và phản hồi' : 'Xem chi tiết'}
                      <span aria-hidden="true"> →</span>
                    </Link>
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}
