import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import type {
  ProjectRunNextAction,
  ProjectRunDashboardResponse,
  ProjectVersionDetailResponse,
  SprintRunResponse,
  SprintRunState,
  TeamMemberSnapshot,
} from '../lib/api/types'
import { DashboardPage } from './DashboardPage'

const projectDeadline = '2026-10-21T08:30:00Z'
const sprintDeadline = '2026-09-23T08:30:00Z'

const roles = {
  backend: {
    id: 'role-backend-api',
    code: 'BACKEND_DEVELOPER',
    name: 'Backend Runtime API',
  },
  frontend: {
    id: 'role-frontend-api',
    code: 'FRONTEND_DEVELOPER',
    name: 'Frontend Runtime API',
  },
  designer: {
    id: 'role-designer-api',
    code: 'PRODUCT_DESIGNER',
    name: 'Designer Runtime API',
  },
}

const stack = {
  id: 'stack-runtime-api',
  code: 'django-drf-runtime',
  name: 'Django Runtime API',
}

function member(
  id: string,
  email: string,
  role: TeamMemberSnapshot['role'],
  technologyStack: TeamMemberSnapshot['technology_stack'],
): TeamMemberSnapshot {
  return {
    id,
    user: { id: `user-${id}`, email },
    role,
    technology_stack: technologyStack,
    ended_at: null,
  }
}

const membership = member(
  'membership-current-api',
  'current-runtime@example.test',
  roles.backend,
  stack,
)

function sprint(
  sequence: number,
  state: SprintRunState,
  overrides: Partial<SprintRunResponse> = {},
): SprintRunResponse {
  return {
    id: `sprint-run-${sequence}-api`,
    sprint_template_id: `sprint-template-${sequence}-api`,
    sequence,
    title: `Sprint title ${sequence} from API`,
    brief: `Sprint brief ${sequence} from API`,
    state,
    planned_start_at: `2026-09-${String(9 + (sequence - 1) * 7).padStart(2, '0')}T08:30:00Z`,
    planned_end_at:
      sequence === 2
        ? sprintDeadline
        : `2026-09-${String(16 + (sequence - 1) * 7).padStart(2, '0')}T08:30:00Z`,
    opened_at: state === 'LOCKED' ? null : '2026-09-16T08:30:00Z',
    completed_at: state === 'COMPLETED' ? '2026-09-15T12:00:00Z' : null,
    designated_submitter: null,
    ...overrides,
  }
}

function sprintList() {
  return [sprint(1, 'COMPLETED'), sprint(2, 'ACTIVE'), sprint(3, 'LOCKED')]
}

function dashboard(
  overrides: Partial<ProjectRunDashboardResponse> = {},
): ProjectRunDashboardResponse {
  const sprints = sprintList()
  return {
    id: 'project-run-api',
    project: {
      id: 'project-template-api',
      name: 'Project name from Dashboard API',
      version_id: 'project-version-api',
      version_number: 7,
      summary: 'ProjectRun summary from API only.',
    },
    state: 'ACTIVE',
    started_at: '2026-09-09T08:30:00Z',
    deadline_at: projectDeadline,
    ended_at: null,
    membership,
    current_sprint: sprints[1],
    deadline: projectDeadline,
    team: [
      membership,
      member(
        'membership-frontend-api',
        'frontend-runtime@example.test',
        roles.frontend,
        { id: 'react-stack-api', code: 'react', name: 'React Runtime API' },
      ),
      member(
        'membership-designer-api',
        'designer-runtime@example.test',
        roles.designer,
        null,
      ),
    ],
    next_action: 'SUBMIT_SPRINT',
    ...overrides,
  }
}

function projectVersion(
  overrides: Partial<ProjectVersionDetailResponse> = {},
): ProjectVersionDetailResponse {
  return {
    project_template: {
      id: 'project-template-api',
      slug: 'project-from-api',
      name: 'Project name from Dashboard API',
      level: { id: 'level-api', number: 2, name: 'Level API Two' },
    },
    id: 'project-version-api',
    version_number: 7,
    summary: 'Exact version summary',
    full_description: 'Exact version description',
    duration_weeks: 6,
    sprint_count: 3,
    weekly_effort_hours_min: 8,
    weekly_effort_hours_max: 12,
    participant_database: 'PostgreSQL',
    published_at: '2026-09-01T00:00:00Z',
    sprint_templates: [],
    role_requirements: [],
    work_items: [
      {
        id: 'work-item-not-for-dashboard',
        title: 'Task content must not render on Dashboard',
        description: '',
        position: 1,
        role: null,
        technology_stack: null,
        sprint_template: null,
      },
    ],
    role_context: null,
    shared_work_items: [],
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
  dashboardData = dashboard(),
  dashboardFailure,
  projectData = projectVersion(),
  sprints = sprintList(),
}: {
  dashboardData?: ProjectRunDashboardResponse
  dashboardFailure?: Failure
  projectData?: ProjectVersionDetailResponse
  sprints?: SprintRunResponse[]
} = {}) {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, request?: RequestInit) => {
      const url = new URL(String(input), 'http://frontend.test')
      if (request?.method && request.method !== 'GET') {
        return jsonResponse({ detail: 'Unexpected mutation.' }, 405)
      }

      if (url.pathname === '/api/v1/project-runs/me/dashboard/') {
        if (dashboardFailure === 'network') {
          throw new TypeError('private network diagnostic')
        }
        if (dashboardFailure) {
          return jsonResponse(dashboardFailure.data, dashboardFailure.status)
        }
        return jsonResponse(dashboardData)
      }

      if (url.pathname === '/api/v1/project-runs/me/sprints/') {
        return jsonResponse(sprints)
      }

      if (url.pathname === '/api/v1/project-versions/project-version-api/') {
        return jsonResponse(projectData)
      }

      return jsonResponse({ detail: `Unexpected endpoint: ${url.pathname}` }, 404)
    },
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderPage(refreshSession = vi.fn(async () => undefined)) {
  const auth: AuthContextValue = {
    status: 'authenticated',
    user: { id: membership.user.id, email: membership.user.email },
    error: null,
    refreshSession,
    logout: vi.fn(async () => undefined),
    authenticate: vi.fn(async () => undefined),
  }
  const rendered = render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={['/dashboard']}>
        <DashboardPage />
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

describe('DashboardPage', () => {
  it('loads and renders authoritative ProjectRun identity, Sprint journey, and Team data', async () => {
    const fetchMock = installApi()
    const { container } = renderPage()

    expect(
      await screen.findByRole('heading', {
        name: 'Project name from Dashboard API',
      }),
    ).toBeInTheDocument()
    expect(screen.getByText('وضعیت پروژه: فعال')).toBeInTheDocument()
    expect(screen.getAllByText('Backend Runtime API').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Django Runtime API').length).toBeGreaterThan(0)
    expect(screen.getByText('project-version-api')).toBeInTheDocument()
    expect(screen.getByText('Level API Two')).toBeInTheDocument()
    expect(screen.getByText('۶ هفته')).toBeInTheDocument()

    const projectDeadlineRow = screen.getByText('مهلت پروژه').closest('div')
    const sprintDeadlineRow = screen
      .getByText('مهلت اسپرینت جاری (برنامه‌ریزی‌شده)')
      .closest('div')
    expect(
      projectDeadlineRow?.querySelector(`time[datetime="${projectDeadline}"]`),
    ).toBeInTheDocument()
    expect(
      sprintDeadlineRow?.querySelector(`time[datetime="${sprintDeadline}"]`),
    ).toBeInTheDocument()

    expect(screen.getByText('اسپرینت ۲ از ۳')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Sprint title 2 from API' }),
    ).toBeInTheDocument()
    expect(screen.getByText('برای ارسال اسپرینت آماده شوید')).toBeInTheDocument()
    expect(
      screen.getByText(
        'هر عضو فعلی تیم در این ProjectRun می‌تواند اسپرینت را ارسال کند. سرور هنگام اقدام، عضویت فعلی، وضعیت و مهلت پروژه را دوباره بررسی می‌کند.',
      ),
    ).toBeInTheDocument()
    expect(container.textContent).not.toContain('ارسال‌کننده تعیین‌شده')
    expect(screen.getByText('تکمیل‌شده')).toBeInTheDocument()
    expect(screen.getByText('فعال · جاری')).toBeInTheDocument()
    expect(screen.getByText('قفل‌شده')).toBeInTheDocument()

    for (const email of [
      'current-runtime@example.test',
      'frontend-runtime@example.test',
      'designer-runtime@example.test',
    ]) {
      expect(screen.getByText(email)).toBeInTheDocument()
    }
    expect(
      screen.getByText(
        'تا زمانی که در یک ProjectRun فعال حضور دارید، امکان تغییر نقش وجود ندارد.',
        { exact: false },
      ),
    ).toBeInTheDocument()
    expect(
      screen.getAllByRole('link', { name: /Workspace/ })[0],
    ).toHaveAttribute('href', '/workspace')

    expect(container.textContent).not.toContain('%')
    expect(container.textContent).not.toContain('Recent Activity')
    expect(container.textContent).not.toContain('Dev Squad Alpha')
    expect(container.textContent).not.toContain(
      'Task content must not render on Dashboard',
    )
    expect(container.querySelector('img')).not.toBeInTheDocument()
    expect(container.querySelector('[class*="avatar"]')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /تغییر نقش/ })).not.toBeInTheDocument()

    expect(callsFor(fetchMock, '/api/v1/project-runs/me/dashboard/')).toHaveLength(1)
    expect(callsFor(fetchMock, '/api/v1/project-runs/me/sprints/')).toHaveLength(1)
    expect(
      callsFor(fetchMock, '/api/v1/project-versions/project-version-api/'),
    ).toHaveLength(1)
    expect(callsFor(fetchMock, '/api/v1/project-runs/me/workspace/')).toHaveLength(0)
    expect(callsFor(fetchMock, '/api/v1/profile/select-role/')).toHaveLength(0)
    expect(
      fetchMock.mock.calls.every(([, request]) =>
        ['GET', undefined].includes(request?.method),
      ),
    ).toBe(true)
  })

  it('degrades gracefully when current Sprint, Team, stack, and duration are absent', async () => {
    installApi({
      dashboardData: dashboard({
        membership: { ...membership, technology_stack: null },
        current_sprint: null,
        team: [],
        next_action: 'NO_SPRINT_AVAILABLE',
      }),
      projectData: projectVersion({ duration_weeks: null, sprint_count: 0 }),
      sprints: [],
    })
    renderPage()

    expect(
      await screen.findByRole('heading', { name: 'اسپرینتی برای اجرا در دسترس نیست' }),
    ).toBeInTheDocument()
    expect(screen.getByText('در پاسخ فعلی سرور اسپرینت جاری وجود ندارد.')).toBeInTheDocument()
    expect(screen.getByText('اطلاعات اسپرینت‌ها فعلاً در دسترس نیست.')).toBeInTheDocument()
    expect(screen.getByText('اطلاعات اعضای تیم فعلاً در دسترس نیست.')).toBeInTheDocument()
    expect(screen.getByText('در API ثبت نشده')).toBeInTheDocument()
    expect(screen.getAllByText('برای این نقش ثبت نشده').length).toBeGreaterThan(0)
  })

  it.each([
    ['WAIT_FOR_FACILITATOR', 'منتظر فعال‌شدن اسپرینت بمانید'],
    ['SUBMIT_SPRINT', 'برای ارسال اسپرینت آماده شوید'],
    ['COLLABORATE', 'برای ارسال اسپرینت آماده شوید'],
    ['WAIT_FOR_REVIEW', 'منتظر بررسی Facilitator بمانید'],
    ['RESUBMIT_SPRINT', 'اصلاحات را برای ارسال مجدد آماده کنید'],
    ['ADDRESS_CHANGES', 'اصلاحات را برای ارسال مجدد آماده کنید'],
    ['SPRINTS_COMPLETED', 'مسیر اسپرینت‌ها تکمیل شده است'],
    ['NO_SPRINT_AVAILABLE', 'اسپرینتی برای اجرا در دسترس نیست'],
  ] satisfies [ProjectRunNextAction, string][]) (
    'maps backend next_action %s without creating an action endpoint',
    async (nextAction, title) => {
      const fetchMock = installApi({
        dashboardData: dashboard({ next_action: nextAction }),
      })
      renderPage()

      expect(await screen.findByRole('heading', { name: title })).toBeInTheDocument()
      expect(
        fetchMock.mock.calls.some(([, request]) => request?.method === 'POST'),
      ).toBe(false)
    },
  )

  it('treats the primary dashboard 404 as no active ProjectRun and makes no supplemental calls', async () => {
    const fetchMock = installApi({
      dashboardFailure: {
        status: 404,
        data: { detail: 'Active project run not found.' },
      },
    })
    renderPage()

    expect(
      await screen.findByRole('heading', { name: 'ProjectRun فعالی ندارید' }),
    ).toBeInTheDocument()
    expect(screen.queryByText('دریافت Dashboard ممکن نشد')).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(callsFor(fetchMock, '/api/v1/project-runs/me/sprints/')).toHaveLength(0)
  })

  it('reconciles a dashboard 401 through the existing session state without exposing raw errors', async () => {
    installApi({
      dashboardFailure: {
        status: 401,
        data: { detail: 'private authentication diagnostic' },
      },
    })
    const { refreshSession } = renderPage()

    expect(
      await screen.findByText('نشست شما پایان یافته است. برای ادامه دوباره وارد شوید.'),
    ).toBeInTheDocument()
    await waitFor(() => expect(refreshSession).toHaveBeenCalledTimes(1))
    expect(screen.queryByText('private authentication diagnostic')).not.toBeInTheDocument()
  })

  it.each([
    {
      name: 'permission response',
      failure: {
        status: 403,
        data: { detail: 'private permission diagnostic' },
      } as Failure,
      expected: 'اجازه دسترسی به این ProjectRun برای حساب شما وجود ندارد.',
      raw: 'private permission diagnostic',
    },
    {
      name: 'network response',
      failure: 'network' as Failure,
      expected:
        'ارتباط با سرور برقرار نشد. اتصال اینترنت را بررسی و دوباره تلاش کنید.',
      raw: 'private network diagnostic',
    },
  ])('maps a $name safely', async ({ failure, expected, raw }) => {
    installApi({ dashboardFailure: failure })
    renderPage()

    expect(await screen.findByText(expected)).toBeInTheDocument()
    expect(screen.queryByText(raw)).not.toBeInTheDocument()
  })

  it('rejects mismatched exact ProjectVersion data instead of drifting to another version', async () => {
    installApi({
      projectData: projectVersion({ id: 'another-project-version' }),
    })
    renderPage()

    expect(
      await screen.findByText(
        'اطلاعات ProjectRun با نسخه یا اسپرینت‌های آن هماهنگ نیست. صفحه را دوباره بارگذاری کنید.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText('another-project-version')).not.toBeInTheDocument()
  })

  it('restores ProjectRun data from the backend again after a remount', async () => {
    const fetchMock = installApi()
    const first = renderPage()
    await screen.findByRole('heading', { name: 'Project name from Dashboard API' })
    first.unmount()

    renderPage()
    await screen.findByRole('heading', { name: 'Project name from Dashboard API' })

    expect(callsFor(fetchMock, '/api/v1/project-runs/me/dashboard/')).toHaveLength(2)
    expect(callsFor(fetchMock, '/api/v1/project-runs/me/sprints/')).toHaveLength(2)
    expect(
      callsFor(fetchMock, '/api/v1/project-versions/project-version-api/'),
    ).toHaveLength(2)
  })
})
