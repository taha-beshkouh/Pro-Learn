import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '../../auth/AuthContext'
import type {
  SprintRunState,
  StaffProjectRunRepository,
  StaffReviewDecisionResponse,
  StaffSprintRunDetailResponse,
  StaffSprintRunListItem,
  StaffSprintSubmissionResponse,
  TeamFormationResponse,
  TeamMemberSnapshot,
} from '../../lib/api/types'
import { StaffSprintReviewSection } from './StaffSprintReviewSection'

const runId = 'project-run-review-api'
const sprintId = 'sprint-run-review-api'

const member: TeamMemberSnapshot = {
  id: 'team-member-api',
  user: { id: 'participant-api', email: 'participant@example.test' },
  role: { id: 'role-api', code: 'BACKEND_DEVELOPER', name: 'Backend Developer' },
  technology_stack: { id: 'stack-api', code: 'django', name: 'Django' },
  ended_at: null,
}

const staffRun: StaffProjectRunRepository = {
  id: runId,
  project: {
    id: 'project-api',
    name: 'پروژه واقعی API',
    version_id: 'project-version-api',
    version_number: 7,
  },
  team_id: 'team-api',
  state: 'ACTIVE',
  started_at: '2026-09-10T08:00:00Z',
  deadline_at: '2026-10-22T08:00:00Z',
  can_mark_incomplete: false,
  repository_url: 'https://github.com/prolearn/review-api',
  design_workspace_url: 'https://www.figma.com/design/review-api',
  members: [],
}

const formation: TeamFormationResponse = {
  id: 'formation-api',
  project_version_id: staffRun.project.version_id,
  project_name: staffRun.project.name,
  created_by: { id: 'staff-api', email: 'staff@example.test' },
  created_at: '2026-09-10T07:00:00Z',
  ready_confirmed_at: '2026-09-10T08:00:00Z',
  team_id: staffRun.team_id,
  project_run_id: runId,
  ready_checks: [],
}

function decision(
  value: 'CHANGES_REQUESTED' | 'COMPLETED',
  feedback: string,
  id = `decision-${value.toLowerCase()}`,
): StaffReviewDecisionResponse {
  return {
    id,
    decision: value,
    feedback,
    reviewed_by: { id: 'reviewer-api', email: 'reviewer@example.test' },
    reviewed_at: '2026-09-12T10:00:00Z',
  }
}

function submission(
  id: string,
  overrides: Partial<StaffSprintSubmissionResponse> = {},
): StaffSprintSubmissionResponse {
  return {
    id,
    submitted_by: member,
    final_commit_url: `https://github.com/prolearn/review-api/commit/${id}`,
    deployment_url: `https://${id}.example.test`,
    design_url_snapshot: `https://www.figma.com/design/${id}`,
    evidence: `یادداشت ${id}`,
    submitted_at:
      id === 'submission-1' ? '2026-09-11T09:00:00Z' : '2026-09-12T09:00:00Z',
    review_decision: null,
    ...overrides,
  }
}

function listItem(
  id: string,
  sequence: number,
  state: SprintRunState,
  latest: StaffSprintSubmissionResponse | null = null,
): StaffSprintRunListItem {
  return {
    id,
    project_run_id: runId,
    sprint_template_id: `template-${sequence}`,
    sequence,
    title: `عنوان Sprint ${sequence}`,
    state,
    planned_start_at: `2026-09-${10 + sequence}T08:00:00Z`,
    planned_end_at: `2026-09-${11 + sequence}T08:00:00Z`,
    opened_at: state === 'LOCKED' ? null : `2026-09-${10 + sequence}T08:00:00Z`,
    completed_at: state === 'COMPLETED' ? `2026-09-${12 + sequence}T08:00:00Z` : null,
    latest_submission: latest
      ? {
          id: latest.id,
          submitted_by: latest.submitted_by,
          submitted_at: latest.submitted_at,
          review_decision: latest.review_decision,
        }
      : null,
  }
}

function detail(
  state: SprintRunState,
  submissions: StaffSprintSubmissionResponse[] = [],
  id = sprintId,
  sequence = 1,
): StaffSprintRunDetailResponse {
  return {
    ...listItem(id, sequence, state, submissions.at(-1) ?? null),
    brief: 'شرح واقعی Sprint از API',
    latest_submission: submissions.at(-1) ?? null,
    submissions,
  }
}

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

type HarnessOptions = {
  initialList: StaffSprintRunListItem[]
  initialDetails: StaffSprintRunDetailResponse[]
  active?: boolean
  failAction?: 'request-changes' | 'complete' | 'under-review' | 'open'
  stateAfterFailure?: SprintRunState
  forbidden?: boolean
}

function installApi({
  initialList,
  initialDetails,
  active = true,
  failAction,
  stateAfterFailure = 'COMPLETED',
  forbidden = false,
}: HarnessOptions) {
  let activeRunVisible = active
  let sprintList = structuredClone(initialList)
  const details = new Map(
    structuredClone(initialDetails).map((item) => [item.id, item]),
  )

  function changeState(targetId: string, state: SprintRunState) {
    sprintList = sprintList.map((item) =>
      item.id === targetId ? { ...item, state } : item,
    )
    const current = details.get(targetId)
    if (current) details.set(targetId, { ...current, state })
  }

  function finalize(targetId: string, kind: 'CHANGES_REQUESTED' | 'COMPLETED', feedback: string) {
    const current = details.get(targetId)
    if (!current?.latest_submission) return
    const nextDecision = decision(kind, feedback, `decision-${current.latest_submission.id}`)
    const submissions = current.submissions.map((item) =>
      item.id === current.latest_submission?.id
        ? { ...item, review_decision: nextDecision }
        : item,
    )
    const latest = submissions.find((item) => item.id === current.latest_submission?.id) ?? null
    const state = kind
    details.set(targetId, {
      ...current,
      state,
      submissions,
      latest_submission: latest,
    })
    sprintList = sprintList.map((item) =>
      item.id === targetId
        ? {
            ...item,
            state,
            latest_submission: latest
              ? {
                  id: latest.id,
                  submitted_by: latest.submitted_by,
                  submitted_at: latest.submitted_at,
                  review_decision: latest.review_decision,
                }
              : null,
          }
        : item,
    )
    if (kind === 'COMPLETED' && sprintList.at(-1)?.id === targetId) {
      activeRunVisible = false
    }
  }

  const api = vi.fn(async (input: RequestInfo | URL, request?: RequestInit) => {
    const url = new URL(String(input), 'http://frontend.test')
    const method = request?.method ?? 'GET'

    if (url.pathname === '/api/v1/auth/csrf/') {
      return jsonResponse({ csrfToken: 'staff-review-csrf' })
    }
    if (url.pathname === '/api/v1/project-runs/' && method === 'GET') {
      return forbidden
        ? jsonResponse({ detail: 'Forbidden.' }, 403)
        : jsonResponse(activeRunVisible ? [staffRun] : [])
    }
    if (url.pathname === '/api/v1/team-formations/' && method === 'GET') {
      return forbidden
        ? jsonResponse({ detail: 'Forbidden.' }, 403)
        : jsonResponse([formation])
    }
    if (
      url.pathname === `/api/v1/project-runs/${runId}/sprints/` &&
      method === 'GET'
    ) {
      return jsonResponse(sprintList)
    }
    const detailMatch = url.pathname.match(
      new RegExp(`^/api/v1/project-runs/${runId}/sprints/([^/]+)/$`),
    )
    if (detailMatch && method === 'GET') {
      const selected = details.get(detailMatch[1] ?? '')
      return selected
        ? jsonResponse(selected)
        : jsonResponse({ detail: 'Sprint not found.' }, 404)
    }
    const actionMatch = url.pathname.match(
      new RegExp(
        `^/api/v1/project-runs/${runId}/sprints/([^/]+)/(open|under-review|request-changes|complete)/$`,
      ),
    )
    if (actionMatch && method === 'POST') {
      const targetId = actionMatch[1] ?? ''
      const action = actionMatch[2] as NonNullable<HarnessOptions['failAction']>
      if (failAction === action) {
        changeState(targetId, stateAfterFailure)
        return jsonResponse({ detail: 'The Sprint state changed.' }, 409)
      }
      const body = request?.body ? (JSON.parse(String(request.body)) as { feedback?: string }) : {}
      if (action === 'open') changeState(targetId, 'ACTIVE')
      if (action === 'under-review') changeState(targetId, 'UNDER_REVIEW')
      if (action === 'request-changes') {
        finalize(targetId, 'CHANGES_REQUESTED', body.feedback ?? '')
      }
      if (action === 'complete') finalize(targetId, 'COMPLETED', body.feedback ?? '')
      return jsonResponse({ id: targetId })
    }
    return jsonResponse({ detail: `Unexpected endpoint: ${method} ${url.pathname}` }, 404)
  })
  vi.stubGlobal('fetch', api)
  return api
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
      <StaffSprintReviewSection />
    </AuthContext.Provider>,
  )
}

function callsFor(api: ReturnType<typeof vi.fn>, pathname: string, method?: string) {
  return api.mock.calls.filter(([input, request]) => {
    const url = new URL(String(input), 'http://frontend.test')
    return url.pathname === pathname && (!method || request?.method === method)
  })
}

async function openReviewArea(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: 'ورود به بررسی اسپرینت‌ها' }))
  await screen.findByLabelText('ProjectRun')
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('StaffSprintReviewSection', () => {
  it('opens from the Staff area and renders server-ordered Sprints, latest evidence, and preserved history', async () => {
    const first = submission('submission-1', {
      review_decision: decision('CHANGES_REQUESTED', 'API feedback for revision one.'),
    })
    const second = submission('submission-2')
    const api = installApi({
      initialList: [
        listItem('sprint-completed', 1, 'COMPLETED', first),
        listItem(sprintId, 2, 'SUBMITTED', second),
        listItem('sprint-locked', 3, 'LOCKED'),
      ],
      initialDetails: [detail('SUBMITTED', [first, second], sprintId, 2)],
    })
    const user = userEvent.setup()
    renderSection()

    expect(screen.queryByLabelText('ProjectRun')).not.toBeInTheDocument()
    await openReviewArea(user)

    const sprintButtons = await screen.findAllByRole('button', { name: /Sprint [123]/ })
    expect(sprintButtons.map((button) => button.textContent)).toEqual([
      expect.stringContaining('Sprint 1'),
      expect.stringContaining('Sprint 2'),
      expect.stringContaining('Sprint 3'),
    ])
    expect(screen.getByRole('link', { name: staffRun.repository_url ?? '' })).toBeInTheDocument()

    const current = await screen.findByRole('region', {
      name: 'ارسال فعلی برای بررسی',
    })
    expect(within(current).getByText('آخرین ارسال قطعی backend')).toBeInTheDocument()
    expect(
      within(current).getByRole('link', { name: second.final_commit_url ?? '' }),
    ).toBeInTheDocument()
    expect(
      within(current).getByRole('link', { name: second.deployment_url ?? '' }),
    ).toBeInTheDocument()
    expect(
      within(current).getByRole('link', { name: second.design_url_snapshot ?? '' }),
    ).toBeInTheDocument()
    expect(within(current).getByText(second.evidence)).toBeInTheDocument()
    expect(within(current).getByText(member.user.email)).toBeInTheDocument()
    expect(screen.getByText('API feedback for revision one.')).toBeInTheDocument()
    expect(screen.getByText('ارسال شماره 1')).toBeInTheDocument()
    expect(screen.getByText('ارسال شماره 2')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'شروع بررسی' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'درخواست اصلاح' })).not.toBeInTheDocument()
    expect(callsFor(api, `/api/v1/project-runs/${runId}/sprints/`, 'GET')).toHaveLength(1)
  })

  it('starts review through the real action and renders UNDER_REVIEW controls only after refetch', async () => {
    const snapshot = submission('submission-2')
    const api = installApi({
      initialList: [listItem(sprintId, 1, 'SUBMITTED', snapshot)],
      initialDetails: [detail('SUBMITTED', [snapshot])],
    })
    const user = userEvent.setup()
    renderSection()
    await openReviewArea(user)

    await user.click(await screen.findByRole('button', { name: 'شروع بررسی' }))

    expect(await screen.findByRole('button', { name: 'درخواست اصلاح' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'تکمیل Sprint' })).toBeInTheDocument()
    const calls = callsFor(
      api,
      `/api/v1/project-runs/${runId}/sprints/${sprintId}/under-review/`,
      'POST',
    )
    expect(calls).toHaveLength(1)
    expect(JSON.parse(String(calls[0]?.[1]?.body))).toEqual({})
    expect(callsFor(api, `/api/v1/project-runs/${runId}/sprints/`, 'GET')).toHaveLength(2)
    expect(
      callsFor(api, `/api/v1/project-runs/${runId}/sprints/${sprintId}/`, 'GET'),
    ).toHaveLength(2)
  })

  it('uses the explicit latest_submission response instead of sorting history in the browser', async () => {
    const authoritativeLatest = submission('submission-2')
    const otherHistory = submission('submission-1')
    const response = detail('SUBMITTED', [authoritativeLatest, otherHistory])
    response.latest_submission = authoritativeLatest
    const list = listItem(sprintId, 1, 'SUBMITTED', authoritativeLatest)
    installApi({ initialList: [list], initialDetails: [response] })
    const user = userEvent.setup()
    renderSection()
    await openReviewArea(user)

    const current = await screen.findByRole('region', {
      name: 'ارسال فعلی برای بررسی',
    })
    expect(
      within(current).getByRole('link', {
        name: authoritativeLatest.final_commit_url ?? '',
      }),
    ).toBeInTheDocument()
    expect(
      within(current).queryByRole('link', {
        name: otherHistory.final_commit_url ?? '',
      }),
    ).not.toBeInTheDocument()
  })

  it('blocks blank change feedback and then persists only the approved feedback payload', async () => {
    const snapshot = submission('submission-2')
    const api = installApi({
      initialList: [listItem(sprintId, 1, 'UNDER_REVIEW', snapshot)],
      initialDetails: [detail('UNDER_REVIEW', [snapshot])],
    })
    const user = userEvent.setup()
    renderSection()
    await openReviewArea(user)

    await user.click(await screen.findByRole('button', { name: 'درخواست اصلاح' }))
    const feedback = screen.getByLabelText('بازخورد موردنیاز برای اصلاح')
    await user.type(feedback, '   ')
    await user.click(screen.getByRole('button', { name: 'ثبت درخواست اصلاح' }))

    expect(
      screen.getByText('برای درخواست اصلاح، بازخورد معنادار وارد کنید.'),
    ).toBeInTheDocument()
    expect(
      callsFor(
        api,
        `/api/v1/project-runs/${runId}/sprints/${sprintId}/request-changes/`,
        'POST',
      ),
    ).toHaveLength(0)

    await user.clear(feedback)
    await user.type(feedback, '  لطفاً تست‌های API را اصلاح کنید.  ')
    await user.click(screen.getByRole('button', { name: 'ثبت درخواست اصلاح' }))

    expect(await screen.findAllByText(/CHANGES_REQUESTED/)).not.toHaveLength(0)
    expect(
      screen.getAllByText('لطفاً تست‌های API را اصلاح کنید.'),
    ).toHaveLength(2)
    const calls = callsFor(
      api,
      `/api/v1/project-runs/${runId}/sprints/${sprintId}/request-changes/`,
      'POST',
    )
    expect(calls).toHaveLength(1)
    expect(JSON.parse(String(calls[0]?.[1]?.body))).toEqual({
      feedback: 'لطفاً تست‌های API را اصلاح کنید.',
    })
  })

  it.each([
    { feedback: '', expectedBody: {} },
    { feedback: 'Accepted by Staff.', expectedBody: { feedback: 'Accepted by Staff.' } },
  ])('completes with optional feedback %# and refetches authoritative history', async ({ feedback, expectedBody }) => {
    const snapshot = submission('submission-2')
    const api = installApi({
      initialList: [listItem(sprintId, 1, 'UNDER_REVIEW', snapshot)],
      initialDetails: [detail('UNDER_REVIEW', [snapshot])],
    })
    const user = userEvent.setup()
    renderSection()
    await openReviewArea(user)

    await user.click(await screen.findByRole('button', { name: 'تکمیل Sprint' }))
    expect(
      screen.getByText('تکمیل این آخرین Sprint، ProjectRun را نیز طبق پاسخ قطعی backend تکمیل می‌کند.'),
    ).toBeInTheDocument()
    if (feedback) await user.type(screen.getByLabelText('بازخورد (اختیاری)'), feedback)
    await user.click(screen.getByRole('button', { name: 'تأیید تکمیل' }))

    expect(await screen.findAllByText(/COMPLETED/)).not.toHaveLength(0)
    const calls = callsFor(
      api,
      `/api/v1/project-runs/${runId}/sprints/${sprintId}/complete/`,
      'POST',
    )
    expect(calls).toHaveLength(1)
    expect(JSON.parse(String(calls[0]?.[1]?.body))).toEqual(expectedBody)
  })

  it('opens a LOCKED Sprint through the backend and keeps non-review states free of review actions', async () => {
    const locked = detail('LOCKED')
    const api = installApi({
      initialList: [listItem(sprintId, 1, 'LOCKED')],
      initialDetails: [locked],
    })
    const user = userEvent.setup()
    renderSection()
    await openReviewArea(user)

    expect(await screen.findByRole('button', { name: 'بازکردن Sprint' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'شروع بررسی' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'درخواست اصلاح' })).not.toBeInTheDocument()
    expect(screen.getByText('تاریخچه ارسال خالی است')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'بازکردن Sprint' }))
    expect(await screen.findAllByText(/ACTIVE/)).not.toHaveLength(0)
    expect(
      callsFor(
        api,
        `/api/v1/project-runs/${runId}/sprints/${sprintId}/open/`,
        'POST',
      ),
    ).toHaveLength(1)
    expect(screen.queryByRole('button', { name: 'شروع بررسی' })).not.toBeInTheDocument()
  })

  it.each<SprintRunState>(['ACTIVE', 'CHANGES_REQUESTED', 'COMPLETED'])(
    'keeps %s read-only from the review-decision perspective',
    async (state) => {
      const snapshot = submission('submission-2')
      installApi({
        initialList: [listItem(sprintId, 1, state, snapshot)],
        initialDetails: [detail(state, [snapshot])],
      })
      const user = userEvent.setup()
      renderSection()
      await openReviewArea(user)
      await screen.findAllByText(new RegExp(state))

      expect(screen.queryByRole('button', { name: 'شروع بررسی' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'درخواست اصلاح' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'تکمیل Sprint' })).not.toBeInTheDocument()
    },
  )

  it('keeps a terminal ProjectRun history visible while hiding every mutation control', async () => {
    const snapshot = submission('submission-2', {
      review_decision: decision('COMPLETED', 'Preserved terminal review.'),
    })
    installApi({
      active: false,
      initialList: [listItem(sprintId, 1, 'COMPLETED', snapshot)],
      initialDetails: [detail('COMPLETED', [snapshot])],
    })
    const user = userEvent.setup()
    renderSection()
    await openReviewArea(user)

    expect(await screen.findAllByText('Preserved terminal review.')).toHaveLength(2)
    expect(
      screen.getByText(/این ProjectRun تاریخی است/),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'بازکردن Sprint' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'شروع بررسی' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'درخواست اصلاح' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'تکمیل Sprint' })).not.toBeInTheDocument()
  })

  it('refetches after a stale mutation conflict and never fakes the requested state', async () => {
    const snapshot = submission('submission-2')
    installApi({
      initialList: [listItem(sprintId, 1, 'UNDER_REVIEW', snapshot)],
      initialDetails: [detail('UNDER_REVIEW', [snapshot])],
      failAction: 'request-changes',
      stateAfterFailure: 'COMPLETED',
    })
    const user = userEvent.setup()
    renderSection()
    await openReviewArea(user)

    await user.click(await screen.findByRole('button', { name: 'درخواست اصلاح' }))
    await user.type(
      screen.getByLabelText('بازخورد موردنیاز برای اصلاح'),
      'Stale action feedback',
    )
    await user.click(screen.getByRole('button', { name: 'ثبت درخواست اصلاح' }))

    expect(await screen.findByText(/وضعیت Sprint تغییر کرده است/)).toBeInTheDocument()
    expect(await screen.findAllByText(/COMPLETED/)).not.toHaveLength(0)
    expect(screen.queryByText(/CHANGES_REQUESTED/)).not.toBeInTheDocument()
  })

  it('surfaces the Staff authorization failure without exposing review data', async () => {
    installApi({
      forbidden: true,
      initialList: [],
      initialDetails: [],
    })
    const user = userEvent.setup()
    renderSection()
    await user.click(screen.getByRole('button', { name: 'ورود به بررسی اسپرینت‌ها' }))

    expect(
      await screen.findByText('این بخش فقط برای Staff/Admin فعال در دسترس است.'),
    ).toBeInTheDocument()
    expect(screen.queryByLabelText('ProjectRun')).not.toBeInTheDocument()
  })
})
