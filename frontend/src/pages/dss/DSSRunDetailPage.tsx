
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'

import {
  useNavigate,
  useParams,
} from 'react-router-dom'

import { dssService } from '../../services/dss/dssService'

import type {
  DSSModuleCode,
  DSSRun,
} from '../../types/dss'

import DSSProgressSteps from '../../components/dss/DSSProgressSteps'
import DirectHubComparison from '../../components/dss/DirectHubComparison'
import CandidateTable from '../../components/dss/CandidateTable'
import ExclusionReasonList from '../../components/dss/ExclusionReasonList'
import SnapshotViewer from '../../components/dss/SnapshotViewer'

import './DSSRunDetailPage.css'

/* =========================================
   HELPERS
========================================= */

function formatDateTime(value: string): string {
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

function formatMoney(value: number): string {
  return `${value.toLocaleString('vi-VN')} ₫`
}

const runStatusLabels = {
  PENDING: 'Chờ xử lý',
  RUNNING: 'Đang chạy',
  COMPLETED: 'Hoàn thành',
  FAILED: 'Thất bại',
} as const

const moduleNames: Record<
  DSSModuleCode,
  string
> = {
  F1: 'Phối hợp nhu cầu',
  F2: 'Xây dựng phương án',
  F3: 'Phân bổ phương tiện',
  F4: 'Kiểm tra thời gian',
  F5: 'Đánh giá kinh tế',
}

const moduleStatusLabels = {
  COMPLETED: 'Hoàn thành',
  BLOCKED: 'Bị chặn',
  SKIPPED: 'Bỏ qua',
} as const

type ResultTab =
  | 'OPTIONS'
  | 'CANDIDATES'
  | 'REASONS'
  | 'SNAPSHOT'

/* =========================================
   MAIN PAGE
========================================= */

export default function DSSRunDetailPage() {
  const navigate = useNavigate()

  const { runId } = useParams<{
    runId: string
  }>()

  const [run, setRun] = useState<DSSRun | null>(
    null
  )

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [activeModule, setActiveModule] =
    useState<DSSModuleCode>('F1')

  const [activeTab, setActiveTab] =
    useState<ResultTab>('OPTIONS')

  /* =========================================
     LOAD RUN
  ========================================= */

  const loadRun = useCallback(async () => {
    if (!runId) {
      setRun(null)
      setLoading(false)
      setError('Thiếu mã lần chạy.')
      return
    }

    setLoading(true)
    setError('')

    try {
      const data = await dssService.getRun(runId)

      setRun(data)

      if (!data) {
        setError(
          'Không tìm thấy lần chạy. ' +
          'Lịch sử mock có thể đã được xóa ' +
          'khi tải lại ứng dụng.'
        )
      }
    } catch (err) {
      setRun(null)

      setError(
        err instanceof Error
          ? err.message
          : 'Không thể tải kết quả mô phỏng.'
      )
    } finally {
      setLoading(false)
    }
  }, [runId])

  useEffect(() => {
    void loadRun()
  }, [loadRun])

  /* =========================================
     DERIVED DATA
  ========================================= */

  const stats = useMemo(() => {
    if (!run) {
      return {
        candidates: 0,
        options: 0,
        feasible: 0,
        blocked: 0,
      }
    }

    return {
      candidates: run.candidates.length,
      options: run.options.length,
      feasible: run.options.filter(
        (option) =>
          option.status === 'FEASIBLE'
      ).length,
      blocked: run.options.filter(
        (option) =>
          option.status !== 'FEASIBLE'
      ).length,
    }
  }, [run])

  const activeModuleResult =
    run?.modules.find(
      (item) => item.module === activeModule
    ) ?? null

  const bestOption = useMemo(() => {
    if (!run) return null

    return [...run.options]
      .filter(
        (option) =>
          option.status === 'FEASIBLE' &&
          option.estimated_cost_vnd !== null
      )
      .sort(
        (a, b) =>
          (a.estimated_cost_vnd ?? 0) -
          (b.estimated_cost_vnd ?? 0)
      )[0] ?? null
  }, [run])

  /* =========================================
     ACTIONS
  ========================================= */

  function handleViewOption(optionId: string) {
    if (!run) return

    navigate(
      `/dss/runs/${run.id}/options/${optionId}`
    )
  }

  function handleBackToScenario() {
    if (!run) {
      navigate('/dss')
      return
    }

    navigate(
      `/dss/scenarios/${run.scenario_id}`
    )
  }

  function handleSelectModule(
    module: DSSModuleCode
  ) {
    setActiveModule(module)

    if (module === 'F1') {
      setActiveTab('CANDIDATES')
    } else if (
      module === 'F3' ||
      module === 'F4'
    ) {
      setActiveTab('REASONS')
    } else {
      setActiveTab('OPTIONS')
    }
  }

  /* =========================================
     LOADING / ERROR
  ========================================= */

  if (loading) {
    return (
      <main className="dssr-page">
        <div className="dssr-loading">
          Đang tải kết quả mô phỏng...
        </div>
      </main>
    )
  }

  if (!run) {
    return (
      <main className="dssr-page">
        <button
          type="button"
          className="dssr-back-link"
          onClick={() => navigate('/dss')}
        >
          ← Về trang tổng quan
        </button>

        <div className="dssr-empty-page">
          <h2>Không tìm thấy kết quả</h2>

          <p>
            {error ||
              'Không có dữ liệu cho lần chạy này.'}
          </p>

          <button
            type="button"
            className="dssr-primary-button"
            onClick={() => navigate('/dss')}
          >
            Quay về Dashboard
          </button>
        </div>
      </main>
    )
  }

  /* =========================================
     MAIN RENDER
  ========================================= */

  return (
    <main className="dssr-page">
      {/* HEADER */}
      <header className="dssr-header">
        <div className="dssr-header-main">
          <button
            type="button"
            className="dssr-back-link"
            onClick={handleBackToScenario}
          >
            ← Quay lại kịch bản
          </button>

          <p className="dssr-eyebrow">
            COLOGI · DSS F1–F5
          </p>

          <h1>Kết quả phân tích vận chuyển</h1>

          <p className="dssr-description">
            Tổng hợp kết quả phối hợp nhu cầu,
            phương án vận chuyển, năng lực xe,
            thời gian và chi phí.
          </p>

          <div className="dssr-header-tags">
            <span className="dssr-demo-badge">
              Dữ liệu mô phỏng · DEMO
            </span>

            <span
              className={`dssr-run-badge is-${run.status.toLowerCase()}`}
            >
              {runStatusLabels[run.status]}
            </span>
          </div>
        </div>

        <div className="dssr-header-actions">
          <button
            type="button"
            className="dssr-secondary-button"
            onClick={() => void loadRun()}
          >
            ↻ Làm mới
          </button>

          <button
            type="button"
            className="dssr-secondary-button"
            onClick={() => navigate('/dss')}
          >
            Tổng quan DSS
          </button>
        </div>
      </header>

      {error && (
        <div className="dssr-alert" role="alert">
          {error}
        </div>
      )}

      {/* RUN INFORMATION */}
      <section className="dssr-panel">
        <div className="dssr-panel-heading">
          <div>
            <p className="dssr-section-index">
              01 · THÔNG TIN LẦN CHẠY
            </p>

            <h2>{run.scenario_name}</h2>

            <p>
              Kết quả mô phỏng theo dữ liệu
              kịch bản đã lựa chọn.
            </p>
          </div>

          <span className="dssr-run-id">
            {run.id}
          </span>
        </div>

        <div className="dssr-run-info">
          <div>
            <span>Mã kịch bản</span>
            <strong>{run.scenario_id}</strong>
          </div>

          <div>
            <span>Thời điểm bắt đầu</span>
            <strong>
              {formatDateTime(run.started_at)}
            </strong>
          </div>

          <div>
            <span>Hoàn thành</span>
            <strong>
              {run.completed_at
                ? formatDateTime(run.completed_at)
                : 'Chưa hoàn thành'}
            </strong>
          </div>

          <div>
            <span>Phiên bản mô phỏng</span>
            <strong>
              {run.simulation_version}
            </strong>
          </div>
        </div>
      </section>

      {/* STATISTICS */}
      <section
        className="dssr-stats"
        aria-label="Chỉ số kết quả mô phỏng"
      >
        <article className="dssr-stat">
          <span>NHÓM ỨNG VIÊN</span>
          <strong>{stats.candidates}</strong>
          <small>Kết quả từ dữ liệu mẫu</small>
        </article>

        <article className="dssr-stat">
          <span>TỔNG PHƯƠNG ÁN</span>
          <strong>{stats.options}</strong>
          <small>Direct và Hub</small>
        </article>

        <article className="dssr-stat is-green">
          <span>PHƯƠNG ÁN KHẢ THI</span>
          <strong>{stats.feasible}</strong>
          <small>Đáp ứng điều kiện mô phỏng</small>
        </article>

        <article className="dssr-stat is-amber">
          <span>KHÔNG KHẢ THI</span>
          <strong>{stats.blocked}</strong>
          <small>Bị chặn hoặc loại trừ</small>
        </article>
      </section>

      {/* BEST COST */}
      {bestOption && (
        <section className="dssr-best-option">
          <div>
            <p>
              PHƯƠNG ÁN CÓ CHI PHÍ MÔ PHỎNG
              THẤP NHẤT
            </p>

            <h2>{bestOption.name}</h2>

            <span>
              {bestOption.mode === 'DIRECT'
                ? 'Giao trực tiếp'
                : 'Giao qua Hub'}
              {' · '}
              {bestOption.vehicle_count} xe
            </span>
          </div>

          <div className="dssr-best-cost">
            <strong>
              {formatMoney(
                bestOption.estimated_cost_vnd ?? 0
              )}
            </strong>

            <button
              type="button"
              onClick={() =>
                handleViewOption(bestOption.id)
              }
            >
              Xem phương án →
            </button>
          </div>
        </section>
      )}

      {!bestOption && (
        <div className="dssr-alert">
          Không có phương án khả thi với
          chi phí xác định trong kết quả
          mô phỏng này.
        </div>
      )}

      {/* F1-F5 */}
      <section className="dssr-panel">
        <div className="dssr-panel-heading">
          <div>
            <p className="dssr-section-index">
              02 · TIẾN TRÌNH DSS
            </p>

            <h2>Kết quả năm bước F1–F5</h2>

            <p>
              Chọn một bước để xem trạng thái
              và thông tin phân tích.
            </p>
          </div>
        </div>

        <DSSProgressSteps
          modules={run.modules}
          activeModule={activeModule}
          onSelect={handleSelectModule}
        />

        {activeModuleResult ? (
          <div className="dssr-module-detail">
            <div className="dssr-module-title">
              <div>
                <span>{activeModule}</span>

                <h3>
                  {activeModuleResult.title ||
                    moduleNames[activeModule]}
                </h3>
              </div>

              <span
                className={`dssr-option-status is-${
                  activeModuleResult.status === 'COMPLETED'
                    ? 'feasible'
                    : activeModuleResult.status === 'BLOCKED'
                      ? 'blocked'
                      : 'excluded'
                }`}
              >
                {
                  moduleStatusLabels[
                    activeModuleResult.status
                  ]
                }
              </span>
            </div>

            <p className="dssr-module-summary">
              {activeModuleResult.summary}
            </p>

            {activeModuleResult.details.length > 0 && (
              <ul className="dssr-module-details">
                {activeModuleResult.details.map(
                  (detail, index) => (
                    <li key={`${activeModule}-${index}`}>
                      {detail}
                    </li>
                  )
                )}
              </ul>
            )}
          </div>
        ) : (
          <div className="dssr-empty-small">
            Chưa có dữ liệu cho bước {activeModule}.
          </div>
        )}
      </section>

      {/* RESULT TABS */}
      <section className="dssr-panel dssr-results-panel">
        <div className="dssr-panel-heading">
          <div>
            <p className="dssr-section-index">
              03 · KẾT QUẢ CHI TIẾT
            </p>

            <h2>Phân tích phương án vận chuyển</h2>

            <p>
              Xem bảng phương án, nhóm ứng viên,
              nguyên nhân loại trừ và snapshot.
            </p>
          </div>
        </div>

        <div
          className="dssr-tabs"
          role="group"
          aria-label="Chọn nội dung kết quả"
        >
          <button
            type="button"
            className={
              activeTab === 'OPTIONS'
                ? 'is-active'
                : ''
            }
            onClick={() => setActiveTab('OPTIONS')}
            aria-pressed={activeTab === 'OPTIONS'}
          >
            Direct / Hub
          </button>

          <button
            type="button"
            className={
              activeTab === 'CANDIDATES'
                ? 'is-active'
                : ''
            }
            onClick={() => setActiveTab('CANDIDATES')}
            aria-pressed={activeTab === 'CANDIDATES'}
          >
            Nhóm ứng viên
          </button>

          <button
            type="button"
            className={
              activeTab === 'REASONS'
                ? 'is-active'
                : ''
            }
            onClick={() => setActiveTab('REASONS')}
            aria-pressed={activeTab === 'REASONS'}
          >
            Lý do loại trừ
          </button>

          <button
            type="button"
            className={
              activeTab === 'SNAPSHOT'
                ? 'is-active'
                : ''
            }
            onClick={() => setActiveTab('SNAPSHOT')}
            aria-pressed={activeTab === 'SNAPSHOT'}
          >
            Snapshot
          </button>
        </div>

        <div className="dssr-tab-content">
          {activeTab === 'OPTIONS' && (
            <DirectHubComparison
              options={run.options}
              onViewOption={handleViewOption}
            />
          )}

          {activeTab === 'CANDIDATES' && (
            <CandidateTable
              candidates={run.candidates}
            />
          )}

          {activeTab === 'REASONS' && (
            <ExclusionReasonList
              candidates={run.candidates}
              options={run.options}
            />
          )}

          {activeTab === 'SNAPSHOT' && (
            <SnapshotViewer
              snapshot={run.snapshot}
            />
          )}
        </div>
      </section>

      {/* FOOTER */}
      <footer className="dssr-footer">
        <div>
          <strong>CoLogi · DSS Demo</strong>

          <p>
            Đây là kết quả mô phỏng từ dữ liệu mẫu.
            Không sử dụng trực tiếp để phân bổ xe,
            xác nhận chuyến hoặc phê duyệt vận chuyển.
          </p>
        </div>

        <button
          type="button"
          className="dssr-secondary-button"
          onClick={handleBackToScenario}
        >
          ← Quay lại kịch bản
        </button>
      </footer>
    </main>
  )
}
