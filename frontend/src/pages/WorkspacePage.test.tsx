import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {
  createMemoryRouter,
  MemoryRouter,
  RouterProvider,
} from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import type {
  ProjectRunWorkspaceResponse,
  ProjectWorkItem,
  SprintRunResponse,
  SprintRunState,
  TeamMemberSnapshot,
} from '../lib/api/types'
import { DashboardPage } from './DashboardPage'
import { WorkspacePage } from './WorkspacePage'

const role = {
  id: 'runtime-role-id',
  code: 'BACKEND_DEVELOPER',
  name: 'Runtime Role From Workspace API',
}
const stack = {
  id: 'runtime-stack-id',
  code: 'django-drf',
  name: 'Runtime Stack From Workspace API',
}

function member(
  id: string,
  email: string,
  memberRole = role,
  memberStack: TeamMemberSnapshot['technology_stack'] = stack,
): TeamMemberSnapshot {
  return {
    id,
    user: { id: `user-${id}`, email },
    role: memberRole,
    technology_stack: memberStack,
    ended_at: null,
  }
}

const membership = member('current-membership', 'current-member@example.test')

function sprint(
  sequence: number,
  state: SprintRunState,
  overrides: Partial<SprintRunResponse> = {},
): SprintRunResponse {
  return {
    id: `sprint-run-${sequence}-api`,
    sprint_template_id: `sprint-template-${sequence}-api`,
    sequence,
    title: `Sprint ${sequence} title from API`,
    brief: `Sprint ${sequence} brief from API`,
    state,
    planned_start_at: `2026-09-${String(9 + sequence).padStart(2, '0')}T07:30:00Z`,
    planned_end_at: `2026-09-${String(16 + sequence).padStart(2, '0')}T07:30:00Z`,
    opened_at: state === 'LOCKED' ? null : '2026-09-10T07:30:00Z',
    completed_at: state === 'COMPLETED' ? '2026-09-16T07:30:00Z' : null,
    designated_submitter: null,
    ...overrides,
  }
}

function resource(
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
    sprint_template: null,
    ...overrides,
  }
}

function workspace(
  overrides: Partial<ProjectRunWorkspaceResponse> = {},
): ProjectRunWorkspaceResponse {
  const sprints = [
    sprint(1, 'COMPLETED'),
    sprint(2, 'ACTIVE'),
    sprint(3, 'LOCKED'),
  ]
  const resources = [
    resource('shared-sprint-work', 'Shared Sprint Work From API', {
      position: 10,
      sprint_template: {
        id: sprints[0].sprint_template_id,
        sequence: sprints[0].sequence,
        title: sprints[0].title,
      },
    }),
    resource('role-work', 'Role Work From API', {
      position: 20,
      role,
      sprint_template: {
        id: sprints[1].sprint_template_id,
        sequence: sprints[1].sequence,
        title: sprints[1].title,
      },
    }),
    resource('stack-work', 'Stack Work From API', {
      position: 30,
      role,
      technology_stack: stack,
      sprint_template: {
        id: sprints[1].sprint_template_id,
        sequence: sprints[1].sequence,
        title: sprints[1].title,
      },
    }),
    resource('shared-project-work', 'Shared Project Work From API', {
      position: 40,
    }),
  ]

  return {
    id: 'project-run-workspace-api',
    project: {
      id: 'project-template-workspace-api',
      name: 'Workspace Project From API',
      version_id: 'exact-project-version-workspace-api',
      version_number: 9,
      summary: 'Workspace project summary from the runtime API.',
    },
    state: 'ACTIVE',
    started_at: '2026-09-09T07:30:00Z',
    deadline_at: '2026-10-21T07:30:00Z',
    ended_at: null,
    membership,
    current_sprint: sprints[1],
    deadline: '2026-10-21T07:30:00Z',
    team: [
      membership,
      member(
        'frontend-membership',
        'frontend-member@example.test',
        { id: 'frontend-role', code: 'FRONTEND_DEVELOPER', name: 'Frontend Runtime Role' },
        { id: 'frontend-stack', code: 'react', name: 'React Runtime Stack' },
      ),
      member(
        'designer-membership',
        'designer-member@example.test',
        { id: 'designer-role', code: 'PRODUCT_DESIGNER', name: 'Designer Runtime Role' },
        null,
      ),
    ],
    next_action: 'SUBMIT_SPRINT',
    repository_url: null,
    sprints,
    resources,
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
  workspaceData = workspace(),
  failure,
  includeDashboard = false,
}: {
  workspaceData?: unknown
  failure?: Failure
  includeDashboard?: boolean
} = {}) {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, request?: RequestInit) => {
      const url = new URL(String(input), 'http://frontend.test')
      const method = request?.method ?? 'GET'
      if (method !== 'GET') throw new Error(`Unexpected mutation: ${method}`)

      if (url.pathname === '/api/v1/project-runs/me/workspace/') {
        if (failure === 'network') throw new TypeError('private network diagnostic')
        if (failure) return jsonResponse(failure.data, failure.status)
        return jsonResponse(workspaceData)
      }

      if (includeDashboard && url.pathname === '/api/v1/project-runs/me/dashboard/') {
        return jsonResponse(workspaceData)
      }
      if (includeDashboard && url.pathname === '/api/v1/project-runs/me/sprints/') {
        return jsonResponse((workspaceData as ProjectRunWorkspaceResponse).sprints)
      }
      if (
        includeDashboard &&
        url.pathname === '/api/v1/project-versions/exact-project-version-workspace-api/'
      ) {
        return jsonResponse({
          project_template: {
            id: 'project-template-workspace-api',
            slug: 'workspace-project',
            name: 'Workspace Project From API',
            level: { id: 'level-api', number: 1, name: 'Level From API' },
          },
          id: 'exact-project-version-workspace-api',
          version_number: 9,
          summary: '',
          full_description: '',
          duration_weeks: 6,
          sprint_count: 3,
          weekly_effort_hours_min: 8,
          weekly_effort_hours_max: 12,
          participant_database: '',
          published_at: '2026-09-01T00:00:00Z',
          sprint_templates: [],
          role_requirements: [],
          work_items: [],
          role_context: null,
          shared_work_items: [],
        })
      }

      throw new Error(`Unexpected request: ${method} ${url.pathname}`)
    },
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function authValue(refreshSession = vi.fn(async () => undefined)): AuthContextValue {
  return {
    status: 'authenticated',
    user: membership.user,
    error: null,
    refreshSession,
    logout: vi.fn(async () => undefined),
    authenticate: vi.fn(async () => undefined),
  }
}

function renderPage(refreshSession = vi.fn(async () => undefined)) {
  const rendered = render(
    <AuthContext.Provider value={authValue(refreshSession)}>
      <MemoryRouter initialEntries={['/workspace']}>
        <WorkspacePage />
      </MemoryRouter>
    </AuthContext.Provider>,
  )
  return { ...rendered, refreshSession }
}

function callsFor(fetchMock: ReturnType<typeof vi.fn>, path: string) {
  return fetchMock.mock.calls.filter(([input]) => {
    const url = new URL(String(input), 'http://frontend.test')
    return url.pathname === path
  })
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('WorkspacePage', () => {
  it('renders exact runtime identity, Sprint state, Team snapshots, and every API-visible work item', async () => {
    const fetchMock = installApi()
    const { container } = renderPage()

    expect(
      await screen.findByRole('heading', { name: 'Workspace Project From API' }),
    ).toBeInTheDocument()
    expect(screen.getByText('وضعیت ProjectRun: فعال')).toBeInTheDocument()
    expect(screen.getAllByText(role.name).length).toBeGreaterThan(0)
    expect(screen.getAllByText(stack.name).length).toBeGreaterThan(0)
    expect(screen.getByText('exact-project-version-workspace-api')).toBeInTheDocument()
    expect(screen.getByText('نسخه ۹')).toBeInTheDocument()

    expect(screen.getByText('اسپرینت ۲ از ۳')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Sprint 2 title from API' }),
    ).toBeInTheDocument()
    expect(screen.getByText('وضعیت اسپرینت: فعال')).toBeInTheDocument()
    expect(screen.getByText('فعال · جاری')).toBeInTheDocument()
    expect(screen.getByText('تکمیل‌شده')).toBeInTheDocument()
    expect(screen.getByText('قفل‌شده')).toBeInTheDocument()

    expect(screen.getByRole('heading', { name: 'کارهای مشترک تیم' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'کارهای مرتبط با نقش شما' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'کارهای مرتبط با Stack شما' })).toBeInTheDocument()
    for (const title of [
      'Shared Sprint Work From API',
      'Role Work From API',
      'Stack Work From API',
      'Shared Project Work From API',
    ]) {
      expect(screen.getByRole('heading', { name: title })).toBeInTheDocument()
    }
    expect(container.textContent).not.toContain('Work Not Returned By API')

    for (const email of [
      'current-member@example.test',
      'frontend-member@example.test',
      'designer-member@example.test',
    ]) {
      expect(screen.getByText(email)).toBeInTheDocument()
    }

    expect(
      screen.getByRole('link', { name: 'مشاهده جزئیات همین اسپرینت' }),
    ).toHaveAttribute('href', '/workspace/sprints/sprint-run-2-api')
    expect(
      screen.getByRole('link', { name: /Sprint 3 title from API/ }),
    ).toHaveAttribute('href', '/workspace/sprints/sprint-run-3-api')

    expect(container.querySelector('input[type="checkbox"]')).not.toBeInTheDocument()
    expect(container.querySelector('progress')).not.toBeInTheDocument()
    expect(container.querySelector('[aria-valuenow]')).not.toBeInTheDocument()
    expect(container.querySelector('img')).not.toBeInTheDocument()
    expect(container.querySelector('a[href^="http"]')).not.toBeInTheDocument()
    expect(container.textContent).not.toContain('%')
    expect(container.textContent).not.toContain('Recent Activity')

    expect(callsFor(fetchMock, '/api/v1/project-runs/me/workspace/')).toHaveLength(1)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(callsFor(fetchMock, '/api/v1/profile/')).toHaveLength(0)
    expect(callsFor(fetchMock, '/api/v1/project-runs/me/sprints/')).toHaveLength(0)
    expect(callsFor(fetchMock, '/api/v1/project-runs/me/dashboard/')).toHaveLength(0)
  })

  it('treats empty work, Team, and Sprint collections as valid empty states', async () => {
    installApi({
      workspaceData: workspace({
        membership: { ...membership, technology_stack: null },
        current_sprint: null,
        sprints: [],
        resources: [],
        team: [],
        next_action: 'NO_SPRINT_AVAILABLE',
      }),
    })
    renderPage()

    expect(
      await screen.findByRole('heading', { name: 'Workspace Project From API' }),
    ).toBeInTheDocument()
    expect(screen.getByText('در پاسخ فعلی Workspace اسپرینت جاری وجود ندارد.')).toBeInTheDocument()
    expect(screen.getByText('اطلاعات اسپرینت‌ها فعلاً در دسترس نیست.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'کار قابل‌نمایشی وجود ندارد' })).toBeInTheDocument()
    expect(screen.getByText('اطلاعات اعضای تیم فعلاً در دسترس نیست.')).toBeInTheDocument()
    expect(screen.getAllByText('برای این نقش ثبت نشده').length).toBeGreaterThan(0)
    expect(screen.queryByRole('link', { name: /جزئیات اسپرینت جاری/ })).not.toBeInTheDocument()
  })

  it('renders the canonical ProjectRun repository returned by the Workspace API', async () => {
    installApi({
      workspaceData: workspace({
        repository_url: 'https://github.com/prolearn/runtime-project',
      }),
    })
    renderPage()

    const repository = await screen.findByRole('link', {
      name: 'https://github.com/prolearn/runtime-project',
    })
    expect(repository).toHaveAttribute(
      'href',
      'https://github.com/prolearn/runtime-project',
    )
    expect(repository).toHaveAttribute('target', '_blank')
  })

  it('treats a missing repository URL as a non-blocking setup state', async () => {
    installApi({ workspaceData: workspace({ repository_url: null }) })
    renderPage()

    expect(await screen.findByRole('heading', { name: 'مخزن پروژه' })).toBeInTheDocument()
    expect(screen.getByText('در حال آماده‌سازی توسط تیم PROLEARN')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /github\.com/ })).not.toBeInTheDocument()
  })

  it('treats Workspace 404 as no active ProjectRun without follow-up requests', async () => {
    const fetchMock = installApi({
      failure: { status: 404, data: { detail: 'Active project run not found.' } },
    })
    renderPage()

    expect(
      await screen.findByRole('heading', {
        name: 'ProjectRun فعالی برای Workspace ندارید',
      }),
    ).toBeInTheDocument()
    expect(screen.queryByText('دریافت Workspace ممکن نشد')).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it.each([
    { status: 401, detail: 'private 401 diagnostic' },
    { status: 403, detail: 'Authentication credentials were not provided.' },
  ])('reconciles a missing session response with status $status', async ({ status, detail }) => {
    installApi({ failure: { status, data: { detail } } })
    const { refreshSession } = renderPage()

    expect(
      await screen.findByText('نشست شما پایان یافته است. برای ادامه دوباره وارد شوید.'),
    ).toBeInTheDocument()
    await waitFor(() => expect(refreshSession).toHaveBeenCalledTimes(1))
    expect(screen.queryByText(detail)).not.toBeInTheDocument()
  })

  it.each([
    {
      name: 'permission failure',
      failure: { status: 403, data: { detail: 'private permission diagnostic' } } as Failure,
      message: 'اجازه دسترسی به این Workspace برای حساب شما وجود ندارد.',
      raw: 'private permission diagnostic',
    },
    {
      name: 'network failure',
      failure: 'network' as Failure,
      message: 'ارتباط با سرور برقرار نشد. اتصال اینترنت را بررسی و دوباره تلاش کنید.',
      raw: 'private network diagnostic',
    },
  ])('maps a $name without exposing raw diagnostics', async ({ failure, message, raw }) => {
    installApi({ failure })
    renderPage()

    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(screen.queryByText(raw)).not.toBeInTheDocument()
  })

  it('rejects malformed Workspace data instead of rendering partial runtime truth', async () => {
    installApi({ workspaceData: { ...workspace(), resources: undefined } })
    renderPage()

    expect(
      await screen.findByText(
        'اطلاعات Workspace با قرارداد فعلی ProjectRun هماهنگ نیست. صفحه را دوباره بارگذاری کنید.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText('Workspace Project From API')).not.toBeInTheDocument()
  })

  it('reloads authoritative Workspace data after an unmount and direct remount', async () => {
    const fetchMock = installApi()
    const first = renderPage()
    await screen.findByRole('heading', { name: 'Workspace Project From API' })
    first.unmount()

    renderPage()
    await screen.findByRole('heading', { name: 'Workspace Project From API' })

    expect(callsFor(fetchMock, '/api/v1/project-runs/me/workspace/')).toHaveLength(2)
  })

  it('follows the existing Dashboard Workspace CTA into the functional route', async () => {
    const workspaceData = workspace()
    const fetchMock = installApi({ workspaceData, includeDashboard: true })
    const router = createMemoryRouter(
      [
        { path: '/dashboard', element: <DashboardPage /> },
        { path: '/workspace', element: <WorkspacePage /> },
      ],
      { initialEntries: ['/dashboard'] },
    )
    render(
      <AuthContext.Provider value={authValue()}>
        <RouterProvider router={router} />
      </AuthContext.Provider>,
    )

    const user = userEvent.setup()
    await screen.findByRole('heading', { name: 'Workspace Project From API' })
    await user.click(screen.getAllByRole('link', { name: /Workspace/ })[0])

    await screen.findByText('PARTICIPANT WORKSPACE')
    expect(router.state.location.pathname).toBe('/workspace')
    expect(callsFor(fetchMock, '/api/v1/project-runs/me/workspace/')).toHaveLength(1)
  })
})
