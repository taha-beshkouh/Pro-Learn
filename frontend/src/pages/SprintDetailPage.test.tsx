import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import type {
  ProjectWorkItem,
  SprintRunDetailResponse,
  SprintRunState,
  SprintSubmissionResponse,
  TeamMemberSnapshot,
} from '../lib/api/types'
import { SprintDetailPage } from './SprintDetailPage'

const role = {
  id: 'runtime-role-api',
  code: 'BACKEND_DEVELOPER',
  name: 'Runtime Role From API',
}
const stack = {
  id: 'runtime-stack-api',
  code: 'django-drf',
  name: 'Runtime Stack From API',
}

function member(id: string, email: string): TeamMemberSnapshot {
  return {
    id,
    user: { id: `user-${id}`, email },
    role,
    technology_stack: stack,
    ended_at: null,
  }
}

const currentMember = member('current-member-api', 'current-member@example.test')
const actualSubmitter = member('actual-submitter-api', 'actual-actor@example.test')
const legacyDesignated = member('legacy-designated-api', 'legacy-designated@example.test')

function workItem(
  id: string,
  title: string,
  overrides: Partial<ProjectWorkItem> = {},
): ProjectWorkItem {
  return {
    id,
    title,
    description: `${title} description from API`,
    position: 1,
    role: null,
    technology_stack: null,
    sprint_template: {
      id: 'sprint-template-route-api',
      sequence: 2,
      title: 'Sprint template from API',
    },
    ...overrides,
  }
}

function submission(
  overrides: Partial<SprintSubmissionResponse> = {},
): SprintSubmissionResponse {
  return {
    id: 'submission-api',
    submitted_by: actualSubmitter,
    evidence: 'Evidence from persisted submission API',
    submitted_at: '2026-09-18T11:30:00Z',
    ...overrides,
  }
}

function sprintDetail(
  state: SprintRunState,
  overrides: Partial<SprintRunDetailResponse> = {},
): SprintRunDetailResponse {
  const submissions =
    overrides.submissions ??
    (state === 'ACTIVE' || state === 'LOCKED' ? [] : [submission()])
  return {
    id: 'sprint-run-route-api',
    sprint_template_id: 'sprint-template-route-api',
    sequence: 2,
    title: 'Sprint title from Detail API',
    brief: 'Sprint brief from Detail API only.',
    state,
    planned_start_at: '2026-09-16T07:30:00Z',
    planned_end_at: '2026-09-23T07:30:00Z',
    opened_at: state === 'LOCKED' ? null : '2026-09-16T08:00:00Z',
    completed_at: state === 'COMPLETED' ? '2026-09-22T14:00:00Z' : null,
    designated_submitter: legacyDesignated,
    repository_url: 'https://github.com/prolearn/runtime-project',
    work_items: [
      workItem('shared-work-api', 'Shared Work From Detail API'),
      workItem('stack-work-api', 'Stack Work From Detail API', {
        role,
        technology_stack: stack,
        position: 2,
      }),
    ],
    latest_submission: submissions.at(-1) ?? null,
    submissions,
    ...overrides,
  }
}

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

type Failure = { status: number; data: unknown } | 'network'

function installApi({
  details = [sprintDetail('ACTIVE')],
  detailFailure,
  submitFailure,
  submitResponder,
}: {
  details?: unknown[]
  detailFailure?: Failure
  submitFailure?: { status: number; data: unknown }
  submitResponder?: () => Response | Promise<Response>
} = {}) {
  let detailIndex = 0
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, request?: RequestInit) => {
      const url = new URL(String(input), 'http://frontend.test')
      const method = request?.method ?? 'GET'

      if (
        method === 'GET' &&
        url.pathname.startsWith('/api/v1/project-runs/me/sprints/')
      ) {
        if (detailFailure === 'network') {
          throw new TypeError('private network diagnostic')
        }
        if (detailFailure) {
          return jsonResponse(detailFailure.data, detailFailure.status)
        }
        const detail = details[Math.min(detailIndex, details.length - 1)]
        detailIndex += 1
        return jsonResponse(detail)
      }

      if (
        method === 'GET' &&
        url.pathname === '/api/v1/project-runs/me/dashboard/'
      ) {
        return jsonResponse({ id: 'project-run-authoritative-api' })
      }

      if (method === 'GET' && url.pathname === '/api/v1/auth/csrf/') {
        return jsonResponse({ csrfToken: 'csrf-from-api' })
      }

      if (
        method === 'POST' &&
        url.pathname ===
          '/api/v1/project-runs/project-run-authoritative-api/sprints/sprint-run-route-api/submit/'
      ) {
        if (submitResponder) return submitResponder()
        if (submitFailure) {
          return jsonResponse(submitFailure.data, submitFailure.status)
        }
        return jsonResponse({ state: 'SUBMITTED' })
      }

      throw new Error(`Unexpected request: ${method} ${url.pathname}`)
    },
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function authValue(
  refreshSession: AuthContextValue['refreshSession'] = vi.fn(
    async () => undefined,
  ),
): AuthContextValue {
  return {
    status: 'authenticated',
    user: currentMember.user,
    error: null,
    refreshSession,
    logout: vi.fn(async () => undefined),
    authenticate: vi.fn(async () => undefined),
  }
}

function renderPage({
  sprintRunId = 'sprint-run-route-api',
  refreshSession = vi.fn(async () => undefined),
}: {
  sprintRunId?: string
  refreshSession?: AuthContextValue['refreshSession']
} = {}) {
  const router = createMemoryRouter(
    [{ path: '/workspace/sprints/:sprintRunId', element: <SprintDetailPage /> }],
    { initialEntries: [`/workspace/sprints/${sprintRunId}`] },
  )
  const rendered = render(
    <AuthContext.Provider value={authValue(refreshSession)}>
      <RouterProvider router={router} />
    </AuthContext.Provider>,
  )
  return { ...rendered, router, refreshSession }
}

function callsFor(fetchMock: ReturnType<typeof vi.fn>, path: string, method = 'GET') {
  return fetchMock.mock.calls.filter(([input, request]) => {
    const url = new URL(String(input), 'http://frontend.test')
    return url.pathname === path && (request?.method ?? 'GET') === method
  })
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('SprintDetailPage', () => {
  it('uses the route SprintRun id and renders API work without designation behavior', async () => {
    const fetchMock = installApi()
    const { container } = renderPage()

    expect(
      await screen.findByRole('heading', { name: 'Sprint title from Detail API' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Sprint brief from Detail API only.')).toBeInTheDocument()
    expect(screen.getByText('Shared Work From Detail API')).toBeInTheDocument()
    expect(screen.getByText('Stack Work From Detail API')).toBeInTheDocument()
    expect(
      screen.getByRole('link', {
        name: 'https://github.com/prolearn/runtime-project',
      }),
    ).toHaveAttribute('href', 'https://github.com/prolearn/runtime-project')
    expect(screen.getByText('هنوز ارسالی برای این اسپرینت ثبت نشده است.')).toBeInTheDocument()
    expect(screen.queryByText('legacy-designated@example.test')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'ثبت ارسال اسپرینت' })).toBeEnabled()
    expect(screen.getByRole('link', { name: 'بازگشت به Workspace' })).toHaveAttribute(
      'href',
      '/workspace',
    )

    expect(
      callsFor(
        fetchMock,
        '/api/v1/project-runs/me/sprints/sprint-run-route-api/',
      ),
    ).toHaveLength(1)
    expect(callsFor(fetchMock, '/api/v1/project-runs/me/dashboard/')).toHaveLength(0)
    expect(container.textContent).not.toContain('Work Not Returned By API')
    expect(container.textContent).not.toContain('designated')
    expect(container.querySelector('input[type="checkbox"]')).not.toBeInTheDocument()
    expect(container.querySelector('progress')).not.toBeInTheDocument()
    expect(container.querySelector('[aria-valuenow]')).not.toBeInTheDocument()
  })

  it('renders a same-run LOCKED Sprint and its work read-only', async () => {
    installApi({ details: [sprintDetail('LOCKED', { submissions: [] })] })
    renderPage()

    expect(await screen.findByText('وضعیت اسپرینت: قفل‌شده')).toBeInTheDocument()
    expect(screen.getByText(/این اسپرینت هنوز باز نشده است/)).toBeInTheDocument()
    expect(screen.getByText('Shared Work From Detail API')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /ارسال/ })).not.toBeInTheDocument()
    expect(screen.getByText('هنوز ارسالی برای این اسپرینت ثبت نشده است.')).toBeInTheDocument()
  })

  it.each<[SprintRunState, string]>([
    ['SUBMITTED', 'وضعیت اسپرینت: ارسال‌شده'],
    ['UNDER_REVIEW', 'وضعیت اسپرینت: در حال بررسی'],
    ['COMPLETED', 'وضعیت اسپرینت: تکمیل‌شده'],
  ])('keeps %s Sprint detail useful and read-only', async (state, status) => {
    installApi({ details: [sprintDetail(state)] })
    renderPage()

    expect(await screen.findByText(status)).toBeInTheDocument()
    expect(screen.getByText('Shared Work From Detail API')).toBeInTheDocument()
    expect(screen.getByText('actual-actor@example.test')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /ارسال/ })).not.toBeInTheDocument()
  })

  it('shows the latest persisted submission separately from immutable earlier history', async () => {
    const earlier = submission({
      id: 'earlier-submission-api',
      evidence: 'Earlier persisted evidence',
      submitted_at: '2026-09-17T11:30:00Z',
    })
    const latest = submission({
      id: 'latest-submission-api',
      evidence: 'Latest persisted evidence',
      submitted_at: '2026-09-18T11:30:00Z',
    })
    installApi({
      details: [
        sprintDetail('SUBMITTED', {
          latest_submission: latest,
          submissions: [earlier, latest],
        }),
      ],
    })
    renderPage()

    const latestRegion = await screen.findByLabelText('آخرین ارسال ثبت‌شده')
    expect(
      within(latestRegion).getByText('Latest persisted evidence'),
    ).toBeInTheDocument()
    expect(
      within(latestRegion).queryByText('Earlier persisted evidence'),
    ).not.toBeInTheDocument()
    expect(screen.getByText('Earlier persisted evidence')).toBeInTheDocument()
  })

  it('submits only evidence, then re-fetches authoritative Sprint detail', async () => {
    const refreshed = sprintDetail('SUBMITTED', {
      designated_submitter: null,
      submissions: [
        submission({
          id: 'new-submission-api',
          submitted_by: currentMember,
          evidence: 'Evidence typed by participant',
        }),
      ],
    })
    const fetchMock = installApi({
      details: [sprintDetail('ACTIVE'), refreshed],
    })
    const user = userEvent.setup()
    renderPage()

    await user.type(
      await screen.findByLabelText('مدرک یا توضیح ارسال'),
      'Evidence typed by participant',
    )
    await user.click(screen.getByRole('button', { name: 'ثبت ارسال اسپرینت' }))

    expect(
      await screen.findByText('ارسال اسپرینت ثبت شد و وضعیت تازه از سرور دریافت شد.'),
    ).toBeInTheDocument()
    expect(screen.getByText('وضعیت اسپرینت: ارسال‌شده')).toBeInTheDocument()
    expect(screen.getByText('current-member@example.test')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /ثبت ارسال/ })).not.toBeInTheDocument()

    const postCalls = callsFor(
      fetchMock,
      '/api/v1/project-runs/project-run-authoritative-api/sprints/sprint-run-route-api/submit/',
      'POST',
    )
    expect(postCalls).toHaveLength(1)
    expect(JSON.parse(String(postCalls[0][1]?.body))).toEqual({
      evidence: 'Evidence typed by participant',
    })
    expect(Object.keys(JSON.parse(String(postCalls[0][1]?.body)))).toEqual([
      'evidence',
    ])
    expect(callsFor(fetchMock, '/api/v1/project-runs/me/dashboard/')).toHaveLength(1)
    expect(
      callsFor(
        fetchMock,
        '/api/v1/project-runs/me/sprints/sprint-run-route-api/',
      ),
    ).toHaveLength(2)
  })

  it('supports resubmission for CHANGES_REQUESTED without using legacy designation', async () => {
    installApi({
      details: [
        sprintDetail('CHANGES_REQUESTED'),
        sprintDetail('SUBMITTED', { designated_submitter: null }),
      ],
    })
    const user = userEvent.setup()
    renderPage()

    expect(
      await screen.findByRole('button', { name: 'ثبت ارسال مجدد' }),
    ).toBeEnabled()
    await user.click(screen.getByRole('button', { name: 'ثبت ارسال مجدد' }))

    expect(
      await screen.findByText('ارسال مجدد ثبت شد و وضعیت تازه از سرور دریافت شد.'),
    ).toBeInTheDocument()
  })

  it('prevents duplicate submission requests while the first request is pending', async () => {
    let resolveSubmit: ((response: Response) => void) | undefined
    const pendingResponse = new Promise<Response>((resolve) => {
      resolveSubmit = resolve
    })
    const fetchMock = installApi({
      details: [sprintDetail('ACTIVE'), sprintDetail('SUBMITTED')],
      submitResponder: () => pendingResponse,
    })
    renderPage()

    const button = await screen.findByRole('button', { name: 'ثبت ارسال اسپرینت' })
    fireEvent.click(button)
    fireEvent.click(button)

    await waitFor(() => {
      expect(
        callsFor(
          fetchMock,
          '/api/v1/project-runs/project-run-authoritative-api/sprints/sprint-run-route-api/submit/',
          'POST',
        ),
      ).toHaveLength(1)
    })
    expect(screen.getByRole('button', { name: 'در حال ثبت...' })).toBeDisabled()
    resolveSubmit?.(jsonResponse({ state: 'SUBMITTED' }))
    await screen.findByText('وضعیت اسپرینت: ارسال‌شده')
  })

  it('maps a stale 409 safely and revalidates the Sprint state', async () => {
    const fetchMock = installApi({
      details: [
        sprintDetail('ACTIVE'),
        sprintDetail('SUBMITTED', {
          submissions: [submission({ evidence: 'Another member submitted first' })],
        }),
      ],
      submitFailure: {
        status: 409,
        data: { detail: 'private state transition diagnostic' },
      },
    })
    const user = userEvent.setup()
    renderPage()

    await user.click(
      await screen.findByRole('button', { name: 'ثبت ارسال اسپرینت' }),
    )

    expect(
      await screen.findByText(
        'وضعیت اسپرینت تغییر کرده و این ارسال دیگر مجاز نیست. اطلاعات تازه از سرور دریافت شد.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('وضعیت اسپرینت: ارسال‌شده')).toBeInTheDocument()
    expect(screen.getByText('Another member submitted first')).toBeInTheDocument()
    expect(screen.queryByText('private state transition diagnostic')).not.toBeInTheDocument()
    expect(
      callsFor(
        fetchMock,
        '/api/v1/project-runs/me/sprints/sprint-run-route-api/',
      ),
    ).toHaveLength(2)
  })

  it('handles zero work items and zero submissions as valid empty states', async () => {
    installApi({
      details: [
        sprintDetail('LOCKED', {
          repository_url: null,
          work_items: [],
          submissions: [],
        }),
      ],
    })
    renderPage()

    expect(
      await screen.findByRole('heading', {
        name: 'کار قابل‌نمایشی برای این اسپرینت وجود ندارد',
      }),
    ).toBeInTheDocument()
    expect(screen.getByText('هنوز ارسالی برای این اسپرینت ثبت نشده است.')).toBeInTheDocument()
    expect(
      screen.getByText('مخزن پروژه در حال آماده‌سازی توسط تیم PROLEARN است.'),
    ).toBeInTheDocument()
  })

  it.each([
    {
      name: 'permission response',
      failure: { status: 403, data: { detail: 'private permission diagnostic' } } as Failure,
      message: 'اجازه دسترسی به این اسپرینت برای حساب شما وجود ندارد.',
      raw: 'private permission diagnostic',
    },
    {
      name: 'network failure',
      failure: 'network' as Failure,
      message: 'ارتباط با سرور برقرار نشد. اتصال اینترنت را بررسی و دوباره تلاش کنید.',
      raw: 'private network diagnostic',
    },
  ])('maps a $name without exposing raw diagnostics', async ({ failure, message, raw }) => {
    installApi({ detailFailure: failure })
    renderPage()

    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(screen.queryByText(raw)).not.toBeInTheDocument()
  })

  it('reconciles a 401 with auth state', async () => {
    installApi({
      detailFailure: { status: 401, data: { detail: 'private auth diagnostic' } },
    })
    const { refreshSession } = renderPage()

    expect(
      await screen.findByText('نشست شما پایان یافته است. برای ادامه دوباره وارد شوید.'),
    ).toBeInTheDocument()
    await waitFor(() => expect(refreshSession).toHaveBeenCalledTimes(1))
    expect(screen.queryByText('private auth diagnostic')).not.toBeInTheDocument()
  })

  it('treats invalid or inaccessible SprintRun ids as a safe 404 state', async () => {
    const fetchMock = installApi({
      detailFailure: { status: 404, data: { detail: 'Sprint not found.' } },
    })
    renderPage({ sprintRunId: 'guessed-other-run-id' })

    expect(
      await screen.findByRole('heading', { name: 'اسپرینت قابل دسترسی نیست' }),
    ).toBeInTheDocument()
    expect(screen.queryByText('Sprint not found.')).not.toBeInTheDocument()
    expect(
      callsFor(
        fetchMock,
        '/api/v1/project-runs/me/sprints/guessed-other-run-id/',
      ),
    ).toHaveLength(1)
  })

  it('rejects malformed Sprint detail instead of rendering partial runtime truth', async () => {
    installApi({ details: [{ ...sprintDetail('ACTIVE'), work_items: undefined }] })
    renderPage()

    expect(
      await screen.findByText(
        'اطلاعات اسپرینت با قرارداد فعلی SprintRun هماهنگ نیست. صفحه را دوباره بارگذاری کنید.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText('Sprint title from Detail API')).not.toBeInTheDocument()
  })

  it('re-fetches Sprint detail after a direct remount', async () => {
    const fetchMock = installApi()
    const first = renderPage()
    await screen.findByRole('heading', { name: 'Sprint title from Detail API' })
    first.unmount()

    renderPage()
    await screen.findByRole('heading', { name: 'Sprint title from Detail API' })

    expect(
      callsFor(
        fetchMock,
        '/api/v1/project-runs/me/sprints/sprint-run-route-api/',
      ),
    ).toHaveLength(2)
  })
})
