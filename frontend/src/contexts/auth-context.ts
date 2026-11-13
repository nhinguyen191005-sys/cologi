import { createContext } from 'react'
import type { CurrentUser, LoginRequest } from '../types/auth'

export interface AuthContextValue {
  user: CurrentUser | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  signIn: (credentials: LoginRequest) => Promise<void>
  signOut: () => Promise<void>
  clearAuthError: () => void
}

export const AuthContext = createContext<AuthContextValue | undefined>(
  undefined,
)
