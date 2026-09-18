import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import type {
  ProjectRunWorkspaceResponse,
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
const finalCommitUrl =
  'https://github.com/prolearn/runtime-project/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
const deploymentUrl = 'https://runtime-project.example.test/revision'

async function fillRequiredSubmissionFields(
  user: ReturnType<typeof userEvent.setup>,
) {
  await user.type(
    await screen.findByLabelText('آدرس کامیت نهایی'),
    finalCommitUrl,
  )
  await user.type(
    screen.getByLabelText('آدرس نسخه استقرار'),
    deploymentUrl,
  )
}

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
    final_commit_url:
      'https://github.com/prolearn/runtime-project/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    deployment_url: 'https://runtime-project.example.test',
    design_url_snapshot: 'https://design.example.test/runtime-project',
    evidence: 'Evidence from persisted submission API',
    submitted_at: '2026-09-18T11:30:00Z',
    review_decision: null,
    ...overrides,
  }
}

function reviewDecision(
  decision: 'CHANGES_REQUESTED' | 'COMPLETED',
  feedback: string,
) {
  return {
    decision,
    feedback,
    reviewed_at: '2026-09-19T09:00:00Z',
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
    design_workspace_url: 'https://design.example.test/runtime-project',
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

function missingDesignWorkspaceContext(roleCode: string): ProjectRunWorkspaceResponse {
  const currentSprint = sprintDetail('ACTIVE', { design_workspace_url: null })
  return {
    id: 'project-run-authoritative-api',
    project: {
      id: 'project-template-api',
      name: 'Project from API',
      version_id: 'project-version-api',
      version_number: 1,
      summary: '',
    },
    state: 'ACTIVE',
    started_at: '2026-09-16T08:00:00Z',
    deadline_at: '2026-10-28T08:00:00Z',
    ended_at: null,
    membership: {
      ...currentMember,
      role: { id: 'current-role-api', code: roleCode, name: 'Current role' },
    },
    current_sprint: currentSprint,
    deadline: '2026-10-28T08:00:00Z',
    team: [],
    next_action: 'SUBMIT_SPRINT',
    repository_url: currentSprint.repository_url,
    design_workspace_url: null,
    sprints: [currentSprint],
    resources: [],
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
  workspaceData,
}: {
  details?: unknown[]
  detailFailure?: Failure
  submitFailure?: { status: number; data: unknown }
  submitResponder?: () => Response | Promise<Response>
  workspaceData?: ProjectRunWorkspaceResponse
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

      if (method === 'GET' && url.pathname === '/api/v1/project-runs/me/workspace/' && workspaceData) {
        return jsonResponse(workspaceData)
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
    expect(screen.getByRole('link', { name: 'https://design.example.test/runtime-project' })).toHaveAttribute(
      'href',
      'https://design.example.test/runtime-project',
    )
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
      final_commit_url:
        'https://github.com/prolearn/runtime-project/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      deployment_url: 'https://runtime-project.example.test/revision-a',
      design_url_snapshot: 'https://design.example.test/workspace-a',
      evidence: 'Earlier persisted evidence',
      submitted_at: '2026-09-17T11:30:00Z',
    })
    const latest = submission({
      id: 'latest-submission-api',
      final_commit_url:
        'https://github.com/prolearn/runtime-project/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
      deployment_url: 'https://runtime-project.example.test/revision-b',
      design_url_snapshot: 'https://design.example.test/workspace-b',
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
    expect(
      within(latestRegion).getByRole('link', {
        name: 'https://design.example.test/workspace-b',
      }),
    ).toHaveAttribute('href', 'https://design.example.test/workspace-b')
    expect(screen.getByText('Earlier persisted evidence')).toBeInTheDocument()
    expect(
      screen.getByRole('link', {
        name: 'https://design.example.test/workspace-a',
      }),
    ).toHaveAttribute('href', 'https://design.example.test/workspace-a')
  })

  it('shows current requested-change feedback beside Resubmit and under the reviewed submission', async () => {
    const reviewed = submission({
      review_decision: reviewDecision('CHANGES_REQUESTED', 'اصلاح اعتبارسنجی فرم لازم است.'),
    })
    installApi({ details: [sprintDetail('CHANGES_REQUESTED', { submissions: [reviewed] })] })
    renderPage()

    const currentFeedback = await screen.findByLabelText('بازخورد اصلاحات جاری')
    expect(within(currentFeedback).getByText('اصلاح اعتبارسنجی فرم لازم است.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'ثبت ارسال مجدد' })).toBeEnabled()
    const history = screen.getByLabelText('آخرین ارسال ثبت‌شده')
    expect(within(history).getByText('بازخورد: اصلاح اعتبارسنجی فرم لازم است.')).toBeInTheDocument()
    expect(within(history).getByText('اصلاحات درخواست‌شده')).toBeInTheDocument()
    expect(within(history).getByText(/زمان بررسی:/)).toBeInTheDocument()
    expect(screen.queryByText('reviewer@example.test')).not.toBeInTheDocument()
  })

  it('keeps old feedback historical after resubmission without a current warning', async () => {
    const reviewed = submission({
      id: 'reviewed-first-api',
      review_decision: reviewDecision('CHANGES_REQUESTED', 'Fix the first revision.'),
    })
    const newer = submission({ id: 'unreviewed-second-api', review_decision: null })
    installApi({ details: [sprintDetail('SUBMITTED', { submissions: [reviewed, newer] })] })
    renderPage()

    expect(await screen.findByText('وضعیت اسپرینت: ارسال‌شده')).toBeInTheDocument()
    expect(screen.queryByLabelText('بازخورد اصلاحات جاری')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'ثبت نسخه جدیدتر' })).toBeEnabled()
    expect(screen.getByText('بازخورد: Fix the first revision.')).toBeInTheDocument()
    expect(within(screen.getByLabelText('آخرین ارسال ثبت‌شده')).queryByLabelText('نتیجه بررسی این ارسال')).not.toBeInTheDocument()
  })

  it('keeps previous review history visible during UNDER_REVIEW without resubmission action', async () => {
    const reviewed = submission({
      id: 'reviewed-first-api',
      review_decision: reviewDecision('CHANGES_REQUESTED', 'Previous correction.'),
    })
    const current = submission({ id: 'current-under-review-api' })
    installApi({ details: [sprintDetail('UNDER_REVIEW', { submissions: [reviewed, current] })] })
    renderPage()

    expect(await screen.findByText('وضعیت اسپرینت: در حال بررسی')).toBeInTheDocument()
    expect(screen.getByText('بازخورد: Previous correction.')).toBeInTheDocument()
    expect(screen.queryByLabelText('بازخورد اصلاحات جاری')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'ثبت ارسال مجدد' })).not.toBeInTheDocument()
  })

  it('attaches separate final decisions to their exact submissions and omits blank completion feedback', async () => {
    const first = submission({
      id: 'first-reviewed-api',
      evidence: 'First revision',
      review_decision: reviewDecision('CHANGES_REQUESTED', 'Correct the API.'),
    })
    const accepted = submission({
      id: 'second-reviewed-api',
      evidence: 'Accepted revision',
      review_decision: reviewDecision('COMPLETED', 'Accepted with thanks.'),
    })
    installApi({ details: [sprintDetail('COMPLETED', { submissions: [first, accepted] })] })
    renderPage()

    const latest = await screen.findByLabelText('آخرین ارسال ثبت‌شده')
    expect(within(latest).getByText('Accepted revision')).toBeInTheDocument()
    expect(within(latest).getByText('ارسال تأیید شد')).toBeInTheDocument()
    expect(within(latest).getByText('بازخورد: Accepted with thanks.')).toBeInTheDocument()
    expect(within(latest).queryByText('Correct the API.')).not.toBeInTheDocument()
    expect(screen.getByText('بازخورد: Correct the API.')).toBeInTheDocument()
    expect(screen.queryByLabelText('بازخورد اصلاحات جاری')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /ثبت ارسال/ })).not.toBeInTheDocument()
  })

  it('renders a decision with blank optional completion feedback without an empty feedback label', async () => {
    const accepted = submission({
      review_decision: reviewDecision('COMPLETED', '   '),
    })
    installApi({ details: [sprintDetail('COMPLETED', { submissions: [accepted] })] })
    renderPage()

    expect(await screen.findByText('ارسال تأیید شد')).toBeInTheDocument()
    expect(screen.queryByText(/بازخورد:/)).not.toBeInTheDocument()
    expect(screen.queryByLabelText('بازخورد اصلاحات جاری')).not.toBeInTheDocument()
  })

  it('rejects malformed participant review data without rendering Staff identity', async () => {
    const malformed = submission({
      review_decision: { decision: 'CHANGES_REQUESTED', feedback: 'Fix it.' } as SprintSubmissionResponse['review_decision'],
    })
    installApi({ details: [sprintDetail('CHANGES_REQUESTED', { submissions: [malformed] })] })
    renderPage()

    expect(await screen.findByText(/اطلاعات اسپرینت با قرارداد فعلی/)).toBeInTheDocument()
    expect(screen.queryByText('Fix it.')).not.toBeInTheDocument()
  })

  it('submits structured evidence, then re-fetches authoritative Sprint detail', async () => {
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

    await fillRequiredSubmissionFields(user)
    await user.type(
      await screen.findByLabelText('یادداشت اختیاری'),
      'Evidence typed by participant',
    )
    await user.click(screen.getByRole('button', { name: 'ثبت ارسال اسپرینت' }))

    expect(
      await screen.findByText('ارسال اسپرینت ثبت شد و وضعیت تازه از سرور دریافت شد.'),
    ).toBeInTheDocument()
    expect(screen.getByText('وضعیت اسپرینت: ارسال‌شده')).toBeInTheDocument()
    expect(screen.getByText('current-member@example.test')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'ثبت نسخه جدیدتر' })).toBeEnabled()

    const postCalls = callsFor(
      fetchMock,
      '/api/v1/project-runs/project-run-authoritative-api/sprints/sprint-run-route-api/submit/',
      'POST',
    )
    expect(postCalls).toHaveLength(1)
    expect(JSON.parse(String(postCalls[0][1]?.body))).toEqual({
      final_commit_url: finalCommitUrl,
      deployment_url: deploymentUrl,
      evidence: 'Evidence typed by participant',
    })
    expect(Object.keys(JSON.parse(String(postCalls[0][1]?.body)))).toEqual([
      'final_commit_url',
      'deployment_url',
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

  it('validates both required HTTP(S) URL fields locally without duplicating repository ownership rules', async () => {
    const fetchMock = installApi({
      details: [sprintDetail('ACTIVE'), sprintDetail('SUBMITTED')],
    })
    renderPage()
    const submit = await screen.findByRole('button', { name: 'ثبت ارسال اسپرینت' })
    fireEvent.click(submit)
    expect(screen.getByText('آدرس کامیت نهایی الزامی است.')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('آدرس کامیت نهایی'), {
      target: { value: 'ftp://example.test/commit' },
    })
    fireEvent.click(submit)
    expect(screen.getByText('آدرس کامیت نهایی باید یک URL کامل HTTP یا HTTPS باشد.')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('آدرس کامیت نهایی'), {
      target: { value: `  ${finalCommitUrl}  ` },
    })
    fireEvent.click(submit)
    expect(screen.getByText('آدرس نسخه استقرار الزامی است.')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('آدرس نسخه استقرار'), {
      target: { value: 'ftp://deploy.example.test/revision' },
    })
    fireEvent.click(submit)
    expect(screen.getByText('آدرس نسخه استقرار باید یک URL کامل HTTP یا HTTPS باشد.')).toBeInTheDocument()
    expect(callsFor(fetchMock, '/api/v1/project-runs/me/dashboard/')).toHaveLength(0)

    fireEvent.change(screen.getByLabelText('آدرس نسخه استقرار'), {
      target: { value: '  https://other-provider.example.test/revision  ' },
    })
    fireEvent.click(submit)
    await screen.findByText('وضعیت اسپرینت: ارسال‌شده')
    const post = callsFor(
      fetchMock,
      '/api/v1/project-runs/project-run-authoritative-api/sprints/sprint-run-route-api/submit/',
      'POST',
    )
    expect(post).toHaveLength(1)
    expect(JSON.parse(String(post[0][1]?.body))).toEqual({
      final_commit_url: finalCommitUrl,
      deployment_url: 'https://other-provider.example.test/revision',
      evidence: '',
    })
  })

  it.each([
    ['ACTIVE', 'ثبت ارسال اسپرینت'],
    ['SUBMITTED', 'ثبت نسخه جدیدتر'],
    ['CHANGES_REQUESTED', 'ثبت ارسال مجدد'],
  ] as const)('%s sends the URL currently visible in the form, not an older React value', async (state, actionLabel) => {
    const oldCommitUrl = submission().final_commit_url!
    const newDeploymentUrl = 'https://runtime-project.example.test/new-revision'
    const fetchMock = installApi({ details: [sprintDetail(state), sprintDetail('SUBMITTED')] })
    const user = userEvent.setup()
    renderPage()

    const commit = await screen.findByLabelText('آدرس کامیت نهایی') as HTMLInputElement
    const deployment = screen.getByLabelText('آدرس نسخه استقرار') as HTMLInputElement
    const evidence = screen.getByLabelText('یادداشت اختیاری') as HTMLTextAreaElement
    await user.type(commit, oldCommitUrl)
    await user.type(deployment, 'https://runtime-project.example.test/old-revision')
    await user.type(evidence, 'Old note')
    expect(commit).toHaveValue(oldCommitUrl)

    // Browser form restoration/autofill can change the visible DOM value without
    // dispatching the React change event that previously updated component state.
    commit.value = finalCommitUrl
    deployment.value = newDeploymentUrl
    evidence.value = 'New note'
    expect(commit).toHaveValue(finalCommitUrl)
    expect(deployment).toHaveValue(newDeploymentUrl)
    await user.click(screen.getByRole('button', { name: actionLabel }))

    await screen.findByText('وضعیت اسپرینت: ارسال‌شده')
    const posts = callsFor(
      fetchMock,
      '/api/v1/project-runs/project-run-authoritative-api/sprints/sprint-run-route-api/submit/',
      'POST',
    )
    expect(posts).toHaveLength(1)
    expect(JSON.parse(String(posts[0][1]?.body))).toEqual({
      final_commit_url: finalCommitUrl,
      deployment_url: newDeploymentUrl,
      evidence: 'New note',
    })
    expect(String(posts[0][1]?.body)).not.toContain(oldCommitUrl)
  })

  it('replaces a browser-restored old commit URL without refreshing the page', async () => {
    const oldCommitUrl = submission().final_commit_url!
    const fetchMock = installApi({ details: [sprintDetail('SUBMITTED'), sprintDetail('SUBMITTED')] })
    const user = userEvent.setup()
    renderPage()
    const commit = await screen.findByLabelText('آدرس کامیت نهایی') as HTMLInputElement
    commit.value = oldCommitUrl
    expect(commit).toHaveValue(oldCommitUrl)
    await user.type(screen.getByLabelText('آدرس نسخه استقرار'), deploymentUrl)
    await user.clear(commit)
    expect(commit).toHaveValue('')
    await user.type(commit, finalCommitUrl)
    expect(commit).toHaveValue(finalCommitUrl)
    await user.click(screen.getByRole('button', { name: 'ثبت نسخه جدیدتر' }))

    await screen.findByText('نسخه جدیدتر ثبت شد و سابقه تازه از سرور دریافت شد.')
    const posts = callsFor(
      fetchMock,
      '/api/v1/project-runs/project-run-authoritative-api/sprints/sprint-run-route-api/submit/',
      'POST',
    )
    expect(posts).toHaveLength(1)
    expect(JSON.parse(String(posts[0][1]?.body)).final_commit_url).toBe(finalCommitUrl)
    expect(String(posts[0][1]?.body)).not.toContain(oldCommitUrl)
  })

  it('treats a visibly cleared final commit as empty instead of reusing its old value', async () => {
    const fetchMock = installApi()
    const user = userEvent.setup()
    renderPage()
    const commit = await screen.findByLabelText('آدرس کامیت نهایی') as HTMLInputElement
    await user.type(commit, submission().final_commit_url!)
    await user.type(screen.getByLabelText('آدرس نسخه استقرار'), deploymentUrl)

    commit.value = ''
    expect(commit).toHaveValue('')
    await user.click(screen.getByRole('button', { name: 'ثبت ارسال اسپرینت' }))

    expect(screen.getByText('آدرس کامیت نهایی الزامی است.')).toBeInTheDocument()
    expect(callsFor(fetchMock, '/api/v1/project-runs/me/dashboard/')).toHaveLength(0)
  })

  it('uses the corrected visible URL on retry after backend validation rejects the prior value', async () => {
    let attempts = 0
    const fetchMock = installApi({
      details: [sprintDetail('SUBMITTED'), sprintDetail('SUBMITTED')],
      submitResponder: () => {
        attempts += 1
        return attempts === 1
          ? jsonResponse({ final_commit_url: ['Commit does not belong to this repository.'] }, 400)
          : jsonResponse({ state: 'SUBMITTED' })
      },
    })
    const user = userEvent.setup()
    renderPage()
    const commit = await screen.findByLabelText('آدرس کامیت نهایی') as HTMLInputElement
    const invalidForRun = 'https://github.com/another-team/repo/commit/cccccccccccccccccccccccccccccccccccccccc'
    await user.type(commit, invalidForRun)
    await user.type(screen.getByLabelText('آدرس نسخه استقرار'), deploymentUrl)
    await user.click(screen.getByRole('button', { name: 'ثبت نسخه جدیدتر' }))
    expect(await screen.findByText('آدرس کامیت نهایی باید به یک کامیت معتبر در مخزن همین ProjectRun اشاره کند.')).toBeInTheDocument()

    commit.value = finalCommitUrl
    expect(commit).toHaveValue(finalCommitUrl)
    await user.click(screen.getByRole('button', { name: 'ثبت نسخه جدیدتر' }))

    expect(await screen.findByText('نسخه جدیدتر ثبت شد و سابقه تازه از سرور دریافت شد.')).toBeInTheDocument()
    const posts = callsFor(
      fetchMock,
      '/api/v1/project-runs/project-run-authoritative-api/sprints/sprint-run-route-api/submit/',
      'POST',
    )
    expect(posts).toHaveLength(2)
    expect(JSON.parse(String(posts[0][1]?.body)).final_commit_url).toBe(invalidForRun)
    expect(JSON.parse(String(posts[1][1]?.body)).final_commit_url).toBe(finalCommitUrl)
  })

  it('keeps an unsaved edit through authoritative revalidation instead of restoring latest_submission', async () => {
    const old = submission({ final_commit_url: submission().final_commit_url })
    let attempts = 0
    const fetchMock = installApi({
      details: [sprintDetail('SUBMITTED', { submissions: [old] }), sprintDetail('SUBMITTED', { submissions: [old] })],
      submitResponder: () => {
        attempts += 1
        return attempts === 1
          ? jsonResponse({ detail: 'Sprint state changed.' }, 409)
          : jsonResponse({ state: 'SUBMITTED' })
      },
    })
    const user = userEvent.setup()
    renderPage()
    const commit = await screen.findByLabelText('آدرس کامیت نهایی') as HTMLInputElement
    expect(commit).toHaveValue('')
    await user.type(commit, old.final_commit_url!)
    commit.value = finalCommitUrl
    await user.type(screen.getByLabelText('آدرس نسخه استقرار'), deploymentUrl)
    expect(commit).toHaveValue(finalCommitUrl)
    await user.click(screen.getByRole('button', { name: 'ثبت نسخه جدیدتر' }))

    expect(await screen.findByText('وضعیت اسپرینت تغییر کرده و این ارسال دیگر مجاز نیست. اطلاعات تازه از سرور دریافت شد.')).toBeInTheDocument()
    expect(commit).toHaveValue(finalCommitUrl)
    expect(callsFor(fetchMock, '/api/v1/project-runs/me/sprints/sprint-run-route-api/')).toHaveLength(2)
    await user.click(screen.getByRole('button', { name: 'ثبت نسخه جدیدتر' }))
    await screen.findByText('نسخه جدیدتر ثبت شد و سابقه تازه از سرور دریافت شد.')
    const posts = callsFor(
      fetchMock,
      '/api/v1/project-runs/project-run-authoritative-api/sprints/sprint-run-route-api/submit/',
      'POST',
    )
    expect(posts).toHaveLength(2)
    expect(JSON.parse(String(posts[1][1]?.body)).final_commit_url).toBe(finalCommitUrl)
  })

  it('adds a newer SUBMITTED snapshot and re-fetches the complete API history', async () => {
    const earlier = submission({
      id: 'pre-review-earlier-api',
      evidence: 'Earlier immutable submission',
      submitted_at: '2026-09-18T11:30:00Z',
    })
    const latest = submission({
      id: 'pre-review-latest-api',
      submitted_by: currentMember,
      evidence: 'Newer pre-review submission',
      submitted_at: '2026-09-18T12:30:00Z',
    })
    const fetchMock = installApi({
      details: [
        sprintDetail('SUBMITTED', { submissions: [earlier] }),
        sprintDetail('SUBMITTED', { submissions: [earlier, latest] }),
      ],
    })
    const user = userEvent.setup()
    renderPage()

    await fillRequiredSubmissionFields(user)
    expect(screen.getByText(/یک ارسال جدید می‌سازد و ارسال‌های قبلی را تغییر نمی‌دهد/)).toBeInTheDocument()
    await user.type(
      await screen.findByLabelText('یادداشت اختیاری'),
      'Newer pre-review submission',
    )
    await user.click(screen.getByRole('button', { name: 'ثبت نسخه جدیدتر' }))

    expect(
      await screen.findByText('نسخه جدیدتر ثبت شد و سابقه تازه از سرور دریافت شد.'),
    ).toBeInTheDocument()
    const latestRegion = screen.getByLabelText('آخرین ارسال ثبت‌شده')
    expect(
      within(latestRegion).getByText('Newer pre-review submission'),
    ).toBeInTheDocument()
    expect(
      within(latestRegion).queryByText('Earlier immutable submission'),
    ).not.toBeInTheDocument()
    expect(screen.getByText('Earlier immutable submission')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'ثبت نسخه جدیدتر' })).toBeEnabled()

    const postCalls = callsFor(
      fetchMock,
      '/api/v1/project-runs/project-run-authoritative-api/sprints/sprint-run-route-api/submit/',
      'POST',
    )
    expect(postCalls).toHaveLength(1)
    expect(JSON.parse(String(postCalls[0][1]?.body))).toEqual({
      final_commit_url: finalCommitUrl,
      deployment_url: deploymentUrl,
      evidence: 'Newer pre-review submission',
    })
    expect(
      callsFor(
        fetchMock,
        '/api/v1/project-runs/me/sprints/sprint-run-route-api/',
      ),
    ).toHaveLength(2)
  })

  it('supports resubmission for CHANGES_REQUESTED without using legacy designation', async () => {
    const earlier = submission({
      id: 'changes-requested-earlier-api',
      evidence: 'Prior reviewed submission',
      review_decision: reviewDecision('CHANGES_REQUESTED', 'Fix the submitted validation.'),
    })
    const latest = submission({
      id: 'resubmission-latest-api',
      submitted_by: currentMember,
      evidence: 'New corrected submission',
    })
    installApi({
      details: [
        sprintDetail('CHANGES_REQUESTED', { submissions: [earlier] }),
        sprintDetail('SUBMITTED', { designated_submitter: null, submissions: [earlier, latest] }),
      ],
    })
    const user = userEvent.setup()
    renderPage()

    await fillRequiredSubmissionFields(user)
    expect(await screen.findByLabelText('بازخورد اصلاحات جاری')).toHaveTextContent('Fix the submitted validation.')
    expect(
      await screen.findByRole('button', { name: 'ثبت ارسال مجدد' }),
    ).toBeEnabled()
    await user.click(screen.getByRole('button', { name: 'ثبت ارسال مجدد' }))

    expect(
      await screen.findByText('ارسال مجدد ثبت شد و وضعیت تازه از سرور دریافت شد.'),
    ).toBeInTheDocument()
    expect(screen.getByText('وضعیت اسپرینت: ارسال‌شده')).toBeInTheDocument()
    expect(screen.queryByLabelText('بازخورد اصلاحات جاری')).not.toBeInTheDocument()
    expect(screen.getByText('Prior reviewed submission')).toBeInTheDocument()
    expect(screen.getByText('بازخورد: Fix the submitted validation.')).toBeInTheDocument()
    expect(within(screen.getByLabelText('آخرین ارسال ثبت‌شده')).getByText('New corrected submission')).toBeInTheDocument()
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
    fireEvent.change(screen.getByLabelText('آدرس کامیت نهایی'), {
      target: { value: finalCommitUrl },
    })
    fireEvent.change(screen.getByLabelText('آدرس نسخه استقرار'), {
      target: { value: deploymentUrl },
    })
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
        sprintDetail('UNDER_REVIEW', {
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

    await fillRequiredSubmissionFields(user)
    await user.click(
      await screen.findByRole('button', { name: 'ثبت ارسال اسپرینت' }),
    )

    expect(
      await screen.findByText(
        'وضعیت اسپرینت تغییر کرده و این ارسال دیگر مجاز نیست. اطلاعات تازه از سرور دریافت شد.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('وضعیت اسپرینت: در حال بررسی')).toBeInTheDocument()
    expect(screen.getByText('Another member submitted first')).toBeInTheDocument()
    expect(screen.queryByText('private state transition diagnostic')).not.toBeInTheDocument()
    expect(
      callsFor(
        fetchMock,
        '/api/v1/project-runs/me/sprints/sprint-run-route-api/',
      ),
    ).toHaveLength(2)
  })

  it('directs a Product Designer with a missing design workspace to configure it in Workspace', async () => {
    const fetchMock = installApi({
      details: [sprintDetail('ACTIVE', { design_workspace_url: null })],
      workspaceData: missingDesignWorkspaceContext('PRODUCT_DESIGNER'),
    })
    renderPage()

    expect(await screen.findByText(/شما می‌توانید لینک آن را در Workspace ثبت کنید/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'بررسی فضای طراحی در Workspace' })).toHaveAttribute('href', '/workspace')
    expect(screen.getByRole('button', { name: 'ثبت ارسال اسپرینت' })).toBeDisabled()
    expect(callsFor(fetchMock, '/api/v1/project-runs/project-run-authoritative-api/sprints/sprint-run-route-api/submit/', 'POST')).toHaveLength(0)
  })

  it('tells a non-designer to wait for the Product Designer when design workspace is missing', async () => {
    installApi({
      details: [sprintDetail('ACTIVE', { design_workspace_url: null })],
      workspaceData: missingDesignWorkspaceContext('BACKEND_DEVELOPER'),
    })
    renderPage()

    expect(await screen.findByText(/شما امکان تغییر آن را ندارید/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'افزودن فضای طراحی' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'ثبت ارسال اسپرینت' })).toBeDisabled()
  })

  it('gives a Frontend Developer the same read-only missing-design prerequisite guidance', async () => {
    installApi({
      details: [sprintDetail('ACTIVE', { design_workspace_url: null })],
      workspaceData: missingDesignWorkspaceContext('FRONTEND_DEVELOPER'),
    })
    renderPage()

    expect(await screen.findByText(/طراح محصول هنوز فضای طراحی پروژه را تنظیم نکرده است/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'ثبت ارسال اسپرینت' })).toBeDisabled()
  })

  it('blocks submission while the Staff-managed canonical repository is missing', async () => {
    const fetchMock = installApi({ details: [sprintDetail('ACTIVE', { repository_url: null })] })
    renderPage()

    expect(await screen.findByText(/پس از آماده‌شدن آن می‌توانید مدارک اسپرینت را ارسال کنید/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'ثبت ارسال اسپرینت' })).toBeDisabled()
    expect(callsFor(fetchMock, '/api/v1/project-runs/me/dashboard/')).toHaveLength(0)
  })

  it('shows exact-repository validation feedback from the backend without faking success', async () => {
    const fetchMock = installApi({
      submitFailure: {
        status: 400,
        data: { final_commit_url: ['Enter an exact commit URL from this ProjectRun repository.'] },
      },
    })
    renderPage()
    const user = userEvent.setup()
    await fillRequiredSubmissionFields(user)
    await user.click(screen.getByRole('button', { name: 'ثبت ارسال اسپرینت' }))

    expect(await screen.findByText(/یک کامیت معتبر در مخزن همین ProjectRun/)).toBeInTheDocument()
    expect(screen.getByText('وضعیت اسپرینت: فعال')).toBeInTheDocument()
    expect(screen.getByLabelText('آدرس کامیت نهایی')).toHaveValue(finalCommitUrl)
    expect(callsFor(fetchMock, '/api/v1/project-runs/me/sprints/sprint-run-route-api/')).toHaveLength(1)
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
