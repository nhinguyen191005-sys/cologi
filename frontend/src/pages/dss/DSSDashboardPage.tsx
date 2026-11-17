
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'
import { useNavigate } from 'react-router-dom'

import { dssService } from '../../services/dss/dssService'

import type {
  DSSRun,
  DSSRunStatus,
  DSSScenario,
  DSSScenarioType,
} from '../../types/dss'

import './DSSDashboardPage.css'

type ScenarioFilter =
  | 'ALL'
  | DSSScenarioType

const RUN_PAGE_SIZE = 5

const scenarioTypeLabels: Record<
  DSSScenarioType,
  string
> = {
  NORMAL: 'Đủ năng lực',
  INSUFFICIENT_VEHICLES: 'Thiếu phương tiện',
  TIME_CONFLICT: 'Xung đột thời gian',
}

const runStatusLabels: Record<
  DSSRunStatus,
  string
> = {
  PENDING: 'Chờ xử lý',
  RUNNING: 'Đang phân tích',
  COMPLETED: 'Đã hoàn thành',
  FAILED: 'Thất bại',
}

function formatDate(value: string): string {
  if (!value) return '—'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('vi-VN', {
    timeZone: 'Asia/Ho_Chi_Minh',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function formatServiceDate(value: string): string {
  if (!value) return '—'

  const [year, month, day] = value.split('-')

  if (!year || !month || !day) return value

  return `${day}/${month}/${year}`
}

function formatMoney(value: number): string {
  return `${value.toLocaleString('vi-VN')} ₫`
}

function getBestOption(run: DSSRun) {
  const feasibleOptions = run.options
    .filter(
      (option) =>
        option.status === 'FEASIBLE' &&
        option.estimated_cost_vnd !== null
    )
    .sort(
      (a, b) =>
        (a.estimated_cost_vnd ?? 0) -
        (b.estimated_cost_vnd ?? 0)
    )

  return feasibleOptions[0] ?? null
}

export default function DSSDashboardPage() {
  const navigate = useNavigate()

  const [scenarios, setScenarios] = useState<
    DSSScenario[]
  >([])

  const [runs, setRuns] = useState<DSSRun[]>([])

  const [selectedScenarioId, setSelectedScenarioId] =
    useState<string>('')

  const [search, setSearch] = useState('')
  const [scenarioFilter, setScenarioFilter] =
    useState<ScenarioFilter>('ALL')

  const [runPage, setRunPage] = useState(1)

  const [loading, setLoading] = useState(true)
  const [runningId, setRunningId] = useState<
    string | null
  >(null)

  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  /* =========================================
     LOAD DATA
  ========================================= */

  const loadData = useCallback(async () => {
    setLoading(true)
    setError('')

    try {
      const [scenarioData, runData] =
        await Promise.all([
          dssService.listScenarios(),
          dssService.listRuns(),
        ])

      setScenarios(scenarioData)
      setRuns(runData)

      setSelectedScenarioId((current) => {
        if (
          current &&
          scenarioData.some(
            (scenario) => scenario.id === current
          )
        ) {
          return current
        }

        return scenarioData[0]?.id ?? ''
      })
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Không thể tải dữ liệu mô phỏng.'
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadData()
  }, [loadData])

  /* =========================================
     DERIVED DATA
  ========================================= */

  const filteredScenarios = useMemo(() => {
    const keyword = search.trim().toLowerCase()

    return scenarios.filter((scenario) => {
      const matchesSearch =
        !keyword ||
        [
          scenario.id,
          scenario.name,
          scenario.description,
        ]
          .join(' ')
          .toLowerCase()
          .includes(keyword)

      const matchesType =
        scenarioFilter === 'ALL' ||
        scenario.scenario_type === scenarioFilter

      return matchesSearch && matchesType
    })
  }, [scenarios, search, scenarioFilter])

  const selectedScenario = useMemo(
    () =>
      scenarios.find(
        (scenario) =>
          scenario.id === selectedScenarioId
      ) ?? null,
    [scenarios, selectedScenarioId]
  )

  const selectedScenarioRuns = useMemo(
    () =>
      runs.filter(
        (run) =>
          run.scenario_id === selectedScenarioId
      ),
    [runs, selectedScenarioId]
  )

  const latestSelectedRun =
    selectedScenarioRuns[0] ?? null

  const stats = useMemo(() => {
    const completedRuns = runs.filter(
      (run) => run.status === 'COMPLETED'
    )

    const feasibleOptions = completedRuns.reduce(
      (total, run) =>
        total +
        run.options.filter(
          (option) =>
            option.status === 'FEASIBLE'
        ).length,
      0
    )

    const blockedOptions = completedRuns.reduce(
      (total, run) =>
        total +
        run.options.filter(
          (option) =>
            option.status !== 'FEASIBLE'
        ).length,
      0
    )

    return {
      scenarios: scenarios.length,
      runs: runs.length,
      feasibleOptions,
      blockedOptions,
    }
  }, [scenarios, runs])

  /* =========================================
     PAGINATION
  ========================================= */

  const totalRunPages = Math.max(
    1,
    Math.ceil(runs.length / RUN_PAGE_SIZE)
  )

  const safeRunPage = Math.min(
    runPage,
    totalRunPages
  )

  const paginatedRuns = runs.slice(
    (safeRunPage - 1) * RUN_PAGE_SIZE,
    safeRunPage * RUN_PAGE_SIZE
  )

  /* =========================================
     ACTIONS
  ========================================= */

  function selectScenario(scenarioId: string) {
    setSelectedScenarioId(scenarioId)
    setError('')
    setSuccess('')
  }

  async function handleRunScenario(
    scenarioId: string
  ) {
    if (runningId) return

    setRunningId(scenarioId)
    setError('')
    setSuccess('')

    try {
      const run =
        await dssService.runScenario(scenarioId)

      const updatedRuns =
        await dssService.listRuns()

      setRuns(updatedRuns)
      setSelectedScenarioId(scenarioId)
      setRunPage(1)

      setSuccess(
        `Đã tạo lần chạy mô phỏng ${run.id}. ` +
        'Bạn có thể xem kết quả trong lịch sử phía dưới.'
      )
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Không thể chạy mô phỏng.'
      )
    } finally {
      setRunningId(null)
    }
  }

  function handleViewRun(runId: string) {
    navigate(`/dss/runs/${runId}`)
  }

  function handleCreateScenario() {
    navigate('/dss/scenarios/new')
  }

  function handleViewScenario(scenarioId: string) {
    navigate(`/dss/scenarios/${scenarioId}`)
  }

  /* =========================================
     RENDER
  ========================================= */

  return (
    <main className="dssd-page">
      {/* HEADER */}
      <header className="dssd-header">
        <div className="dssd-header-copy">
          <p className="dssd-eyebrow">
            COLOGI · DECISION SUPPORT
          </p>

          <h1>Hỗ trợ lập kế hoạch vận chuyển</h1>

          <p className="dssd-description">
            Quản lý kịch bản, mô phỏng phương án
            vận chuyển và theo dõi kết quả phân tích.
          </p>

          <span className="dssd-demo-badge">
            <span className="dssd-demo-dot" />
            Chế độ mô phỏng · Dữ liệu minh họa
          </span>
        </div>

        <div className="dssd-header-actions">
          <button
            type="button"
            className="dssd-button dssd-button-secondary"
            onClick={() => void loadData()}
            disabled={loading}
          >
            ↻ Làm mới
          </button>

          <button
            type="button"
            className="dssd-button dssd-button-primary"
            onClick={handleCreateScenario}
          >
            + Tạo kịch bản
          </button>
        </div>
      </header>

      {/* ALERTS */}
      {error && (
        <div
          className="dssd-alert dssd-alert-error"
          role="alert"
        >
          <span>{error}</span>

          <button
            type="button"
            onClick={() => setError('')}
            aria-label="Đóng thông báo lỗi"
          >
            ×
          </button>
        </div>
      )}

      {success && (
        <div
          className="dssd-alert dssd-alert-success"
          role="status"
        >
          <span>{success}</span>

          <button
            type="button"
            onClick={() => setSuccess('')}
            aria-label="Đóng thông báo"
          >
            ×
          </button>
        </div>
      )}

      {loading ? (
        <div className="dssd-loading">
          Đang tải dữ liệu lập kế hoạch...
        </div>
      ) : (
        <>
          {/* KPI SUMMARY */}
          <section
            className="dssd-stats"
            aria-label="Tổng quan mô phỏng"
          >
            <article className="dssd-stat">
              <span>TỔNG KỊCH BẢN</span>
              <strong>{stats.scenarios}</strong>
              <small>Kịch bản đã tạo</small>
            </article>

            <article className="dssd-stat">
              <span>LẦN CHẠY MÔ PHỎNG</span>
              <strong>{stats.runs}</strong>
              <small>Lượt phân tích đã thực hiện</small>
            </article>

            <article className="dssd-stat dssd-stat-green">
              <span>PHƯƠNG ÁN KHẢ THI</span>
              <strong>{stats.feasibleOptions}</strong>
              <small>Tổng từ các lần chạy</small>
            </article>

            <article className="dssd-stat dssd-stat-amber">
              <span>PHƯƠNG ÁN BỊ CHẶN</span>
              <strong>{stats.blockedOptions}</strong>
              <small>Tổng từ các lần chạy</small>
            </article>
          </section>

          {/* MAIN WORKSPACE */}
          <div className="dssd-workspace">
            {/* SCENARIO LIST */}
            <section className="dssd-panel">
              <div className="dssd-panel-heading">
                <div>
                  <p className="dssd-section-index">
                    01 · KỊCH BẢN
                  </p>

                  <h2>Danh sách kịch bản</h2>

                  <p>
                    Chọn kịch bản để xem và chạy mô phỏng.
                  </p>
                </div>

                <span className="dssd-count">
                  {filteredScenarios.length} kịch bản
                </span>
              </div>

              <div className="dssd-filters">
                <input
                  type="search"
                  placeholder="Tìm kịch bản..."
                  aria-label="Tìm kịch bản"
                  value={search}
                  onChange={(event) =>
                    setSearch(event.target.value)
                  }
                />

                <select
                  aria-label="Lọc loại kịch bản"
                  value={scenarioFilter}
                  onChange={(event) =>
                    setScenarioFilter(
                      event.target.value as ScenarioFilter
                    )
                  }
                >
                  <option value="ALL">
                    Tất cả loại
                  </option>
                  <option value="NORMAL">
                    Đủ năng lực
                  </option>
                  <option value="INSUFFICIENT_VEHICLES">
                    Thiếu phương tiện
                  </option>
                  <option value="TIME_CONFLICT">
                    Xung đột thời gian
                  </option>
                </select>
              </div>

              <div className="dssd-scenario-list">
                {filteredScenarios.length === 0 ? (
                  <div className="dssd-empty">
                    Không tìm thấy kịch bản phù hợp.
                  </div>
                ) : (
                  filteredScenarios.map((scenario) => {
                    const isSelected =
                      scenario.id === selectedScenarioId

                    return (
                      <button
                        key={scenario.id}
                        type="button"
                        className={`dssd-scenario-card ${
                          isSelected ? 'is-selected' : ''
                        }`}
                        onClick={() =>
                          selectScenario(scenario.id)
                        }
                        aria-pressed={isSelected}
                      >
                        <div className="dssd-scenario-card-top">
                          <span className="dssd-scenario-code">
                            {scenario.id}
                          </span>

                          <span
                            className={`dssd-type-tag ${
                              scenario.scenario_type.toLowerCase()
                            }`}
                          >
                            {scenarioTypeLabels[
                              scenario.scenario_type
                            ]}
                          </span>
                        </div>

                        <strong>{scenario.name}</strong>

                        <p>{scenario.description}</p>

                        <div className="dssd-scenario-meta">
                          <span>
                            📅 {formatServiceDate(
                              scenario.service_date
                            )}
                          </span>
                          <span>
                            📦 {scenario.demand_count} nhu cầu
                          </span>
                        </div>
                      </button>
                    )
                  })
                )}
              </div>
            </section>

            {/* SELECTED SCENARIO */}
            <section className="dssd-panel dssd-detail-panel">
              <div className="dssd-panel-heading">
                <div>
                  <p className="dssd-section-index">
                    02 · PHÂN TÍCH
                  </p>
                  <h2>Thông tin kịch bản</h2>
                  <p>
                    Kiểm tra điều kiện trước khi mô phỏng.
                  </p>
                </div>
              </div>

              {!selectedScenario ? (
                <div className="dssd-empty">
                  Chọn một kịch bản để xem thông tin.
                </div>
              ) : (
                <>
                  <div className="dssd-selected-head">
                    <span className="dssd-scenario-code">
                      {selectedScenario.id}
                    </span>

                    <h3>{selectedScenario.name}</h3>

                    <p>
                      {selectedScenario.description}
                    </p>
                  </div>

                  <dl className="dssd-info-list">
                    <div>
                      <dt>Ngày vận chuyển</dt>
                      <dd>
                        {formatServiceDate(
                          selectedScenario.service_date
                        )}
                      </dd>
                    </div>

                    <div>
                      <dt>Số nhu cầu</dt>
                      <dd>
                        {selectedScenario.demand_count}
                      </dd>
                    </div>

                    <div>
                      <dt>Loại kịch bản</dt>
                      <dd>
                        {scenarioTypeLabels[
                          selectedScenario.scenario_type
                        ]}
                      </dd>
                    </div>

                    <div>
                      <dt>Số lần đã chạy</dt>
                      <dd>
                        {selectedScenarioRuns.length}
                      </dd>
                    </div>
                  </dl>

                  <div className="dssd-flow-preview">
                    <p>QUY TRÌNH PHÂN TÍCH</p>

                    <div className="dssd-flow-steps">
                      {[
                        ['F1', 'Phối hợp'],
                        ['F2', 'Phương án'],
                        ['F3', 'Phương tiện'],
                        ['F4', 'Thời gian'],
                        ['F5', 'Chi phí'],
                      ].map(([code, label]) => (
                        <div
                          key={code}
                          className="dssd-flow-step"
                        >
                          <strong>{code}</strong>
                          <span>{label}</span>
                        </div>
                      ))}
                    </div>

                    <small>
                      Năm bước trên đang sử dụng kết quả
                      minh họa, chưa thực thi thuật toán thật.
                    </small>
                  </div>

                  {latestSelectedRun && (
                    <div className="dssd-latest-run">
                      <div>
                        <span>LẦN CHẠY GẦN NHẤT</span>

                        <strong>
                          {latestSelectedRun.id}
                        </strong>

                        <small>
                          {formatDate(
                            latestSelectedRun.started_at
                          )}
                        </small>
                      </div>

                      <button
                        type="button"
                        onClick={() =>
                          handleViewRun(
                            latestSelectedRun.id
                          )
                        }
                      >
                        Xem kết quả →
                      </button>
                    </div>
                  )}

                  <div className="dssd-detail-actions">
                    <button
                      type="button"
                      className="dssd-button dssd-button-primary"
                      onClick={() =>
                        void handleRunScenario(
                          selectedScenario.id
                        )
                      }
                      disabled={runningId !== null}
                    >
                      {runningId === selectedScenario.id
                        ? 'Đang tạo kết quả...'
                        : '▶ Chạy mô phỏng'}
                    </button>

                    <button
                      type="button"
                      className="dssd-button dssd-button-secondary"
                      onClick={() =>
                        handleViewScenario(
                          selectedScenario.id
                        )
                      }
                    >
                      Chi tiết kịch bản
                    </button>
                  </div>

                  <p className="dssd-disclaimer">
                    Kết quả sử dụng bộ dữ liệu mô phỏng
                    cố định, không phải phương án được tính
                    từ nhu cầu và lịch xe thực tế.
                  </p>
                </>
              )}
            </section>
          </div>

          {/* RUN HISTORY */}
          <section className="dssd-panel dssd-history">
            <div className="dssd-panel-heading">
              <div>
                <p className="dssd-section-index">
                  03 · LỊCH SỬ
                </p>

                <h2>Các lần chạy gần đây</h2>

                <p>
                  Tra cứu kết quả phân tích đã tạo
                  trong phiên demo hiện tại.
                </p>
              </div>

              <span className="dssd-count">
                {runs.length} lần chạy
              </span>
            </div>

            {runs.length === 0 ? (
              <div className="dssd-empty dssd-empty-history">
                <strong>Chưa có lần chạy nào</strong>

                <p>
                  Chọn một kịch bản phía trên,
                  sau đó nhấn "Chạy mô phỏng".
                </p>
              </div>
            ) : (
              <>
                <div className="dssd-table-wrap">
                  <table className="dssd-table">
                    <thead>
                      <tr>
                        <th>MÃ LẦN CHẠY</th>
                        <th>KỊCH BẢN</th>
                        <th>THỜI ĐIỂM</th>
                        <th>TRẠNG THÁI</th>
                        <th>PHƯƠNG ÁN TỐT NHẤT</th>
                        <th>THAO TÁC</th>
                      </tr>
                    </thead>

                    <tbody>
                      {paginatedRuns.map((run) => {
                        const best = getBestOption(run)

                        return (
                          <tr key={run.id}>
                            <td>
                              <strong>{run.id}</strong>
                            </td>

                            <td>
                              <span className="dssd-table-main">
                                {run.scenario_name}
                              </span>

                              <small>
                                {run.scenario_id}
                              </small>
                            </td>

                            <td>
                              {formatDate(run.started_at)}
                            </td>

                            <td>
                              <span
                                className={`dssd-run-status ${
                                  run.status.toLowerCase()
                                }`}
                              >
                                {runStatusLabels[run.status]}
                              </span>
                            </td>

                            <td>
                              {best ? (
                                <>
                                  <span className="dssd-table-main">
                                    {best.mode === 'DIRECT'
                                      ? 'Direct'
                                      : 'Hub'}
                                  </span>

                                  <small>
                                    {formatMoney(
                                      best.estimated_cost_vnd ?? 0
                                    )}
                                  </small>
                                </>
                              ) : (
                                <span className="dssd-no-option">
                                  Không có phương án khả thi
                                </span>
                              )}
                            </td>

                            <td>
                              <button
                                type="button"
                                className="dssd-view-button"
                                onClick={() =>
                                  handleViewRun(run.id)
                                }
                              >
                                Xem chi tiết →
                              </button>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>

                <div className="dssd-pagination">
                  <span>
                    Hiển thị{' '}
                    {(safeRunPage - 1) *
                      RUN_PAGE_SIZE +
                      1}
                    {'–'}
                    {Math.min(
                      safeRunPage * RUN_PAGE_SIZE,
                      runs.length
                    )}
                    {' / '}
                    {runs.length} lần chạy
                  </span>

                  <div>
                    <button
                      type="button"
                      disabled={safeRunPage <= 1}
                      onClick={() =>
                        setRunPage((page) =>
                          Math.max(1, page - 1)
                        )
                      }
                    >
                      ‹ Trước
                    </button>

                    <span>
                      {safeRunPage}/{totalRunPages}
                    </span>

                    <button
                      type="button"
                      disabled={
                        safeRunPage >= totalRunPages
                      }
                      onClick={() =>
                        setRunPage((page) =>
                          Math.min(
                            totalRunPages,
                            page + 1
                          )
                        )
                      }
                    >
                      Sau ›
                    </button>
                  </div>
                </div>
              </>
            )}
          </section>
        </>
      )}
    </main>
  )
}