import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { ApiError, clearToken, getToken } from '../services/api/client'
import {
  getCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
} from '../services/api/auth'
import type { CurrentUser, LoginRequest } from '../types/auth'
import { AuthContext, type AuthContextValue } from './auth-context'

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message
  }

  return 'Đã xảy ra lỗi. Vui lòng thử lại.'
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [isLoading, setIsLoading] = useState(() => getToken() !== null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!getToken()) return

    let active = true

    getCurrentUser()
      .then((currentUser) => {
        if (active) {
          setUser(currentUser)
        }
      })
      .catch((requestError: unknown) => {
        if (!active) return

        if (
          requestError instanceof ApiError &&
          requestError.status === 401
        ) {
          clearToken()
          setUser(null)
          return
        }

        setError(getErrorMessage(requestError))
      })
      .finally(() => {
        if (active) {
          setIsLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [])

  const signIn = useCallback(async (credentials: LoginRequest) => {
    setIsLoading(true)
    setError(null)

    try {
      const currentUser = await loginRequest(credentials)
      setUser(currentUser)
    } catch (requestError: unknown) {
      setError(getErrorMessage(requestError))
      throw requestError
    } finally {
      setIsLoading(false)
    }
  }, [])

  const signOut = useCallback(async () => {
    setError(null)

    try {
      await logoutRequest()
    } catch (requestError: unknown) {
      setError(getErrorMessage(requestError))
      throw requestError
    } finally {
      setUser(null)
    }
  }, [])

  const clearAuthError = useCallback(() => {
    setError(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: user !== null,
      isLoading,
      error,
      signIn,
      signOut,
      clearAuthError,
    }),
    [user, isLoading, error, signIn, signOut, clearAuthError],
  )

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}
