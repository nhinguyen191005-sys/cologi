
import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/useAuth'
import './LoginPage.css'

export default function LoginPage() {
  const {
    signIn,
    isAuthenticated,
    isLoading,
    error,
    clearAuthError,
  } = useAuth()

  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showHelp, setShowHelp] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const busy = isLoading || submitting

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    clearAuthError()
    setSubmitting(true)

    try {
      await signIn({
        email: email.trim(),
        password,
      })

      navigate('/', { replace: true })
    } catch {
      // Thông báo lỗi được AuthContext xử lý.
    } finally {
      setSubmitting(false)
    }
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }

  return (
    <main className="cg-login">

      {/* BÊN TRÁI - THƯƠNG HIỆU */}
      <section
        className="cg-login-story"
        aria-label="Giới thiệu CoLogi"
      >
        <div
          className="cg-story-grid"
          aria-hidden="true"
        />

        <div className="cg-brand">
  <img src="/images/logo.png" alt="CoLogi" />
</div>

        <div className="cg-story-body">
          <span className="cg-eyebrow">
            <i />
            SMART LOGISTICS WORKSPACE
          </span>

          <h1>
            Mọi điểm kết nối.
            <br />
            <em>Một dòng chảy.</em>
          </h1>

          <p>
            Từ nhu cầu mua hàng đến cung ứng và vận chuyển —
            mọi thông tin được kết nối trong một không gian làm việc.
          </p>

          {/* ANIMATION KẾT NỐI LOGISTICS */}
          <div
            className="cg-network"
            aria-hidden="true"
          >
            <svg
              className="cg-network-lines"
              viewBox="0 0 460 290"
              fill="none"
            >
              <path d="M230 151 C180 110 157 90 102 62" />
              <path d="M230 151 C274 106 311 89 362 63" />
              <path d="M230 151 C230 195 230 222 230 254" />
            </svg>

            <div className="cg-core">
              <span>CoLogi</span>
              <small>CONNECTED</small>
            </div>

            <div className="cg-flow-node cg-node-one">
              <span className="cg-node-number">01</span>

              <span>
                <strong>Nhu cầu</strong>
                <small>Demand</small>
              </span>
            </div>

            <div className="cg-flow-node cg-node-two">
              <span className="cg-node-number">02</span>

              <span>
                <strong>Cung ứng</strong>
                <small>Supply</small>
              </span>
            </div>

            <div className="cg-flow-node cg-node-three">
              <span className="cg-node-number">03</span>

              <span>
                <strong>Vận chuyển</strong>
                <small>Delivery</small>
              </span>
            </div>
          </div>
        </div>

        <div className="cg-story-footer">
          <span>THINK CONNECTED. MOVE SMARTER.</span>
          <span>COLOGI / 2026</span>
        </div>
      </section>

      {/* BÊN PHẢI - FORM ĐĂNG NHẬP */}
      <section
        className="cg-login-form-side"
        aria-labelledby="cg-login-title"
      >
        <div className="cg-login-card">

          <div
            className="cg-welcome-symbol"
            aria-hidden="true"
          >
            <svg
              width="25"
              height="25"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect
                x="5"
                y="10"
                width="14"
                height="11"
                rx="2"
              />
              <path d="M8 10V7a4 4 0 0 1 8 0v3" />
            </svg>
          </div>

          <span className="cg-form-kicker">
            CHÀO MỪNG TRỞ LẠI
          </span>

          <h2 id="cg-login-title">
            Đăng nhập <span>CoLogi.</span>
          </h2>

          <p className="cg-form-intro">
            Tiếp tục công việc của bạn trên nền tảng
            quản lý logistics.
          </p>

          <form
            className="cg-form"
            onSubmit={handleSubmit}
          >
            {/* EMAIL */}
            <label htmlFor="cg-email">
              Địa chỉ email
            </label>

            <div className="cg-field">
              <span
                className="cg-field-icon"
                aria-hidden="true"
              >
                @
              </span>

              <input
                id="cg-email"
                type="email"
                autoComplete="username"
                placeholder="name@company.com"
                value={email}
                onChange={(event) =>
                  setEmail(event.target.value)
                }
                required
              />
            </div>

            {/* PASSWORD */}
            <label htmlFor="cg-password">
              Mật khẩu
            </label>

            <div className="cg-field">
              <span
                className="cg-field-icon"
                aria-hidden="true"
              >
                ●
              </span>

              <input
                id="cg-password"
                type={
                  showPassword
                    ? 'text'
                    : 'password'
                }
                autoComplete="current-password"
                placeholder="Nhập mật khẩu"
                value={password}
                onChange={(event) =>
                  setPassword(event.target.value)
                }
                required
              />

              <button
                type="button"
                className="cg-show-password"
                aria-label={
                  showPassword
                    ? 'Ẩn mật khẩu'
                    : 'Hiện mật khẩu'
                }
                aria-pressed={showPassword}
                onClick={() =>
                  setShowPassword((visible) => !visible)
                }
              >
                {showPassword ? 'Ẩn' : 'Hiện'}
              </button>
            </div>

            {/* OPTIONS */}
            <div className="cg-form-options">
              <span>Đăng nhập an toàn</span>

              <button
                type="button"
                onClick={() =>
                  setShowHelp((open) => !open)
                }
              >
                Quên mật khẩu?
              </button>
            </div>

            {showHelp && (
              <p
                className="cg-help-message"
                role="status"
              >
                Vui lòng liên hệ quản trị viên CoLogi
                để được hỗ trợ đặt lại mật khẩu.
              </p>
            )}

            {/* API ERROR */}
            {error && (
              <p
                className="cg-login-error"
                role="alert"
              >
                {error}
              </p>
            )}

            {/* LOGIN BUTTON */}
            <button
              className="cg-login-submit"
              type="submit"
              disabled={busy}
            >
              <span>
                {busy
                  ? 'Đang đăng nhập...'
                  : 'Đăng nhập vào hệ thống'}
              </span>

              <span
                className="cg-submit-arrow"
                aria-hidden="true"
              >
                →
              </span>
            </button>
          </form>

          <div className="cg-login-bottom">
            <span className="cg-safe-dot" />
            Truy cập được quản lý theo vai trò người dùng
          </div>
        </div>

        <p className="cg-login-copyright">
          © {new Date().getFullYear()} CoLogi ·
          Logistics Decision Support
        </p>
      </section>
    </main>
  )
}
