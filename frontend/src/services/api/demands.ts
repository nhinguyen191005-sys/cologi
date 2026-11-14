import { apiRequest } from './client'
import type {
  CargoCategory,
  DeliveryDemand,
  DemandCancelResponse,
  DemandCreateInput,
  DemandStatusResponse,
  DemandSubmitResponse,
  DemandUpdateInput,
  Item,
  Outlet,
  Supplier,
} from '../../types/demand'

export function listDemands(): Promise<DeliveryDemand[]> {
  return apiRequest<DeliveryDemand[]>('/demands/')
}

export function getDemand(id: number): Promise<DeliveryDemand> {
  return apiRequest<DeliveryDemand>(`/demands/${id}/`)
}

export function createDemand(
  payload: DemandCreateInput,
): Promise<DeliveryDemand> {
  return apiRequest<DeliveryDemand>('/demands/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateDemand(
  id: number,
  payload: DemandUpdateInput,
): Promise<DeliveryDemand> {
  return apiRequest<DeliveryDemand>(`/demands/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function getDemandStatus(
  id: number,
): Promise<DemandStatusResponse> {
  return apiRequest<DemandStatusResponse>(`/demands/${id}/status/`)
}

export function submitDemand(
  id: number,
): Promise<DemandSubmitResponse> {
  return apiRequest<DemandSubmitResponse>(`/demands/${id}/submit`, {
    method: 'POST',
  })
}

export function cancelDemand(
  id: number,
): Promise<DemandCancelResponse> {
  return apiRequest<DemandCancelResponse>(`/demands/${id}/cancel`, {
    method: 'POST',
  })
}

export function listSuppliers(): Promise<Supplier[]> {
  return apiRequest<Supplier[]>('/masterdata/suppliers/')
}

export function listOutlets(): Promise<Outlet[]> {
  return apiRequest<Outlet[]>('/masterdata/outlets/')
}

export function listCargoCategories(): Promise<CargoCategory[]> {
  return apiRequest<CargoCategory[]>('/masterdata/cargo-categories/')
}

export function listItems(): Promise<Item[]> {
  return apiRequest<Item[]>('/masterdata/items/')
}
