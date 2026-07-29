import { useState, type FormEvent } from "react"
import {
  Link,
  Navigate,
  useLocation,
  useNavigate,
} from "react-router-dom"

import { apiRequest } from "../api/client"
import {
  useAuthStore,
  type AuthUser,
} from "../auth/authStore"

interface TokenResponse {
  access_token: string
  token_type: string
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Login failed. Please try again."
}

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()

  const existingToken = useAuthStore(
    (state) => state.token,
  )

  const setSession = useAuthStore(
    (state) => state.setSession,
  )

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [errorMessage, setErrorMessage] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (existingToken) {
    return <Navigate to="/" replace />
  }

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()
    setErrorMessage("")
    setIsSubmitting(true)

    try {
      const body = new URLSearchParams({
        username: email.trim(),
        password,
      })

      const tokenResponse =
        await apiRequest<TokenResponse>(
          "/auth/login",
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/x-www-form-urlencoded",
            },
            body,
          },
          null,
        )

      const user = await apiRequest<AuthUser>(
        "/auth/me",
        { method: "GET" },
        tokenResponse.access_token,
      )

      setSession(tokenResponse.access_token, user)

      const destination =
        typeof location.state === "object" &&
        location.state !== null &&
        "from" in location.state &&
        typeof location.state.from === "string"
          ? location.state.from
          : "/"

      navigate(destination, { replace: true })
    } catch (error) {
      setErrorMessage(getErrorMessage(error))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card">
        <div className="brand-mark">N</div>

        <p className="eyebrow">
          Trustworthy Knowledge Intelligence
        </p>

        <h1>Welcome back</h1>

        <p className="auth-description">
          Sign in to your secure NoorOS workspace.
        </p>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label>
            Email address
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) =>
                setEmail(event.target.value)
              }
              placeholder="you@example.com"
            />
          </label>

          <label>
            Password
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) =>
                setPassword(event.target.value)
              }
              placeholder="Enter your password"
            />
          </label>

          {errorMessage ? (
            <div className="form-error">
              {errorMessage}
            </div>
          ) : null}

          <button
            className="primary-button"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="auth-switch">
          New to NoorOS?{" "}
          <Link to="/register">
            Create an account
          </Link>
        </p>
      </section>
    </main>
  )
}
