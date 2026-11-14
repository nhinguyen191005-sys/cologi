import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../services/api/client'
import { listDemands } from '../services/api/demands'
import type { DeliveryDemand, DemandStatus } from '../types/demand'
import './DemandsPage.css'

const statusLabels: Record<DemandStatus, string> = {
  DRAFT: 'Bản nháp',
  SUBMITTED: 'Đã gửi',
  PLANNING: 'Đang lập kế hoạch',
  PLANNED: 'Đã lên kế hoạch',
  CANCELLED: 'Đã hủy',
}

const statusClasses: Record<DemandStatus, string> = {
  DRAFT: 'draft',
  SUBMITTED: 'submitted',
  PLANNING: 'planning',
  PLANNED: 'planned',
  CANCELLED: 'cancelled',
}

function formatDate(value: string): string {
  if (!value) return '—'
  const date = new Date(`${value}T00:00:00`)
  return new Intl.DateTimeFormat('vi-VN').format(date)
}

function formatWeight(value: string): string {
  return `${Number(value).toLocaleString('vi-VN', {
    maximumFractionDigits: 3,
  })} kg`
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'
    if (error.status === 403) return 'Bạn không có quyền xem danh sách nhu cầu.'
    return error.message
  }
  return error instanceof Error ? error.message : 'Không thể tải danh sách nhu cầu.'
}

export default function DemandsPage() {
  const [demands, setDemands] = useState<DeliveryDemand[]>([])
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<'ALL' | DemandStatus>('ALL')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  async function loadDemands() {
    setIsLoading(true)
    setError('')
    try {
      const data = await listDemands()
      setDemands(data)
    } catch (loadError) {
      setError(getErrorMessage(loadError))
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void loadDemands()
  }, [])

  const filteredDemands = useMemo(() => {
    const keyword = search.trim().toLocaleLowerCase('vi')
    return demands.filter((demand) => {
      const matchesStatus =
        statusFilter === 'ALL' || demand.status === statusFilter
      const searchable = [
        demand.demand_code,
        demand.supplier_name,
        demand.supplier_code,
        demand.outlet_name,
        demand.outlet_code,
      ].join(' ').toLocaleLowerCase('vi')
      return matchesStatus && (!keyword || searchable.includes(keyword))
    })
  }, [demands, search, statusFilter])

  const draftCount = demands.filter((demand) => demand.status === 'DRAFT').length

  return (
    <div className="demands-page">
      <section className="demands-heading">
        <div>
          <p className="demands-eyebrow">PURCHASING WORKSPACE</p>
          <h1>Quản lý nhu cầu</h1>
          <p className="demands-description">
            Theo dõi và quản lý các yêu cầu giao hàng từ cửa hàng.
          </p>
        </div>
        <Link className="demand-primary-button" to="/demands/new">
          <span aria-hidden="true">＋</span>
          Tạo nhu cầu
        </Link>
      </section>

      <section className="demand-summary-grid" aria-label="Tổng quan nhu cầu">
        <article className="demand-summary-card">
          <span>TỔNG SỐ NHU CẦU</span>
          <strong>{isLoading ? '—' : demands.length}</strong>
        </article>
        <article className="demand-summary-card">
          <span>BẢN NHÁP</span>
          <strong>{isLoading ? '—' : draftCount}</strong>
        </article>
        <article className="demand-summary-card">
          <span>KẾT QUẢ HIỂN THỊ</span>
          <strong>{isLoading ? '—' : filteredDemands.length}</strong>
        </article>
      </section>

      <section className="demand-list-section">
        <div className="demand-list-heading">
          <div>
            <h2>Danh sách nhu cầu</h2>
            <p>Các nhu cầu trong phạm vi dữ liệu bạn được phép truy cập.</p>
          </div>
          <button
            type="button"
            className="demand-refresh-button"
            onClick={() => void loadDemands()}
            disabled={isLoading}
          >
            ↻ Làm mới
          </button>
        </div>

        <div className="demand-filters">
          <label className="demand-search">
            <span aria-hidden="true">⌕</span>
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Tìm mã nhu cầu, nhà cung cấp, cửa hàng..."
              aria-label="Tìm kiếm nhu cầu"
            />
          </label>
          <select
            value={statusFilter}
            onChange={(event) =>
              setStatusFilter(event.target.value as 'ALL' | DemandStatus)
            }
            aria-label="Lọc theo trạng thái"
          >
            <option value="ALL">Tất cả trạng thái</option>
            {Object.entries(statusLabels).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>

        {error && (
          <div className="demand-error" role="alert">
            <span>{error}</span>
            <button type="button" onClick={() => void loadDemands()}>
              Thử lại
            </button>
          </div>
        )}

        {isLoading ? (
          <div className="demand-state">Đang tải danh sách nhu cầu...</div>
        ) : !error && filteredDemands.length === 0 ? (
          <div className="demand-state">
            <div className="demand-empty-icon">▤</div>
            <strong>
              {demands.length === 0
                ? 'Chưa có nhu cầu nào'
                : 'Không tìm thấy nhu cầu phù hợp'}
            </strong>
            <p>
              {demands.length === 0
                ? 'Tạo nhu cầu đầu tiên để bắt đầu quy trình mua hàng.'
                : 'Thử thay đổi từ khóa hoặc bộ lọc trạng thái.'}
            </p>
            {demands.length === 0 && (
              <Link className="demand-primary-button" to="/demands/new">
                Tạo nhu cầu đầu tiên
              </Link>
            )}
          </div>
        ) : !error ? (
          <div className="demand-table-wrapper">
            <table className="demand-table">
              <thead>
                <tr>
                  <th>MÃ NHU CẦU</th>
                  <th>NHÀ CUNG CẤP</th>
                  <th>CỬA HÀNG</th>
                  <th>KHỐI LƯỢNG</th>
                  <th>NGÀY YÊU CẦU</th>
                  <th>TRẠNG THÁI</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filteredDemands.map((demand) => (
                  <tr key={demand.id}>
                    <td>
                      <Link
                        className="demand-code-link"
                        to={`/demands/${demand.id}`}
                      >
                        {demand.demand_code}
                      </Link>
                    </td>
                    <td>
                      <strong>{demand.supplier_name}</strong>
                      <small>{demand.supplier_code}</small>
                    </td>
                    <td>
                      <strong>{demand.outlet_name}</strong>
                      <small>{demand.outlet_code}</small>
                    </td>
                    <td className="demand-weight">
                      {formatWeight(demand.quantity_kg)}
                    </td>
                    <td>{formatDate(demand.requested_date)}</td>
                    <td>
                      <span className={`demand-status ${statusClasses[demand.status]}`}>
                        {statusLabels[demand.status]}
                      </span>
                    </td>
                    <td>
                      <Link
                        className="demand-view-link"
                        to={`/demands/${demand.id}`}
                        aria-label={`Xem ${demand.demand_code}`}
                      >
                        Xem →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </div>
  )
}
