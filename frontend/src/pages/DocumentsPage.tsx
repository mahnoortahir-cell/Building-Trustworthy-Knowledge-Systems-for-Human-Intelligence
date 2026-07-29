import { useEffect, useMemo, useState } from "react"
import {
  ArrowLeft,
  FileSearch,
  FileText,
  Search,
  UploadCloud,
} from "lucide-react"
import { Link } from "react-router-dom"

import { apiRequest } from "../api/client"
import {
  useAuthStore,
  type AuthUser,
  type OrganizationSummary,
} from "../auth/authStore"
import type {
  DocumentRecord,
  SemanticSearchResponse,
} from "../types/documents"

function getErrorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "The request failed. Please try again."
}

function formatBytes(value: number): string {
  if (!Number.isFinite(value) || value <= 0) {
    return "0 B"
  }

  const units = ["B", "KB", "MB", "GB"]
  const unitIndex = Math.min(
    Math.floor(Math.log(value) / Math.log(1024)),
    units.length - 1,
  )

  const amount = value / 1024 ** unitIndex

  return `${amount.toFixed(unitIndex === 0 ? 0 : 1)} ${
    units[unitIndex]
  }`
}

function formatDate(value: string): string {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date)
}

function readRecentDocuments(
  organizationId: string,
): DocumentRecord[] {
  try {
    const rawValue = localStorage.getItem(
      `nooros-recent-documents:${organizationId}`,
    )

    if (!rawValue) {
      return []
    }

    const parsedValue = JSON.parse(rawValue)

    return Array.isArray(parsedValue)
      ? (parsedValue as DocumentRecord[])
      : []
  } catch {
    return []
  }
}

function saveRecentDocuments(
  organizationId: string,
  documents: DocumentRecord[],
) {
  localStorage.setItem(
    `nooros-recent-documents:${organizationId}`,
    JSON.stringify(documents.slice(0, 20)),
  )
}

const EMPTY_ORGANIZATIONS: OrganizationSummary[] = []

export function DocumentsPage() {
  const token = useAuthStore((state) => state.token)
  const storedUser = useAuthStore((state) => state.user)
  const setSession = useAuthStore(
    (state) => state.setSession,
  )

  const initialOrganizationId =
    storedUser?.organizations?.[0]?.id ?? ""

  const [selectedOrganizationId, setSelectedOrganizationId] =
    useState(initialOrganizationId)
  const [title, setTitle] = useState("")
  const [selectedFile, setSelectedFile] =
    useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState("")
  const [uploadedDocument, setUploadedDocument] =
    useState<DocumentRecord | null>(null)
  const [recentDocuments, setRecentDocuments] = useState<
    DocumentRecord[]
  >(() =>
    initialOrganizationId
      ? readRecentDocuments(initialOrganizationId)
      : [],
  )
  const [query, setQuery] = useState("")
  const [documentFilterId, setDocumentFilterId] =
    useState("")
  const [isSearching, setIsSearching] = useState(false)
  const [searchError, setSearchError] = useState("")
  const [searchResponse, setSearchResponse] =
    useState<SemanticSearchResponse | null>(null)

  useEffect(() => {
    if (!token) {
      return
    }

    apiRequest<AuthUser>("/auth/me")
      .then((user) => {
        setSession(token, user)

        if (
          !selectedOrganizationId &&
          user.organizations.length > 0
        ) {
          const organizationId =
            user.organizations[0].id

          setSelectedOrganizationId(organizationId)

          setRecentDocuments(
            readRecentDocuments(organizationId),
          )
        }
      })
      .catch(() => {
        // The existing authenticated screen handles invalid sessions.
      })
  }, [selectedOrganizationId, setSession, token])

  const organizations =
    storedUser?.organizations ?? EMPTY_ORGANIZATIONS

  const selectedOrganization = useMemo(
    () =>
      organizations.find(
        (organization) =>
          organization.id === selectedOrganizationId,
      ) ?? null,
    [organizations, selectedOrganizationId],
  )

  async function handleUpload(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()
    setUploadError("")
    setUploadedDocument(null)

    if (!selectedOrganizationId) {
      setUploadError("Select an organisation first.")
      return
    }

    if (!selectedFile) {
      setUploadError("Select a PDF file.")
      return
    }

    if (
      selectedFile.type !== "application/pdf" &&
      !selectedFile.name.toLowerCase().endsWith(".pdf")
    ) {
      setUploadError("Only PDF files are supported.")
      return
    }

    setIsUploading(true)

    try {
      const formData = new FormData()
      formData.append("title", title.trim())
      formData.append("file", selectedFile)

      const uploadedResponse = await apiRequest<DocumentRecord>(
        `/organizations/${encodeURIComponent(
          selectedOrganizationId,
        )}/documents`,
        {
          method: "POST",
          body: formData,
        },
      )

      setUploadedDocument(uploadedResponse)

      const updatedRecentDocuments = [
        uploadedResponse,
        ...recentDocuments.filter(
          (item) => item.id !== uploadedResponse.id,
        ),
      ].slice(0, 20)

      setRecentDocuments(updatedRecentDocuments)
      saveRecentDocuments(
        selectedOrganizationId,
        updatedRecentDocuments,
      )

      setTitle("")
      setSelectedFile(null)

      const fileInput = globalThis.document.getElementById(
        "document-file",
      ) as HTMLInputElement | null

      if (fileInput) {
        fileInput.value = ""
      }
    } catch (error) {
      setUploadError(getErrorMessage(error))
    } finally {
      setIsUploading(false)
    }
  }

  async function handleSearch(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()
    setSearchError("")
    setSearchResponse(null)

    if (!selectedOrganizationId) {
      setSearchError("Select an organisation first.")
      return
    }

    if (!query.trim()) {
      setSearchError("Enter a search question.")
      return
    }

    setIsSearching(true)

    try {
      const body: {
        query: string
        limit: number
        document_id?: string
      } = {
        query: query.trim(),
        limit: 10,
      }

      if (documentFilterId) {
        body.document_id = documentFilterId
      }

      const response =
        await apiRequest<SemanticSearchResponse>(
          `/organizations/${encodeURIComponent(
            selectedOrganizationId,
          )}/documents/search`,
          {
            method: "POST",
            body: JSON.stringify(body),
          },
        )

      setSearchResponse(response)
    } catch (error) {
      setSearchError(getErrorMessage(error))
    } finally {
      setIsSearching(false)
    }
  }

  return (
    <main className="documents-page">
      <header className="documents-header">
        <div>
          <Link className="back-link" to="/">
            <ArrowLeft size={17} />
            Dashboard
          </Link>

          <p className="eyebrow">Knowledge library</p>
          <h1>Documents</h1>

          <p>
            Upload trusted PDFs and search their extracted
            knowledge by meaning.
          </p>
        </div>

        <div className="organization-control">
          <label htmlFor="organization">
            Organisation
          </label>

          <select
            id="organization"
            value={selectedOrganizationId}
            onChange={(event) => {
              const organizationId =
                event.target.value

              setSelectedOrganizationId(
                organizationId,
              )

              setRecentDocuments(
                organizationId
                  ? readRecentDocuments(
                      organizationId,
                    )
                  : [],
              )

              setDocumentFilterId("")
              setSearchResponse(null)
            }}
          >
            {organizations.length === 0 ? (
              <option value="">
                No organisation available
              </option>
            ) : null}

            {organizations.map((organization) => (
              <option
                key={organization.id}
                value={organization.id}
              >
                {organization.name} â€” {organization.role}
              </option>
            ))}
          </select>
        </div>
      </header>

      <section className="documents-grid">
        <article className="document-card">
          <div className="card-heading">
            <div className="card-icon">
              <UploadCloud size={23} />
            </div>

            <div>
              <h2>Upload PDF</h2>
              <p>
                Files are processed inside the selected
                organisation.
              </p>
            </div>
          </div>

          <form
            className="document-form"
            onSubmit={handleUpload}
          >
            <label>
              Document title
              <input
                type="text"
                required
                minLength={1}
                maxLength={255}
                value={title}
                onChange={(event) =>
                  setTitle(event.target.value)
                }
                placeholder="Example: Employee Handbook"
              />
            </label>

            <label>
              PDF file
              <input
                id="document-file"
                type="file"
                required
                accept=".pdf,application/pdf"
                onChange={(event) =>
                  setSelectedFile(
                    event.target.files?.[0] ?? null,
                  )
                }
              />
            </label>

            {selectedFile ? (
              <div className="selected-file">
                <FileText size={18} />

                <div>
                  <strong>{selectedFile.name}</strong>
                  <span>
                    {formatBytes(selectedFile.size)}
                  </span>
                </div>
              </div>
            ) : null}

            {uploadError ? (
              <div className="form-error">
                {uploadError}
              </div>
            ) : null}

            <button
              className="primary-button"
              type="submit"
              disabled={
                isUploading ||
                !selectedOrganizationId
              }
            >
              {isUploading
                ? "Uploading and processing..."
                : "Upload document"}
            </button>
          </form>

          {uploadedDocument ? (
            <div className="upload-success">
              <strong>Upload completed</strong>

              <span>
                {uploadedDocument.title} Â·{" "}
                {uploadedDocument.status}
              </span>

              <small>
                Extraction:{" "}
                {
                  uploadedDocument.latest_version
                    .extraction_status
                }
              </small>
            </div>
          ) : null}
        </article>

        <article className="document-card">
          <div className="card-heading">
            <div className="card-icon">
              <Search size={23} />
            </div>

            <div>
              <h2>Semantic search</h2>
              <p>
                Search document chunks using natural language.
              </p>
            </div>
          </div>

          <form
            className="document-form"
            onSubmit={handleSearch}
          >
            <label>
              Search query
              <textarea
                required
                maxLength={2000}
                rows={4}
                value={query}
                onChange={(event) =>
                  setQuery(event.target.value)
                }
                placeholder="What does the policy say about annual leave?"
              />
            </label>

            <label>
              Limit to a recent upload
              <select
                value={documentFilterId}
                onChange={(event) =>
                  setDocumentFilterId(
                    event.target.value,
                  )
                }
              >
                <option value="">
                  Search all organisation documents
                </option>

                {recentDocuments.map((document) => (
                  <option
                    key={document.id}
                    value={document.id}
                  >
                    {document.title}
                  </option>
                ))}
              </select>
            </label>

            {searchError ? (
              <div className="form-error">
                {searchError}
              </div>
            ) : null}

            <button
              className="primary-button"
              type="submit"
              disabled={
                isSearching ||
                !selectedOrganizationId
              }
            >
              {isSearching
                ? "Searching..."
                : "Search knowledge"}
            </button>
          </form>
        </article>
      </section>

      <section className="library-card">
        <div className="library-heading">
          <div>
            <p className="eyebrow">Recent uploads</p>
            <h2>
              {selectedOrganization?.name ??
                "Organisation"}{" "}
              documents
            </h2>
          </div>

          <span className="count-pill">
            {recentDocuments.length} saved locally
          </span>
        </div>

        <p className="library-note">
          The current backend exposes upload and semantic
          search endpoints but not a document-list endpoint.
          This section therefore remembers successful uploads
          in this browser until the server-side list endpoint
          is added.
        </p>

        {recentDocuments.length === 0 ? (
          <div className="empty-library">
            <FileSearch size={31} />
            <strong>No recent uploads</strong>
            <span>
              Upload a PDF to add it to this browser view.
            </span>
          </div>
        ) : (
          <div className="document-list">
            {recentDocuments.map((document) => (
              <article key={document.id}>
                <div className="document-list-icon">
                  <FileText size={21} />
                </div>

                <div className="document-list-main">
                  <strong>{document.title}</strong>
                  <span>
                    {document.original_filename}
                  </span>
                </div>

                <div className="document-list-meta">
                  <span>{document.status}</span>
                  <small>
                    Version{" "}
                    {
                      document.latest_version
                        .version_number
                    }{" "}
                    Â·{" "}
                    {formatBytes(
                      document.latest_version.file_size,
                    )}
                  </small>
                  <small>
                    {formatDate(document.created_at)}
                  </small>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="library-card">
        <div className="library-heading">
          <div>
            <p className="eyebrow">Search results</p>
            <h2>Grounded document chunks</h2>
          </div>

          {searchResponse ? (
            <span className="count-pill">
              {searchResponse.result_count} results
            </span>
          ) : null}
        </div>

        {!searchResponse ? (
          <div className="empty-library">
            <Search size={31} />
            <strong>No search completed</strong>
            <span>
              Enter a natural-language query above.
            </span>
          </div>
        ) : searchResponse.results.length === 0 ? (
          <div className="empty-library">
            <FileSearch size={31} />
            <strong>No matching chunks</strong>
            <span>
              Try another query or upload more documents.
            </span>
          </div>
        ) : (
          <div className="search-results">
            {searchResponse.results.map((result) => (
              <article key={result.chunk_id}>
                <div className="search-result-topline">
                  <strong>
                    Chunk {result.chunk_index}
                  </strong>

                  <span>
                    Score {result.score.toFixed(4)}
                  </span>
                </div>

                <p>{result.content}</p>

                <small>
                  Document: {result.document_id}
                </small>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  )
}

