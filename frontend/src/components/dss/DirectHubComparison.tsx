
import type {
  DSSOption,
  DSSOptionMode,
} from '../../types/dss'

interface DirectHubComparisonProps {
  options: DSSOption[]
  onViewOption: (optionId: string) => void
}

function formatMoney(
  value: number | null
): string {
  if (value === null) return 'Chưa xác định'

  return `${value.toLocaleString('vi-VN')} ₫`
}

function formatDistance(
  value: number | null
): string {
  if (value === null) return 'Chưa xác định'

  return `${value.toLocaleString('vi-VN')} km`
}

const modes: Array<{
  mode: DSSOptionMode
  name: string
  description: string
}> = [
  {
    mode: 'DIRECT',
    name: 'Direct',
    description: 'Giao hàng trực tiếp',
  },
  {
    mode: 'HUB',
    name: 'Hub',
    description: 'Giao hàng qua điểm trung chuyển',
  },
]

export default function DirectHubComparison({
  options,
  onViewOption,
}: DirectHubComparisonProps) {
  const bestOption = [...options]
    .filter(
      (option) =>
        option.status === 'FEASIBLE' &&
        option.estimated_cost_vnd !== null
    )
    .sort(
      (a, b) =>
        (a.estimated_cost_vnd ?? 0) -
        (b.estimated_cost_vnd ?? 0)
    )[0]

  const statusLabels = {
    FEASIBLE: 'Khả thi',
    BLOCKED: 'Bị chặn',
    EXCLUDED: 'Bị loại trừ',
  }

  return (
    <div className="dssr-comparison-grid">
      {modes.map(({ mode, name, description }) => {
        const modeOptions = options.filter(
          (option) => option.mode === mode
        )

        return (
          <section
            key={mode}
            className="dssr-comparison-card"
          >
            <div className="dssr-comparison-heading">
              <span
                className={`dssr-mode-icon is-${mode.toLowerCase()}`}
              >
                {mode === 'DIRECT' ? 'D' : 'H'}
              </span>

              <div>
                <h3>{name}</h3>
                <p>{description}</p>
              </div>
            </div>

            {modeOptions.length === 0 ? (
              <div className="dssr-empty-small">
                Chưa có phương án {name} trong
                lần chạy này.
              </div>
            ) : (
              <div className="dssr-mode-options">
                {modeOptions.map((option) => {
                  const isBest =
                    option.id === bestOption?.id

                  return (
                    <article
                      key={option.id}
                      className="dssr-mode-option"
                    >
                      <div className="dssr-option-title">
                        <strong>{option.name}</strong>

                        {isBest && (
                          <span className="dssr-best-label">
                            Chi phí thấp nhất
                          </span>
                        )}
                      </div>

                      <span
                        className={`dssr-option-status is-${option.status.toLowerCase()}`}
                      >
                        {statusLabels[option.status]}
                      </span>

                      <div className="dssr-cost">
                        {formatMoney(
                          option.estimated_cost_vnd
                        )}
                      </div>

                      <dl className="dssr-option-metrics">
                        <div>
                          <dt>Phương tiện</dt>
                          <dd>{option.vehicle_name}</dd>
                        </div>

                        <div>
                          <dt>Số lượng xe</dt>
                          <dd>
                            {option.vehicle_count}
                          </dd>
                        </div>

                        <div>
                          <dt>Khối lượng</dt>
                          <dd>
                            {option.total_quantity_kg.toLocaleString(
                              'vi-VN'
                            )} kg
                          </dd>
                        </div>

                        <div>
                          <dt>Tải trọng</dt>
                          <dd>
                            {option.capacity_kg.toLocaleString(
                              'vi-VN'
                            )} kg
                          </dd>
                        </div>

                        <div>
                          <dt>Quãng đường</dt>
                          <dd>
                            {formatDistance(
                              option.estimated_distance_km
                            )}
                          </dd>
                        </div>

                        <div>
                          <dt>Nhu cầu</dt>
                          <dd>
                            {option.demand_ids.length}
                          </dd>
                        </div>
                      </dl>

                      {option.reasons.length > 0 && (
                        <div className="dssr-option-warning">
                          {option.reasons.length} lý do
                          cần xem xét
                        </div>
                      )}

                      <button
                        type="button"
                        className="dssr-text-button"
                        onClick={() =>
                          onViewOption(option.id)
                        }
                      >
                        Xem chi tiết phương án →
                      </button>
                    </article>
                  )
                })}
              </div>
            )}
          </section>
        )
      })}
    </div>
  )
}
