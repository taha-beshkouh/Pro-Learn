import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import type {
  CurrentProjectRunSummary,
  ProjectVersionDetailResponse,
  ReadyCheckResponse,
} from '../lib/api/types'
import { ReadyCheckPage } from './ReadyCheckPage'

const role = {
  id: 'role-from-api',
  code: 'FRONTEND_DEVELOPER',
  name: 'نقش رابط از API',
}

const stack = {
  id: 'stack-from-api',
  code: 'react-typescript',
  name: 'React API Stack',
}

function projectVersion(): ProjectVersionDetailResponse {
  return {
    project_template: {
      id: 'template-from-api',
      slug: 'api-project',
      name: 'پروژه دقیق از API',
      level: { id: 'level-api', number: 2, name: 'سطح API' },
    },
    id: 'version-from-api',
    version_number: 7,
    summary: 'خلاصه‌ای که فقط پاسخ نسخه دقیق API فراهم کرده است.',
    full_description: '',
    duration_weeks: 6,
    sprint_count: 6,
    weekly_effort_hours_min: 10,
    weekly_effort_hours_max: 12,
    participant_database: 'PostgreSQL',
    published_at: '2026-09-01T00:00:00Z',
    sprint_templates: Array.from({ length: 6 }, (_, index) => ({
      id: `sprint-${index + 1}`,
      sequence: index + 1,
      title: `Sprint ${index + 1}`,
      brief: '',
      planned_start_offset_days: index * 7,
      planned_duration_days: 7,
      planned_end_offset_days: (index + 1) * 7,
    })),
    role_requirements: [],
    work_items: [],
    role_context: null,
    shared_work_items: [],
  }
}

function pendingReadyCheck(
  overrides: Partial<ReadyCheckResponse> = {},
): ReadyCheckResponse {
  const startedAt = Date.now() - 60 * 60 * 1_000
  return {
    formation_id: 'formation-from-api',
    project_version_id: 'version-from-api',
    project_name: 'پروژه دقیق از API',
    id: 'ready-check-from-api',
    user: { id: 'user-from-api', email: 'participant-from-api@example.test' },
    role,
    technology_stack: stack,
    github_username: 'frontend-contributor',
    status: 'PENDING',
    effective_status: 'PENDING',
    is_current: true,
    started_at: new Date(startedAt).toISOString(),
    expires_at: new Date(startedAt + 48 * 60 * 60 * 1_000).toISOString(),
    responded_at: null,
    ...overrides,
  }
}

function confirmedReadyCheck(base = pendingReadyCheck()): ReadyCheckResponse {
  return {
    ...base,
    status: 'CONFIRMED',
    effective_status: 'CONFIRMED',
    responded_at: new Date().toISOString(),
  }
}

function declinedReadyCheck(base = pendingReadyCheck()): ReadyCheckResponse {
  return {
    ...base,
    status: 'DECLINED',
    effective_status: 'DECLINED',
    responded_at: new Date().toISOString(),
  }
}

function activeProjectRun(): CurrentProjectRunSummary {
  return {
    id: 'run-from-api',
    project: {
      id: 'template-from-api',
      name: 'پروژه دقیق از API',
      version_id: 'version-from-api',
      version_number: 7,
      summary: 'ProjectRun summary',
    },
    state: 'ACTIVE',
    started_at: '2026-09-08T12:00:00Z',
    deadline_at: '2026-10-20T12:00:00Z',
    ended_at: null,
  }
}

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

type HttpFailure = { data: unknown; status: number } | 'network'

type ApiOptions = {
  actionFailure?: HttpFailure
  check?: ReadyCheckResponse
  confirmGate?: Promise<void>
  csrfFailure?: HttpFailure
  project?: ProjectVersionDetailResponse
  readyCheckSequence?: ReadyCheckResponse[]
  run?: CurrentProjectRunSummary | null
  runAfterConfirm?: CurrentProjectRunSummary | null
}

function installApi({
  actionFailure,
  check = pendingReadyCheck(),
  confirmGate,
  csrfFailure,
  project = projectVersion(),
  readyCheckSequence,
  run = null,
  runAfterConfirm = null,
}: ApiOptions = {}) {
  let currentCheck = check
  let currentRun = run
  let readyCheckRequests = 0

  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, request?: RequestInit) => {
      const url = new URL(String(input), 'http://frontend.test')

      if (url.pathname === '/api/v1/ready-checks/me/') {
        const sequenced = readyCheckSequence?.[
          Math.min(readyCheckRequests, readyCheckSequence.length - 1)
        ]
        readyCheckRequests += 1
        if (sequenced) currentCheck = sequenced
        return jsonResponse([currentCheck])
      }

      if (url.pathname === '/api/v1/project-runs/me/dashboard/') {
        return currentRun
          ? jsonResponse(currentRun)
          : jsonResponse({ detail: 'Active project run not found.' }, 404)
      }

      if (url.pathname === '/api/v1/project-versions/version-from-api/') {
        return jsonResponse(project)
      }

      if (url.pathname === '/api/v1/auth/csrf/') {
        if (csrfFailure === 'network') throw new TypeError('Network unavailable')
        if (csrfFailure) return jsonResponse(csrfFailure.data, csrfFailure.status)
        return jsonResponse({ csrfToken: 'csrf-from-api' })
      }

      const isConfirm =
        url.pathname ===
          '/api/v1/ready-checks/ready-check-from-api/confirm/' &&
        request?.method === 'POST'
      const isDecline =
        url.pathname ===
          '/api/v1/ready-checks/ready-check-from-api/decline/' &&
        request?.method === 'POST'

      if (isConfirm || isDecline) {
        if (actionFailure === 'network') throw new TypeError('Network unavailable')
        if (actionFailure) {
          return jsonResponse(actionFailure.data, actionFailure.status)
        }
        const submitted = request?.body
          ? (JSON.parse(String(request.body)) as { github_username?: string })
          : {}
        currentCheck = isConfirm
          ? confirmedReadyCheck({
              ...currentCheck,
              github_username:
                submitted.github_username ?? currentCheck.github_username,
            })
          : declinedReadyCheck(currentCheck)
        if (isConfirm) {
          currentRun = runAfterConfirm
          if (confirmGate) await confirmGate
        }
        return jsonResponse(currentCheck)
      }

      return jsonResponse({ detail: `Unexpected endpoint: ${url.pathname}` }, 404)
    },
  )

  vi.stubGlobal('fetch', fetchMock)
  return {
    fetchMock,
    readyCheckRequestCount: () => readyCheckRequests,
  }
}

function renderPage(refreshSession = vi.fn(async () => undefined)) {
  const auth: AuthContextValue = {
    status: 'authenticated',
    user: { id: 'user-from-api', email: 'participant-from-api@example.test' },
    error: null,
    refreshSession,
    logout: vi.fn(async () => undefined),
    authenticate: vi.fn(async () => undefined),
  }
  const rendered = render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={['/ready-check']}>
        <ReadyCheckPage />
      </MemoryRouter>
    </AuthContext.Provider>,
  )
  return { ...rendered, refreshSession }
}

function callsFor(
  fetchMock: ReturnType<typeof vi.fn>,
  path: string,
  method?: string,
) {
  return fetchMock.mock.calls.filter(([input, request]) => {
    const url = new URL(String(input), 'http://frontend.test')
    return url.pathname === path && (!method || request?.method === method)
  })
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('ReadyCheckPage', () => {
  it('loads the authenticated page from the real contracts and renders only API project/member data', async () => {
    const { fetchMock } = installApi()
    const { container } = renderPage()

    expect(
      await screen.findByRole('heading', {
        name: 'تأیید نهایی پیش از شروع پروژه',
      }),
    ).toBeInTheDocument()
    expect(screen.getByText('پروژه دقیق از API')).toBeInTheDocument()
    expect(screen.getByText('سطح API')).toBeInTheDocument()
    expect(screen.getAllByText('نقش رابط از API').length).toBeGreaterThan(0)
    expect(screen.getByText('React API Stack')).toBeInTheDocument()
    expect(
      screen.getByText('participant-from-api@example.test'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('اطلاعات این بخش فعلاً در دسترس نیست.'),
    ).toBeInTheDocument()
    expect(container.querySelector('img')).not.toBeInTheDocument()
    expect(container.querySelector('[class*="avatar"]')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Dashboard' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Profile' })).not.toBeInTheDocument()

    expect(callsFor(fetchMock, '/api/v1/ready-checks/me/')).toHaveLength(1)
    expect(
      callsFor(fetchMock, '/api/v1/project-versions/version-from-api/'),
    ).toHaveLength(1)
    expect(
      callsFor(fetchMock, '/api/v1/project-runs/me/dashboard/'),
    ).toHaveLength(1)
  })

  it('derives the countdown from backend expires_at instead of starting a new 48-hour deadline', async () => {
    const now = Date.parse('2026-09-08T12:00:00Z')
    vi.spyOn(Date, 'now').mockReturnValue(now)
    const check = pendingReadyCheck({
      started_at: '2026-09-06T16:30:00Z',
      expires_at: '2026-09-08T16:30:00Z',
    })
    installApi({ check })
    renderPage()

    expect(await screen.findByTestId('ready-check-countdown')).toHaveTextContent(
      '۴ ساعت و ۳۰ دقیقه',
    )
    expect(screen.getByTestId('ready-check-countdown')).not.toHaveTextContent(
      '۴۸ ساعت',
    )
    expect(
      screen.getByText(
        'این شمارش فقط برای نمایش است؛ وضعیت و امکان ثبت پاسخ را سرور تعیین می‌کند.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
    expect(screen.getByText(/مهلت ثبت‌شده در سرور/)).toBeInTheDocument()
  })

  it('calls the real confirm endpoint once, sends no timing payload, and shows the confirmed waiting state', async () => {
    let releaseConfirm: () => void = () => {}
    const confirmGate = new Promise<void>((resolve) => {
      releaseConfirm = resolve
    })
    const { fetchMock } = installApi({ confirmGate })
    const user = userEvent.setup()
    renderPage()

    const confirm = await screen.findByRole('button', {
      name: 'تأیید مشارکت',
    })
    await user.click(confirm)
    expect(confirm).toBeDisabled()
    await user.click(confirm)

    await waitFor(() =>
      expect(
        callsFor(
          fetchMock,
          '/api/v1/ready-checks/ready-check-from-api/confirm/',
          'POST',
        ),
      ).toHaveLength(1),
    )
    const confirmCall = callsFor(
      fetchMock,
      '/api/v1/ready-checks/ready-check-from-api/confirm/',
      'POST',
    )[0]
    expect(JSON.parse(String(confirmCall[1]?.body))).toEqual({})

    releaseConfirm()
    expect(
      await screen.findByRole('heading', { name: 'تأیید شما ثبت شد' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/منتظر پاسخ سایر اعضای تیم هستیم/),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'تأیید مشارکت' }),
    ).not.toBeInTheDocument()
  })

  it('prefills an existing profile GitHub username without requiring re-entry', async () => {
    installApi({
      check: pendingReadyCheck({ github_username: 'existing-profile-user' }),
    })
    renderPage()

    const input = await screen.findByLabelText(/نام کاربری GitHub/)
    await waitFor(() => expect(input).toHaveValue('existing-profile-user'))
    expect(screen.getByRole('button', { name: 'تأیید مشارکت' })).toBeEnabled()
  })

  it('requires a valid GitHub username for a Developer and sends only that field', async () => {
    const user = userEvent.setup()
    const { fetchMock } = installApi({
      check: pendingReadyCheck({ github_username: null }),
    })
    renderPage()

    const confirm = await screen.findByRole('button', { name: 'تأیید مشارکت' })
    expect(confirm).toBeDisabled()
    await user.type(screen.getByLabelText(/نام کاربری GitHub/), 'new-developer')
    expect(confirm).toBeEnabled()
    await user.click(confirm)

    await waitFor(() =>
      expect(
        callsFor(
          fetchMock,
          '/api/v1/ready-checks/ready-check-from-api/confirm/',
          'POST',
        ),
      ).toHaveLength(1),
    )
    const call = callsFor(
      fetchMock,
      '/api/v1/ready-checks/ready-check-from-api/confirm/',
      'POST',
    )[0]
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      github_username: 'new-developer',
    })
  })

  it('keeps GitHub username optional for Product Designer confirmation', async () => {
    const user = userEvent.setup()
    const { fetchMock } = installApi({
      check: pendingReadyCheck({
        github_username: null,
        role: {
          id: 'designer-role',
          code: 'PRODUCT_DESIGNER',
          name: 'Product Designer',
        },
        technology_stack: null,
      }),
    })
    renderPage()

    const confirm = await screen.findByRole('button', { name: 'تأیید مشارکت' })
    expect(confirm).toBeEnabled()
    await user.click(confirm)

    await waitFor(() =>
      expect(
        callsFor(
          fetchMock,
          '/api/v1/ready-checks/ready-check-from-api/confirm/',
          'POST',
        ),
      ).toHaveLength(1),
    )
    const call = callsFor(
      fetchMock,
      '/api/v1/ready-checks/ready-check-from-api/confirm/',
      'POST',
    )[0]
    expect(JSON.parse(String(call[1]?.body))).toEqual({})
  })

  it('requires a confirmation step and then calls the real decline endpoint without a timing payload', async () => {
    const { fetchMock } = installApi()
    const user = userEvent.setup()
    renderPage()

    await user.click(
      await screen.findByRole('button', { name: 'رد مشارکت' }),
    )
    expect(
      screen.getByText('رد مشارکت را ثبت می‌کنید؟'),
    ).toBeInTheDocument()
    expect(screen.getByText(/از Formation جاری کنار می‌روید/)).toBeInTheDocument()
    expect(screen.getByText(/هنوز ProjectRun فعالی شروع نشده است/)).toBeInTheDocument()
    expect(
      callsFor(
        fetchMock,
        '/api/v1/ready-checks/ready-check-from-api/decline/',
        'POST',
      ),
    ).toHaveLength(0)

    await user.click(screen.getByRole('button', { name: 'بله، رد می‌کنم' }))
    expect(
      await screen.findByRole('heading', { name: 'رد شده' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'رد مشارکت' })).not.toBeInTheDocument()
    const declineCall = callsFor(
      fetchMock,
      '/api/v1/ready-checks/ready-check-from-api/decline/',
      'POST',
    )[0]
    expect(declineCall).toBeDefined()
    expect(declineCall[1]?.body).toBeUndefined()
  })

  it('uses effective_status to block both actions for an expired Ready Check', async () => {
    const check = pendingReadyCheck({
      effective_status: 'EXPIRED',
      expires_at: '2026-09-01T00:00:00Z',
    })
    const { fetchMock } = installApi({ check })
    const user = userEvent.setup()
    renderPage()

    expect(
      await screen.findByRole('heading', { name: 'مهلت تمام شده' }),
    ).toBeInTheDocument()
    const confirm = screen.getByRole('button', { name: 'تأیید مشارکت' })
    const decline = screen.getByRole('button', { name: 'رد مشارکت' })
    expect(confirm).toBeDisabled()
    expect(decline).toBeDisabled()
    await user.click(confirm)
    await user.click(decline)
    expect(
      callsFor(
        fetchMock,
        '/api/v1/ready-checks/ready-check-from-api/confirm/',
        'POST',
      ),
    ).toHaveLength(0)
  })

  it('revalidates backend state when the display countdown reaches zero', async () => {
    const expiry = new Date(Date.now() + 80).toISOString()
    const pending = pendingReadyCheck({
      started_at: new Date(Date.parse(expiry) - 48 * 60 * 60 * 1_000).toISOString(),
      expires_at: expiry,
    })
    const expired = { ...pending, effective_status: 'EXPIRED' as const }
    const api = installApi({ readyCheckSequence: [pending, expired] })
    renderPage()

    await screen.findByRole('heading', {
      name: 'تأیید نهایی پیش از شروع پروژه',
    })
    await waitFor(
      () => expect(api.readyCheckRequestCount()).toBeGreaterThanOrEqual(2),
      { timeout: 2_000 },
    )
    expect(
      await screen.findByRole('heading', { name: 'مهلت تمام شده' }),
    ).toBeInTheDocument()
  })

  it('shows the authoritative ProjectRun-created state and never implies waiting for the full 48 hours', async () => {
    installApi({
      check: confirmedReadyCheck(),
      run: activeProjectRun(),
    })
    renderPage()

    expect(
      await screen.findByRole('heading', { name: 'پروژه شروع شده است' }),
    ).toBeInTheDocument()
    expect(screen.getAllByText(/ProjectRun.*ACTIVE/).length).toBeGreaterThan(0)
    expect(
      screen.getByText(/لازم نیست تا پایان ۴۸ ساعت صبر کنید/),
    ).toBeInTheDocument()
    expect(screen.queryByText(/پروژه پس از ۴۸ ساعت شروع/)).not.toBeInTheDocument()
  })

  it('revalidates ProjectRun state after a successful last-member confirmation', async () => {
    const { fetchMock } = installApi({ runAfterConfirm: activeProjectRun() })
    const user = userEvent.setup()
    renderPage()

    await user.click(
      await screen.findByRole('button', { name: 'تأیید مشارکت' }),
    )
    expect(
      await screen.findByRole('heading', { name: 'پروژه شروع شده است' }),
    ).toBeInTheDocument()
    expect(
      callsFor(fetchMock, '/api/v1/project-runs/me/dashboard/').length,
    ).toBeGreaterThanOrEqual(2)
  })

  it.each([
    {
      name: 'expired validation',
      actionFailure: {
        status: 400,
        data: { ready_check: ['This Ready Check has expired.'] },
      } as HttpFailure,
      expected: 'مهلت پاسخ این Ready Check به پایان رسیده است.',
    },
    {
      name: 'wrong object access',
      actionFailure: {
        status: 404,
        data: { detail: 'Ready check not found.' },
      } as HttpFailure,
      expected: 'این Ready Check برای حساب شما پیدا نشد',
    },
    {
      name: 'already responded state',
      actionFailure: {
        status: 400,
        data: { ready_check: ['This Ready Check is no longer pending.'] },
      } as HttpFailure,
      expected: 'این Ready Check قبلاً پاسخ داده شده',
    },
    {
      name: 'state conflict',
      actionFailure: {
        status: 409,
        data: { detail: 'The team cannot be started from this formation.' },
      } as HttpFailure,
      expected: 'وضعیت تشکیل تیم هم‌زمان تغییر کرده است.',
    },
    {
      name: 'network failure',
      actionFailure: 'network' as HttpFailure,
      expected: 'ارتباط با سرور برقرار نشد.',
    },
  ])('maps $name to a useful Persian action error', async ({ actionFailure, expected }) => {
    installApi({ actionFailure })
    const user = userEvent.setup()
    renderPage()

    await user.click(
      await screen.findByRole('button', { name: 'تأیید مشارکت' }),
    )
    expect(await screen.findByText(new RegExp(expected))).toBeInTheDocument()
  })

  it('maps authentication and CSRF failures without exposing raw backend errors', async () => {
    const refreshSession = vi.fn(async () => undefined)
    installApi({
      csrfFailure: {
        status: 403,
        data: { detail: 'CSRF Failed: CSRF token missing.' },
      },
    })
    const user = userEvent.setup()
    renderPage(refreshSession)

    await user.click(
      await screen.findByRole('button', { name: 'تأیید مشارکت' }),
    )
    expect(
      await screen.findByText('اعتبار امنیتی درخواست تأیید نشد. دوباره تلاش کنید.'),
    ).toBeInTheDocument()
    expect(screen.queryByText(/CSRF Failed/)).not.toBeInTheDocument()
  })

  it('refreshes the auth session when an action receives 401', async () => {
    const refreshSession = vi.fn(async () => undefined)
    installApi({
      actionFailure: {
        status: 401,
        data: { detail: 'Authentication credentials were not provided.' },
      },
    })
    const user = userEvent.setup()
    renderPage(refreshSession)

    await user.click(
      await screen.findByRole('button', { name: 'تأیید مشارکت' }),
    )
    expect(
      await screen.findByText('نشست شما پایان یافته است. دوباره وارد شوید.'),
    ).toBeInTheDocument()
    await waitFor(() => expect(refreshSession).toHaveBeenCalledTimes(1))
  })

  it('styles the primary action through the Ready Check token class, not inline color', async () => {
    installApi()
    renderPage()

    await screen.findByRole('heading', {
      name: 'تأیید نهایی پیش از شروع پروژه',
    })
    const confirm = screen.getByRole('button', { name: 'تأیید مشارکت' })
    expect(confirm).toHaveClass('ready-check__confirm-button')
    expect(confirm).not.toHaveAttribute('style')
  })
})
