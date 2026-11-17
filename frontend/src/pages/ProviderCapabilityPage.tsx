
import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  getProviderProfile,
  listProviderVehicleOffers,
  listProviderAvailability,
  listProviderSupplierCoverages,
  listProviderVehicleTypes,
} from '../services/api/providers'

import type {
  ProviderProfile,
  ProviderVehicleOffer,
  ProviderAvailability,
  ProviderSupplierCoverage,
  ProviderVehicleType,
} from '../types/provider'

import ProviderCapacityCalendar from '../components/ProviderCapacityCalendar'

import './ProviderCapabilityPage.css'

const dateFormatter = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Ho_Chi_Minh',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})

function todayVietnam() {
  const parts = dateFormatter.formatToParts(new Date())

  const get = (type: string) =>
    parts.find((part) => part.type === type)?.value ?? ''

  return `${get('year')}-${get('month')}-${get('day')}`
}

export default function ProviderCapabilityPage() {
  const [profile, setProfile] =
    useState<ProviderProfile | null>(null)

  const [offers, setOffers] =
    useState<ProviderVehicleOffer[]>([])

  const [slots, setSlots] =
    useState<ProviderAvailability[]>([])

  const [coverages, setCoverages] =
    useState<ProviderSupplierCoverage[]>([])

  const [vehicleTypes, setVehicleTypes] =
    useState<ProviderVehicleType[]>([])

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadData = useCallback(async () => {
    setLoading(true)
    setError('')

    try {
      const [provider, vehicleOffers, availability, supplierCoverages, types] =
        await Promise.all([
          getProviderProfile(),
          listProviderVehicleOffers(),
          listProviderAvailability(),
          listProviderSupplierCoverages(),
          listProviderVehicleTypes(),
        ])

      setProfile(provider)
      setOffers(vehicleOffers)
      setSlots(availability)
      setCoverages(supplierCoverages)
      setVehicleTypes(types)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Không thể tải dữ liệu năng lực vận chuyển.'
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadData()
  }, [loadData])

  const today = todayVietnam()

  const stats = useMemo(() => {
    const activeOffers = offers.filter(
      (offer) => offer.is_active
    )

    const upcomingAvailableSlots = slots.filter(
      (slot) =>
        slot.service_date >= today &&
        slot.availability_status === 'AVAILABLE' &&
        slot.available_vehicle_count > 0
    )

    const activeCoverages = coverages.filter(
      (coverage) =>
        coverage.coverage_status === 'ACTIVE' &&
        coverage.can_pickup
    )

    return {
      activeOffers: activeOffers.length,

      declaredVehicles: activeOffers.reduce(
        (sum, offer) =>
          sum + offer.available_vehicle_count,
        0
      ),

      availableSlots: upcomingAvailableSlots.length,

      suppliers: activeCoverages.length,
    }
  }, [offers, slots, coverages, today])

  const readiness = useMemo(() => {
    const activeOffers = offers.filter(
      (offer) => offer.is_active
    )

    const activeOfferIds = new Set(
      activeOffers.map((offer) => offer.id)
    )

    const validOffers = activeOffers.filter(
      (offer) =>
        offer.available_vehicle_count > 0
    )

    const availableSlots = slots.filter(
      (slot) =>
        slot.service_date >= today &&
        slot.availability_status === 'AVAILABLE' &&
        slot.available_vehicle_count > 0 &&
        activeOfferIds.has(
          slot.provider_vehicle_offer_id
        )
    )

    const activeCoverages = coverages.filter(
      (coverage) =>
        coverage.coverage_status === 'ACTIVE' &&
        coverage.can_pickup
    )

    const quotedOffers = activeOffers.filter(
      (offer) =>
        offer.fixed_quote_vnd != null ||
        offer.estimated_cost_per_km_vnd != null
    )

    const checks = [
      {
        id: 'vehicle',
        label: 'Cấu hình phương tiện',
        description:
          validOffers.length > 0
            ? `${validOffers.length} cấu hình xe đang hoạt động và có số lượng hợp lệ`
            : 'Chưa có cấu hình xe hoạt động với số lượng lớn hơn 0',
        ready: validOffers.length > 0,
      },
      {
        id: 'availability',
        label: 'Lịch khả dụng',
        description:
          availableSlots.length > 0
            ? `${availableSlots.length} khung lịch sắp tới có liên kết cấu hình xe hoạt động`
            : 'Chưa có khung lịch khả dụng gắn với cấu hình xe hoạt động',
        ready: availableSlots.length > 0,
      },
      {
        id: 'coverage',
        label: 'Phạm vi lấy hàng',
        description:
          activeCoverages.length > 0
            ? `${activeCoverages.length} nhà cung cấp trong phạm vi có thể lấy hàng`
            : 'Chưa có nhà cung cấp có thể lấy hàng trong phạm vi hoạt động',
        ready: activeCoverages.length > 0,
      },
      {
        id: 'quote',
        label: 'Dữ liệu báo giá',
        description:
          quotedOffers.length > 0
            ? `${quotedOffers.length} cấu hình xe đang hoạt động có khai báo chi phí`
            : 'Chưa có cấu hình xe hoạt động có dữ liệu báo giá',
        ready: quotedOffers.length > 0,
      },
    ]

    return {
      checks,
      passed: checks.filter((check) => check.ready).length,
    }
  }, [offers, slots, coverages, today])


  return (
    <main className="pcw-page">
      {/* HEADER */}
      <header className="pcw-header">
        <div>
          <p className="pcw-eyebrow">
            TRANSPORT PROVIDER WORKSPACE
          </p>

          <h1>Tổng quan năng lực vận chuyển</h1>

          <p>
            Theo dõi nguồn lực đã khai báo,
            lịch khả dụng và điều kiện phục vụ.
          </p>

          {profile && (
            <span className="pcw-provider-name">
              {profile.provider_name}
              {' · '}
              {profile.provider_code}
            </span>
          )}
        </div>

        <button
          type="button"
          className="pcw-refresh"
          onClick={() => void loadData()}
          disabled={loading}
        >
          {loading ? 'Đang tải...' : '↻ Làm mới'}
        </button>
      </header>

      {/* ERROR */}
      {error && (
        <div className="pcw-error" role="alert">
          <strong>Không thể tải dữ liệu</strong>
          <p>{error}</p>

          <button
            type="button"
            onClick={() => void loadData()}
          >
            Thử lại
          </button>
        </div>
      )}

      {loading ? (
        <div className="pcw-loading">
          Đang đồng bộ dữ liệu năng lực vận chuyển...
        </div>
      ) : error ? null : (
        <>
          {/* SUMMARY */}
          <section
            className="pcw-stats"
            aria-label="Tổng quan năng lực vận chuyển"
          >
            <article className="pcw-stat pcw-blue">
              <span>CẤU HÌNH XE HOẠT ĐỘNG</span>

              <strong>
                {stats.activeOffers}
              </strong>

              <small>
                {stats.declaredVehicles} xe theo cấu hình
              </small>
            </article>

            <article className="pcw-stat pcw-green">
              <span>KHUNG LỊCH KHẢ DỤNG</span>

              <strong>
                {stats.availableSlots}
              </strong>

              <small>
                Khung lịch từ hôm nay
              </small>
            </article>

            
<article className="pcw-stat pcw-gold pcw-supplier-stat">
  <span>NCC TRONG PHẠM VI PHỤC VỤ</span>

  <div className="pcw-supplier-total">
    <strong>{stats.suppliers}</strong>
    <span>/ {coverages.length} NCC đã khai báo</span>
  </div>

  <div className="pcw-supplier-breakdown">
    <div>
      <span className="pcw-supplier-dot is-active" />
      <span>
        {stats.suppliers} có thể lấy hàng
      </span>
    </div>

    <div>
      <span className="pcw-supplier-dot is-inactive" />
      <span>
        {coverages.length - stats.suppliers} không khả dụng
      </span>
    </div>
  </div>
</article>

          </section>


{/* MỨC ĐỘ SẴN SÀNG LẬP KẾ HOẠCH */}
<section className="pcw-section pcw-readiness-compact">
  <div className="pcw-section-heading">
    <div>
      <p className="pcw-section-eyebrow">
        01 · KIỂM TRA NĂNG LỰC
      </p>

      <h2>Mức độ sẵn sàng lập kế hoạch</h2>

      <p>
        Kiểm tra thông tin cần thiết để hỗ trợ
        lập kế hoạch vận chuyển.
      </p>
    </div>

    <span className="pcw-readiness-count">
      {readiness.passed}/{readiness.checks.length}
      {' '}đã khai báo
    </span>
  </div>

  <div className="pcw-compact-checks">
    {readiness.checks.map((check) => (
      <div
        key={check.id}
        className={`pcw-compact-check ${
          check.ready ? 'is-ready' : 'is-warning'
        }`}
      >
        <span className="pcw-compact-icon">
          {check.ready ? '✓' : '!'}
        </span>

        <span className="pcw-compact-label">
          {check.label}
        </span>

        <span className="pcw-compact-status">
          {check.ready ? 'Đã khai báo' : 'Cần bổ sung'}
        </span>
      </div>
    ))}
  </div>

  <p className="pcw-compact-note">
    Trạng thái dựa trên thông tin đã khai báo.
    Khả năng thực hiện chuyến sẽ được kiểm tra
    khi lập phương án vận chuyển.
  </p>
</section>


          {/* CALENDAR */}
          <ProviderCapacityCalendar
            slots={slots}
            offers={offers}
            vehicleTypes={vehicleTypes}
          />

          
        </>
      )}
    </main>
  )
}
