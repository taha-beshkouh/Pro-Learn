import { API_ENDPOINTS } from './endpoints'
import type { ApiErrorPayload, CsrfResponse } from './types'

const DEFAULT_API_BASE_URL = '/api/v1'
const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL
).replace(/\/+$/, '')

const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

type ApiRequestOptions = Omit<RequestInit, 'body'> & {
  body?: unknown
}

export class ApiError extends Error {
  readonly status: number
  readonly data: ApiErrorPayload

  constructor(message: string, status: number, data: ApiErrorPayload) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

function buildUrl(path: string) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${API_BASE_URL}${normalizedPath}`
}

async function readResponse(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return undefined
  }

  const body = await response.text()
  if (!body) {
    return undefined
  }

  if (response.headers.get('content-type')?.includes('application/json')) {
    try {
      return JSON.parse(body) as unknown
    } catch {
      return body
    }
  }

  return body
}

function errorMessage(response: Response, data: unknown) {
  if (
    data &&
    typeof data === 'object' &&
    'detail' in data &&
    typeof data.detail === 'string'
  ) {
    return data.detail
  }

  return response.statusText || `API request failed with status ${response.status}`
}

async function fetchCsrfToken(signal?: AbortSignal | null) {
  const response = await fetch(buildUrl(API_ENDPOINTS.auth.csrf), {
    credentials: 'include',
    headers: { Accept: 'application/json' },
    signal,
  })
  const data = await readResponse(response)

  if (!response.ok) {
    throw new ApiError(
      errorMessage(response, data),
      response.status,
      data as ApiErrorPayload,
    )
  }

  const token = (data as Partial<CsrfResponse> | undefined)?.csrfToken
  if (!token) {
    throw new ApiError('The API did not provide a CSRF token.', response.status, null)
  }

  return token
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const { body: requestBody, ...fetchOptions } = options
  const method = (fetchOptions.method || 'GET').toUpperCase()
  const headers = new Headers(fetchOptions.headers)
  headers.set('Accept', 'application/json')

  if (UNSAFE_METHODS.has(method)) {
    headers.set('X-CSRFToken', await fetchCsrfToken(fetchOptions.signal))
  }

  let body: BodyInit | undefined
  if (requestBody instanceof FormData) {
    body = requestBody
  } else if (requestBody !== undefined) {
    headers.set('Content-Type', 'application/json')
    body = JSON.stringify(requestBody)
  }

  const response = await fetch(buildUrl(path), {
    ...fetchOptions,
    method,
    headers,
    body,
    credentials: 'include',
  })
  const data = await readResponse(response)

  if (!response.ok) {
    throw new ApiError(
      errorMessage(response, data),
      response.status,
      data as ApiErrorPayload,
    )
  }

  return data as T
}

export const apiClient = {
  get<T>(path: string, options?: ApiRequestOptions) {
    return apiRequest<T>(path, { ...options, method: 'GET' })
  },
  post<T>(path: string, body?: unknown, options?: ApiRequestOptions) {
    return apiRequest<T>(path, { ...options, method: 'POST', body })
  },
  patch<T>(path: string, body: unknown, options?: ApiRequestOptions) {
    return apiRequest<T>(path, { ...options, method: 'PATCH', body })
  },
  delete<T>(path: string, options?: ApiRequestOptions) {
    return apiRequest<T>(path, { ...options, method: 'DELETE' })
  },
}
