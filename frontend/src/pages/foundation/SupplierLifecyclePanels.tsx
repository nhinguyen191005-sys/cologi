
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listSupplierRequests } from '../../services/api/suppliers'
import type { SupplierRequest } from '../../types/supplier'
import './SupplierLifecyclePanels.css'

type Props = {
  request: SupplierRequest
}

const labels: Record<string, string> = {
  WAITING: 'Chờ phản hồi',
  RESPONDED: 'Đã phản hồi',
  EXPIRED: 'Hết hạn',
  PENDING: 'Chờ xác nhận',
  CONFIRMED: 'Xác nhận đủ',
  PARTIAL: 'Xác nhận một phần',
  DECLINED: 'Từ chối',
}

function weight(value: string | number) {
  return `${Number(value).toLocaleString('vi-VN', {
    maximumFractionDigits: 3,
  })} kg`
}

function date(value: string | null) {
  if (!value) return '—'

  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)

  return match
    ? `${match[3]}/${match[2]}/${match[1]}`
    : value
}

function dateTime(value: string | null) {
  if (!value) return '—'

  const parsed = new Date(value)

  if (Number.isNaN(parsed.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(parsed)
}

export function SupplierLifecyclePanels({ request }: Props) {
  const [attempts, setAttempts] = useState<SupplierRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    async function loadHistory() {
      setLoading(true)
      setError('')

      try {
        // Backend chỉ trả dữ liệu thuộc Supplier đang đăng nhập.
        const all = await listSupplierRequests()

        if (!active) return

        setAttempts(
          all
            .filter(
              (item) =>
                item.demand.demand_code ===
                request.demand.demand_code
            )
            .sort(
              (a, b) =>
                b.attempt_no - a.attempt_no ||
                b.id - a.id
            )
        )
      } catch {
        if (active) {
          setError('Chưa thể tải lịch sử yêu cầu.')
        }
      } finally {
        if (active) setLoading(false)
      }
    }

    void loadHistory()

    return () => {
      active = false
    }
  }, [request.demand.demand_code, request.responded_at])

  const confirmed = request.items.reduce(
    (sum, item) => sum + Number(item.confirmed_weight_kg),
    0
  )

  const promised = request.items.reduce(
    (sum, item) => sum + Number(item.promised_weight_kg),
    0
  )

  return (
    <div className="slp-stack">

      {request.request_status === 'RESPONDED' && (
        <section
          className="slp-panel"
          aria-label="Cam kết cung ứng đã ghi nhận"
        >
          <div className="slp-heading">
            <div>
              <span className="slp-eyebrow">
                SUPPLY COMMITMENT
              </span>

              <h2>Cam kết & kết quả phản hồi</h2>

              <p>
                Dữ liệu đã lưu cho lần gửi này;
                không thể chỉnh sửa trực tiếp.
              </p>
            </div>

            <span
              className={
                `slp-status slp-${request.confirmation_status.toLowerCase()}`
              }
            >
              {labels[request.confirmation_status] ??
                request.confirmation_status}
            </span>
          </div>

          <div className="slp-metrics">
            <div>
              <span>Đã hứa cung ứng</span>
              <strong>{weight(promised)}</strong>
            </div>

            <div>
              <span>Đã xác nhận</span>
              <strong>{weight(confirmed)}</strong>
            </div>

            <div>
              <span>Chưa đáp ứng</span>
              <strong>
                {weight(Math.max(0, promised - confirmed))}
              </strong>
            </div>
          </div>

          <dl className="slp-commitment">
            <div>
              <dt>Ngày hàng sẵn sàng</dt>
              <dd>{date(request.ready_date)}</dd>
            </div>

            <div>
              <dt>Giờ lấy hàng</dt>
              <dd>
                {request.ready_start_time?.slice(0, 5) ?? '—'}
                {' – '}
                {request.ready_end_time?.slice(0, 5) ?? '—'}
              </dd>
            </div>

            <div>
              <dt>Thời điểm phản hồi</dt>
              <dd>{dateTime(request.responded_at)}</dd>
            </div>
          </dl>

          {request.confirmation_note && (
            <p className="slp-note">
              <strong>Ghi chú:</strong>{' '}
              {request.confirmation_note}
            </p>
          )}

          {request.items.some(
            (item) => item.decline_reason
          ) && (
            <div className="slp-declines">
              <strong>Các mặt hàng bị từ chối</strong>

              {request.items
                .filter((item) => item.decline_reason)
                .map((item) => (
                  <p key={item.id}>
                    {item.item_name}: {item.decline_reason}
                  </p>
                ))}
            </div>
          )}
        </section>
      )}

      <section
        className="slp-panel"
        aria-label="Lịch sử các lần gửi tới nhà cung cấp"
      >
        <div className="slp-heading">
          <div>
            <span className="slp-eyebrow">
              ATTEMPT HISTORY
            </span>

            <h2>Lịch sử lần gửi</h2>

            <p>
              Chỉ hiển thị những lần gửi cùng mã nhu cầu
              đến Supplier này.
            </p>
          </div>

          {!loading && !error && (
            <span className="slp-history-count">
              {attempts.length} lần
            </span>
          )}
        </div>

        {loading ? (
          <p className="slp-muted" role="status">
            Đang tải lịch sử...
          </p>
        ) : error ? (
          <p className="slp-error" role="alert">
            {error}
          </p>
        ) : attempts.length === 0 ? (
          <p className="slp-muted">
            Chưa có bản ghi nào để hiển thị.
          </p>
        ) : (
          <ol className="slp-attempt-list">
            {attempts.map((item) => {
              const itemConfirmed = item.items.reduce(
                (sum, line) =>
                  sum + Number(line.confirmed_weight_kg),
                0
              )

              return (
                <li
                  key={item.id}
                  className={
                    item.id === request.id
                      ? 'current'
                      : ''
                  }
                >
                  <div className="slp-attempt-number">
                    #{item.attempt_no}
                  </div>

                  <div className="slp-attempt-copy">
                    <strong>{item.request_code}</strong>

                    <small>
                      {labels[String(item.request_status)] ??
                        item.request_status}
                      {' · '}
                      {labels[item.confirmation_status] ??
                        item.confirmation_status}
                      {' · '}Đã nhận {weight(itemConfirmed)}
                    </small>

                    <small>
                      Gửi {dateTime(item.sent_at)}
                      {' · '}
                      Phản hồi {dateTime(item.responded_at)}
                    </small>
                  </div>

                  {item.id === request.id ? (
                    <span className="slp-current-label">
                      Đang xem
                    </span>
                  ) : (
                    <Link
                      to={`/supplier/requests/${item.id}`}
                    >
                      Chi tiết →
                    </Link>
                  )}
                </li>
              )
            })}
          </ol>
        )}
      </section>
    </div>
  )
}
