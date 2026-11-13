export type BusinessRole =
  | 'PURCHASING_STAFF'
  | 'SUPPLIER'
  | 'TRANSPORT_PROVIDER'
  | 'MANAGER'

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  token: string
  user: {
    id: number
    email: string
    full_name: string
  }
}

export interface ExternalAccess {
  actor_type: string
  supplier_id: number | null
  provider_id: number | null
}

export interface CurrentUser {
  id: number
  email: string
  full_name: string
  roles: BusinessRole[]
  external_accesses: ExternalAccess[]
}
