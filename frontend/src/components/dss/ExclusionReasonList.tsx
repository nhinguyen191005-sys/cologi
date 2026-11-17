
import { useMemo } from 'react'

import type {
  DSSCandidate,
  DSSModuleCode,
  DSSOption,
  DSSReason,
} from '../../types/dss'

interface ExclusionReasonListProps {
  candidates: DSSCandidate[]
  options: DSSOption[]
}

interface ReasonEntry {
  key: string
  subjectId: string
  subjectType: 'Ứng viên' | 'Phương án'
  reason: DSSReason
}

const moduleLabels: Record<
  DSSModuleCode,
  string
> = {
  F1: 'Phối hợp nhu cầu',
  F2: 'Xây dựng phương án',
  F3: 'Phân bổ phương tiện',
  F4: 'Kiểm tra thời gian',
  F5: 'Đánh giá kinh tế',
}

export default function ExclusionReasonList({
  candidates,
  options,
}: ExclusionReasonListProps) {
  const entries = useMemo(() => {
    const results: ReasonEntry[] = []

    candidates.forEach((candidate) => {
      candidate.reasons.forEach((reason, index) => {
        results.push({
          key: `candidate-${candidate.id}-${index}`,
          subjectId: candidate.id,
          subjectType: 'Ứng viên',
          reason,
        })
      })
    })

    options.forEach((option) => {
      option.reasons.forEach((reason, index) => {
        results.push({
          key: `option-${option.id}-${index}`,
          subjectId: option.id,
          subjectType: 'Phương án',
          reason,
        })
      })
    })

    return results
  }, [candidates, options])

  if (entries.length === 0) {
    return (
      <div className="dssr-empty-small">
        Không có nguyên nhân loại trừ hoặc
        chặn phương án nào được ghi nhận.
      </div>
    )
  }

  return (
    <div className="dssr-reason-list">
      {entries.map((entry) => (
        <article
          key={entry.key}
          className="dssr-reason-card"
        >
          <div className="dssr-reason-symbol">
            !
          </div>

          <div className="dssr-reason-content">
            <div className="dssr-reason-meta">
              <span className="dssr-reason-code">
                {entry.reason.code}
              </span>

              <span className="dssr-reason-module">
                {entry.reason.module} ·{' '}
                {moduleLabels[entry.reason.module]}
              </span>
            </div>

            <strong>
              {entry.subjectType} {entry.subjectId}
            </strong>

            <p>{entry.reason.message}</p>
          </div>
        </article>
      ))}
    </div>
  )
}
