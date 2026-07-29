const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "/api"

interface StoredAuth {
  state?: {
    token?: string | null
  }
}

function getStoredToken(): string | null {
  try {
    const storedValue = localStorage.getItem("nooros-auth")

    if (!storedValue) {
      return null
    }

    const parsedValue = JSON.parse(storedValue) as StoredAuth
    return parsedValue.state?.token || null
  } catch {
    return null
  }
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  suppliedToken?: string | null,
): Promise<T> {
  const headers = new Headers(options.headers)

  const token =
    suppliedToken === undefined
      ? getStoredToken()
      : suppliedToken

  if (token) {
    headers.set("Authorization", `Bearer ${token}`)
  }

  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !(options.body instanceof URLSearchParams) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json")
  }

  const response = await fetch(API_BASE_URL + path, {
    ...options,
    headers,
  })

  if (response.status === 204) {
    return undefined as T
  }

  const contentType =
    response.headers.get("content-type") || ""

  const responseBody: unknown =
    contentType.includes("application/json")
      ? await response.json()
      : await response.text()

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`

    if (
      typeof responseBody === "object" &&
      responseBody !== null &&
      "detail" in responseBody
    ) {
      const detail = responseBody.detail

      message =
        typeof detail === "string"
          ? detail
          : JSON.stringify(detail)
    } else if (
      typeof responseBody === "string" &&
      responseBody.trim()
    ) {
      message = responseBody
    }

    throw new ApiError(response.status, message)
  }

  return responseBody as T
}
