import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { appRoutes } from '../app/router'
import type { GuestParticipationContext, ProjectVersionDetailResponse } from '../lib/api/types'

const versionId = '00000000-0000-4000-8000-000000000042'
const role = { id: '00000000-0000-4000-8000-000000000001', code: 'BACKEND_DEVELOPER', name: 'Backend Developer' }
const account = { id: 'member-id', email: 'member@example.com' }
const stack = { id: 'stack-id', code: 'configured-stack', name: 'Configured Stack' }
const path = `/projects/${versionId}/stack-selection`
const continuation: GuestParticipationContext = {
  selected_role_id: role.id, project_version_id: versionId,
  intended_action: 'join_project', return_path: path,
}
const version: ProjectVersionDetailResponse = {
  id: versionId, version_number: 2,
  project_template: { id: 'template-id', name: 'Contract Project', slug: 'contract-project', level: { id: 'level-id', number: 1, name: 'Level 1' } },
  summary: 'Public project summary', full_description: 'Public project description',
  duration_weeks: 6, sprint_count: 6, weekly_effort_hours_min: 8, weekly_effort_hours_max: 12,
  participant_database: '', published_at: '2026-09-01T00:00:00Z', sprint_templates: [],
  role_requirements: [{ id: 'requirement-id', role, requires_stack: true, stack_policy: 'FIXED', context: '', configured_stacks: [stack], prerequisites: [] }],
  work_items: [], shared_work_items: [],
  role_context: { id: 'requirement-id', role, requires_stack: true, stack_policy: 'FIXED', context: '', compatible_stacks: [stack], auto_selected_stack: stack, selected_stack: stack, prerequisites: [], work_items: [] },
}
function json(data: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
}

// HTTP fixtures follow the existing API contracts; session/profile changes occur
// only on successful backend responses. No production data or browser store is used.
function backend(options: {
  authenticated?: boolean
  context?: GuestParticipationContext
  conflict?: boolean
  failure?: { status: number; body: unknown }
  lifecycle?: 'readiness' | 'ready-check' | 'run'
  pauseAuth?: Promise<void>
  lifecycleFailure?: number
} = {}) {
  let signedIn = options.authenticated ?? false
  let context = { ...options.context }
  let persistedRole = options.conflict ? { ...role, id: 'existing-role', code: 'FRONTEND_DEVELOPER' } : role
  let csrf = 0
  const api = vi.fn(async (input: RequestInfo | URL, request?: RequestInit) => {
    const url = new URL(String(input), 'http://frontend.test').pathname
    const method = request?.method ?? 'GET'
    if (url === '/api/v1/auth/csrf/') return json({ csrfToken: `csrf-${++csrf}` })
    if (url === '/api/v1/auth/me/') return signedIn ? json(account) : json({ detail: 'Authentication credentials were not provided.' }, 403)
    if (url === '/api/v1/auth/login/' || url === '/api/v1/auth/register/') {
      await options.pauseAuth
      if (options.failure) return json(options.failure.body, options.failure.status)
      signedIn = true
      if (url.endsWith('/register/') && context.selected_role_id) persistedRole = { ...role, id: context.selected_role_id }
      return json(account, url.endsWith('/register/') ? 201 : 200)
    }
    if (url === '/api/v1/auth/logout/') { signedIn = false; context = {}; return json(null, 204) }
    if (url === '/api/v1/guest-context/') {
      if (method === 'PATCH') context = { ...context, ...JSON.parse(String(request?.body)) }
      return json(context)
    }
    if (url === '/api/v1/roles/') return json([role])
    if (url === '/api/v1/profile/') return json({ selected_role: persistedRole })
    if (url === '/api/v1/levels/') return json([version.project_template.level])
    if (url === '/api/v1/projects/') return json([{ ...version.project_template, published_version_id: versionId }])
    if (url === '/api/v1/projects/template-id/') return json({ ...version.project_template, published_version_id: versionId, published_version: version })
    if (url === `/api/v1/project-versions/${versionId}/`) return json(version)
    if (url === `/api/v1/project-versions/${versionId}/stack-selection/`) {
      return signedIn ? json({ project_version_id: versionId, selected_role_id: persistedRole.id, selected_stack_id: stack.id }) : json({ detail: 'Authentication credentials were not provided.' }, 403)
    }
    if (options.lifecycleFailure) return json({ detail: 'State unavailable.' }, options.lifecycleFailure)
    if (url === '/api/v1/project-readiness/me/') {
      if (method === 'POST') return json({
        id: 'readiness-id', user: account, role: persistedRole,
        project_version_id: versionId, project_name: 'Contract Project', version_number: 2,
        technology_stack: stack, created_at: '2026-09-08T12:00:00Z', consumed_at: null,
      }, 201)
      return options.lifecycle === 'readiness' ? json({ project_version_id: versionId, project_name: 'Contract Project' }) : json({ detail: 'Active project readiness not found.' }, 404)
    }
    if (url === '/api/v1/ready-checks/me/') return json(options.lifecycle === 'ready-check' ? [{ id: 'invitation-id', project_version_id: versionId, is_current: true, status: 'CONFIRMED' }] : [])
    if (url === '/api/v1/project-runs/me/dashboard/') return options.lifecycle === 'run' ? json({
      id: 'run-id',
      project: {
        id: version.project_template.id,
        name: version.project_template.name,
        version_id: version.id,
        version_number: version.version_number,
        summary: version.summary,
      },
      state: 'ACTIVE',
      started_at: '2026-09-09T07:30:00Z',
      deadline_at: '2026-10-21T07:30:00Z',
      ended_at: null,
      membership: {
        id: 'membership-id',
        user: account,
        role: persistedRole,
        technology_stack: stack,
        ended_at: null,
      },
      current_sprint: null,
      deadline: '2026-10-21T07:30:00Z',
      team: [],
      next_action: 'NO_SPRINT_AVAILABLE',
    }) : json({ detail: 'Active project run not found.' }, 404)
    if (url === '/api/v1/project-runs/me/sprints/' && options.lifecycle === 'run') return json([])
    throw new Error(`Unexpected request: ${method} ${url}`)
  })
  vi.stubGlobal('fetch', api)
  return { api, context: () => context }
}
function mount(initialPath = '/login') {
  const router = createMemoryRouter(appRoutes, { initialEntries: [initialPath] })
  const view = render(<App router={router} />)
  return { router, ...view }
}
async function fillForm() {
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText('ایمیل'), account.email)
  await user.type(screen.getByLabelText('رمز عبور'), 'Test-Password-781!')
  return user
}
afterEach(() => vi.unstubAllGlobals())

describe('session authentication and continuation', () => {
  it('renders the compact login form with accessible email/password fields', async () => {
    backend()
    mount()
    expect(await screen.findByLabelText('ایمیل')).toHaveAttribute('type', 'email')
    expect(screen.getByLabelText('رمز عبور')).toHaveAttribute('autocomplete', 'current-password')
    expect(screen.getByRole('button', { name: 'ورود' })).toBeEnabled()
  })

  it('signs in with cookies/CSRF and does not invent a direct-login destination', async () => {
    const { api } = backend()
    const { router } = mount()
    const user = await fillForm()
    await user.click(screen.getByRole('button', { name: 'ورود' }))
    expect(await screen.findByText('با موفقیت وارد حساب خود شده‌اید.')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    const post = api.mock.calls.find(([url]) => String(url).endsWith('/auth/login/'))![1]!
    expect(JSON.parse(String(post.body))).toEqual({ email: account.email, password: 'Test-Password-781!' })
    expect(new Headers(post.headers).get('X-CSRFToken')).toBe('csrf-1')
    expect(post.credentials).toBe('include')
    expect(screen.getByRole('button', { name: 'خروج' })).toBeInTheDocument()
  })

  it.each([
    [400, { detail: 'Unable to log in with the provided credentials.' }, 'ایمیل یا رمز عبور درست نیست.'],
    [401, { detail: 'Unauthorized' }, 'نشست شما پایان یافته است. دوباره وارد شوید.'],
    [403, { detail: 'CSRF Failed: token incorrect.' }, 'اعتبار امنیتی درخواست تأیید نشد. دوباره تلاش کنید.'],
    [403, { detail: 'Permission denied.' }, 'دسترسی به این درخواست ممکن نیست. وضعیت ورود خود را بررسی کنید.'],
    [429, { detail: 'Throttled' }, 'تعداد تلاش‌ها بیش از حد مجاز است. کمی بعد دوباره تلاش کنید.'],
  ])('handles login HTTP %s without creating local authentication', async (status, body, message) => {
    backend({ failure: { status, body } })
    mount()
    const user = await fillForm()
    await user.click(screen.getByRole('button', { name: 'ورود' }))
    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'خروج' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('رمز عبور')).toHaveValue('')
  })

  it.each([
    [{ email: ['A user with this email already exists.'] }, 'این ایمیل قبلاً ثبت شده است. وارد حساب خود شوید.'],
    [{ email: ['Enter a valid email address.'] }, 'یک نشانی ایمیل معتبر وارد کنید.'],
    [{ password: ['This password is too common.'] }, 'رمز عبور بسیار رایج است؛ رمز دیگری انتخاب کنید.'],
  ])('displays registration validation with no role selector', async (body, message) => {
    backend({ failure: { status: 400, body } })
    mount('/register')
    const user = await fillForm()
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    expect(screen.queryByRole('radio')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'ثبت نام' }))
    expect(await screen.findByText(message)).toBeInTheDocument()
  })

  it.each(['login', 'register'] as const)('preserves guest role/exact version through %s and resumes authenticated stack confirmation', async (mode) => {
    const { api, context } = backend()
    const { router } = mount('/')
    const user = userEvent.setup()
    const roleLink = screen.getByRole('link', { name: 'Back-end developer - دیدن پروژه‌ها' })
    await waitFor(() => expect(roleLink).toHaveAttribute('aria-disabled', 'false'))
    await user.click(roleLink)
    await screen.findByRole('heading', { name: /پروژه‌های مناسب نقش/ })
    await user.click(await screen.findByRole('link', { name: /Contract Project/ }))
    await screen.findByRole('heading', { level: 1, name: 'Contract Project' })
    expect(api.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
    await user.click(screen.getByRole('link', { name: 'ادامه با این پروژه' }))
    await screen.findByLabelText('ایمیل')
    expect(router.state.location.pathname).toBe('/login')
    expect(context()).toEqual(continuation)
    expect(api.mock.calls.some(([url]) => String(url).endsWith('/stack-selection/'))).toBe(false)
    if (mode === 'register') await user.click(screen.getByRole('link', { name: 'ساخت حساب' }))
    await fillForm()
    await user.click(screen.getByRole('button', { name: mode === 'register' ? 'ثبت نام' : 'ورود' }))
    await screen.findByRole('heading', { name: 'انتخاب تکنولوژی / Stack' })
    expect(router.state.location.pathname).toBe(path)
    expect(context()).toEqual(continuation)
    expect(screen.getByText('Backend Developer')).toBeInTheDocument()
    expect(api.mock.calls.some(([url]) => String(url).includes('/profile/select-role/'))).toBe(false)
    await user.click(screen.getByRole('button', { name: 'تأیید Stack' }))
    await screen.findByText('آمادگی شما ثبت شد')
    const stackPost = api.mock.calls.find(([url]) => String(url).endsWith('/stack-selection/'))!
    const readinessPost = api.mock.calls.find(([url, init]) =>
      String(url).endsWith('/project-readiness/me/') && init?.method === 'POST',
    )!
    expect(stackPost[0]).toBe(`/api/v1/project-versions/${versionId}/stack-selection/`)
    expect(new Headers(stackPost[1]?.headers).get('X-CSRFToken')).toBe('csrf-4')
    expect(readinessPost[0]).toBe('/api/v1/project-readiness/me/')
    expect(JSON.parse(String(readinessPost[1]?.body))).toEqual({})
    expect(new Headers(readinessPost[1]?.headers).get('X-CSRFToken')).toBe('csrf-5')
    expect(api.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(3)
  })

  it('guards direct guest stack URLs and saves continuation before login', async () => {
    const { api, context } = backend({ context: { selected_role_id: role.id } })
    const { router } = mount(path)
    await screen.findByLabelText('ایمیل')
    expect(router.state.location.pathname).toBe('/login')
    expect(context()).toEqual(continuation)
    expect(api.mock.calls.some(([url]) => String(url).includes('/project-versions/'))).toBe(false)
  })

  it('restores an authenticated session and exact continuation after a frontend refresh', async () => {
    const { api } = backend({ authenticated: true, context: continuation })
    const view = mount()
    await screen.findByRole('heading', { name: 'انتخاب تکنولوژی / Stack' })
    view.unmount()
    mount(path)
    await screen.findByRole('heading', { name: 'انتخاب تکنولوژی / Stack' })
    expect(api.mock.calls.some(([url]) => String(url).includes('/api/v1/projects/'))).toBe(false)
    expect(api.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })

  it('blocks role conflict, keeps the version and never overwrites either role', async () => {
    const { api, context } = backend({ context: continuation, conflict: true })
    mount()
    const user = await fillForm()
    await user.click(screen.getByRole('button', { name: 'ورود' }))
    await screen.findByText(/نقش انتخاب‌شده پیش از ورود با نقش حساب شما یکسان نیست/)
    expect(context()).toEqual(continuation)
    expect(screen.getByRole('link', { name: 'مشاهده همان نسخه پروژه' })).toHaveAttribute('href', `/projects/${versionId}`)
    expect(api.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
    expect(api.mock.calls.some(([, init]) => init?.method === 'PATCH')).toBe(false)
  })

  it.each(['readiness', 'ready-check', 'run'] as const)('respects existing %s instead of creating a new participation flow', async (lifecycle) => {
    const { api } = backend({ authenticated: true, context: continuation, lifecycle })
    const { router } = mount(path)
    if (lifecycle === 'run') {
      await waitFor(() => expect(router.state.location.pathname).toBe('/dashboard'))
      await screen.findByRole('heading', { name: version.project_template.name })
    }
    else await screen.findByText(lifecycle === 'readiness' ? /آمادگی شما برای پروژه/ : /دعوت Ready Check در حساب شما وجود دارد/)
    expect(screen.queryByRole('button', { name: 'تأیید Stack' })).not.toBeInTheDocument()
    expect(api.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })

  it('does not treat a lifecycle server error as absence of participation', async () => {
    backend({ authenticated: true, context: continuation, lifecycleFailure: 503 })
    mount(path)
    await screen.findByText('سرور اکنون نمی‌تواند درخواست را انجام دهد. دوباره تلاش کنید.')
    expect(screen.queryByRole('button', { name: 'تأیید Stack' })).not.toBeInTheDocument()
  })

  it('keeps exact continuation when a different version is opened directly', async () => {
    const { api, context } = backend({ authenticated: true, context: continuation })
    mount('/projects/another-version/stack-selection')
    await screen.findByText('نسخه این صفحه با نسخه ذخیره‌شده برای ادامه یکسان نیست.')
    expect(context()).toEqual(continuation)
    expect(screen.getByRole('link', { name: 'مشاهده همان نسخه پروژه' })).toHaveAttribute('href', `/projects/${versionId}`)
    expect(api.mock.calls.some(([, init]) => init?.method === 'PATCH' || init?.method === 'POST')).toBe(false)
  })

  it('does not navigate an arbitrary return path from the session', async () => {
    backend({ authenticated: true, context: { ...continuation, return_path: '//external.example/path' } })
    const { router } = mount()
    await screen.findByText('نسخه پروژه حفظ شده است، اما مسیر ادامه مشخص نیست.')
    expect(router.state.location.pathname).toBe('/login')
    expect(screen.getByRole('link', { name: 'مشاهده همان نسخه پروژه' })).toHaveAttribute('href', `/projects/${versionId}`)
  })

  it('shows forbidden continuation without a session-refresh loop', async () => {
    const { api } = backend({ authenticated: true, context: continuation, lifecycleFailure: 403 })
    mount()
    await screen.findByText('دسترسی به این درخواست ممکن نیست. وضعیت ورود خود را بررسی کنید.')
    expect(api.mock.calls.filter(([url]) => String(url).endsWith('/auth/me/'))).toHaveLength(1)
  })

  it('reconciles an expired session before offering authentication again', async () => {
    const { api } = backend({ authenticated: true, context: continuation })
    const { router } = mount(path)
    await screen.findByRole('button', { name: 'تأیید Stack' })
    const original = api.getMockImplementation()!
    api.mockImplementation(async (input, request) => {
      if (String(input).endsWith('/auth/me/') || String(input).endsWith('/profile/')) {
        return json({ detail: 'Authentication credentials were not provided.' }, 403)
      }
      return original(input, request)
    })
    await userEvent.setup().click(screen.getByRole('button', { name: 'تأیید Stack' }))
    await screen.findByLabelText('ایمیل')
    expect(router.state.location.pathname).toBe('/login')
    expect(api.mock.calls.some(([url]) => String(url).endsWith('/stack-selection/'))).toBe(false)
  })

  it('prevents duplicate submission while the authentication request is pending', async () => {
    let release!: () => void
    const pauseAuth = new Promise<void>((resolve) => { release = resolve })
    const { api } = backend({ pauseAuth })
    mount()
    await fillForm()
    const form = screen.getByLabelText('ایمیل').closest('form')!
    fireEvent.submit(form)
    fireEvent.submit(form)
    await waitFor(() => expect(api.mock.calls.filter(([url]) => String(url).endsWith('/auth/login/'))).toHaveLength(1))
    expect(screen.getByRole('button', { name: 'در حال ارسال...' })).toBeDisabled()
    await act(async () => release())
    await screen.findByText('با موفقیت وارد حساب خود شده‌اید.')
  })

  it('ends the backend session and removes the private page on logout', async () => {
    const { api } = backend({ authenticated: true })
    const { router } = mount('/dashboard')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'خروج' }))
    await screen.findByLabelText('ایمیل')
    expect(router.state.location.pathname).toBe('/login')
    expect(screen.queryByRole('heading', { name: 'Dashboard' })).not.toBeInTheDocument()
    const post = api.mock.calls.find(([url]) => String(url).endsWith('/auth/logout/'))![1]!
    expect(post.method).toBe('POST')
    expect(new Headers(post.headers).get('X-CSRFToken')).toBe('csrf-1')
    expect(api.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
    await act(async () => { await router.navigate('/dashboard') })
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
  })

  it('reports a network failure without exposing a raw exception', async () => {
    backend()
    mount()
    const user = await fillForm()
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('private diagnostic')))
    await user.click(screen.getByRole('button', { name: 'ورود' }))
    await screen.findByText('ارتباط با سرور برقرار نشد. اتصال اینترنت را بررسی و دوباره تلاش کنید.')
    expect(screen.queryByText('private diagnostic')).not.toBeInTheDocument()
  })
})
