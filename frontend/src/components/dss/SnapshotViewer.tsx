
import { useState } from 'react'

import type {
  DSSSnapshot,
} from '../../types/dss'

interface SnapshotViewerProps {
  snapshot: DSSSnapshot
}

function formatDate(value: string): string {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) return value

  return new Intl.DateTimeFormat('vi-VN', {
    timeZone: 'Asia/Ho_Chi_Minh',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export default function SnapshotViewer({
  snapshot,
}: SnapshotViewerProps) {
  const [showJson, setShowJson] = useState(false)
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(
        JSON.stringify(snapshot, null, 2)
      )

      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="dssr-snapshot">
      <div className="dssr-snapshot-grid">
        <div className="dssr-snapshot-group">
          <h3>Dữ liệu đầu vào</h3>

          <dl>
            <div>
              <dt>Mã kịch bản</dt>
              <dd>{snapshot.scenario_id}</dd>
            </div>

            <div>
              <dt>Ngày phục vụ</dt>
              <dd>{snapshot.input.service_date}</dd>
            </div>

            <div>
              <dt>Số nhu cầu</dt>
              <dd>{snapshot.input.demand_count}</dd>
            </div>

            <div>
              <dt>Loại tình huống</dt>
              <dd>
                {snapshot.input.scenario_type}
              </dd>
            </div>

            <div>
              <dt>Nguồn dữ liệu</dt>
              <dd>{snapshot.source}</dd>
            </div>
          </dl>
        </div>

        <div className="dssr-snapshot-group">
          <h3>Kết quả mô phỏng</h3>

          <dl>
            <div>
              <dt>Số nhóm ứng viên</dt>
              <dd>
                {snapshot.output.candidate_count}
              </dd>
            </div>

            <div>
              <dt>Tổng phương án</dt>
              <dd>
                {snapshot.output.option_count}
              </dd>
            </div>

            <div>
              <dt>Phương án khả thi</dt>
              <dd>
                {snapshot.output.feasible_count}
              </dd>
            </div>

            <div>
              <dt>Phương án bị chặn</dt>
              <dd>
                {snapshot.output.blocked_count}
              </dd>
            </div>

            <div>
              <dt>Thời điểm ghi nhận</dt>
              <dd>
                {formatDate(snapshot.captured_at)}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="dssr-snapshot-note">
        <strong>Ghi chú dữ liệu</strong>
        <p>
          {snapshot.input.note}
        </p>
        <p>
          Snapshot có nguồn DEMO_FIXTURE. Các chỉ số
          được cung cấp từ dữ liệu minh họa, chưa
          chứng minh thuật toán F1–F5 đã tính toán
          trên dữ liệu vận hành thực tế.
        </p>
      </div>

      <div className="dssr-snapshot-actions">
        <button
          type="button"
          className="dssr-secondary-button"
          onClick={() => setShowJson((value) => !value)}
        >
          {showJson
            ? 'Ẩn dữ liệu JSON'
            : 'Xem dữ liệu JSON'}
        </button>

        {showJson && (
          <button
            type="button"
            className="dssr-secondary-button"
            onClick={() => void handleCopy()}
          >
            {copied ? 'Đã sao chép' : 'Sao chép JSON'}
          </button>
        )}
      </div>

      {showJson && (
        <pre className="dssr-json">
          <code>
            {JSON.stringify(snapshot, null, 2)}
          </code>
        </pre>
      )}
    </div>
  )
}
