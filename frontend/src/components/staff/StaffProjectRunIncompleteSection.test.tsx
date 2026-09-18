import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '../../auth/AuthContext'
import type { StaffProjectRunRepository } from '../../lib/api/types'
import { StaffProjectRunIncompleteSection } from './StaffProjectRunIncompleteSection'

const runId = 'run-incomplete-api'
const actionPath = `/api/v1/project-runs/${runId}/incomplete/`

const eligibleRun: StaffProjectRunRepository = {
  id: runId,
  project: {
    id: 'project-api',
    name: 'پروژه آزمایشی',
    version_id: 'version-api',
    version_number: 2,
  },
  team_id: 'team-api',
  state: 'ACTIVE',
  started_at: '2026-07-01T08:00:00Z',
  deadline_at: '2026-08-12T08:00:00Z',
  can_mark_incomplete: true,
  repository_url: null,
  design_workspace_url: null,
  members: [],
}

function jsonResponse(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function callsFor(api: ReturnType<typeof vi.fn>, path: string, method: string) {
  return api.mock.calls.filter(([input, options]) =>
    new URL(String(input), 'http://frontend.test').pathname === path &&
    (options?.method ?? 'GET') === method,
  )
}

function renderSection() {
  const auth: AuthContextValue = {
    status: 'authenticated',
    user: { id: 'staff-api', email: 'staff@example.test' },
    error: null,
    refreshSession: vi.fn(async () => undefined),
    logout: vi.fn(async () => undefined),
    authenticate: vi.fn(async () => undefined),
  }
  return render(
    <AuthContext.Provider value={auth}>
      <StaffProjectRunIncompleteSection />
    </AuthContext.Provider>,
  )
}

async function openSection(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: 'مشاهده ProjectRunهای فعال' }))
  await screen.findByText('پروژه آزمایشی')
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('StaffProjectRunIncompleteSection', () => {
  it('does not expose the action when the Staff read endpoint denies access', async () => {
    const user = userEvent.setup()
    const api = vi.fn(async () => jsonResponse({ detail: 'Forbidden.' }, 403))
    vi.stubGlobal('fetch', api)
    renderSection()
    await user.click(screen.getByRole('button', { name: 'مشاهده ProjectRunهای فعال' }))

    expect(await screen.findByText('این عملیات فقط برای Staff/Admin فعال در دسترس است.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'ثبت ProjectRun ناتمام' })).not.toBeInTheDocument()
    expect(callsFor(api, actionPath, 'POST')).toHaveLength(0)
  })

  it('shows only server-eligible actions and cancels without a mutation', async () => {
    const user = userEvent.setup()
    const api = vi.fn(async (input: RequestInfo | URL, options?: RequestInit) => {
      const path = new URL(String(input), 'http://frontend.test').pathname
      if (path === '/api/v1/project-runs/') {
        return jsonResponse([
          eligibleRun,
          {
            ...eligibleRun,
            id: 'early-run',
            project: { ...eligibleRun.project, name: 'پروژه زودهنگام' },
            can_mark_incomplete: false,
          },
          {
            ...eligibleRun,
            id: 'terminal-run',
            project: { ...eligibleRun.project, name: 'پروژه پایان‌یافته' },
            state: 'INCOMPLETE',
            can_mark_incomplete: false,
          },
        ])
      }
      if (path === '/api/v1/auth/csrf/') return jsonResponse({ csrfToken: 'test-csrf' })
      return jsonResponse({ detail: `Unexpected ${options?.method ?? 'GET'} ${path}` }, 404)
    })
    vi.stubGlobal('fetch', api)
    renderSection()
    await openSection(user)

    const eligible = screen.getByText('پروژه آزمایشی').closest<HTMLElement>('.staff-incomplete__run')!
    expect(within(eligible).getByText('ACTIVE')).toBeInTheDocument()
    expect(within(eligible).getByText(/مهلت ProjectRun/)).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'ثبت ProjectRun ناتمام' })).toHaveLength(1)
    expect(screen.getAllByText('ثبت وضعیت ناتمام در حال حاضر از سوی سرور مجاز نیست.')).toHaveLength(2)

    await user.click(within(eligible).getByRole('button', { name: 'ثبت ProjectRun ناتمام' }))
    expect(screen.getByText(/هیچ تغییر وضعیت Sprint مجاز نیست/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'انصراف' }))
    expect(callsFor(api, actionPath, 'POST')).toHaveLength(0)
  })

  it('posts an empty body once, disables repeat submission, and trusts the refetched run list', async () => {
    const user = userEvent.setup()
    let releaseAction: ((response: Response) => void) | undefined
    let active = true
    const api = vi.fn(async (input: RequestInfo | URL, options?: RequestInit) => {
      const path = new URL(String(input), 'http://frontend.test').pathname
      if (path === '/api/v1/project-runs/') {
        return jsonResponse(active ? [eligibleRun] : [])
      }
      if (path === '/api/v1/auth/csrf/') return jsonResponse({ csrfToken: 'test-csrf' })
      if (path === actionPath && options?.method === 'POST') {
        return new Promise<Response>((resolve) => { releaseAction = resolve })
      }
      return jsonResponse({ detail: `Unexpected ${path}` }, 404)
    })
    vi.stubGlobal('fetch', api)
    renderSection()
    await openSection(user)
    await user.click(screen.getByRole('button', { name: 'ثبت ProjectRun ناتمام' }))
    await user.click(screen.getByRole('button', { name: 'تأیید ثبت وضعیت ناتمام' }))

    expect(screen.getByRole('button', { name: 'در حال ثبت...' })).toBeDisabled()
    expect(callsFor(api, actionPath, 'POST')).toHaveLength(1)
    expect(JSON.parse(String(callsFor(api, actionPath, 'POST')[0]?.[1]?.body))).toEqual({})
    active = false
    releaseAction?.(jsonResponse({ id: runId, state: 'INCOMPLETE' }))

    expect(await screen.findByText('ProjectRun طبق وضعیت قطعی سرور ناتمام شد.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'ثبت ProjectRun ناتمام' })).not.toBeInTheDocument()
    expect(callsFor(api, '/api/v1/project-runs/', 'GET')).toHaveLength(2)
  })

  it('shows a stale-state rejection and refetches without faking terminal success', async () => {
    const user = userEvent.setup()
    let active = true
    const api = vi.fn(async (input: RequestInfo | URL, options?: RequestInit) => {
      const path = new URL(String(input), 'http://frontend.test').pathname
      if (path === '/api/v1/project-runs/') return jsonResponse(active ? [eligibleRun] : [])
      if (path === '/api/v1/auth/csrf/') return jsonResponse({ csrfToken: 'test-csrf' })
      if (path === actionPath && options?.method === 'POST') {
        active = false
        return jsonResponse({ detail: 'The ProjectRun is no longer ACTIVE.' }, 409)
      }
      return jsonResponse({ detail: `Unexpected ${path}` }, 404)
    })
    vi.stubGlobal('fetch', api)
    renderSection()
    await openSection(user)
    await user.click(screen.getByRole('button', { name: 'ثبت ProjectRun ناتمام' }))
    await user.click(screen.getByRole('button', { name: 'تأیید ثبت وضعیت ناتمام' }))

    expect(await screen.findByText(/The ProjectRun is no longer ACTIVE/)).toBeInTheDocument()
    expect(screen.queryByText('ProjectRun طبق وضعیت قطعی سرور ناتمام شد.')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'ثبت ProjectRun ناتمام' })).not.toBeInTheDocument()
    expect(callsFor(api, '/api/v1/project-runs/', 'GET')).toHaveLength(2)
  })
})
