export type DemandStatus =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'PLANNING'
  | 'PLANNED'
  | 'CANCELLED'

export interface DemandItem {
  id: number
  item_id: number
  item_code: string
  item_name: string
  required_weight_kg: string
  unit_of_measure: string
  item_note: string | null
}

export interface DeliveryDemand {
  id: number
  demand_code: string
  supplier_id: number
  supplier_code: string
  supplier_name: string
  outlet_id: number
  outlet_code: string
  outlet_name: string
  cargo_category_id: number
  cargo_category_code: string
  cargo_category_name: string
  quantity_kg: string
  requested_date: string
  requested_start_time: string | null
  requested_end_time: string | null
  status: DemandStatus
  notes: string | null
  created_by_id: number
  created_at: string
  updated_at: string
  items: DemandItem[]
}

export interface DemandItemInput {
  item_id: number
  required_weight_kg: string
  unit_of_measure?: string
  item_note?: string | null
}

export interface DemandCreateInput {
  supplier_id: number
  outlet_id: number
  requested_date: string
  requested_start_time?: string | null
  requested_end_time?: string | null
  notes?: string | null
  items: DemandItemInput[]
}

export type DemandUpdateInput = Partial<
  Omit<DemandCreateInput, 'outlet_id'>
>

export interface DemandStatusResponse {
  id: number
  demand_code: string
  status: DemandStatus
  updated_at: string
}

export interface DemandSubmitResponse {
  submission_status: string
  supplier_request_id: number
}

export interface DemandCancelResponse {
  cancellation_status: string
  demand_id: number
  demand_code: string
}

export interface Supplier {
  id: number
  supplier_code: string
  supplier_name: string
  contact_name: string | null
  phone: string | null
  email: string | null
  address: string | null
  is_active: boolean
}

export interface Outlet {
  id: number
  outlet_code: string
  outlet_name: string
  address: string | null
  contact_name: string | null
  phone: string | null
  is_active: boolean
}

export interface CargoCategory {
  id: number
  category_code: string
  category_name: string
  description: string | null
  is_active: boolean
}

export interface Item {
  id: number
  item_code: string
  item_name: string
  cargo_category_id: number
  category_code: string
  category_name: string
  weight_unit: string
  item_description: string | null
  is_active: boolean
}
