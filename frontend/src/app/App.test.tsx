import { render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { appRoutes } from './router'

function anonymousResponse() {
  return new Response(JSON.stringify({ detail: 'Authentication required.' }), {
    status: 403,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('app router', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(anonymousResponse()))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the public home placeholder', async () => {
    const router = createMemoryRouter(appRoutes, { initialEntries: ['/'] })

    render(<App router={router} />)

    expect(screen.getByRole('heading', { name: 'Home' })).toBeInTheDocument()
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))
  })

  it.each([
    ['/profile/setup', 'Profile setup'],
    ['/ready-check', 'Ready Check'],
    ['/dashboard', 'Dashboard'],
    ['/workspace', 'Workspace'],
    ['/workspace/sprints/some-id', 'Sprint detail'],
  ])('renders the protected placeholder at %s', async (path, heading) => {
    const router = createMemoryRouter(appRoutes, { initialEntries: [path] })

    render(<App router={router} />)

    expect(
      await screen.findByRole('heading', { name: heading }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe(path)
  })

  it('renders NotFound for an invalid route', async () => {
    const router = createMemoryRouter(appRoutes, {
      initialEntries: ['/not-a-real-route'],
    })

    render(<App router={router} />)

    expect(
      screen.getByText('The requested frontend route does not exist.'),
    ).toBeInTheDocument()
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))
  })
})
