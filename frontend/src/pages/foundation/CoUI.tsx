
import {
  useEffect,
  useId,
  useRef,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SVGProps,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react'

import type {
  CoToastMessage,
  CoToastTone,
} from './useCoToast'

import './CoUI.css'

/* ========================================
   COLOGI LOCAL ICON SYSTEM
   Không phụ thuộc components/ui
======================================== */

type IconName =
  | 'clipboard'
  | 'check'
  | 'alert'
  | 'info'
  | 'close'
  | 'shield'
  | 'search'
  | 'refresh'
  | 'box'
  | 'truck'
  | 'user'
  | 'clock'
  | 'layers'
  | 'mail'
  | 'arrow-right'
  | 'calendar'

const iconPaths: Record<IconName, ReactNode> = {
  clipboard: (
    <>
      <rect x="5" y="5" width="14" height="17" rx="2" />
      <path d="M9 5V3h6v2M9 12h6m-6 4h6" />
    </>
  ),

  check: <path d="m4 12 5 5L20 6" />,

  alert: (
    <>
      <path d="m12 3 10 18H2z" />
      <path d="M12 9v5m0 3h.01" />
    </>
  ),

  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v6M12 7h.01" />
    </>
  ),

  close: <path d="M5 5l14 14M19 5 5 19" />,

  shield: (
    <>
      <path d="m12 2 9 4v6c0 5-3.6 8-9 10-5.4-2-9-5-9-10V6z" />
      <path d="m8.5 12 2.3 2.3 4.8-4.8" />
    </>
  ),

  search: (
    <>
      <circle cx="10.7" cy="10.7" r="7" />
      <path d="m16 16 5 5" />
    </>
  ),

  refresh: (
    <>
      <path d="M20 11a8 8 0 0 0-14-5L3 9m0-6v6h6" />
      <path d="M4 13a8 8 0 0 0 14 5l3-3m0 6v-6h-6" />
    </>
  ),

  box: (
    <>
      <path d="m12 3 9 5-9 5-9-5 9-5Z" />
      <path d="M3 8v8l9 5 9-5V8" />
      <path d="M12 13v8" />
    </>
  ),

  truck: (
    <>
      <path d="M3 6h11v11H3zM14 10h4l3 4v3h-7" />
      <circle cx="7" cy="18" r="2" />
      <circle cx="18" cy="18" r="2" />
    </>
  ),

  user: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 3.6-6 8-6s8 2 8 6" />
    </>
  ),

  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),

  layers: (
    <>
      <path d="m12 3 9 5-9 5-9-5 9-5Z" />
      <path d="m3 12 9 5 9-5M3 16l9 5 9-5" />
    </>
  ),

  mail: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3 7 9 6 9-6" />
    </>
  ),

  'arrow-right': (
    <path d="M4 12h16m-6-6 6 6-6 6" />
  ),

  calendar: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M7 3v4M17 3v4M3 10h18" />
    </>
  ),
}

function Icon({
  name,
  size = 20,
  ...props
}: SVGProps<SVGSVGElement> & {
  name: IconName
  size?: number
}) {
  return (
    <svg
      {...props}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {iconPaths[name]}
    </svg>
  )
}

/* ========================================
   LOCAL BASE BUTTON
======================================== */

function BaseButton({
  variant = 'primary',
  className = '',
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost'
}) {
  return (
    <button
      {...props}
      className={
        `cof-base-button cof-base-button--${variant} ${className}`.trim()
      }
    >
      {children}
    </button>
  )
}

/* ========================================
   CARD
======================================== */

function CoCard({
  children,
  className = '',
  ...props
}: HTMLAttributes<HTMLElement>) {
  return (
    <section
      {...props}
      className={`cof-card ${className}`.trim()}
    >
      {children}
    </section>
  )
}

/* ========================================
   AVATAR
======================================== */

function CoAvatar({
  name,
  size = 'md',
}: {
  name: string
  size?: 'md' | 'lg'
}) {
  const initials =
    name
      .trim()
      .split(/\s+/)
      .slice(-2)
      .map((part) =>
        part.charAt(0).toUpperCase()
      )
      .join('') || 'C'

  return (
    <span
      className={`cof-avatar cof-avatar--${size}`}
      aria-label={name}
    >
      {initials}
    </span>
  )
}

/* ========================================
   SKELETON
======================================== */

function CoSkeleton({
  className = '',
}: {
  className?: string
}) {
  return (
    <span
      className={`cof-skeleton ${className}`}
      aria-hidden="true"
    />
  )
}

/* PUBLIC EXPORTS */

export {
  CoAvatar,
  CoCard,
  CoSkeleton,
}
/* ========================================
   BUTTON
======================================== */

export type CoButtonVariant =
  | 'primary'
  | 'secondary'
  | 'ghost'
  | 'danger'

export function CoButton({
  children,
  variant = 'primary',
  icon,
  busy = false,
  disabled,
  className = '',
  type = 'button',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode
  variant?: CoButtonVariant
  icon?: IconName
  busy?: boolean
}) {
  return (
    <BaseButton
      {...props}
      type={type}
      variant={
        variant === 'danger'
          ? 'secondary'
          : variant
      }
      className={
        `cof-button cof-button--${variant} ${className}`.trim()
      }
      disabled={disabled || busy}
      aria-busy={busy || undefined}
    >
      {busy ? (
        <span
          className="cof-spinner"
          aria-hidden="true"
        />
      ) : icon ? (
        <Icon name={icon} size={17} />
      ) : null}

      {children}
    </BaseButton>
  )
}

/* ========================================
   FORM FIELD SHELL
======================================== */

type FieldMeta = {
  label: string
  hint?: string
  error?: string
  fieldClassName?: string
}

function FieldShell({
  label,
  hint,
  error,
  required,
  fieldId,
  children,
}: FieldMeta & {
  required?: boolean
  fieldId: string
  children: ReactNode
}) {
  return (
    <div
      className={
        `cof-field${error ? ' cof-field--invalid' : ''}`
      }
    >
      <label
        className="cof-field-label"
        htmlFor={fieldId}
      >
        {label}

        {required && (
          <span
            className="cof-required"
            aria-label="bắt buộc"
          >
            {' '}*
          </span>
        )}
      </label>

      {children}

      {error ? (
        <p
          id={`${fieldId}-error`}
          className="cof-field-error"
          role="alert"
        >
          {error}
        </p>
      ) : hint ? (
        <p
          id={`${fieldId}-hint`}
          className="cof-field-hint"
        >
          {hint}
        </p>
      ) : null}
    </div>
  )
}

/* ========================================
   INPUT
======================================== */

export function CoInput({
  label,
  hint,
  error,
  fieldClassName = '',
  leadingIcon,
  id,
  required,
  className = '',
  'aria-describedby': describedBy,
  ...props
}: InputHTMLAttributes<HTMLInputElement> &
  FieldMeta & {
    leadingIcon?: IconName
  }) {
  const generatedId = useId()
  const fieldId = id ?? generatedId

  return (
    <div className={fieldClassName}>
      <FieldShell
        label={label}
        hint={hint}
        error={error}
        fieldId={fieldId}
        required={required}
      >
        <div className="cof-control-wrap">
          {leadingIcon && (
            <Icon
              name={leadingIcon}
              size={18}
              className="cof-control-icon"
            />
          )}

          <input
            {...props}
            id={fieldId}
            required={required}
            className={
              `cof-input ${className}`.trim()
            }
            aria-invalid={
              Boolean(error) || undefined
            }
            aria-describedby={
              [
                describedBy,
                error
                  ? `${fieldId}-error`
                  : hint
                    ? `${fieldId}-hint`
                    : '',
              ]
                .filter(Boolean)
                .join(' ') || undefined
            }
          />
        </div>
      </FieldShell>
    </div>
  )
}

/* ========================================
   SELECT
======================================== */

export function CoSelect({
  label,
  hint,
  error,
  fieldClassName = '',
  id,
  required,
  children,
  className = '',
  'aria-describedby': describedBy,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> &
  FieldMeta) {
  const generatedId = useId()
  const fieldId = id ?? generatedId

  return (
    <div className={fieldClassName}>
      <FieldShell
        label={label}
        hint={hint}
        error={error}
        fieldId={fieldId}
        required={required}
      >
        <select
          {...props}
          id={fieldId}
          required={required}
          className={
            `cof-select ${className}`.trim()
          }
          aria-invalid={
            Boolean(error) || undefined
          }
          aria-describedby={
            [
              describedBy,
              error
                ? `${fieldId}-error`
                : hint
                  ? `${fieldId}-hint`
                  : '',
            ]
              .filter(Boolean)
              .join(' ') || undefined
          }
        >
          {children}
        </select>
      </FieldShell>
    </div>
  )
}

/* ========================================
   TEXTAREA
======================================== */

export function CoTextarea({
  label,
  hint,
  error,
  fieldClassName = '',
  id,
  required,
  className = '',
  'aria-describedby': describedBy,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> &
  FieldMeta) {
  const generatedId = useId()
  const fieldId = id ?? generatedId

  return (
    <div className={fieldClassName}>
      <FieldShell
        label={label}
        hint={hint}
        error={error}
        fieldId={fieldId}
        required={required}
      >
        <textarea
          {...props}
          id={fieldId}
          required={required}
          className={
            `cof-textarea ${className}`.trim()
          }
          aria-invalid={
            Boolean(error) || undefined
          }
          aria-describedby={
            [
              describedBy,
              error
                ? `${fieldId}-error`
                : hint
                  ? `${fieldId}-hint`
                  : '',
            ]
              .filter(Boolean)
              .join(' ') || undefined
          }
        />
      </FieldShell>
    </div>
  )
}

/* ========================================
   BADGE
======================================== */

export type CoBadgeTone =
  | 'neutral'
  | 'success'
  | 'warning'
  | 'danger'
  | 'info'

export function CoBadge({
  children,
  tone = 'neutral',
}: {
  children: ReactNode
  tone?: CoBadgeTone
}) {
  return (
    <span
      className={
        `cof-badge cof-badge--${tone}`
      }
    >
      {children}
    </span>
  )
}

/* ========================================
   STATUS BADGE
======================================== */

const statusInfo: Record<
  string,
  {
    label: string
    tone: CoBadgeTone
  }
> = {
  DRAFT: {
    label: 'Bản nháp',
    tone: 'neutral',
  },

  SUBMITTED: {
    label: 'Đã gửi',
    tone: 'info',
  },

  PLANNING: {
    label: 'Đang lập kế hoạch',
    tone: 'warning',
  },

  PLANNED: {
    label: 'Đã lập kế hoạch',
    tone: 'success',
  },

  CANCELLED: {
    label: 'Đã hủy',
    tone: 'danger',
  },

  WAITING: {
    label: 'Chờ phản hồi',
    tone: 'warning',
  },

  RESPONDED: {
    label: 'Đã phản hồi',
    tone: 'success',
  },

  PARTIAL: {
    label: 'Xác nhận một phần',
    tone: 'warning',
  },

  CONFIRMED: {
    label: 'Đã xác nhận',
    tone: 'success',
  },

  ACTIVE: {
    label: 'Đang hoạt động',
    tone: 'success',
  },

  INACTIVE: {
    label: 'Không hoạt động',
    tone: 'neutral',
  },

  AVAILABLE: {
    label: 'Khả dụng',
    tone: 'success',
  },

  UNAVAILABLE: {
    label: 'Không khả dụng',
    tone: 'danger',
  },
}

export function CoStatusBadge({
  status,
}: {
  status: string
}) {
  const value = statusInfo[status] ?? {
    label: status,
    tone: 'neutral' as const,
  }

  return (
    <CoBadge tone={value.tone}>
      {value.label}
    </CoBadge>
  )
}

/* ========================================
   LOADING STATE
======================================== */

export function CoLoading({
  label = 'Đang tải dữ liệu...',
}: {
  label?: string
}) {
  return (
    <div
      className="cof-state"
      role="status"
      aria-live="polite"
    >
      <span
        className="cof-spinner cof-spinner--large"
        aria-hidden="true"
      />

      <p>{label}</p>
    </div>
  )
}

/* ========================================
   EMPTY STATE
======================================== */

export function CoEmpty({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="cof-state cof-state--empty">
      <span className="cof-state-symbol">
        <Icon name="clipboard" size={23} />
      </span>

      <strong>{title}</strong>

      {description && (
        <p>{description}</p>
      )}

      {action && (
        <div className="cof-state-action">
          {action}
        </div>
      )}
    </div>
  )
}

/* ========================================
   ERROR STATE
======================================== */

export function CoError({
  message,
  onRetry,
}: {
  message: string
  onRetry?: () => void
}) {
  return (
    <div
      className="cof-error"
      role="alert"
    >
      <Icon name="alert" size={20} />

      <div>
        <strong>
          Không thể hoàn tất thao tác
        </strong>

        <p>{message}</p>
      </div>

      {onRetry && (
        <CoButton
          variant="secondary"
          onClick={onRetry}
        >
          Thử lại
        </CoButton>
      )}
    </div>
  )
}

/* ========================================
   CONFIRM DIALOG
======================================== */

export function CoConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Xác nhận',
  cancelLabel = 'Đóng',
  dangerous = false,
  busy = false,
  onClose,
  onConfirm,
}: {
  open: boolean
  title: string
  description: string
  confirmLabel?: string
  cancelLabel?: string
  dangerous?: boolean
  busy?: boolean
  onClose: () => void
  onConfirm: () => void | Promise<void>
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const descriptionId = useId()

  useEffect(() => {
    const element = ref.current

    if (!element) return

    if (open && !element.open) {
      element.showModal()
    }

    if (!open && element.open) {
      element.close()
    }

    return () => {
      if (element.open) element.close()
    }
  }, [open])

  return (
    <dialog
      ref={ref}
      className="cof-dialog"
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      onCancel={(event) => {
        event.preventDefault()
        if (!busy) onClose()
      }}
    >
      <div className="cof-dialog-mark">
        <Icon
          name={
            dangerous ? 'alert' : 'shield'
          }
          size={23}
        />
      </div>

      <h2 id={titleId}>
        {title}
      </h2>

      <p id={descriptionId}>
        {description}
      </p>

      <div className="cof-dialog-actions">
        <CoButton
          variant="secondary"
          disabled={busy}
          onClick={onClose}
        >
          {cancelLabel}
        </CoButton>

        <CoButton
          variant={
            dangerous
              ? 'danger'
              : 'primary'
          }
          busy={busy}
          onClick={() => {
            void onConfirm()
          }}
        >
          {confirmLabel}
        </CoButton>
      </div>
    </dialog>
  )
}

/* ========================================
   TOAST
======================================== */

const toastIcons: Record<
  CoToastTone,
  IconName
> = {
  success: 'check',
  error: 'alert',
  info: 'info',
  warning: 'alert',
}

function CoToastRow({
  entry,
  onDismiss,
}: {
  entry: CoToastMessage
  onDismiss: (id: number) => void
}) {
  useEffect(() => {
    if (entry.durationMs <= 0) return

    const timer = window.setTimeout(
      () => onDismiss(entry.id),
      entry.durationMs,
    )

    return () => {
      window.clearTimeout(timer)
    }
  }, [
    entry.durationMs,
    entry.id,
    onDismiss,
  ])

  return (
    <div
      className={
        `cof-toast cof-toast--${entry.tone}`
      }
      role={
        entry.tone === 'error'
          ? 'alert'
          : 'status'
      }
    >
      <Icon
        name={toastIcons[entry.tone]}
        size={19}
      />

      <span>{entry.message}</span>

      <button
        type="button"
        onClick={() => onDismiss(entry.id)}
        aria-label="Đóng thông báo"
      >
        <Icon name="close" size={17} />
      </button>
    </div>
  )
}

export function CoToastViewport({
  toasts,
  onDismiss,
}: {
  toasts: CoToastMessage[]
  onDismiss: (id: number) => void
}) {
  if (!toasts.length) return null

  return (
    <div
      className="cof-toast-viewport"
      aria-label="Thông báo hệ thống"
    >
      {toasts.map((entry) => (
        <CoToastRow
          key={entry.id}
          entry={entry}
          onDismiss={onDismiss}
        />
      ))}
    </div>
  )
}
