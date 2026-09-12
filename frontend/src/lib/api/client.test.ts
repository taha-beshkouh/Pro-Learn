import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiClient } from './client'

describe('api client', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('normalizes a JSON error response as ApiError', async () => {
    const payload = { evidence: ['This field is required.'] }
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiClient.get('/example/')).rejects.toMatchObject({
      name: 'ApiError',
      status: 400,
      data: payload,
    } satisfies Partial<ApiError>)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/example/',
      expect.objectContaining({ credentials: 'include', method: 'GET' }),
    )
  })

  it('acquires a fresh CSRF token for each unsafe request, including after auth rotation', async () => {
    let token = 0
    const fetchMock = vi.fn(async (url: string) => new Response(
      JSON.stringify(url.endsWith('/csrf/') ? { csrfToken: `token-${++token}` } : {}),
      { headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)
    await apiClient.post('/auth/login/', { email: 'test@example.com', password: 'test-only' })
    await apiClient.post('/auth/logout/')
    const requests = vi.mocked(fetch).mock.calls
    expect(new Headers(requests[1][1]?.headers).get('X-CSRFToken')).toBe('token-1')
    expect(new Headers(requests[3][1]?.headers).get('X-CSRFToken')).toBe('token-2')
    for (const [, options] of requests) expect(options?.credentials).toBe('include')
  })

  it('never sends the unsafe request when CSRF acquisition fails', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('Forbidden', { status: 403 }))
    vi.stubGlobal('fetch', fetchMock)
    await expect(apiClient.post('/auth/login/', {})).rejects.toMatchObject({ status: 403 })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/auth/csrf/')
  })
})
