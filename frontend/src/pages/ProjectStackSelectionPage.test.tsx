import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type {
  ProjectReadinessResponse,
  ProjectVersionDetailResponse,
  TechnologyStack,
} from '../lib/api/types'
import { ProjectStackSelectionPage } from './ProjectStackSelectionPage'
import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import { ParticipationRoute } from '../auth/ParticipationRoute'

type Policy = 'FIXED' | 'ALLOWLIST' | 'OPEN'

const role = {
  id: 'role-api',
  code: 'API_ROLE',
  name: 'API Role',
}

const stackAlpha = {
  id: 'stack-alpha',
  code: 'stack-alpha-code',
  name: 'Stack Alpha',
}

const stackBeta = {
  id: 'stack-beta',
  code: 'stack-beta-code',
  name: 'Stack Beta',
}

const stackGamma = {
  id: 'stack-gamma',
  code: 'stack-gamma-code',
  name: 'Stack Gamma',
}

type VersionOptions = {
  compatibleStacks?: TechnologyStack[]
  configuredStacks?: TechnologyStack[]
  requiresStack?: boolean
  selectedStack?: TechnologyStack | null
}

function versionForPolicy(
  policy: Policy | null,
  {
    compatibleStacks,
    configuredStacks,
    requiresStack = true,
    selectedStack,
  }: VersionOptions = {},
): ProjectVersionDetailResponse {
  const defaultConfigured =
    policy === 'FIXED'
      ? [stackAlpha]
      : policy === 'ALLOWLIST'
        ? [stackAlpha, stackBeta]
        : []
  const defaultCompatible =
    policy === 'FIXED'
      ? [stackAlpha]
      : policy === 'ALLOWLIST'
        ? [stackAlpha, stackBeta]
        : [stackAlpha, stackBeta]
  const effectiveConfigured = configuredStacks ?? defaultConfigured
  const effectiveCompatible = compatibleStacks ?? defaultCompatible
  const effectiveSelected =
    selectedStack === undefined
      ? policy === 'FIXED'
        ? stackAlpha
        : null
      : selectedStack

  return {
    project_template: {
      id: 'template-1',
      slug: 'api-project',
      name: 'API Project',
      level: { id: 'level-1', number: 1, name: 'Level 1' },
    },
    id: 'version-1',
    version_number: 3,
    summary: '',
    full_description: '',
    duration_weeks: 6,
    sprint_count: 6,
    weekly_effort_hours_min: 8,
    weekly_effort_hours_max: 12,
    participant_database: '',
    published_at: '2026-09-01T12:00:00Z',
    sprint_templates: [],
    role_requirements: [
      {
        id: 'requirement-1',
        role,
        requires_stack: requiresStack,
        stack_policy: policy,
        context: '',
        configured_stacks: effectiveConfigured,
        prerequisites: [],
      },
    ],
    work_items: [],
    role_context: {
      id: 'requirement-1',
      role,
      requires_stack: requiresStack,
      stack_policy: policy,
      context: '',
      compatible_stacks: effectiveCompatible,
      auto_selected_stack:
        effectiveCompatible.length === 1 ? effectiveCompatible[0] : null,
      selected_stack: effectiveSelected,
      prerequisites: [],
      work_items: [],
    },
    shared_work_items: [],
  }
}

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function projectReadiness(): ProjectReadinessResponse {
  return {
    id: 'readiness-1',
    user: { id: 'user-1', email: 'user@example.com' },
    role,
    project_version_id: 'version-1',
    project_name: 'API Project',
    version_number: 3,
    technology_stack: stackAlpha,
    created_at: '2026-09-08T12:00:00Z',
    consumed_at: null,
  }
}

type HttpFailure = {
  data: unknown
  status: number
}

type ApiOptions = {
  activeReadiness?: ProjectReadinessResponse | null
  currentVersionId?: string | null
  exactFailureCount?: number
  exactStatus?: number
  readinessFailure?: HttpFailure
  readinessGate?: Promise<void>
  stackFailure?: HttpFailure
  version: ProjectVersionDetailResponse
}

function installApi({
  activeReadiness = null,
  currentVersionId = 'version-1',
  exactFailureCount = 0,
  exactStatus = 503,
  readinessFailure,
  readinessGate,
  stackFailure,
  version,
}: ApiOptions) {
  let remainingExactFailures = exactFailureCount
  let currentReadiness = activeReadiness
  const api = vi.fn(
    async (input: RequestInfo | URL, request?: RequestInit) => {
      const url = new URL(String(input), 'http://frontend.test')

      if (url.pathname === '/api/v1/project-versions/version-1/') {
        if (remainingExactFailures > 0) {
          remainingExactFailures -= 1
          return jsonResponse({ detail: 'Temporary stack context error.' }, exactStatus)
        }
        return jsonResponse(version)
      }

      if (url.pathname === '/api/v1/projects/template-1/') {
        return jsonResponse({
          id: 'template-1',
          slug: 'api-project',
          name: 'API Project',
          level: version.project_template.level,
          published_version_id: currentVersionId,
          published_version:
            currentVersionId === null
              ? null
              : {
                  id: currentVersionId,
                  version_number: 3,
                  summary: '',
                  duration_weeks: 6,
                  sprint_count: 6,
                  role_context: null,
                },
        })
      }

      if (url.pathname === '/api/v1/auth/csrf/') {
        return jsonResponse({ csrfToken: 'csrf-test-token' })
      }

      if (url.pathname === '/api/v1/profile/') return jsonResponse({ selected_role: role })
      if (url.pathname === '/api/v1/guest-context/') return jsonResponse({})
      if (url.pathname === '/api/v1/ready-checks/me/') return jsonResponse([])

      if (url.pathname === '/api/v1/project-readiness/me/') {
        if (request?.method === 'POST') {
          if (readinessGate) await readinessGate
          if (readinessFailure) {
            return jsonResponse(readinessFailure.data, readinessFailure.status)
          }
          currentReadiness = projectReadiness()
          return jsonResponse(currentReadiness, 201)
        }
        return currentReadiness
          ? jsonResponse(currentReadiness)
          : jsonResponse({ detail: 'Active project readiness not found.' }, 404)
      }

      if (
        url.pathname === '/api/v1/project-versions/version-1/stack-selection/' &&
        request?.method === 'POST'
      ) {
        if (stackFailure) {
          return jsonResponse(stackFailure.data, stackFailure.status)
        }
        const body = JSON.parse(String(request.body)) as {
          technology_stack_id: string
        }
        return jsonResponse({
          project_version_id: 'version-1',
          selected_role_id: role.id,
          selected_stack_id: body.technology_stack_id ?? null,
        })
      }

      return jsonResponse({ detail: `Unexpected endpoint: ${url.pathname}` }, 404)
    },
  )
  vi.stubGlobal('fetch', api)
  return api
}

function renderPage({ guarded = false }: { guarded?: boolean } = {}) {
  const auth: AuthContextValue = {
    status: 'authenticated', user: { id: 'user-1', email: 'user@example.com' }, error: null,
    refreshSession: vi.fn(async () => undefined), logout: vi.fn(async () => undefined), authenticate: vi.fn(async () => undefined),
  }
  return render(
    <AuthContext.Provider value={auth}>
    <MemoryRouter initialEntries={['/projects/version-1/stack-selection']}>
      <Routes>
        {guarded ? (
          <Route element={<ParticipationRoute />}>
            <Route
              path="/projects/:projectVersionId/stack-selection"
              element={<ProjectStackSelectionPage />}
            />
          </Route>
        ) : (
          <Route
            path="/projects/:projectVersionId/stack-selection"
            element={<ProjectStackSelectionPage />}
          />
        )}
        <Route path="/ready-check" element={<h1>Ready Check destination</h1>} />
      </Routes>
    </MemoryRouter>
    </AuthContext.Provider>,
  )
}

function callsFor(
  api: ReturnType<typeof vi.fn>,
  pathname: string,
  method?: string,
) {
  return api.mock.calls.filter(([input, request]) => {
    const url = new URL(String(input), 'http://frontend.test')
    return url.pathname === pathname && (!method || request?.method === method)
  })
}

function continueButton() {
  return screen.getByRole('button', { name: 'تأیید Stack' })
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('ProjectStackSelectionPage', () => {
  it('persists FIXED stack, creates readiness once with an empty body, and then completes', async () => {
    const user = userEvent.setup()
    const api = installApi({ version: versionForPolicy('FIXED') })

    renderPage()

    expect(
      await screen.findByRole('heading', {
        name: 'Stack این نقش از قبل مشخص شده است',
      }),
    ).toBeInTheDocument()
    expect(screen.getByText('FIXED')).toBeInTheDocument()
    expect(screen.queryByText('ALLOWLIST')).not.toBeInTheDocument()
    expect(screen.queryByText('OPEN')).not.toBeInTheDocument()
    expect(screen.getByText('Stack Alpha')).toBeInTheDocument()
    expect(screen.queryByRole('radio')).not.toBeInTheDocument()
    expect(continueButton()).toBeEnabled()

    await user.click(continueButton())

    expect(await screen.findByText('آمادگی شما ثبت شد')).toBeInTheDocument()
    expect(
      screen.getByText(
        'در انتظار تشکیل تیم هستید. پس از تشکیل تیم، Ready Check برای شما فعال می‌شود.',
      ),
    ).toBeInTheDocument()

    const stackPosts = callsFor(
      api,
      '/api/v1/project-versions/version-1/stack-selection/',
      'POST',
    )
    const readinessPosts = callsFor(
      api,
      '/api/v1/project-readiness/me/',
      'POST',
    )
    expect(stackPosts).toHaveLength(1)
    expect(readinessPosts).toHaveLength(1)
    expect(JSON.parse(String(stackPosts[0]?.[1]?.body))).toEqual({
      technology_stack_id: stackAlpha.id,
    })
    expect(JSON.parse(String(readinessPosts[0]?.[1]?.body))).toEqual({})
    const stackPostIndex = api.mock.calls.findIndex(([input, request]) => {
      const url = new URL(String(input), 'http://frontend.test')
      return url.pathname.endsWith('/stack-selection/') && request?.method === 'POST'
    })
    const readinessPostIndex = api.mock.calls.findIndex(([input, request]) => {
      const url = new URL(String(input), 'http://frontend.test')
      return url.pathname === '/api/v1/project-readiness/me/' && request?.method === 'POST'
    })
    expect(stackPostIndex).toBeLessThan(readinessPostIndex)
  })

  it('does not create readiness when Stack confirmation fails', async () => {
    const user = userEvent.setup()
    const api = installApi({
      stackFailure: {
        status: 400,
        data: { technology_stack_id: ['Invalid stack selection.'] },
      },
      version: versionForPolicy('FIXED'),
    })

    renderPage()
    await screen.findByText('Stack Alpha')
    await user.click(continueButton())

    expect(await screen.findByText('ثبت Stack ممکن نشد.')).toBeInTheDocument()
    expect(
      callsFor(api, '/api/v1/project-readiness/me/', 'POST'),
    ).toHaveLength(0)
    expect(screen.queryByText('آمادگی شما ثبت شد')).not.toBeInTheDocument()
  })

  it('uses an existing active readiness on refresh without creating another one', async () => {
    const api = installApi({
      activeReadiness: projectReadiness(),
      version: versionForPolicy('FIXED'),
    })

    renderPage({ guarded: true })

    expect(
      await screen.findByText(/آمادگی شما برای پروژه «API Project» ثبت شده است/),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'تأیید Stack' })).not.toBeInTheDocument()
    expect(
      callsFor(api, '/api/v1/project-readiness/me/', 'POST'),
    ).toHaveLength(0)
    expect(
      callsFor(
        api,
        '/api/v1/project-versions/version-1/stack-selection/',
        'POST',
      ),
    ).toHaveLength(0)
  })

  it('treats readiness GET 404 as no active readiness instead of a page error', async () => {
    installApi({ version: versionForPolicy('FIXED') })

    renderPage({ guarded: true })

    expect(
      await screen.findByRole('heading', {
        name: 'Stack این نقش از قبل مشخص شده است',
      }),
    ).toBeInTheDocument()
    expect(continueButton()).toBeEnabled()
    expect(screen.queryByText('اطلاعات موردنیاز پیدا نشد.')).not.toBeInTheDocument()
  })

  it('does not show false success when readiness creation fails after Stack succeeds', async () => {
    const user = userEvent.setup()
    const api = installApi({
      readinessFailure: {
        status: 409,
        data: { detail: 'The user is already in a current proposed formation.' },
      },
      version: versionForPolicy('FIXED'),
    })

    renderPage()
    await screen.findByText('Stack Alpha')
    await user.click(continueButton())

    expect(await screen.findByText('ثبت آمادگی ممکن نشد.')).toBeInTheDocument()
    expect(
      screen.getByText('این حساب هم‌اکنون در یک Formation جاری قرار دارد.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('آمادگی شما ثبت شد')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Stack تأیید شد' })).toBeDisabled()
    expect(
      callsFor(
        api,
        '/api/v1/project-versions/version-1/stack-selection/',
        'POST',
      ),
    ).toHaveLength(1)
    expect(
      callsFor(api, '/api/v1/project-readiness/me/', 'POST'),
    ).toHaveLength(1)
  })

  it('prevents duplicate Stack and readiness requests while creation is pending', async () => {
    const user = userEvent.setup()
    let releaseReadiness: () => void = () => {}
    const readinessGate = new Promise<void>((resolve) => {
      releaseReadiness = resolve
    })
    const api = installApi({
      readinessGate,
      version: versionForPolicy('FIXED'),
    })

    renderPage()
    await screen.findByText('Stack Alpha')
    await user.dblClick(continueButton())

    await waitFor(() =>
      expect(
        callsFor(api, '/api/v1/project-readiness/me/', 'POST'),
      ).toHaveLength(1),
    )
    expect(
      callsFor(
        api,
        '/api/v1/project-versions/version-1/stack-selection/',
        'POST',
      ),
    ).toHaveLength(1)
    expect(screen.getByRole('button', { name: 'در حال ثبت آمادگی...' })).toBeDisabled()

    releaseReadiness()
    expect(await screen.findByText('آمادگی شما ثبت شد')).toBeInTheDocument()
    expect(
      callsFor(api, '/api/v1/project-readiness/me/', 'POST'),
    ).toHaveLength(1)
  })

  it('keeps ReadyCheck lookup read-only and separate from readiness creation', async () => {
    const user = userEvent.setup()
    const api = installApi({ version: versionForPolicy('FIXED') })

    renderPage()
    await screen.findByText('Stack Alpha')
    await user.click(continueButton())
    await screen.findByText('آمادگی شما ثبت شد')

    expect(callsFor(api, '/api/v1/ready-checks/me/', 'GET')).toHaveLength(1)
    expect(
      api.mock.calls.filter(([input, request]) => {
        const url = new URL(String(input), 'http://frontend.test')
        return url.pathname.startsWith('/api/v1/ready-checks/') && request?.method === 'POST'
      }),
    ).toHaveLength(0)
  })

  it('renders only ALLOWLIST, restores the selected stack, and permits a valid change', async () => {
    const user = userEvent.setup()
    const api = installApi({
      version: versionForPolicy('ALLOWLIST', { selectedStack: stackAlpha }),
    })

    renderPage()

    expect(
      await screen.findByRole('heading', { name: 'Stack موردنظرت را انتخاب کن' }),
    ).toBeInTheDocument()
    expect(screen.getByText('ALLOWLIST')).toBeInTheDocument()
    expect(screen.queryByText('FIXED')).not.toBeInTheDocument()
    expect(screen.queryByText('OPEN')).not.toBeInTheDocument()
    const alpha = screen.getByRole('radio', { name: /Stack Alpha/ })
    const beta = screen.getByRole('radio', { name: /Stack Beta/ })
    expect(alpha).toBeChecked()

    await user.click(beta)
    expect(beta).toBeChecked()
    expect(continueButton()).toBeEnabled()
    await user.click(continueButton())

    await screen.findByText('آمادگی شما ثبت شد')
    const stackPost = callsFor(
      api,
      '/api/v1/project-versions/version-1/stack-selection/',
      'POST',
    )[0]
    expect(JSON.parse(String(stackPost?.[1]?.body))).toEqual({
      technology_stack_id: stackBeta.id,
    })
  })

  it('renders only OPEN and uses only contextual compatible choices', async () => {
    const user = userEvent.setup()
    installApi({
      version: versionForPolicy('OPEN', {
        compatibleStacks: [stackBeta, stackGamma],
        selectedStack: null,
      }),
    })

    renderPage()

    expect(
      await screen.findByRole('heading', {
        name: 'Stack سازگار پروفایلت را انتخاب کن',
      }),
    ).toBeInTheDocument()
    expect(screen.getByText('OPEN')).toBeInTheDocument()
    expect(screen.queryByText('FIXED')).not.toBeInTheDocument()
    expect(screen.queryByText('ALLOWLIST')).not.toBeInTheDocument()
    expect(screen.queryByText('Stack Alpha')).not.toBeInTheDocument()
    const onlyCompatibleChoice = screen.getByRole('radio', { name: /Stack Beta/ })
    expect(continueButton()).toBeDisabled()

    await user.click(onlyCompatibleChoice)
    expect(continueButton()).toBeEnabled()
  })

  it.each(['ALLOWLIST', 'OPEN'] as const)(
    'blocks %s when the API returns no available choices',
    async (policy) => {
      installApi({
        version: versionForPolicy(policy, {
          compatibleStacks: [],
          selectedStack: null,
        }),
      })

      renderPage()

      expect(
        await screen.findByRole('heading', {
          name: 'Stack قابل انتخابی در دسترس نیست',
        }),
      ).toBeInTheDocument()
      expect(continueButton()).toBeDisabled()
    },
  )

  it('confirms a stackless role with an empty payload and a NULL response', async () => {
    const user = userEvent.setup()
    const api = installApi({
      version: versionForPolicy(null, {
        compatibleStacks: [],
        configuredStacks: [],
        requiresStack: false,
        selectedStack: null,
      }),
    })

    renderPage()

    expect(
      await screen.findByRole('heading', {
        name: 'این نقش به Stack فنی نیاز ندارد',
      }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('radio')).not.toBeInTheDocument()
    await user.click(continueButton())
    expect(await screen.findByText('آمادگی شما ثبت شد')).toBeInTheDocument()
    const stackPost = callsFor(
      api,
      '/api/v1/project-versions/version-1/stack-selection/',
      'POST',
    )[0]
    expect(JSON.parse(String(stackPost?.[1]?.body))).toEqual({})
  })

  it('handles missing role, role requirement, and stack policy without fake choices', async () => {
    const missingRole = versionForPolicy('ALLOWLIST')
    missingRole.role_context = null
    const api = installApi({ version: missingRole })

    const firstRender = renderPage()
    expect(
      await screen.findByRole('heading', { name: 'نقش انتخابی پیدا نشد' }),
    ).toBeInTheDocument()
    firstRender.unmount()

    const missingRequirement = versionForPolicy('ALLOWLIST')
    missingRequirement.role_requirements = []
    api.mockImplementationOnce(async () => jsonResponse(missingRequirement))
    const secondRender = renderPage()
    expect(
      await screen.findByRole('heading', { name: 'نیازمندی نقش پیدا نشد' }),
    ).toBeInTheDocument()
    secondRender.unmount()

    const missingPolicy = versionForPolicy(null)
    api.mockImplementationOnce(async () => jsonResponse(missingPolicy))
    renderPage()
    expect(
      await screen.findByRole('heading', {
        name: 'سیاست Stack پشتیبانی نمی‌شود',
      }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('radio')).not.toBeInTheDocument()
  })

  it('confirms the exact version even when the template has a newer published version', async () => {
    const user = userEvent.setup()
    const api = installApi({
      currentVersionId: 'version-newer',
      version: versionForPolicy('FIXED'),
    })

    renderPage()

    expect(
      await screen.findByText('Stack Alpha'),
    ).toBeInTheDocument()
    expect(continueButton()).toBeEnabled()
    await user.click(continueButton())
    await screen.findByText('آمادگی شما ثبت شد')
    expect(api.mock.calls.some(([input]) => String(input).includes('/api/v1/projects/'))).toBe(false)
  })

  it('shows API errors and retries the exact-version load', async () => {
    const user = userEvent.setup()
    const api = installApi({
      exactFailureCount: 1,
      version: versionForPolicy('FIXED'),
    })

    renderPage()

    expect(
      await screen.findByRole('heading', {
        name: 'دریافت اطلاعات Stack ممکن نشد',
      }),
    ).toBeInTheDocument()
    expect(screen.getByText('سرور اکنون نمی‌تواند درخواست را انجام دهد. دوباره تلاش کنید.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'تلاش دوباره' }))
    expect(
      await screen.findByRole('heading', {
        name: 'Stack این نقش از قبل مشخص شده است',
      }),
    ).toBeInTheDocument()
    await waitFor(() =>
      expect(
        api.mock.calls.filter(([input]) =>
          String(input).includes('/api/v1/project-versions/version-1/'),
        ),
      ).toHaveLength(2),
    )
  })
})
