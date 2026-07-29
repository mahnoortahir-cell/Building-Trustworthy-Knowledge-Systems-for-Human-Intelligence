import { useState, type FormEvent } from "react"
import {
  Link,
  Navigate,
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

function isTokenResponse(
  value: unknown,
): value is TokenResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "access_token" in value &&
    typeof value.access_token === "string"
  )
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Registration failed. Please try again."
}

export function RegisterPage() {
  const navigate = useNavigate()

  const existingToken = useAuthStore(
    (state) => state.token,
  )

  const setSession = useAuthStore(
    (state) => state.setSession,
  )

  const [fullName, setFullName] = useState("")
  const [organizationName, setOrganizationName] =
    useState("")
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
      const registrationResponse =
        await apiRequest<unknown>(
          "/auth/register",
          {
            method: "POST",
            body: JSON.stringify({
              full_name: fullName.trim(),
              organization_name:
                organizationName.trim(),
              email: email.trim(),
              password,
            }),
          },
          null,
        )

      let accessToken: string

      if (isTokenResponse(registrationResponse)) {
        accessToken =
          registrationResponse.access_token
      } else {
        const loginBody = new URLSearchParams({
          username: email.trim(),
          password,
        })

        const loginResponse =
          await apiRequest<TokenResponse>(
            "/auth/login",
            {
              method: "POST",
              headers: {
                "Content-Type":
                  "application/x-www-form-urlencoded",
              },
              body: loginBody,
            },
            null,
          )

        accessToken = loginResponse.access_token
      }

      const user = await apiRequest<AuthUser>(
        "/auth/me",
        { method: "GET" },
        accessToken,
      )

      setSession(accessToken, user)
      navigate("/", { replace: true })
    } catch (error) {
      setErrorMessage(getErrorMessage(error))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card wide">
        <div className="brand-mark">N</div>

        <p className="eyebrow">
          Create your NoorOS workspace
        </p>

        <h1>Start building trusted knowledge</h1>

        <p className="auth-description">
          Register an organisation-scoped account.
        </p>

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="form-grid">
            <label>
              Full name
              <input
                type="text"
                autoComplete="name"
                required
                value={fullName}
                onChange={(event) =>
                  setFullName(event.target.value)
                }
                placeholder="Your full name"
              />
            </label>

            <label>
              Organisation
              <input
                type="text"
                required
                value={organizationName}
                onChange={(event) =>
                  setOrganizationName(
                    event.target.value,
                  )
                }
                placeholder="Organisation name"
              />
            </label>
          </div>

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
              autoComplete="new-password"
              required
              minLength={8}
              value={password}
              onChange={(event) =>
                setPassword(event.target.value)
              }
              placeholder="Minimum 8 characters"
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
            {isSubmitting
              ? "Creating workspace..."
              : "Create workspace"}
          </button>
        </form>

        <p className="auth-switch">
          Already registered?{" "}
          <Link to="/login">Sign in</Link>
        </p>
      </section>
    </main>
  )
}
