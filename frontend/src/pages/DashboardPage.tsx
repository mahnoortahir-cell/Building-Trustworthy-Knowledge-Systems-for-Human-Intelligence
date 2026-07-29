import { useEffect, useState } from "react"
import { FileText } from "lucide-react"
import {
  Link,
  useNavigate,
} from "react-router-dom"

import { apiRequest } from "../api/client"
import {
  useAuthStore,
  type AuthUser,
} from "../auth/authStore"

export function DashboardPage() {
  const navigate = useNavigate()

  const token = useAuthStore((state) => state.token)
  const storedUser = useAuthStore((state) => state.user)
  const setSession = useAuthStore(
    (state) => state.setSession,
  )
  const clearSession = useAuthStore(
    (state) => state.clearSession,
  )

  const [isRefreshing, setIsRefreshing] = useState(true)
  const [errorMessage, setErrorMessage] = useState("")

  useEffect(() => {
    if (!token) {
      return
    }

    apiRequest<AuthUser>("/auth/me")
      .then((user) => {
        setSession(token, user)
      })
      .catch((error: unknown) => {
        setErrorMessage(
          error instanceof Error
            ? error.message
            : "Unable to refresh the current user.",
        )
      })
      .finally(() => {
        setIsRefreshing(false)
      })
  }, [setSession, token])

  function handleLogout() {
    clearSession()
    navigate("/login", { replace: true })
  }

  const displayName =
    storedUser?.full_name ||
    storedUser?.email ||
    "NoorOS User"

  const primaryOrganization =
    storedUser?.organizations?.[0]

  return (
    <main className="dashboard-page">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">NoorOS workspace</p>
          <h1>Welcome, {displayName}</h1>
          <p>
            Your authenticated frontend is connected to the
            FastAPI backend.
          </p>
        </div>

        <button
          className="secondary-button"
          type="button"
          onClick={handleLogout}
        >
          Log out
        </button>
      </header>

      {errorMessage ? (
        <div className="form-error dashboard-message">
          {errorMessage}
        </div>
      ) : null}

      <section className="dashboard-grid">
        <article>
          <strong>Authentication</strong>
          <span>
            {isRefreshing
              ? "Refreshing user session..."
              : "JWT session active"}
          </span>
        </article>

        <article className="dashboard-action-card">
          <strong>Documents</strong>
          <span>
            Upload trusted PDFs and search extracted knowledge.
          </span>

          <Link
            className="dashboard-card-link"
            to="/documents"
          >
            <FileText size={17} />
            Open document library
          </Link>
        </article>

        <article>
          <strong>Knowledge Chat</strong>
          <span>
            Grounded answers and citations are ready in the
            backend.
          </span>
        </article>

        <article>
          <strong>Conversation Lifecycle</strong>
          <span>
            Pin, archive, trash, restore and permanent delete.
          </span>
        </article>
      </section>

      <section className="session-card">
        <h2>Current session</h2>

        <dl>
          <div>
            <dt>Email</dt>
            <dd>{storedUser?.email || "Loading..."}</dd>
          </div>

          <div>
            <dt>Role</dt>
            <dd>
              {primaryOrganization?.role || "Member"}
            </dd>
          </div>

          <div>
            <dt>Organisation</dt>
            <dd>
              {primaryOrganization?.name ||
                "Organisation-scoped"}
            </dd>
          </div>
        </dl>
      </section>
    </main>
  )
}
