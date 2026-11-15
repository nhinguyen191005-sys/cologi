export type ProviderFuelType = 'ELECTRIC' | 'GASOLINE' | 'DIESEL'

export type ProviderCoverageStatus = 'ACTIVE' | 'INACTIVE'

export type ProviderAvailabilityStatus = 'AVAILABLE' | 'UNAVAILABLE'

export interface ProviderProfile {
  id: number
  provider_code: string
  provider_name: string
  provider_type: string
  service_region: string
  contact_email: string
  is_active: boolean
}

export interface ProviderVehicleOffer {
  id: number
  provider_id: number
  vehicle_type_id: number
  available_vehicle_count: number
  fuel_type: ProviderFuelType
  operating_start_time: string | null
  operating_end_time: string | null
  fixed_quote_vnd: string | null
  estimated_cost_per_km_vnd: string | null
  is_active: boolean
  vehicle_note: string
  created_at: string
  updated_at: string
}

export interface ProviderVehicleOfferUpdateInput {
  available_vehicle_count?: number
  fuel_type?: ProviderFuelType
  operating_start_time?: string | null
  operating_end_time?: string | null
  fixed_quote_vnd?: string | null
  estimated_cost_per_km_vnd?: string | null
  is_active?: boolean
  vehicle_note?: string
}

export interface ProviderAvailability {
  id: number
  provider_vehicle_offer_id: number
  service_date: string
  available_vehicle_count: number
  start_time: string
  end_time: string
  availability_status: ProviderAvailabilityStatus
  source_mode: string
  created_at: string
  updated_at: string
}

export interface ProviderAvailabilityInput {
  service_date: string
  start_time: string
  end_time: string
  available_vehicle_count: number
  availability_status: ProviderAvailabilityStatus
}

export interface ProviderSupplierCoverage {
  id: number
  provider_id: number
  supplier_id: number
  coverage_status: ProviderCoverageStatus
  can_pickup: boolean
  service_note: string
  created_at: string
  updated_at: string
}

export interface ProviderVehicleType {
  id: number
  vehicle_code: string
  vehicle_name: string
  capacity_kg: string
}

export interface ProviderVehicleTypeCreateInput {
  vehicle_name: string
  capacity_kg: string
  description?: string | null
}

export interface ProviderVehicleOfferCreateInput {
  vehicle_type_id?: number
  new_vehicle_type?: ProviderVehicleTypeCreateInput
  available_vehicle_count: number
  fuel_type: ProviderFuelType
  operating_start_time?: string | null
  operating_end_time?: string | null
  fixed_quote_vnd?: string | null
  estimated_cost_per_km_vnd?: string | null
  is_active?: boolean
  vehicle_note?: string
}