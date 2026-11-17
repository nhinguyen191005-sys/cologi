
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../services/api/client'
import { listSupplierRequests } from '../services/api/suppliers'
import type { SupplierRequest } from '../types/supplier'
import './SupplierInboxPage.css'

type FilterStatus =
  | 'ALL'
  | 'WAITING'
  | 'RESPONDED'
  | 'CONFIRMED'
  | 'PARTIAL'
  | 'DECLINED'

const resultLabels: Record<string, string> = {
  PENDING: 'Chờ xác nhận',
  CONFIRMED: 'Xác nhận đủ',
  PARTIAL: 'Xác nhận một phần',
  DECLINED: 'Từ chối cung ứng',
}

function formatDate(value: string | null) {
  if (!value) return '—'

  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)

  return match
    ? `${match[3]}/${match[2]}/${match[1]}`
    : value
}

function formatTime(value: string | null) {
  return value?.slice(0, 5) || '—'
}

function formatWeight(value: number) {
  return `${value.toLocaleString('vi-VN', {
    maximumFractionDigits: 3,
  })} kg`
}

function dateValue(value: string | null) {
  if (!value) return 0
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function getErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'
    }

    if (error.status === 403) {
      return 'Tài khoản không có quyền truy cập yêu cầu này.'
    }

    return error.message
  }

  return error instanceof Error
    ? error.message
    : 'Không thể tải danh sách yêu cầu.'
}

function matchesFilter(
  request: SupplierRequest,
  filter: FilterStatus
) {
  if (filter === 'ALL') return true

  if (filter === 'WAITING' || filter === 'RESPONDED') {
    return request.request_status === filter
  }

  return (
    request.request_status === 'RESPONDED' &&
    request.confirmation_status === filter
  )
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
      const data = await listSupplierRequests()
      setRequests(data)
    } catch (loadError) {
      setError(getErrorMessage(loadError))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadRequests()
  }, [loadRequests])

  const waitingCount = requests.filter(
    (request) => request.request_status === 'WAITING'
  ).length

  const respondedCount = requests.filter(
    (request) => request.request_status === 'RESPONDED'
  ).length

  const filteredRequests = useMemo(() => {
    const keyword = search.trim().toLocaleLowerCase('vi')

    return requests
      .filter((request) => {
        if (!matchesFilter(request, filter)) return false

        if (!keyword) return true

        return [
          request.request_code,
          request.demand.demand_code,
          request.demand.outlet_name,
          request.demand.outlet_address,
          ...request.items.map((item) => item.item_name),
        ]
          .join(' ')
          .toLocaleLowerCase('vi')
          .includes(keyword)
      })
      .sort((a, b) => {
        // Yêu cầu chưa phản hồi luôn nằm trên cùng.
        const priorityA =
          a.request_status === 'WAITING' ? 0 : 1
        const priorityB =
          b.request_status === 'WAITING' ? 0 : 1

        if (priorityA !== priorityB) {
          return priorityA - priorityB
        }

        if (priorityA === 0) {
          // Yêu cầu chờ lâu nhất được đưa lên trước.
          return (
            dateValue(a.sent_at) - dateValue(b.sent_at) ||
            a.id - b.id
          )
        }

        // Phản hồi mới nhất ở phía trên.
        return (
          dateValue(b.responded_at ?? b.sent_at) -
            dateValue(a.responded_at ?? a.sent_at) ||
          b.id - a.id
        )
      })
  }, [requests, search, filter])

  return (
    <div className="supplier-inbox-page">
      <section className="supplier-inbox-heading">
        <div>
          <p className="supplier-inbox-eyebrow">
            SUPPLIER WORKSPACE
          </p>
          <h1>Yêu cầu cung ứng</h1>
          <p className="supplier-inbox-description">
            Tiếp nhận, xác nhận và theo dõi cam kết cung ứng.
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

      <section
        className="supplier-summary-grid"
        aria-label="Tổng quan yêu cầu"
      >
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

      <section className="si2-panel">
        <header className="si2-heading">
          <div>
            <span className="si2-eyebrow">
              SUPPLY REQUEST INBOX
            </span>

            <h2>Danh sách yêu cầu</h2>

            <p>
              Yêu cầu cần phản hồi được ưu tiên hiển thị trước.
            </p>
          </div>

          {!isLoading && !error && (
            <div
              className={
                waitingCount > 0
                  ? 'si2-priority-summary is-urgent'
                  : 'si2-priority-summary'
              }
            >
              <span className="si2-priority-dot" />
              <div>
                <strong>
                  {waitingCount > 0
                    ? `${waitingCount} yêu cầu cần xử lý`
                    : 'Không có yêu cầu đang chờ'}
                </strong>
                <small>
                  {waitingCount > 0
                    ? 'Ưu tiên phản hồi'
                    : 'Đã xử lý các yêu cầu hiện có'}
                </small>
              </div>
            </div>
          )}
        </header>

        <div className="si2-toolbar">
          <label className="si2-search">
            <span aria-hidden="true">⌕</span>
            <input
              type="search"
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
              placeholder="Tìm mã yêu cầu, cửa hàng, mặt hàng..."
              aria-label="Tìm kiếm yêu cầu"
            />
          </label>

          <select
            className="si2-filter"
            value={filter}
            onChange={(event) =>
              setFilter(event.target.value as FilterStatus)
            }
            aria-label="Lọc trạng thái yêu cầu"
          >
            <option value="ALL">Tất cả trạng thái</option>
            <option value="WAITING">Chờ phản hồi</option>
            <option value="RESPONDED">Đã phản hồi</option>
            <option value="CONFIRMED">Xác nhận đủ</option>
            <option value="PARTIAL">Xác nhận một phần</option>
            <option value="DECLINED">Từ chối</option>
          </select>
        </div>

        <div className="si2-filter-row">
          <div className="si2-quick-filters">
            <button
              type="button"
              className={filter === 'ALL' ? 'active' : ''}
              onClick={() => setFilter('ALL')}
              aria-pressed={filter === 'ALL'}
            >
              Tất cả
              <span>{requests.length}</span>
            </button>

            <button
              type="button"
              className={
                filter === 'WAITING'
                  ? 'active is-waiting'
                  : ''
              }
              onClick={() => setFilter('WAITING')}
              aria-pressed={filter === 'WAITING'}
            >
              Cần phản hồi
              <span>{waitingCount}</span>
            </button>

            <button
              type="button"
              className={
                filter === 'RESPONDED' ? 'active' : ''
              }
              onClick={() => setFilter('RESPONDED')}
              aria-pressed={filter === 'RESPONDED'}
            >
              Đã xử lý
              <span>{respondedCount}</span>
            </button>
          </div>

          <span className="si2-result-count">
            {isLoading
              ? 'Đang tải...'
              : `${filteredRequests.length} kết quả`}
          </span>
        </div>

        {error && (
          <div className="supplier-inbox-error" role="alert">
            <span>{error}</span>
            <button
              type="button"
              onClick={() => void loadRequests()}
            >
              Thử lại
            </button>
          </div>
        )}

        {isLoading ? (
          <div className="supplier-inbox-empty" role="status">
            Đang tải danh sách yêu cầu...
          </div>
        ) : !error && filteredRequests.length === 0 ? (
          <div className="supplier-inbox-empty">
            <span className="supplier-empty-icon">◇</span>
            <strong>Không tìm thấy yêu cầu</strong>
            <p>
              Hãy thử thay đổi trạng thái hoặc từ khóa.
            </p>
          </div>
        ) : !error ? (
          <div className="si2-list">
            {filteredRequests.map((request) => {
              const isWaiting =
                request.request_status === 'WAITING'

              const tone = isWaiting
                ? 'waiting'
                : request.confirmation_status.toLowerCase()

              const totalPromised = request.items.reduce(
                (sum, item) =>
                  sum + Number(item.promised_weight_kg),
                0
              )

              const totalConfirmed = request.items.reduce(
                (sum, item) =>
                  sum + Number(item.confirmed_weight_kg),
                0
              )

              const missing = Math.max(
                0,
                totalPromised - totalConfirmed
              )

              const declineLines = request.items.filter(
                (item) => item.decline_reason?.trim()
              )

const hasPickup =
  Boolean(request.ready_date) ||
  Boolean(request.ready_start_time) ||
  Boolean(request.ready_end_time)
              return (
                <article
                  key={request.id}
                  className={`si2-card si2-card--${tone}`}
                >
                  <div className="si2-card-top">
                    <div className="si2-card-identity">
                      <span className="si2-card-code">
                        {request.request_code}
                      </span>

                      {isWaiting ? (
                        <span className="si2-waiting-badge">
                          <span className="si2-pulse" />
                          Cần phản hồi
                        </span>
                      ) : (
                        <span className="si2-resolved">
                          Đã phản hồi
                        </span>
                      )}
                    </div>

                    <span className="si2-card-date">
                      Gửi {formatDate(request.sent_at)}
                    </span>
                  </div>

                  <div className="si2-card-main">
                    <div>
                      <span className="si2-data-label">
                        MÃ NHU CẦU
                      </span>
                      <strong>
                        {request.demand.demand_code}
                      </strong>
                    </div>

                    <div>
                      <span className="si2-data-label">
                        CỬA HÀNG NHẬN
                      </span>
                      <strong>
                        {request.demand.outlet_name}
                      </strong>
                      <small>
                        {request.demand.outlet_address}
                      </small>
                    </div>

                    <div>
                      <span className="si2-data-label">
                        NGÀY GIAO DỰ KIẾN
                      </span>
                      <strong>
                        {formatDate(
                          request.demand.requested_date
                        )}
                      </strong>
                      <small>
                        {formatTime(
                          request.demand.requested_start_time
                        )}
                        {' – '}
                        {formatTime(
                          request.demand.requested_end_time
                        )}
                      </small>
                    </div>

                    <div>
                      <span className="si2-data-label">
                        MẶT HÀNG / KHỐI LƯỢNG
                      </span>
                      <strong>
                        {request.items.length} mặt hàng
                      </strong>
                      <small>
                        {formatWeight(totalPromised)} yêu cầu
                      </small>
                    </div>
                  </div>

                  {isWaiting ? (
                    <div className="si2-action-needed">
                      <div>
                        <strong>
                          Đang chờ xác nhận cung ứng
                        </strong>
                        <p>
                          Kiểm tra số lượng từng mặt hàng
                          và phản hồi khả năng cung ứng.
                        </p>
                      </div>

                      <span className="si2-action-arrow">
                        →
                      </span>
                    </div>
                  ) : (
                    <div className="si2-result">
                      <div className="si2-result-heading">
                        <span className="si2-result-kicker">
                          KẾT QUẢ CUNG ỨNG
                        </span>

                        <span
                          className={
                            `si2-outcome si2-outcome--${tone}`
                          }
                        >
                          {resultLabels[
                            request.confirmation_status
                          ] ?? request.confirmation_status}
                        </span>
                      </div>

                      <div className="si2-quantity-grid">
                        <div>
                          <span>Đã xác nhận</span>
                          <strong>
                            {formatWeight(totalConfirmed)}
                          </strong>
                        </div>

                        <div>
                          <span>Khối lượng yêu cầu</span>
                          <strong>
                            {formatWeight(totalPromised)}
                          </strong>
                        </div>

                        <div
                          className={
                            missing > 0 ? 'has-missing' : ''
                          }
                        >
                          <span>Chưa đáp ứng</span>
                          <strong>
                            {formatWeight(missing)}
                          </strong>
                        </div>
                      </div>

                      {hasPickup && (
                        <div className="si2-pickup">
                          <div className="si2-pickup-heading">
                            <span aria-hidden="true">▣</span>
                            <strong>Cam kết lấy hàng</strong>
                          </div>

                          <div className="si2-pickup-details">
                            <span>
                              <b>Ngày:</b>{' '}
                              {formatDate(request.ready_date)}
                            </span>

                            <span>
                              <b>Giờ:</b>{' '}
                              {formatTime(
                                request.ready_start_time
                              )}
                              {' – '}
                              {formatTime(
                                request.ready_end_time
                              )}
                            </span>
                          </div>

                        </div>
                      )}

                      {declineLines.length > 0 && (
                        <div className="si2-decline-reasons">
                          <strong>Lý do không đáp ứng</strong>

                          {declineLines.map((item) => (
                            <p key={item.id}>
                              <b>{item.item_name}:</b>{' '}
                              {item.decline_reason}
                            </p>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  <footer className="si2-card-footer">
                    <span>
                      Lần gửi thứ {request.attempt_no}
                    </span>

                    <Link
                      className={
                        isWaiting
                          ? 'si2-card-cta is-urgent'
                          : 'si2-card-cta'
                      }
                      to={`/supplier/requests/${request.id}`}
                    >
                      {isWaiting
                        ? 'Xem và phản hồi'
                        : 'Xem chi tiết'}
                      <span aria-hidden="true">→</span>
                    </Link>
                  </footer>
                </article>
              )
            })}
          </div>
        ) : null}
      </section>
    </div>
  )
}