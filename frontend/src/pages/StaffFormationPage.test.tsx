import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import type {
  PlatformRole,
  ProjectListItem,
  ProjectReadinessResponse,
  TechnologyStack,
  StaffProjectRunRepository,
} from '../lib/api/types'
import { StaffFormationPage } from './StaffFormationPage'

const versionA = '00000000-0000-4000-8000-000000000101'
const versionB = '00000000-0000-4000-8000-000000000202'

const roles = {
  backend: {
    id: 'role-backend',
    code: 'BACKEND_DEVELOPER',
    name: 'Backend Developer',
  },
  frontend: {
    id: 'role-frontend',
    code: 'FRONTEND_DEVELOPER',
    name: 'Frontend Developer',
  },
  designer: {
    id: 'role-designer',
    code: 'PRODUCT_DESIGNER',
    name: 'Product Designer',
  },
} satisfies Record<string, PlatformRole>

const stacks = {
  backend: {
    id: 'stack-django',
    code: 'django-drf',
    name: 'Django + DRF',
  },
  frontend: {
    id: 'stack-react',
    code: 'react-typescript-vite',
    name: 'React + TypeScript',
  },
} satisfies Record<string, TechnologyStack>

const projects: ProjectListItem[] = [
  {
    id: 'project-a',
    slug: 'api-project-a',
    name: 'API Project Alpha',
    level: { id: 'level-1', number: 1, name: 'Level 1' },
    published_version_id: versionA,
  },
  {
    id: 'project-b',
    slug: 'api-project-b',
    name: 'API Project Beta',
    level: { id: 'level-2', number: 2, name: 'Level 2' },
    published_version_id: versionB,
  },
]

function readiness(
  id: string,
  email: string,
  role: PlatformRole,
  projectVersionId = versionA,
  versionNumber = 3,
): ProjectReadinessResponse {
  return {
    id,
    user: { id: `user-${id}`, email },
    role,
    project_version_id: projectVersionId,
    project_name:
      projectVersionId === versionA ? 'API Project Alpha' : 'API Project Beta',
    version_number: versionNumber,
    technology_stack:
      role.code === 'BACKEND_DEVELOPER'
        ? stacks.backend
        : role.code === 'FRONTEND_DEVELOPER'
          ? stacks.frontend
          : null,
    created_at: '2026-09-09T08:00:00Z',
    consumed_at: null,
  }
}

const initialCandidates = {
  [versionA]: [
    readiness('readiness-backend-a1', 'backend.alpha.one@example.test', roles.backend),
    readiness('readiness-backend-a2', 'backend.alpha.two@example.test', roles.backend),
    readiness('readiness-frontend-a', 'frontend.alpha@example.test', roles.frontend),
    readiness('readiness-designer-a', 'designer.alpha@example.test', roles.designer),
  ],
  [versionB]: [
    readiness('readiness-backend-b', 'backend.beta@example.test', roles.backend, versionB, 4),
    readiness('readiness-frontend-b', 'frontend.beta@example.test', roles.frontend, versionB, 4),
    readiness('readiness-designer-b', 'designer.beta@example.test', roles.designer, versionB, 4),
  ],
}

const staffProjectRun: StaffProjectRunRepository = {
  id: 'project-run-repository-api',
  project: {
    id: 'project-a',
    name: 'API Project Alpha',
    version_id: versionA,
    version_number: 3,
  },
  team_id: 'team-runtime-api',
  state: 'ACTIVE',
  started_at: '2026-09-09T09:00:00Z',
  deadline_at: '2026-10-21T09:00:00Z',
  can_mark_incomplete: false,
  repository_url: null,
  design_workspace_url: null,
  members: [
    {
      id: 'member-backend',
      user: { id: 'user-backend', email: 'backend.runtime@example.test' },
      role: roles.backend,
      technology_stack: stacks.backend,
      ended_at: null,
      github_username: 'backend-runtime',
    },
    {
      id: 'member-frontend',
      user: { id: 'user-frontend', email: 'frontend.runtime@example.test' },
      role: roles.frontend,
      technology_stack: stacks.frontend,
      ended_at: null,
      github_username: 'frontend-runtime',
    },
    {
      id: 'member-designer',
      user: { id: 'user-designer', email: 'designer.runtime@example.test' },
      role: roles.designer,
      technology_stack: null,
      ended_at: null,
      github_username: null,
    },
  ],
}

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

type ApiOptions = {
  formationFailure?: { status: number; data: unknown }
  formationGate?: Promise<void>
  nonStaff?: boolean
  repositoryFailure?: { status: number; data: unknown }
  repositoryUrl?: string | null
}

function installApi({
  formationFailure,
  formationGate,
  nonStaff = false,
  repositoryFailure,
  repositoryUrl = null,
}: ApiOptions = {}) {
  const candidates = new Map(
    Object.entries(initialCandidates).map(([versionId, items]) => [
      versionId,
      [...items],
    ]),
  )
  let repositoryRun = { ...staffProjectRun, repository_url: repositoryUrl }
  const api = vi.fn(
    async (input: RequestInfo | URL, request?: RequestInit) => {
      const url = new URL(String(input), 'http://frontend.test')

      if (url.pathname === '/api/v1/projects/') {
        return jsonResponse(projects)
      }
      if (url.pathname === '/api/v1/auth/csrf/') {
        return jsonResponse({ csrfToken: 'staff-csrf-token' })
      }
      if (url.pathname === '/api/v1/project-runs/' && request?.method !== 'PATCH') {
        return nonStaff
          ? jsonResponse(
              { detail: 'You do not have permission to perform this action.' },
              403,
            )
          : jsonResponse([repositoryRun])
      }
      if (
        url.pathname ===
          '/api/v1/project-runs/project-run-repository-api/repository/' &&
        request?.method === 'PATCH'
      ) {
        if (nonStaff) {
          return jsonResponse(
            { detail: 'You do not have permission to perform this action.' },
            403,
          )
        }
        if (repositoryFailure) {
          return jsonResponse(repositoryFailure.data, repositoryFailure.status)
        }
        const body = JSON.parse(String(request.body)) as {
          repository_url: string | null
        }
        repositoryRun = { ...repositoryRun, repository_url: body.repository_url }
        return jsonResponse(repositoryRun)
      }
      if (url.pathname === '/api/v1/project-readiness/') {
        if (nonStaff) {
          return jsonResponse(
            { detail: 'You do not have permission to perform this action.' },
            403,
          )
        }
        const versionId = url.searchParams.get('project_version_id') ?? ''
        return jsonResponse(candidates.get(versionId) ?? [])
      }
      if (
        url.pathname === '/api/v1/team-formations/' &&
        request?.method === 'POST'
      ) {
        if (formationGate) await formationGate
        if (formationFailure) {
          return jsonResponse(formationFailure.data, formationFailure.status)
        }
        const body = JSON.parse(String(request.body)) as {
          readiness_ids: string[]
        }
        for (const [versionId, items] of candidates) {
          candidates.set(
            versionId,
            items.filter((item) => !body.readiness_ids.includes(item.id)),
          )
        }
        const selectedCandidates = Object.values(initialCandidates)
          .flat()
          .filter((item) => body.readiness_ids.includes(item.id))
        return jsonResponse(
          {
            id: 'formation-from-api',
            project_version_id: selectedCandidates[0]?.project_version_id,
            project_name: selectedCandidates[0]?.project_name,
            created_by: { id: 'staff-1', email: 'staff@example.test' },
            created_at: '2026-09-09T09:00:00Z',
            ready_confirmed_at: null,
            team_id: null,
            project_run_id: null,
            ready_checks: selectedCandidates.map((candidate) => ({
              id: `check-${candidate.id}`,
              user: candidate.user,
              role: candidate.role,
              technology_stack: candidate.technology_stack,
              github_username:
                candidate.role.code === 'PRODUCT_DESIGNER'
                  ? null
                  : `github-${candidate.id}`,
              status: 'PENDING',
              effective_status: 'PENDING',
              is_current: true,
              started_at: '2026-09-09T09:00:00Z',
              expires_at: '2026-09-11T09:00:00Z',
              responded_at: null,
            })),
          },
          201,
        )
      }

      return jsonResponse({ detail: `Unexpected endpoint: ${url.pathname}` }, 404)
    },
  )
  vi.stubGlobal('fetch', api)
  return api
}

function renderPage() {
  const auth: AuthContextValue = {
    status: 'authenticated',
    user: { id: 'staff-1', email: 'staff@example.test' },
    error: null,
    refreshSession: vi.fn(async () => undefined),
    logout: vi.fn(async () => undefined),
    authenticate: vi.fn(async () => undefined),
  }
  return render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={['/staff/formations']}>
        <StaffFormationPage />
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

async function selectCompleteTeam(user: ReturnType<typeof userEvent.setup>) {
  await user.click(
    screen.getByRole('radio', { name: /backend\.alpha\.one@example\.test/ }),
  )
  await user.click(
    screen.getByRole('radio', { name: /frontend\.alpha@example\.test/ }),
  )
  await user.click(
    screen.getByRole('radio', { name: /designer\.alpha@example\.test/ }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('StaffFormationPage', () => {
  it('shows active ProjectRun members with real GitHub identities and saves the canonical URL', async () => {
    const user = userEvent.setup()
    const api = installApi()
    renderPage()

    expect(await screen.findByText('backend.runtime@example.test')).toBeInTheDocument()
    expect(screen.getByText('GitHub: backend-runtime')).toBeInTheDocument()
    expect(screen.getByText('GitHub: frontend-runtime')).toBeInTheDocument()
    expect(screen.getByText('GitHub: ثبت نشده')).toBeInTheDocument()
    expect(screen.queryByText(/دعوت ارسال شد|دسترسی اعطا شد/)).not.toBeInTheDocument()

    await user.type(
      screen.getByLabelText('نشانی canonical مخزن پروژه'),
      'https://github.com/prolearn/api-project-alpha',
    )
    await user.click(screen.getByRole('button', { name: 'افزودن مخزن' }))

    expect(
      await screen.findByText('نشانی canonical مخزن ProjectRun ذخیره شد.'),
    ).toBeInTheDocument()
    const calls = callsFor(
      api,
      '/api/v1/project-runs/project-run-repository-api/repository/',
      'PATCH',
    )
    expect(calls).toHaveLength(1)
    expect(JSON.parse(String(calls[0]?.[1]?.body))).toEqual({
      repository_url: 'https://github.com/prolearn/api-project-alpha',
    })
    expect(callsFor(api, '/api/v1/project-runs/', 'GET')).toHaveLength(2)
    expect(
      screen.getByRole('link', {
        name: 'https://github.com/prolearn/api-project-alpha',
      }),
    ).toBeInTheDocument()
  })

  it('edits an existing repository and refreshes authoritative server state', async () => {
    const user = userEvent.setup()
    const api = installApi({
      repositoryUrl: 'https://github.com/prolearn/original',
    })
    renderPage()

    expect(
      await screen.findByRole('link', {
        name: 'https://github.com/prolearn/original',
      }),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'ویرایش نشانی' }))
    const input = screen.getByLabelText('نشانی جدید مخزن canonical')
    await user.clear(input)
    await user.type(input, 'https://github.com/prolearn/replacement')
    await user.click(screen.getByRole('button', { name: 'ذخیره تغییرات' }))

    expect(
      await screen.findByRole('link', {
        name: 'https://github.com/prolearn/replacement',
      }),
    ).toBeInTheDocument()
    const calls = callsFor(
      api,
      '/api/v1/project-runs/project-run-repository-api/repository/',
      'PATCH',
    )
    expect(calls).toHaveLength(1)
    expect(JSON.parse(String(calls[0]?.[1]?.body))).toEqual({
      repository_url: 'https://github.com/prolearn/replacement',
    })
    expect(callsFor(api, '/api/v1/project-runs/', 'GET')).toHaveLength(2)
  })

  it('clears only the PROLEARN repository reference after explicit confirmation', async () => {
    const user = userEvent.setup()
    const api = installApi({
      repositoryUrl: 'https://github.com/prolearn/to-clear',
    })
    renderPage()

    await screen.findByRole('link', {
      name: 'https://github.com/prolearn/to-clear',
    })
    await user.click(screen.getByRole('button', { name: 'حذف ارجاع مخزن' }))
    expect(
      screen.getByText(
        'فقط ارجاع مخزن از PROLEARN حذف می‌شود. مخزن GitHub، دسترسی‌ها و اعضای آن حذف یا تغییر نمی‌کنند.',
      ),
    ).toBeInTheDocument()
    expect(
      callsFor(
        api,
        '/api/v1/project-runs/project-run-repository-api/repository/',
        'PATCH',
      ),
    ).toHaveLength(0)

    await user.click(screen.getByRole('button', { name: 'تأیید حذف ارجاع' }))

    expect(
      await screen.findByText('ارجاع مخزن از PROLEARN حذف شد.'),
    ).toBeInTheDocument()
    const calls = callsFor(
      api,
      '/api/v1/project-runs/project-run-repository-api/repository/',
      'PATCH',
    )
    expect(calls).toHaveLength(1)
    expect(JSON.parse(String(calls[0]?.[1]?.body))).toEqual({
      repository_url: null,
    })
    expect(screen.getByRole('button', { name: 'افزودن مخزن' })).toBeInTheDocument()
    expect(callsFor(api, '/api/v1/project-runs/', 'GET')).toHaveLength(2)
  })

  it('shows a clear conflict when the canonical repository belongs to another ProjectRun', async () => {
    const user = userEvent.setup()
    installApi({
      repositoryFailure: {
        status: 400,
        data: {
          repository_url: [
            'This repository is already assigned to another ProjectRun.',
          ],
        },
      },
    })
    renderPage()

    await user.type(
      await screen.findByLabelText('نشانی canonical مخزن پروژه'),
      'https://github.com/prolearn/already-used',
    )
    await user.click(screen.getByRole('button', { name: 'افزودن مخزن' }))

    expect(
      await screen.findByText('این مخزن قبلاً برای ProjectRun دیگری ثبت شده است.'),
    ).toBeInTheDocument()
    expect(
      screen.queryByText('نشانی canonical مخزن ProjectRun ذخیره شد.'),
    ).not.toBeInTheDocument()
  })

  it('loads authoritative active readiness data without profile images or ranking UI', async () => {
    const api = installApi()
    renderPage()

    expect(
      await screen.findByText('backend.alpha.one@example.test'),
    ).toBeInTheDocument()
    expect(screen.getByText('frontend.alpha@example.test')).toBeInTheDocument()
    expect(screen.getByText('designer.alpha@example.test')).toBeInTheDocument()
    expect(screen.getAllByText('Django + DRF')).toHaveLength(2)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.queryByText(/رتبه|امتیاز|پیشنهاد تیم/)).not.toBeInTheDocument()

    const candidateCalls = callsFor(api, '/api/v1/project-readiness/', 'GET')
    expect(candidateCalls).toHaveLength(1)
    expect(
      new URL(String(candidateCalls[0]?.[0]), 'http://frontend.test').searchParams.get(
        'project_version_id',
      ),
    ).toBe(versionA)
  })

  it('blocks a normal authenticated participant when the staff API returns 403', async () => {
    installApi({ nonStaff: true })
    renderPage()

    expect(
      await screen.findByRole('heading', { name: 'دسترسی Staff لازم است' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText('این بخش فقط برای Staff/Admin در دسترس است.'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'ساخت Formation' })).not.toBeInTheDocument()
  })

  it('keeps exact ProjectVersions separated through the backend-provided selector', async () => {
    const user = userEvent.setup()
    const api = installApi()
    renderPage()

    await screen.findByText('backend.alpha.one@example.test')
    const versionSelect = screen.getByLabelText('نسخه دقیق پروژه')
    expect(within(versionSelect).getByRole('option', { name: new RegExp(versionA) })).toBeInTheDocument()
    expect(within(versionSelect).getByRole('option', { name: new RegExp(versionB) })).toBeInTheDocument()

    await user.selectOptions(versionSelect, versionB)

    expect(await screen.findByText('backend.beta@example.test')).toBeInTheDocument()
    expect(screen.queryByText('backend.alpha.one@example.test')).not.toBeInTheDocument()
    expect(screen.getByText(versionB)).toBeInTheDocument()
    const candidateCalls = callsFor(api, '/api/v1/project-readiness/', 'GET')
    expect(candidateCalls).toHaveLength(2)
  })

  it('places candidates only in their authoritative role slot and allows one per role', async () => {
    const user = userEvent.setup()
    installApi()
    renderPage()
    await screen.findByText('backend.alpha.one@example.test')

    const backendSlot = screen.getByRole('group', {
      name: 'توسعه‌دهنده Backend',
    })
    const frontendSlot = screen.getByRole('group', {
      name: 'توسعه‌دهنده Frontend',
    })
    const designerSlot = screen.getByRole('group', { name: 'طراح محصول' })
    expect(within(backendSlot).getByText('backend.alpha.one@example.test')).toBeInTheDocument()
    expect(within(backendSlot).queryByText('frontend.alpha@example.test')).not.toBeInTheDocument()
    expect(within(frontendSlot).getByText('frontend.alpha@example.test')).toBeInTheDocument()
    expect(within(designerSlot).getByText('designer.alpha@example.test')).toBeInTheDocument()

    const firstBackend = within(backendSlot).getByRole('radio', {
      name: /backend\.alpha\.one@example\.test/,
    })
    const secondBackend = within(backendSlot).getByRole('radio', {
      name: /backend\.alpha\.two@example\.test/,
    })
    await user.click(firstBackend)
    await user.click(secondBackend)
    expect(firstBackend).not.toBeChecked()
    expect(secondBackend).toBeChecked()
    expect(screen.getByRole('button', { name: 'ساخت Formation' })).toBeDisabled()
  })

  it('posts only three readiness IDs and refreshes consumed candidates after success', async () => {
    const user = userEvent.setup()
    const api = installApi()
    renderPage()
    await screen.findByText('backend.alpha.one@example.test')
    await selectCompleteTeam(user)

    const submit = screen.getByRole('button', { name: 'ساخت Formation' })
    expect(submit).toBeEnabled()
    await user.click(submit)

    expect(
      await screen.findByText('Formation با موفقیت ساخته شد.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Ready Check برای سه عضو انتخاب‌شده آغاز شد.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('backend.alpha.one@example.test')).not.toBeInTheDocument()
    expect(screen.queryByText('frontend.alpha@example.test')).not.toBeInTheDocument()
    expect(screen.queryByText('designer.alpha@example.test')).not.toBeInTheDocument()

    const formationPosts = callsFor(api, '/api/v1/team-formations/', 'POST')
    expect(formationPosts).toHaveLength(1)
    expect(JSON.parse(String(formationPosts[0]?.[1]?.body))).toEqual({
      readiness_ids: [
        'readiness-backend-a1',
        'readiness-frontend-a',
        'readiness-designer-a',
      ],
    })
    expect(callsFor(api, '/api/v1/project-readiness/', 'GET')).toHaveLength(2)
  })

  it('keeps candidates and avoids false success when Formation is rejected', async () => {
    const user = userEvent.setup()
    const api = installApi({
      formationFailure: {
        status: 409,
        data: {
          detail: 'A selected user is already in a current proposed formation.',
        },
      },
    })
    renderPage()
    await screen.findByText('backend.alpha.one@example.test')
    await selectCompleteTeam(user)
    await user.click(screen.getByRole('button', { name: 'ساخت Formation' }))

    expect(await screen.findByText('ساخت Formation ممکن نشد.')).toBeInTheDocument()
    expect(
      screen.getByText(
        'یکی از کاربران انتخاب‌شده هم‌اکنون در یک Formation جاری قرار دارد.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText('Formation با موفقیت ساخته شد.')).not.toBeInTheDocument()
    expect(screen.getByText('backend.alpha.one@example.test')).toBeInTheDocument()
    expect(callsFor(api, '/api/v1/project-readiness/', 'GET')).toHaveLength(2)
  })

  it('prevents duplicate Formation submissions while the request is pending', async () => {
    const user = userEvent.setup()
    let releaseFormation: () => void = () => {}
    const formationGate = new Promise<void>((resolve) => {
      releaseFormation = resolve
    })
    const api = installApi({ formationGate })
    renderPage()
    await screen.findByText('backend.alpha.one@example.test')
    await selectCompleteTeam(user)

    await user.dblClick(screen.getByRole('button', { name: 'ساخت Formation' }))

    await waitFor(() =>
      expect(callsFor(api, '/api/v1/team-formations/', 'POST')).toHaveLength(1),
    )
    expect(
      screen.getByRole('button', { name: 'در حال ساخت Formation...' }),
    ).toBeDisabled()

    releaseFormation()
    expect(
      await screen.findByText('Formation با موفقیت ساخته شد.'),
    ).toBeInTheDocument()
    expect(callsFor(api, '/api/v1/team-formations/', 'POST')).toHaveLength(1)
  })
})
