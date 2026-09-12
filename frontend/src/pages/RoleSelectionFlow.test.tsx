import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { appRoutes } from '../app/router'
import type {
  GuestParticipationContext,
  PlatformRole,
} from '../lib/api/types'

const roles = [
  {
    id: '00000000-0000-4000-8000-000000000001',
    code: 'FRONTEND_DEVELOPER',
    name: 'Frontend Developer',
    cardLabel: 'Front-end developer',
    toastLabel: 'Front-end Developer',
  },
  {
    id: '00000000-0000-4000-8000-000000000002',
    code: 'PRODUCT_DESIGNER',
    name: 'Product Designer',
    cardLabel: 'Product Designer',
    toastLabel: 'Product Designer',
  },
  {
    id: '00000000-0000-4000-8000-000000000003',
    code: 'BACKEND_DEVELOPER',
    name: 'Backend Developer',
    cardLabel: 'Back-end developer',
    toastLabel: 'Back-end Developer',
  },
] as const

type BackendOptions = {
  authenticated?: boolean
  blockedReason?:
    | 'active_readiness'
    | 'current_formation_or_ready_check'
    | 'active_project_run'
  context?: GuestParticipationContext
  failGuestSelection?: boolean
  pauseGuestSelection?: Promise<void>
  profileRole?: PlatformRole
}

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function installBackend(options: BackendOptions = {}) {
  let context = { ...options.context }
  let profileRole = options.profileRole ?? null
  let csrfCount = 0

  const api = vi.fn(
    async (input: RequestInfo | URL, request?: RequestInit) => {
      const url = new URL(String(input), 'http://frontend.test')
      const method = request?.method ?? 'GET'

      if (url.pathname === '/api/v1/auth/me/') {
        return options.authenticated
          ? json({ id: 'member-id', email: 'member@example.com' })
          : json(
              { detail: 'Authentication credentials were not provided.' },
              403,
            )
      }
      if (url.pathname === '/api/v1/auth/csrf/') {
        return json({ csrfToken: `csrf-${++csrfCount}` })
      }
      if (url.pathname === '/api/v1/roles/') {
        return json(
          roles.map((role) => ({
            id: role.id,
            code: role.code,
            name: role.name,
          })),
        )
      }
      if (url.pathname === '/api/v1/guest-context/') {
        if (method === 'PATCH') {
          await options.pauseGuestSelection
          if (options.failGuestSelection) {
            return json({ detail: 'Guest context unavailable.' }, 503)
          }
          context = {
            ...context,
            ...(JSON.parse(String(request?.body)) as GuestParticipationContext),
          }
        }
        return json(context)
      }
      if (url.pathname === '/api/v1/profile/select-role/') {
        if (options.blockedReason) {
          return json(
            {
              detail: 'The backend blocked this role change.',
              code: 'role_change_blocked',
              reason: options.blockedReason,
            },
            409,
          )
        }
        const { role_id: roleId } = JSON.parse(String(request?.body)) as {
          role_id: string
        }
        profileRole =
          roles.find((role) => role.id === roleId) ?? profileRole
        return json({ selected_role: profileRole })
      }
      if (url.pathname === '/api/v1/profile/') {
        return json({ selected_role: profileRole })
      }
      if (url.pathname === '/api/v1/levels/') return json([])
      if (url.pathname === '/api/v1/projects/') return json([])

      return json({ detail: `Unexpected endpoint: ${method} ${url.pathname}` }, 404)
    },
  )

  vi.stubGlobal('fetch', api)
  return {
    api,
    context: () => context,
    profileRole: () => profileRole,
  }
}

type MemoryEntry =
  | string
  | {
      hash?: string
      key?: string
      pathname: string
      search?: string
      state?: unknown
    }

function mount(initialEntry: MemoryEntry = '/') {
  const router = createMemoryRouter(appRoutes, {
    initialEntries: [initialEntry],
  })
  const view = render(<App router={router} />)
  return { router, ...view }
}

function callsFor(
  api: ReturnType<typeof vi.fn>,
  path: string,
  method?: string,
) {
  return api.mock.calls.filter(([input, request]) => {
    const url = new URL(String(input), 'http://frontend.test')
    return (
      url.pathname === path &&
      (method === undefined || (request?.method ?? 'GET') === method)
    )
  })
}

async function readyRoleLink(cardLabel: string) {
  const link = screen.getByRole('link', {
    name: `${cardLabel} - دیدن پروژه‌ها`,
  })
  await waitFor(() => expect(link).toHaveAttribute('aria-disabled', 'false'))
  return link
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('Home role selection', () => {
  it.each(roles)(
    'maps the whole $cardLabel card to $code and the guest catalog',
    async (role) => {
      const backend = installBackend()
      const { router } = mount()
      const link = await readyRoleLink(role.cardLabel)

      expect(link).toHaveClass('role-card__link')
      expect(link.closest('article')).toHaveClass(
        `role-card--${
          role.code === 'FRONTEND_DEVELOPER'
            ? 'frontend'
            : role.code === 'PRODUCT_DESIGNER'
              ? 'product'
              : 'backend'
        }`,
      )

      await userEvent.setup().click(link)

      await waitFor(() => expect(router.state.location.pathname).toBe('/projects'))
      expect(backend.context().selected_role_id).toBe(role.id)
      const patch = callsFor(
        backend.api,
        '/api/v1/guest-context/',
        'PATCH',
      )
      expect(patch).toHaveLength(1)
      expect(JSON.parse(String(patch[0][1]?.body))).toEqual({
        selected_role_id: role.id,
      })
      expect(
        await screen.findByRole('heading', {
          name: `پروژه‌های مناسب نقش ${role.name}`,
        }),
      ).toBeInTheDocument()
      expect(screen.getByRole('status')).toHaveTextContent(
        `نقش ${role.toastLabel} انتخاب شد`,
      )

      const search = screen.getByLabelText('جست‌وجوی پروژه')
      await userEvent.setup().type(search, 'Helpdesk')
      expect(search).toHaveValue('Helpdesk')
    },
  )

  it('routes the CTA through the card action and prevents duplicate requests', async () => {
    let releaseSelection!: () => void
    const pauseGuestSelection = new Promise<void>((resolve) => {
      releaseSelection = resolve
    })
    const backend = installBackend({ pauseGuestSelection })
    mount()
    const link = await readyRoleLink('Back-end developer')
    const cta = link.querySelector('.role-card__cta-label')!

    fireEvent.click(cta)
    fireEvent.click(cta)

    await waitFor(() =>
      expect(
        callsFor(backend.api, '/api/v1/guest-context/', 'PATCH'),
      ).toHaveLength(1),
    )
    expect(link).toHaveAttribute('aria-busy', 'true')
    expect(cta).toHaveTextContent('در حال انتخاب...')

    await act(async () => releaseSelection())
    expect(
      await screen.findByText('نقش Back-end Developer انتخاب شد'),
    ).toBeInTheDocument()
  })

  it('keeps the full card keyboard operable with a visible-focus link', async () => {
    const backend = installBackend()
    mount()
    const link = await readyRoleLink('Front-end developer')
    const user = userEvent.setup()

    link.focus()
    expect(link).toHaveFocus()
    await user.keyboard('{Enter}')

    expect(
      await screen.findByText('نقش Front-end Developer انتخاب شد'),
    ).toBeInTheDocument()
    expect(
      callsFor(backend.api, '/api/v1/guest-context/', 'PATCH'),
    ).toHaveLength(1)
  })

  it('preserves the rest of the server-owned guest continuation context', async () => {
    const exactVersion = '00000000-0000-4000-8000-000000000042'
    const backend = installBackend({
      context: {
        selected_role_id: roles[2].id,
        project_version_id: exactVersion,
        intended_action: 'join_project',
        return_path: `/projects/${exactVersion}/stack-selection`,
      },
    })
    mount()

    await userEvent.setup().click(await readyRoleLink('Front-end developer'))
    await screen.findByText('نقش Front-end Developer انتخاب شد')

    expect(backend.context()).toEqual({
      selected_role_id: roles[0].id,
      project_version_id: exactVersion,
      intended_action: 'join_project',
      return_path: `/projects/${exactVersion}/stack-selection`,
    })
  })

  it('restores card interaction and does not show success after a failed request', async () => {
    installBackend({ failGuestSelection: true })
    const { router } = mount()
    const link = await readyRoleLink('Product Designer')

    await userEvent.setup().click(link)

    expect(
      await screen.findByText(
        'سرور اکنون نمی‌تواند درخواست را انجام دهد. دوباره تلاش کنید.',
      ),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/')
    expect(link).toHaveAttribute('aria-disabled', 'false')
    expect(screen.queryByText(/نقش Product Designer انتخاب شد/)).not.toBeInTheDocument()
  })

  it('uses the authenticated role endpoint and reloads catalog role truth', async () => {
    const backend = installBackend({
      authenticated: true,
      profileRole: roles[2],
    })
    const { router } = mount()

    await userEvent.setup().click(await readyRoleLink('Front-end developer'))

    await waitFor(() => expect(router.state.location.pathname).toBe('/projects'))
    expect(backend.profileRole()?.id).toBe(roles[0].id)
    const selectionCalls = callsFor(
      backend.api,
      '/api/v1/profile/select-role/',
      'POST',
    )
    expect(selectionCalls).toHaveLength(1)
    expect(JSON.parse(String(selectionCalls[0][1]?.body))).toEqual({
      role_id: roles[0].id,
    })
    expect(callsFor(backend.api, '/api/v1/guest-context/', 'PATCH')).toHaveLength(0)
    expect(
      await screen.findByRole('heading', {
        name: 'پروژه‌های مناسب نقش Frontend Developer',
      }),
    ).toBeInTheDocument()
    expect(screen.getByText('نقش Front-end Developer انتخاب شد')).toBeInTheDocument()

    const selectionIndex = backend.api.mock.calls.findIndex(
      ([input, request]) =>
        new URL(String(input), 'http://frontend.test').pathname ===
          '/api/v1/profile/select-role/' && request?.method === 'POST',
    )
    const profileIndex = backend.api.mock.calls.findIndex(
      ([input]) =>
        new URL(String(input), 'http://frontend.test').pathname ===
        '/api/v1/profile/',
    )
    expect(profileIndex).toBeGreaterThan(selectionIndex)
  })

  it('lets the backend handle same-role idempotency with one selection request', async () => {
    const backend = installBackend({
      authenticated: true,
      profileRole: roles[2],
    })
    mount()

    await userEvent.setup().click(await readyRoleLink('Back-end developer'))

    expect(
      await screen.findByText('نقش Back-end Developer انتخاب شد'),
    ).toBeInTheDocument()
    expect(
      callsFor(
        backend.api,
        '/api/v1/profile/select-role/',
        'POST',
      ),
    ).toHaveLength(1)
    expect(backend.profileRole()?.id).toBe(roles[2].id)
  })

  it.each([
    [
      'active_readiness',
      'تا زمانی که آمادگی فعال پروژه دارید، تغییر نقش ممکن نیست.',
    ],
    [
      'current_formation_or_ready_check',
      'تا پایان وضعیت فعلی تشکیل تیم یا Ready Check، تغییر نقش ممکن نیست.',
    ],
    [
      'active_project_run',
      'در زمان اجرای یک پروژه فعال، تغییر نقش ممکن نیست.',
    ],
  ] as const)(
    'keeps the authoritative role when the backend blocks %s',
    async (blockedReason, message) => {
      const backend = installBackend({
        authenticated: true,
        blockedReason,
        profileRole: roles[2],
      })
      const { router } = mount()

      await userEvent.setup().click(await readyRoleLink('Front-end developer'))

      expect(await screen.findByText(message)).toBeInTheDocument()
      expect(router.state.location.pathname).toBe('/')
      expect(backend.profileRole()?.id).toBe(roles[2].id)
      expect(
        screen.queryByText('نقش Front-end Developer انتخاب شد'),
      ).not.toBeInTheDocument()
      expect(callsFor(backend.api, '/api/v1/profile/', 'GET')).toHaveLength(0)
    },
  )

  it('consumes toast navigation state so a catalog refresh cannot replay it', async () => {
    installBackend()
    const first = mount()

    await userEvent.setup().click(await readyRoleLink('Product Designer'))
    expect(
      await screen.findByText('نقش Product Designer انتخاب شد'),
    ).toBeInTheDocument()
    await waitFor(() => expect(first.router.state.location.state).toBeNull())

    const refreshedLocation = first.router.state.location
    first.unmount()
    mount(refreshedLocation)

    await screen.findByRole('heading', {
      name: 'پروژه‌های مناسب نقش Product Designer',
    })
    expect(
      screen.queryByText('نقش Product Designer انتخاب شد'),
    ).not.toBeInTheDocument()
  })
})
