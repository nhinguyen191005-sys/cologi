
import type {
  DSSModuleCode,
  DSSModuleResult,
} from '../../types/dss'

interface DSSProgressStepsProps {
  modules: DSSModuleResult[]
  activeModule: DSSModuleCode
  onSelect: (module: DSSModuleCode) => void
}

const moduleOrder: DSSModuleCode[] = [
  'F1',
  'F2',
  'F3',
  'F4',
  'F5',
]

const labels: Record<DSSModuleCode, string> = {
  F1: 'Phối hợp nhu cầu',
  F2: 'Xây dựng phương án',
  F3: 'Phân bổ phương tiện',
  F4: 'Kiểm tra thời gian',
  F5: 'Đánh giá kinh tế',
}

const statusLabels = {
  COMPLETED: 'Hoàn thành',
  BLOCKED: 'Bị chặn',
  SKIPPED: 'Bỏ qua',
} as const

export default function DSSProgressSteps({
  modules,
  activeModule,
  onSelect,
}: DSSProgressStepsProps) {
  return (
    <div className="dssr-progress">
      {moduleOrder.map((code) => {
        const module = modules.find(
          (item) => item.module === code
        )

        const status = module?.status ?? 'SKIPPED'
        const isActive = activeModule === code

        return (
          <button
            key={code}
            type="button"
            className={[
              'dssr-progress-step',
              `is-${status.toLowerCase()}`,
              isActive ? 'is-active' : '',
            ].join(' ')}
            onClick={() => onSelect(code)}
            aria-pressed={isActive}
          >
            <span className="dssr-progress-number">
              {code}
            </span>

            <span className="dssr-progress-copy">
              <strong>{labels[code]}</strong>
              <small>{statusLabels[status]}</small>
            </span>

            <span
              className="dssr-progress-indicator"
              aria-hidden="true"
            >
              {status === 'COMPLETED'
                ? '✓'
                : status === 'BLOCKED'
                  ? '!'
                  : '–'}
            </span>
          </button>
        )
      })}
    </div>
  )
}
