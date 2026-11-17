
import { useEffect, useState } from 'react'
import { useAuth } from '../../contexts/useAuth'
import { ApiError, apiRequest } from '../../services/api/client'
import {
  listSuppliers,
  submitDemand,
} from '../../services/api/demands'
import type {
  DeliveryDemand,
  Supplier,
} from '../../types/demand'
import './SupplierResubmitPanel.css'

type Props = {
  demand: DeliveryDemand
  onResubmitted: () => void
}

function messageOf(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 403) {
      return 'Tài khoản không có quyền chọn nhà cung cấp hoặc gửi lại.'
    }

    if (error.status === 409) {
      return 'Yêu cầu trước còn hiệu lực, chưa được giải phóng cam kết hoặc chưa có lựa chọn NCC hợp lệ.'
    }

    if (error.data && typeof error.data === 'object') {
      const values: string[] = []

      const collect = (value: unknown) => {
        if (typeof value === 'string') {
          values.push(value)
        } else if (Array.isArray(value)) {
          value.forEach(collect)
        } else if (value && typeof value === 'object') {
          Object.values(value).forEach(collect)
        }
      }

      collect(error.data)

      if (values.length) return values.join(' · ')
    }

    return error.message
  }

  return error instanceof Error
    ? error.message
    : 'Không thể hoàn thành thao tác.'
}

export function SupplierResubmitPanel({
  demand,
  onResubmitted,
}: Props) {
  const { user } = useAuth()

  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [selectedSupplierId, setSelectedSupplierId] = useState('')
  const [loadingSuppliers, setLoadingSuppliers] = useState(false)
  const [busy, setBusy] = useState(false)

  const [chosenButNotSubmitted, setChosenButNotSubmitted] =
    useState(false)

  const [completed, setCompleted] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const allowed = Boolean(
    user &&
    user.roles.includes('PURCHASING_STAFF') &&
    !user.roles.includes('MANAGER') &&
    demand.created_by_id === user.id &&
    demand.status === 'SUBMITTED'
  )

  useEffect(() => {
    if (!allowed) return

    let active = true

    async function loadOptions() {
      setLoadingSuppliers(true)

      try {
        const list = await listSuppliers()

        if (active) {
          setSuppliers(
            list.filter((row) => row.is_active)
          )
        }
      } catch (loadError) {
        if (active) setError(messageOf(loadError))
      } finally {
        if (active) setLoadingSuppliers(false)
      }
    }

    void loadOptions()

    return () => {
      active = false
    }
  }, [allowed])

  if (!allowed) return null

  async function retrySubmit() {
    if (busy || completed) return

    setBusy(true)
    setError('')
    setSuccess('')

    try {
      const result = await submitDemand(demand.id)

      setChosenButNotSubmitted(false)
      setCompleted(true)

      setSuccess(
        `Đã gửi yêu cầu lần tiếp theo. Mã yêu cầu: #${result.supplier_request_id}.`
      )

      onResubmitted()
    } catch (submitError) {
      setError(messageOf(submitError))
    } finally {
      setBusy(false)
    }
  }

  async function chooseAndResubmit() {
    if (
      busy ||
      completed ||
      !selectedSupplierId ||
      chosenButNotSubmitted
    ) {
      return
    }

    setBusy(true)
    setError('')
    setSuccess('')

    try {
      // Bước 1: Lưu lựa chọn NCC thay thế.
      await apiRequest(
        `/demands/${demand.id}/select-supplier`,
        {
          method: 'POST',
          body: JSON.stringify({
            selected_supplier_id: Number(selectedSupplierId),
          }),
        }
      )

      setChosenButNotSubmitted(true)

      // Bước 2: Gửi lại demand.
      try {
        const result = await submitDemand(demand.id)

        setChosenButNotSubmitted(false)
        setCompleted(true)

        setSuccess(
          `Đã chọn NCC và gửi lại thành công. Mã yêu cầu: #${result.supplier_request_id}.`
        )

        onResubmitted()
      } catch (submitError) {
        setError(
          `Đã lưu lựa chọn nhà cung cấp nhưng chưa gửi lại: ${messageOf(submitError)}`
        )
      }
    } catch (selectionError) {
      setError(messageOf(selectionError))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section
      className="srp-card"
      aria-label="Chọn nhà cung cấp và gửi lại yêu cầu"
    >
      <div className="srp-heading">
        <span>SUPPLIER RESELECTION</span>

        <h2>Chọn NCC thay thế & gửi lại</h2>

        <p>
          Chỉ thực hiện khi lần phản hồi trước đã từ chối,
          hết hạn hoặc xác nhận một phần đã được giải phóng
          cam kết. Mọi điều kiện và quyền đều do Backend kiểm tra.
        </p>
      </div>

      <div className="srp-controls">
        <label>
          <span>Nhà cung cấp muốn chọn</span>

          <select
            value={selectedSupplierId}
            onChange={(event) =>
              setSelectedSupplierId(event.target.value)
            }
            disabled={
              busy ||
              completed ||
              chosenButNotSubmitted ||
              loadingSuppliers
            }
          >
            <option value="">
              {loadingSuppliers
                ? 'Đang tải NCC...'
                : 'Chọn nhà cung cấp...'}
            </option>

            {suppliers.map((supplier) => (
              <option
                key={supplier.id}
                value={supplier.id}
              >
                {supplier.supplier_code}
                {' · '}
                {supplier.supplier_name}
                {supplier.id === demand.supplier_id
                  ? ' (NCC hiện tại)'
                  : ''}
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          className="srp-primary"
          onClick={() => void chooseAndResubmit()}
          disabled={
            busy ||
            completed ||
            chosenButNotSubmitted ||
            !selectedSupplierId
          }
        >
          {busy
            ? 'Đang xử lý...'
            : 'Chọn NCC và gửi lại'}
        </button>
      </div>

      <p className="srp-hint">
        NCC được chọn phải có mặt hàng và năng lực cung ứng
        hợp lệ. Hệ thống sẽ tạo một SupplierRequest mới,
        tăng số lần gửi và giữ lại lịch sử cũ sau khi gửi thành công.
      </p>

      {chosenButNotSubmitted && (
        <div className="srp-pending" role="status">
          <strong>
            Đã chọn NCC nhưng chưa tạo yêu cầu mới.
          </strong>

          <button
            type="button"
            disabled={busy}
            onClick={() => void retrySubmit()}
          >
            Thử gửi lại
          </button>
        </div>
      )}

      {!chosenButNotSubmitted && !completed && (
        <details className="srp-retry">
          <summary>
            Đã chọn NCC ở lần trước nhưng chưa gửi lại?
          </summary>

          <p>
            Chỉ dùng tùy chọn này nếu Backend đã lưu
            lựa chọn NCC hợp lệ.
          </p>

          <button
            type="button"
            disabled={busy}
            onClick={() => void retrySubmit()}
          >
            Gửi lại theo NCC đã chọn
          </button>
        </details>
      )}

      {error && (
        <p className="srp-error" role="alert">
          {error}
        </p>
      )}

      {success && (
        <p className="srp-success" role="status">
          {success}
        </p>
      )}
    </section>
  )
}
