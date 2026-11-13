import type {
  CurrentUser,
  LoginRequest,
  LoginResponse,
} from '../../types/auth'
import { apiRequest, clearToken, setToken } from './client'

export async function login(
  credentials: LoginRequest,
): Promise<CurrentUser> {
  const result = await apiRequest<LoginResponse>('/auth/login/', {
    method: 'POST',
    body: JSON.stringify(credentials),
  })

  setToken(result.token)

  try {
    return await getCurrentUser()
  } catch (error) {
    clearToken()
    throw error
  }
}

export function getCurrentUser(): Promise<CurrentUser> {
  return apiRequest<CurrentUser>('/auth/me/')
}

export async function logout(): Promise<void> {
  try {
    await apiRequest<void>('/auth/logout/', {
      method: 'POST',
    })
  } finally {
    clearToken()
  }
}
