export type SupplierOfferStatus = 'ACTIVE' | 'INACTIVE'

export interface SupplierCatalogItem {
  id: number
  supplier_id: number
  supplier_code: string
  supplier_name: string
  item_id: number
  item_code: string
  item_name: string
  unit_price_vnd_per_kg: string
  max_daily_supply_kg: string | null
  lead_time_hours: number | null
  minimum_order_kg: string | null
  offer_status: SupplierOfferStatus
  updated_at: string
}

export type SupplierRequestStatus = 'WAITING' | 'RESPONDED'
export type SupplierConfirmationStatus = 'PENDING' | 'CONFIRMED' | 'PARTIAL' | 'DECLINED'
export type SupplierLineStatus = 'PENDING' | 'CONFIRMED' | 'PARTIAL' | 'DECLINED'

export interface SupplierDemandSummary {
  demand_code: string
  requested_date: string
  requested_start_time: string | null
  requested_end_time: string | null
  notes: string | null
  outlet_name: string
  outlet_address: string
}

export interface SupplierPromise {
  id: number
  demand_item_id: number
  item_code: string
  item_name: string
  required_weight_kg: string
  item_note: string | null
  promised_weight_kg: string
  confirmed_weight_kg: string
  line_status: SupplierLineStatus
  decline_reason: string
  unit_price_vnd_per_kg_snapshot: string | null
  lead_time_hours_snapshot: number | null
}

export interface SupplierRequest {
  id: number
  request_code: string
  attempt_no: number
  request_status: SupplierRequestStatus
  sent_at: string | null
  responded_at: string | null
  demand: SupplierDemandSummary
  confirmation_status: SupplierConfirmationStatus
  ready_date: string | null
  ready_start_time: string | null
  ready_end_time: string | null
  pickup_address: string | null
  confirmation_note: string
  recorded_at: string | null
  items: SupplierPromise[]
}

export interface SupplierPromiseResponseInput {
  promise_id: number
  confirmed_weight_kg: string
  decline_reason?: string
}

export interface SupplierRequestResponseInput {
  items: SupplierPromiseResponseInput[]
  ready_date?: string | null
  ready_start_time?: string | null
  ready_end_time?: string | null
  pickup_address?: string | null
  confirmation_note?: string
}

export interface SupplierRequestResponse {
  confirmation_status: SupplierConfirmationStatus
  missing_qty: string
  request: SupplierRequest
}

export interface SupplierAvailableItem {
  id: number
  item_code: string
  item_name: string
  cargo_category_id: number
  category_name: string
  weight_unit: string
  item_description: string | null
}

export interface SupplierCargoCategory {
  id: number
  category_code: string
  category_name: string
}

export interface SupplierCatalogCreateInput {
  item_id?: number
  item_name?: string
  cargo_category_id?: number
  weight_unit?: string
  item_description?: string
  unit_price_vnd_per_kg: string
  max_daily_supply_kg?: string | null
  lead_time_hours?: number | null
  minimum_order_kg?: string | null
  offer_status?: SupplierOfferStatus
}

export interface SupplierCatalogUpdateInput {
  unit_price_vnd_per_kg?: string
  max_daily_supply_kg?: string | null
  lead_time_hours?: number | null
  minimum_order_kg?: string | null
  offer_status?: SupplierOfferStatus
}
