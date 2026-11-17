
import {
  useCallback,
  useRef,
  useState,
} from 'react'

export type CoToastTone =
  | 'success'
  | 'error'
  | 'info'
  | 'warning'

export interface CoToastMessage {
  id: number
  tone: CoToastTone
  message: string
  durationMs: number
}

export function useCoToast() {
  const [toasts, setToasts] =
    useState<CoToastMessage[]>([])

  const nextId = useRef(1)

  const toast = useCallback(
    (
      tone: CoToastTone,
      message: string,
      durationMs = 4500,
    ) => {
      const id = nextId.current++

      setToasts((current) => [
        ...current,
        { id, tone, message, durationMs },
      ])

      return id
    },
    [],
  )

  const dismissToast = useCallback(
    (id: number) => {
      setToasts((current) =>
        current.filter((entry) => entry.id !== id),
      )
    },
    [],
  )

  const clearToasts = useCallback(
    () => setToasts([]),
    [],
  )

  return {
    toasts,
    toast,
    dismissToast,
    clearToasts,
  }
}
