
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from 'react'
import {
  useNavigate,
  useParams,
} from 'react-router-dom'

import { dssService } from '../../services/dss/dssService'

import type {
  DSSCreateScenarioInput,
  DSSRun,
  DSSScenario,
  DSSScenarioType,
} from '../../types/dss'

import './DSSScenarioPage.css'

/* =========================================
   CONFIGURATION
========================================= */

const scenarioTypeOptions: Array<{
  value: DSSScenarioType
  title: string
  description: string
  icon: string
}> = [
  {
    value: 'NORMAL',
    title: 'Đủ năng lực vận chuyển',
    description:
      'Mô phỏng trường hợp có phương án Direct ' +
      'và Hub khả thi để so sánh.',
    icon: '✓',
  },
  {
    value: 'INSUFFICIENT_VEHICLES',
    title: 'Thiếu năng lực phương tiện',
    description:
      'Mô phỏng phương án bị chặn do thiếu xe ' +
      'hoặc không đáp ứng năng lực.',
    icon: '!',
  },
  {
    value: 'TIME_CONFLICT',
    title: 'Xung đột thời gian',
    description:
      'Mô phỏng trường hợp khung giờ lấy hàng ' +
      'và giao hàng không phù hợp.',
    icon: '◷',
  },
]

const steps = [
  { code: 'F1', label: 'Phối hợp nhu cầu' },
  { code: 'F2', label: 'Xây dựng phương án' },
  { code: 'F3', label: 'Phân bổ phương tiện' },
  { code: 'F4', label: 'Kiểm tra thời gian' },
  { code: 'F5', label: 'Đánh giá kinh tế' },
]

function getVietnamDate(): string {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Ho_Chi_Minh',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).formatToParts(new Date())

  const get = (type: string) =>
    parts.find((part) => part.type === type)?.value ?? ''

  return `${get('year')}-${get('month')}-${get('day')}`
}

function formatServiceDate(value: string): string {
  const [year, month, day] = value.split('-')

  return year && month && day
    ? `${day}/${month}/${year}`
    : value
}

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

function getScenarioTypeLabel(
  type: DSSScenarioType
): string {
  return (
    scenarioTypeOptions.find(
      (option) => option.value === type
    )?.title ?? 'Không xác định'
  )
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : 'Đã xảy ra lỗi. Vui lòng thử lại.'
}

function initialValues(): DSSCreateScenarioInput {
  return {
    name: '',
    description: '',
    service_date: getVietnamDate(),
    demand_count: 8,
    scenario_type: 'NORMAL',
  }
}

/* =========================================
   MAIN COMPONENT
========================================= */

export default function DSSScenarioPage() {
  const navigate = useNavigate()
  const { scenarioId } = useParams<{
    scenarioId: string
  }>()

  const isCreateMode = !scenarioId

  const [form, setForm] =
    useState<DSSCreateScenarioInput>(
      initialValues
    )

  const [scenario, setScenario] =
    useState<DSSScenario | null>(null)

  const [runs, setRuns] = useState<DSSRun[]>([])

  const [loading, setLoading] = useState(
    !isCreateMode
  )

  const [saving, setSaving] = useState(false)
  const [running, setRunning] = useState(false)

  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  /* =========================================
     LOAD DETAIL
  ========================================= */

  const loadScenario = useCallback(async () => {
    if (!scenarioId) return

    setLoading(true)
    setError('')

    try {
      const [scenarioData, runData] =
        await Promise.all([
          dssService.getScenario(scenarioId),
          dssService.listRuns(scenarioId),
        ])

      setScenario(scenarioData)
      setRuns(runData)

      if (!scenarioData) {
        setError(
          'Không tìm thấy kịch bản. ' +
          'Kịch bản có thể đã mất sau khi tải lại trang.'
        )
      }
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [scenarioId])

  useEffect(() => {
    if (scenarioId) {
      void loadScenario()
    }
  }, [scenarioId, loadScenario])

  /* =========================================
     DERIVED VALUES
  ========================================= */

  const selectedType = useMemo(
    () =>
      scenarioTypeOptions.find(
        (option) =>
          option.value === form.scenario_type
      ),
    [form.scenario_type]
  )

  const latestRun = runs[0] ?? null

  const completedRuns = runs.filter(
    (run) => run.status === 'COMPLETED'
  ).length

  /* =========================================
     FORM ACTIONS
  ========================================= */

  function updateForm<K extends keyof DSSCreateScenarioInput>(
    field: K,
    value: DSSCreateScenarioInput[K]
  ) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }))

    setError('')
  }

  function validateForm(): string | null {
    if (!form.name.trim()) {
      return 'Vui lòng nhập tên kịch bản.'
    }

    if (form.name.trim().length < 5) {
      return 'Tên kịch bản cần ít nhất 5 ký tự.'
    }

    if (
      !/^\d{4}-\d{2}-\d{2}$/.test(
        form.service_date
      )
    ) {
      return 'Vui lòng chọn ngày phục vụ hợp lệ.'
    }

    const parsedDate = new Date(
      `${form.service_date}T00:00:00Z`
    )

    if (
      Number.isNaN(parsedDate.getTime()) ||
      parsedDate.toISOString().slice(0, 10) !==
        form.service_date
    ) {
      return 'Ngày phục vụ không hợp lệ.'
    }

    if (
      !Number.isInteger(form.demand_count) ||
      form.demand_count < 1
    ) {
      return 'Số nhu cầu phải là số nguyên lớn hơn 0.'
    }

    if (form.demand_count > 1000) {
      return 'Số nhu cầu không được vượt quá 1.000.'
    }

    return null
  }

  async function handleCreate(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault()

    if (saving) return

    setError('')
    setSuccess('')

    const validationError = validateForm()

    if (validationError) {
      setError(validationError)
      return
    }

    setSaving(true)

    try {
      const created =
        await dssService.createScenario({
          ...form,
          name: form.name.trim(),
          description: form.description.trim(),
        })

      // Chuyển sang chế độ xem chi tiết
      navigate(
        `/dss/scenarios/${created.id}`,
        { replace: true }
      )
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  async function handleRun() {
    if (!scenario || running) return

    setRunning(true)
    setError('')
    setSuccess('')

    try {
      const run = await dssService.runScenario(
        scenario.id
      )

      const latestRuns =
        await dssService.listRuns(scenario.id)

      setRuns(latestRuns)

      setSuccess(
        `Đã tạo lần chạy mô phỏng ${run.id}. ` +
        'Kết quả minh họa đã được lưu trong phiên này.'
      )
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setRunning(false)
    }
  }

  /* =========================================
     RENDER
  ========================================= */

  return (
    <main className="dssc-page">
      {/* HEADER */}
      <header className="dssc-header">
        <div>
          <button
            type="button"
            className="dssc-back-link"
            onClick={() => navigate('/dss')}
          >
            ← Quay lại tổng quan
          </button>

          <p className="dssc-eyebrow">
            COLOGI · LẬP KẾ HOẠCH
          </p>

          <h1>
            {isCreateMode
              ? 'Thiết lập kịch bản vận chuyển'
              : 'Chi tiết kịch bản vận chuyển'}
          </h1>

          <p className="dssc-description">
            {isCreateMode
              ? (
                'Xác định điều kiện đầu vào ' +
                'cho quá trình phân tích mô phỏng.'
              )
              : (
                'Xem điều kiện kịch bản, các lần chạy ' +
                'và kết quả mô phỏng.'
              )}
          </p>

          <span className="dssc-demo-badge">
            Chế độ mô phỏng · Dữ liệu minh họa
          </span>
        </div>
      </header>

      {/* ALERTS */}
      {error && (
        <div
          className="dssc-alert is-error"
          role="alert"
        >
          {error}
        </div>
      )}

      {success && (
        <div
          className="dssc-alert is-success"
          role="status"
        >
          {success}
        </div>
      )}

      {/* CREATE MODE */}
      {isCreateMode ? (
        <div className="dssc-layout">
          <section className="dssc-panel">
            <div className="dssc-panel-heading">
              <p className="dssc-section-index">
                01 · THIẾT LẬP
              </p>

              <h2>Thông tin kịch bản</h2>

              <p>
                Nhập thông tin để tạo một
                kịch bản mô phỏng mới.
              </p>
            </div>

            <form
              className="dssc-form"
              onSubmit={handleCreate}
            >
              <label className="dssc-field">
                <span>
                  Tên kịch bản
                  <em> *</em>
                </span>

                <input
                  type="text"
                  value={form.name}
                  maxLength={100}
                  placeholder={
                    'Ví dụ: Kế hoạch vận chuyển ' +
                    'ngày 20/11'
                  }
                  onChange={(event) =>
                    updateForm(
                      'name',
                      event.target.value
                    )
                  }
                  required
                />
              </label>

              <label className="dssc-field">
                <span>Mô tả</span>

                <textarea
                  rows={3}
                  maxLength={500}
                  placeholder={
                    'Mục tiêu và các điều kiện ' +
                    'cần đánh giá trong kịch bản...'
                  }
                  value={form.description}
                  onChange={(event) =>
                    updateForm(
                      'description',
                      event.target.value
                    )
                  }
                />
              </label>

              <div className="dssc-form-grid">
                <label className="dssc-field">
                  <span>
                    Ngày phục vụ
                    <em> *</em>
                  </span>

                  <input
                    type="date"
                    value={form.service_date}
                    onChange={(event) =>
                      updateForm(
                        'service_date',
                        event.target.value
                      )
                    }
                    required
                  />
                </label>

                <label className="dssc-field">
                  <span>
                    Số nhu cầu mô phỏng
                    <em> *</em>
                  </span>

                  <input
                    type="number"
                    min={1}
                    max={1000}
                    step={1}
                    value={form.demand_count}
                    onChange={(event) =>
                      updateForm(
                        'demand_count',
                        event.target.value === ''
                          ? 0
                          : Number(
                              event.target.value
                            )
                      )
                    }
                    required
                  />
                </label>
              </div>

              <div className="dssc-type-section">
                <div className="dssc-type-heading">
                  <strong>
                    Tình huống mô phỏng
                  </strong>
                  <small>
                    Chọn một trong ba loại tình huống.
                  </small>
                </div>

                <div className="dssc-type-list">
                  {scenarioTypeOptions.map(
                    (option) => {
                      const isSelected =
                        form.scenario_type ===
                        option.value

                      return (
                        <label
                          key={option.value}
                          className={`dssc-type-card ${
                            isSelected
                              ? 'is-selected'
                              : ''
                          }`}
                        >
                          <input
                            type="radio"
                            name="scenario_type"
                            value={option.value}
                            checked={isSelected}
                            onChange={() =>
                              updateForm(
                                'scenario_type',
                                option.value
                              )
                            }
                          />

                          <span className="dssc-type-icon">
                            {option.icon}
                          </span>

                          <span className="dssc-type-copy">
                            <strong>
                              {option.title}
                            </strong>
                            <small>
                              {option.description}
                            </small>
                          </span>
                        </label>
                      )
                    }
                  )}
                </div>
              </div>

              <div className="dssc-form-actions">
                <button
                  type="button"
                  className="dssc-button dssc-button-secondary"
                  onClick={() => navigate('/dss')}
                  disabled={saving}
                >
                  Hủy
                </button>

                <button
                  type="submit"
                  className="dssc-button dssc-button-primary"
                  disabled={saving}
                >
                  {saving
                    ? 'Đang tạo...'
                    : '+ Tạo kịch bản'}
                </button>
              </div>
            </form>
          </section>

          {/* CREATE SIDE PANEL */}
          <aside className="dssc-side-panel">
            <section className="dssc-panel">
              <div className="dssc-panel-heading">
                <p className="dssc-section-index">
                  02 · XEM TRƯỚC
                </p>

                <h2>Tóm tắt thiết lập</h2>
              </div>

              <div className="dssc-preview">
                <div>
                  <span>Tên kịch bản</span>
                  <strong>
                    {form.name.trim() ||
                      'Chưa đặt tên'}
                  </strong>
                </div>

                <div>
                  <span>Ngày phục vụ</span>
                  <strong>
                    {formatServiceDate(
                      form.service_date
                    )}
                  </strong>
                </div>

                <div>
                  <span>Số nhu cầu</span>
                  <strong>
                    {form.demand_count || '—'}
                  </strong>
                </div>

                <div>
                  <span>Tình huống</span>
                  <strong>
                    {selectedType?.title}
                  </strong>
                </div>
              </div>

              <div className="dssc-info-note">
                <strong>
                  Lưu ý về dữ liệu mô phỏng
                </strong>

                <p>
                  Số nhu cầu là tham số hiển thị.
                  Kết quả nhóm hàng, phân bổ xe
                  và chi phí hiện được lấy từ
                  bộ dữ liệu mẫu cố định,
                  chưa tính từ số nhu cầu bạn nhập.
                </p>
              </div>
            </section>

            <section className="dssc-panel">
              <div className="dssc-panel-heading">
                <p className="dssc-section-index">
                  03 · QUY TRÌNH
                </p>

                <h2>Năm bước phân tích</h2>
              </div>

              <div className="dssc-steps">
                {steps.map((step) => (
                  <div
                    key={step.code}
                    className="dssc-step"
                  >
                    <span>{step.code}</span>
                    <strong>{step.label}</strong>
                  </div>
                ))}
              </div>
            </section>
          </aside>
        </div>
      ) : loading ? (
        <div className="dssc-loading">
          Đang tải thông tin kịch bản...
        </div>
      ) : !scenario ? (
        <section className="dssc-panel">
          <div className="dssc-empty">
            <strong>Không tìm thấy kịch bản</strong>

            <p>
              Vui lòng quay lại tổng quan
              và chọn kịch bản khác.
            </p>

            <button
              type="button"
              className="dssc-button dssc-button-secondary"
              onClick={() => navigate('/dss')}
            >
              Quay lại tổng quan
            </button>
          </div>
        </section>
      ) : (
        /* DETAIL MODE */
        <div className="dssc-layout">
          <section className="dssc-panel">
            <div className="dssc-panel-heading">
              <p className="dssc-section-index">
                01 · KỊCH BẢN ĐÃ LƯU
              </p>

              <h2>{scenario.name}</h2>

              <p>
                {scenario.description ||
                  'Không có mô tả.'}
              </p>
            </div>

            <div className="dssc-detail-summary">
              <div>
                <span>MÃ KỊCH BẢN</span>
                <strong>{scenario.id}</strong>
              </div>

              <div>
                <span>NGÀY PHỤC VỤ</span>
                <strong>
                  {formatServiceDate(
                    scenario.service_date
                  )}
                </strong>
              </div>

              <div>
                <span>SỐ NHU CẦU</span>
                <strong>
                  {scenario.demand_count}
                </strong>
              </div>

              <div>
                <span>TÌNH HUỐNG</span>
                <strong>
                  {getScenarioTypeLabel(
                    scenario.scenario_type
                  )}
                </strong>
              </div>
            </div>

            <div className="dssc-divider" />

            <div className="dssc-panel-heading">
              <p className="dssc-section-index">
                02 · PHÂN TÍCH
              </p>

              <h2>Chạy mô phỏng F1–F5</h2>

              <p>
                Tạo một lần chạy mới từ kịch bản
                đã chọn.
              </p>
            </div>

            <div className="dssc-steps">
              {steps.map((step) => (
                <div
                  key={step.code}
                  className="dssc-step"
                >
                  <span>{step.code}</span>
                  <strong>{step.label}</strong>
                </div>
              ))}
            </div>

            <div className="dssc-run-actions">
              <button
                type="button"
                className="dssc-button dssc-button-primary"
                onClick={() => void handleRun()}
                disabled={running}
              >
                {running
                  ? 'Đang tạo kết quả...'
                  : '▶ Chạy mô phỏng'}
              </button>

              <p>
                Kết quả chỉ phục vụ demo,
                không tạo kế hoạch vận chuyển
                thực tế và không phê duyệt
                phương án.
              </p>
            </div>

            <div className="dssc-divider" />

            <div className="dssc-panel-heading">
              <p className="dssc-section-index">
                03 · LỊCH SỬ
              </p>

              <h2>Lịch sử lần chạy</h2>

              <p>
                Có {runs.length} lần chạy trong
                phiên demo hiện tại.
              </p>
            </div>

            {runs.length === 0 ? (
              <div className="dssc-empty">
                Chưa có lần chạy nào.
                Nhấn “Chạy mô phỏng” để tạo kết quả.
              </div>
            ) : (
              <div className="dssc-run-list">
                {runs.map((run) => {
                  const feasibleCount =
                    run.options.filter(
                      (option) =>
                        option.status === 'FEASIBLE'
                    ).length

                  return (
                    <div
                      key={run.id}
                      className="dssc-run-item"
                    >
                      <div>
                        <strong>{run.id}</strong>

                        <small>
                          {formatDateTime(
                            run.started_at
                          )}
                        </small>

                        <span>
                          {feasibleCount} phương án
                          khả thi / {run.options.length}
                          {' '}phương án
                        </span>
                      </div>

                      <button
                        type="button"
                        onClick={() =>
                          navigate(
                            `/dss/runs/${run.id}`
                          )
                        }
                      >
                        Xem kết quả →
                      </button>
                    </div>
                  )
                })}
              </div>
            )}
          </section>

          {/* DETAIL SIDE PANEL */}
          <aside className="dssc-side-panel">
            <section className="dssc-panel">
              <div className="dssc-panel-heading">
                <p className="dssc-section-index">
                  THÔNG TIN BỔ SUNG
                </p>

                <h2>Trạng thái kịch bản</h2>
              </div>

              <div className="dssc-preview">
                <div>
                  <span>Ngày tạo</span>
                  <strong>
                    {formatDateTime(
                      scenario.created_at
                    )}
                  </strong>
                </div>

                <div>
                  <span>Chế độ dữ liệu</span>
                  <strong>
                    Mô phỏng
                  </strong>
                </div>

                <div>
                  <span>Số lần chạy</span>
                  <strong>
                    {runs.length}
                  </strong>
                </div>

                <div>
                  <span>Lần chạy hoàn thành</span>
                  <strong>
                    {completedRuns}
                  </strong>
                </div>
              </div>

              {latestRun && (
                <div className="dssc-latest-run">
                  <small>LẦN CHẠY GẦN NHẤT</small>

                  <strong>
                    {latestRun.id}
                  </strong>

                  <button
                    type="button"
                    onClick={() =>
                      navigate(
                        `/dss/runs/${latestRun.id}`
                      )
                    }
                  >
                    Xem kết quả →
                  </button>
                </div>
              )}

              <div className="dssc-info-note">
                <strong>
                  Kịch bản chưa kết nối dữ liệu thật
                </strong>

                <p>
                  Thông tin nhu cầu, nhà cung cấp
                  và lịch xe trong kết quả là fixture
                  mô phỏng. Chưa có thao tác phê duyệt
                  hay điều phối thực tế.
                </p>
              </div>
            </section>
          </aside>
        </div>
      )}
    </main>
  )
}
