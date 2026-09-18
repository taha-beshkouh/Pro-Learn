import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '../../auth/AuthContext'
import type {
  FormationReadyCheckResponse,
  ProjectReadinessResponse,
  TeamFormationResponse,
} from '../../lib/api/types'
import { StaffReadyCheckReplacementSection } from './StaffReadyCheckReplacementSection'

const role = {
  id: 'frontend-role',
  code: 'FRONTEND_DEVELOPER',
  name: 'Frontend Developer',
}
const backendRole = {
  id: 'backend-role',
  code: 'BACKEND_DEVELOPER',
  name: 'Backend Developer',
}
const designerRole = {
  id: 'designer-role',
  code: 'PRODUCT_DESIGNER',
  name: 'Product Designer',
}
const timestamp = '2026-09-17T09:00:00Z'

function check(
  id: string,
  email: string,
  checkRole: typeof role,
  status: FormationReadyCheckResponse['status'],
  effectiveStatus = status,
): FormationReadyCheckResponse {
  return {
    id,
    user: { id: `user-${id}`, email },
    role: checkRole,
    technology_stack: null,
    github_username: null,
    status,
    effective_status: effectiveStatus,
    is_current: true,
    started_at: timestamp,
    expires_at: '2026-09-19T09:00:00Z',
    responded_at: status === 'EXPIRED' || status === 'PENDING' ? null : timestamp,
  }
}

const formation: TeamFormationResponse = {
  id: 'formation-1',
  project_version_id: 'version-1',
  project_name: 'Project Alpha',
  created_by: { id: 'staff-1', email: 'staff@example.test' },
  created_at: timestamp,
  ready_confirmed_at: null,
  team_id: null,
  project_run_id: null,
  ready_checks: [
    check('backend', 'backend@example.test', backendRole, 'CONFIRMED'),
    check('frontend', 'frontend@example.test', role, 'DECLINED'),
    check('designer', 'designer@example.test', designerRole, 'PENDING', 'EXPIRED'),
  ],
}

const candidates: ProjectReadinessResponse[] = [
  {
    id: 'readiness-replacement',
    user: { id: 'replacement-user', email: 'replacement@example.test' },
    role,
    project_version_id: 'version-1',
    project_name: 'Project Alpha',
    version_number: 1,
    technology_stack: null,
    created_at: timestamp,
    consumed_at: null,
  },
  {
    id: 'readiness-other-role',
    user: { id: 'other-user', email: 'other@example.test' },
    role: backendRole,
    project_version_id: 'version-1',
    project_name: 'Project Alpha',
    version_number: 1,
    technology_stack: null,
    created_at: timestamp,
    consumed_at: null,
  },
]

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function installApi() {
  let current = formation
  const api = vi.fn(async (input: RequestInfo | URL, request?: RequestInit) => {
    const url = new URL(String(input), 'http://frontend.test')
    if (url.pathname === '/api/v1/team-formations/' && (!request?.method || request.method === 'GET')) {
      return jsonResponse([current])
    }
    if (url.pathname === '/api/v1/project-readiness/' && url.searchParams.get('project_version_id') === 'version-1') {
      return jsonResponse(candidates)
    }
    if (url.pathname === '/api/v1/auth/csrf/') {
      return jsonResponse({ csrfToken: 'test-csrf' })
    }
    if (url.pathname === '/api/v1/team-formations/formation-1/ready-checks/frontend/replace/' && request?.method === 'POST') {
      const body = JSON.parse(String(request.body)) as { readiness_id: string }
      if (body.readiness_id !== 'readiness-replacement') {
        return jsonResponse({ readiness_id: ['The replacement must have the same role.'] }, 400)
      }
      const old = { ...current.ready_checks[1], is_current: false }
      const replacement = check('replacement', 'replacement@example.test', role, 'PENDING')
      current = {
        ...current,
        ready_checks: [current.ready_checks[0], old, replacement, current.ready_checks[2]],
      }
      return jsonResponse(replacement, 201)
    }
    return jsonResponse({ detail: `Unexpected endpoint: ${url.pathname}` }, 404)
  })
  vi.stubGlobal('fetch', api)
  return api
}

function renderSection() {
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
      <StaffReadyCheckReplacementSection />
    </AuthContext.Provider>,
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('StaffReadyCheckReplacementSection', () => {
  it('shows authoritative current statuses and replacement only for declined/expired slots', async () => {
    installApi()
    const user = userEvent.setup()
    renderSection()
    await user.click(screen.getByRole('button', { name: 'مشاهده Formationها و Ready Checkها' }))

    expect(await screen.findByText('frontend@example.test')).toBeInTheDocument()
    expect(screen.queryByText('در انتظار پاسخ')).not.toBeInTheDocument()
    expect(screen.getByText('تأیید شده')).toBeInTheDocument()
    expect(screen.getByText('رد شده')).toBeInTheDocument()
    expect(screen.getByText('مهلت پایان یافته')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'جایگزینی عضو' })).toHaveLength(2)
  })

  it('uses only server-provided readiness IDs and refetches preserved history after replacement', async () => {
    const api = installApi()
    const user = userEvent.setup()
    renderSection()
    await user.click(screen.getByRole('button', { name: 'مشاهده Formationها و Ready Checkها' }))
    await screen.findByText('frontend@example.test')
    await user.click(screen.getAllByRole('button', { name: 'جایگزینی عضو' })[0])

    const chooser = await screen.findByLabelText('آمادگی داوطلب جایگزین')
    expect(screen.getByRole('option', { name: /other@example.test/ })).toBeInTheDocument()
    await user.selectOptions(chooser, 'readiness-replacement')
    await user.click(screen.getByRole('button', { name: 'ثبت جایگزینی' }))

    await waitFor(() => expect(screen.getByText('replacement@example.test')).toBeInTheDocument())
    expect(screen.getByText('سابقه جایگاه‌های جایگزین‌شده')).toBeInTheDocument()
    expect(screen.getAllByText('frontend@example.test')).toHaveLength(1)
    const posts = api.mock.calls.filter(([input, request]) =>
      String(input).includes('/ready-checks/frontend/replace/') && request?.method === 'POST',
    )
    expect(posts).toHaveLength(1)
    expect(JSON.parse(String(posts[0][1]?.body))).toEqual({ readiness_id: 'readiness-replacement' })
    expect(api.mock.calls.filter(([input]) => String(input).endsWith('/api/v1/team-formations/'))).toHaveLength(2)
  })

  it('leaves a rejected candidate unmodified and displays the backend error', async () => {
    installApi()
    const user = userEvent.setup()
    renderSection()
    await user.click(screen.getByRole('button', { name: 'مشاهده Formationها و Ready Checkها' }))
    await screen.findByText('frontend@example.test')
    await user.click(screen.getAllByRole('button', { name: 'جایگزینی عضو' })[0])
    await user.selectOptions(await screen.findByLabelText('آمادگی داوطلب جایگزین'), 'readiness-other-role')
    await user.click(screen.getByRole('button', { name: 'ثبت جایگزینی' }))

    expect(await screen.findByText(/داوطلب جایگزین باید نقش همین جایگاه را داشته باشد/)).toBeInTheDocument()
    expect(screen.getByText('frontend@example.test')).toBeInTheDocument()
    expect(screen.queryByText('سابقه جایگاه‌های جایگزین‌شده')).not.toBeInTheDocument()
  })
})
