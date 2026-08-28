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
})
