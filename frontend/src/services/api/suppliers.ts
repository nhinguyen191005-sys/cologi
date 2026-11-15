import { apiRequest } from './client'
import type {
  SupplierAvailableItem,
  SupplierCargoCategory,
  SupplierCatalogCreateInput,
  SupplierCatalogItem,
  SupplierCatalogUpdateInput,
  SupplierRequest,
  SupplierRequestResponse,
  SupplierRequestResponseInput,
} from '../../types/supplier'

export function listSupplierCatalog(): Promise<SupplierCatalogItem[]> {
  return apiRequest<SupplierCatalogItem[]>('/suppliers/me/items')
}

export function listSupplierOffers(): Promise<SupplierCatalogItem[]> {
  return apiRequest<SupplierCatalogItem[]>('/masterdata/supplier-items/')
}

export function listSupplierAvailableItems(): Promise<SupplierAvailableItem[]> {
  return apiRequest<SupplierAvailableItem[]>('/suppliers/me/available-items')
}

export function listSupplierCargoCategories(): Promise<SupplierCargoCategory[]> {
  return apiRequest<SupplierCargoCategory[]>('/suppliers/me/cargo-categories')
}

export function createSupplierCatalogItem(
  payload: SupplierCatalogCreateInput,
): Promise<SupplierCatalogItem> {
  return apiRequest<SupplierCatalogItem>('/suppliers/me/items', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateSupplierCatalogItem(
  id: number,
  payload: SupplierCatalogUpdateInput,
): Promise<SupplierCatalogItem> {
  return apiRequest<SupplierCatalogItem>(`/suppliers/me/items/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function listSupplierRequests(): Promise<SupplierRequest[]> {
  return apiRequest<SupplierRequest[]>('/suppliers/me/requests')
}

export function respondToSupplierRequest(
  id: number,
  payload: SupplierRequestResponseInput,
): Promise<SupplierRequestResponse> {
  return apiRequest<SupplierRequestResponse>(`/supply-requests/${id}/confirm`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
