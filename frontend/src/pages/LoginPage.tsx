import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/useAuth'

export default function LoginPage() {
  const { signIn, isAuthenticated, isLoading, error, clearAuthError } =
    useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    clearAuthError()
    setSubmitting(true)

    try {
      await signIn({ email, password })
      navigate('/', { replace: true })
    } catch {
      // The authentication context stores the error for display.
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card">
        <img className="brand-mark" src="/images/logo.png" alt="CoLogi" />
        <p className="eyebrow">COLOGI PLATFORM</p>
        <h1>Đăng nhập</h1>
        <p className="muted">
          Đăng nhập để tiếp tục sử dụng hệ thống CoLogi.
        </p>

        <form onSubmit={handleSubmit} className="auth-form">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            placeholder="name@example.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />

          <label htmlFor="password">Mật khẩu</label>
          <div className="password-input-wrapper">
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              placeholder="Nhập mật khẩu"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
            <button
              type="button"
              className="password-toggle"
              aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
              aria-pressed={showPassword}
              onClick={() => setShowPassword((visible) => !visible)}
            >
              {showPassword ? 'Ẩn' : 'Hiện'}
            </button>
          </div>

          {error && (
            <p className="error-message" role="alert">
              {error}
            </p>
          )}

          <button type="submit" disabled={submitting || isLoading}>
            {submitting ? 'Đang đăng nhập...' : 'Đăng nhập'}
          </button>
        </form>
      </section>
    </main>
  )
}
