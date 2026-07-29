import { useEffect, useState } from "react"

import { apiRequest } from "./api/client"
import "./index.css"

interface HealthResponse {
  status: string
  environment: string
}

export default function App() {
  const [health, setHealth] =
    useState<HealthResponse | null>(null)

  const [error, setError] =
    useState<string | null>(null)

  useEffect(() => {
    apiRequest<HealthResponse>("/health")
      .then(setHealth)
      .catch((requestError: unknown) => {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Backend connection failed",
        )
      })
  }, [])

  return (
    <main className="app-page">
      <section className="welcome-card">
        <div className="logo-mark">N</div>

        <p className="eyebrow">
          Trustworthy Knowledge Intelligence
        </p>

        <h1>NoorOS</h1>

        <p className="description">
          Secure organisation-scoped document search,
          grounded AI answers, citations and conversation
          management.
        </p>

        {health ? (
          <div className="status success">
            <span />
            Backend connected — {health.environment}
          </div>
        ) : null}

        {error ? (
          <div className="status error">
            Backend connection failed: {error}
          </div>
        ) : null}

        {!health && !error ? (
          <div className="status loading">
            Checking backend connection...
          </div>
        ) : null}
      </section>
    </main>
  )
}

