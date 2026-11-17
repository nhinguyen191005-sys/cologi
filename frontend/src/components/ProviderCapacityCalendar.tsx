
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import type {
  ProviderAvailability,
  ProviderVehicleOffer,
  ProviderVehicleType,
} from '../types/provider'
import './ProviderCapacityCalendar.css'

type Props = {
  slots: ProviderAvailability[]
  offers: ProviderVehicleOffer[]
  vehicleTypes: ProviderVehicleType[]
}

type CalendarMode = 'month' | 'week'

const weekdays = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']

function toKey(date: Date): string {
  return [
    date.getUTCFullYear(),
    String(date.getUTCMonth() + 1).padStart(2, '0'),
    String(date.getUTCDate()).padStart(2, '0'),
  ].join('-')
}

function fromKey(key: string): Date {
  const [y, m, d] = key.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d))
}

function addDays(date: Date, days: number): Date {
  const next = new Date(date)
  next.setUTCDate(next.getUTCDate() + days)
  return next
}

function startOfWeek(date: Date): Date {
  const weekday = (date.getUTCDay() + 6) % 7
  return addDays(date, -weekday)
}

function todayVietnam(): string {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Ho_Chi_Minh',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())

  const get = (type: string) =>
    parts.find((p) => p.type === type)?.value ?? ''

  return `${get('year')}-${get('month')}-${get('day')}`
}

function displayDate(key: string) {
  const [year, month, day] = key.split('-')
  return `${day}/${month}/${year}`
}

export default function ProviderCapacityCalendar({
  slots,
  offers,
  vehicleTypes,
}: Props) {
  const [mode, setMode] = useState<CalendarMode>('month')
  const [cursor, setCursor] = useState(() =>
    fromKey(todayVietnam())
  )
  const [selectedDate, setSelectedDate] = useState(() =>
    todayVietnam()
  )

  const today = todayVietnam()

  const offerMap = useMemo(
    () => new Map(offers.map((offer) => [offer.id, offer])),
    [offers]
  )

  const typeMap = useMemo(
    () => new Map(vehicleTypes.map((type) => [type.id, type])),
    [vehicleTypes]
  )

  const slotsByDate = useMemo(() => {
    const map = new Map<string, ProviderAvailability[]>()

    for (const slot of slots) {
      const existing = map.get(slot.service_date) ?? []
      existing.push(slot)
      map.set(slot.service_date, existing)
    }

    for (const entries of map.values()) {
      entries.sort((a, b) =>
        a.start_time.localeCompare(b.start_time)
      )
    }

    return map
  }, [slots])

  const days = useMemo(() => {
    if (mode === 'week') {
      const start = startOfWeek(cursor)
      return Array.from({ length: 7 }, (_, index) =>
        addDays(start, index)
      )
    }

    const firstDay = new Date(Date.UTC(
      cursor.getUTCFullYear(),
      cursor.getUTCMonth(),
      1
    ))

    const start = startOfWeek(firstDay)
    const lastDay = new Date(Date.UTC(
      cursor.getUTCFullYear(),
      cursor.getUTCMonth() + 1,
      0
    ))

    const lastWeekEnd = addDays(
      startOfWeek(lastDay), 6
    )

    const totalDays =
      Math.round(
        (lastWeekEnd.getTime() - start.getTime()) /
        86400000
      ) + 1

    return Array.from({ length: totalDays }, (_, index) =>
      addDays(start, index)
    )
  }, [cursor, mode])

  const selectedSlots = slotsByDate.get(selectedDate) ?? []

  const title = mode === 'month'
    ? `Tháng ${cursor.getUTCMonth() + 1} / ${cursor.getUTCFullYear()}`
    : `${displayDate(toKey(days[0]))} – ${
        displayDate(toKey(days[days.length - 1]))
      }`

  function navigate(direction: number) {
    setCursor((previous) => {
      if (mode === 'week') {
        return addDays(previous, direction * 7)
      }

      const day = Math.min(
        previous.getUTCDate(),
        new Date(Date.UTC(
          previous.getUTCFullYear(),
          previous.getUTCMonth() + direction + 1,
          0
        )).getUTCDate()
      )

      return new Date(Date.UTC(
        previous.getUTCFullYear(),
        previous.getUTCMonth() + direction,
        day
      ))
    })
  }

  function goToday() {
    const key = todayVietnam()
    setCursor(fromKey(key))
    setSelectedDate(key)
  }

  function selectDay(key: string) {
    setSelectedDate(key)
  }

  function getVehicleName(slot: ProviderAvailability) {
    const offer = offerMap.get(slot.provider_vehicle_offer_id)
    const type = offer
      ? typeMap.get(offer.vehicle_type_id)
      : undefined

    return type?.vehicle_name ??
      `Cấu hình xe #${slot.provider_vehicle_offer_id}`
  }

  return (
    <section className="pcal">
      <header className="pcal-heading">
        <div>
          <span className="pcal-eyebrow">
            TRANSPORT CAPACITY CALENDAR
          </span>
          <h2>Lịch năng lực & kế hoạch vận chuyển</h2>
          <p>
            Theo dõi lịch xe đã khai báo. Các khung giờ
            chưa phải chuyến vận chuyển được phê duyệt.
          </p>
        </div>

        <Link to="/provider/availability" className="pcal-link">
          Quản lý lịch →
        </Link>
      </header>

      <div className="pcal-toolbar">
        <div className="pcal-navigation">
          <button
            type="button"
            onClick={() => navigate(-1)}
            aria-label="Kỳ trước"
          >
            ‹
          </button>

          <button
            type="button"
            onClick={() => navigate(1)}
            aria-label="Kỳ sau"
          >
            ›
          </button>

          <button
            type="button"
            className="pcal-today"
            onClick={goToday}
          >
            Hôm nay
          </button>

          <strong>{title}</strong>
        </div>

        <div className="pcal-modes">
          <button
            type="button"
            className={mode === 'month' ? 'active' : ''}
            onClick={() => setMode('month')}
            aria-pressed={mode === 'month'}
          >
            Tháng
          </button>

          <button
            type="button"
            className={mode === 'week' ? 'active' : ''}
            onClick={() => setMode('week')}
            aria-pressed={mode === 'week'}
          >
            Tuần
          </button>
        </div>
      </div>

      <div className="pcal-calendar-scroll">
        <div className="pcal-calendar">
          {weekdays.map((day) => (
            <div className="pcal-weekday" key={day}>
              {day}
            </div>
          ))}

          {days.map((day) => {
            const date = toKey(day)
            const entries = slotsByDate.get(date) ?? []

            const outsideMonth =
              mode === 'month' &&
              day.getUTCMonth() !== cursor.getUTCMonth()

            return (
              <button
                type="button"
                key={date}
                onClick={() => selectDay(date)}
                className={[
                  'pcal-day',
                  date === today ? 'is-today' : '',
                  date === selectedDate ? 'is-selected' : '',
                  outsideMonth ? 'is-outside' : '',
                ].filter(Boolean).join(' ')}
                aria-label={`Xem lịch ngày ${displayDate(date)}`}
                aria-pressed={date === selectedDate}
              >
                <span className="pcal-day-number">
                  {day.getUTCDate()}
                </span>

                <div className="pcal-day-events">
                  {entries.slice(0, 3).map((slot) => {
                    const isAvailable =
                      slot.availability_status === 'AVAILABLE'

                    return (
                      <div
                        key={slot.id}
                        className={`pcal-event ${
                          isAvailable ? 'available' : 'unavailable'
                        }`}
                        title={
                          `${getVehicleName(slot)} · ` +
                          `${slot.start_time.slice(0, 5)}–` +
                          `${slot.end_time.slice(0, 5)}`
                        }
                      >
                        <span>{slot.start_time.slice(0, 5)}</span>
                        <b>
                          {isAvailable
                            ? `${slot.available_vehicle_count} xe`
                            : 'Không có xe'}
                        </b>
                      </div>
                    )
                  })}

                  {entries.length > 3 && (
                    <span className="pcal-more">
                      +{entries.length - 3} khung khác
                    </span>
                  )}
                </div>
              </button>
            )
          })}
        </div>
      </div>

      <div className="pcal-legend">
        <span><i className="available" /> Có xe khả dụng</span>
        <span><i className="unavailable" /> Không khả dụng</span>
      </div>

      <div className="pcal-detail">
        <div className="pcal-detail-heading">
          <div>
            <span>CHI TIẾT NGÀY</span>
            <h3>{displayDate(selectedDate)}</h3>
          </div>
          <strong>{selectedSlots.length} khung lịch</strong>
        </div>

        {selectedSlots.length === 0 ? (
          <div className="pcal-empty">
            Chưa khai báo lịch khả dụng cho ngày này.
          </div>
        ) : (
          <div className="pcal-detail-list">
            {selectedSlots.map((slot) => {
              const available =
                slot.availability_status === 'AVAILABLE'

              const offer = offerMap.get(
                slot.provider_vehicle_offer_id
              )

              const type = offer
                ? typeMap.get(offer.vehicle_type_id)
                : undefined

              return (
                <article className="pcal-detail-row" key={slot.id}>
                  <div>
                    <strong>
                      {slot.start_time.slice(0, 5)}
                      {' – '}
                      {slot.end_time.slice(0, 5)}
                    </strong>
                    <p>{getVehicleName(slot)}</p>
                    {type && (
                      <small>
                        Tải trọng danh định:{' '}
                        {Number(type.capacity_kg)
                          .toLocaleString('vi-VN')} kg/xe
                      </small>
                    )}
                  </div>

                  <div className="pcal-detail-right">
                    <b>{slot.available_vehicle_count} xe</b>
                    <span className={
                      available
                        ? 'pcal-badge available'
                        : 'pcal-badge unavailable'
                    }>
                      {available ? 'Khả dụng' : 'Không khả dụng'}
                    </span>
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </div>
    </section>
  )
}