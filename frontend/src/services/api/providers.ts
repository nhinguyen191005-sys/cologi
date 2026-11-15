import { apiRequest } from './client'
import type {
  ProviderAvailability,
  ProviderAvailabilityInput,
  ProviderProfile,
  ProviderSupplierCoverage,
  ProviderVehicleOffer,
  ProviderVehicleOfferUpdateInput,
  ProviderVehicleType,
  ProviderVehicleOfferCreateInput,
} from '../../types/provider'

export function getProviderProfile(): Promise<ProviderProfile> {
  return apiRequest<ProviderProfile>('/providers/me/')
}

export function updateProviderProfile(
  payload: Pick<ProviderProfile, 'service_region'>,
): Promise<ProviderProfile> {
  return apiRequest<ProviderProfile>('/providers/me/', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function listProviderSupplierCoverages(): Promise<ProviderSupplierCoverage[]> {
  return apiRequest<ProviderSupplierCoverage[]>('/providers/me/supplier-coverages/')
}

export function listProviderVehicleOffers(): Promise<ProviderVehicleOffer[]> {
  return apiRequest<ProviderVehicleOffer[]>('/providers/me/vehicle-offers/')
}

export function listProviderVehicleTypes(): Promise<ProviderVehicleType[]> {
  return apiRequest<ProviderVehicleType[]>('/providers/vehicle-types/')
}

export function createProviderVehicleOffer(
  payload: ProviderVehicleOfferCreateInput,
): Promise<ProviderVehicleOffer> {
  return apiRequest<ProviderVehicleOffer>('/providers/me/vehicle-offers/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateProviderVehicleOffer(
  id: number,
  payload: ProviderVehicleOfferUpdateInput,
): Promise<ProviderVehicleOffer> {
  return apiRequest<ProviderVehicleOffer>(`/providers/me/vehicle-offers/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function listProviderAvailability(): Promise<ProviderAvailability[]> {
  return apiRequest<ProviderAvailability[]>('/providers/me/availability/')
}

export function createProviderAvailability(
  payload: ProviderAvailabilityInput & { provider_vehicle_offer_id: number },
): Promise<ProviderAvailability> {
  return apiRequest<ProviderAvailability>('/providers/me/availability/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateProviderAvailability(
  id: number,
  payload: ProviderAvailabilityInput,
): Promise<ProviderAvailability> {
  return apiRequest<ProviderAvailability>(`/providers/me/availability/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

