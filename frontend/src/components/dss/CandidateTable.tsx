
import type {
  DSSCandidate,
} from '../../types/dss'

interface CandidateTableProps {
  candidates: DSSCandidate[]
}

export default function CandidateTable({
  candidates,
}: CandidateTableProps) {
  if (candidates.length === 0) {
    return (
      <div className="dssr-empty-small">
        Không có nhóm ứng viên trong kết quả mô phỏng.
      </div>
    )
  }

  return (
    <div className="dssr-table-scroll">
      <table className="dssr-table">
        <thead>
          <tr>
            <th>MÃ NHÓM</th>
            <th>NHU CẦU</th>
            <th>NHÀ CUNG CẤP</th>
            <th>KHỐI LƯỢNG</th>
            <th>TRẠNG THÁI</th>
            <th>GHI CHÚ</th>
          </tr>
        </thead>

        <tbody>
          {candidates.map((candidate) => {
            const eligible =
              candidate.status === 'ELIGIBLE'

            return (
              <tr key={candidate.id}>
                <td>
                  <strong className="dssr-table-id">
                    {candidate.id}
                  </strong>
                </td>

                <td>
                  <span className="dssr-table-main">
                    {candidate.demand_ids.length} nhu cầu
                  </span>

                  <small>
                    {candidate.demand_ids.join(', ') ||
                      'Chưa có mã nhu cầu'}
                  </small>
                </td>

                <td>
                  {candidate.supplier_names.join(', ') ||
                    'Chưa xác định'}
                </td>

                <td>
                  {candidate.total_quantity_kg.toLocaleString(
                    'vi-VN'
                  )} kg
                </td>

                <td>
                  <span
                    className={`dssr-option-status ${
                      eligible
                        ? 'is-feasible'
                        : 'is-excluded'
                    }`}
                  >
                    {eligible
                      ? 'Đủ điều kiện'
                      : 'Bị loại trừ'}
                  </span>
                </td>

                <td>
                  {candidate.reasons.length > 0
                    ? candidate.reasons
                        .map((reason) => reason.message)
                        .join('; ')
                    : 'Không có lý do loại trừ'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
