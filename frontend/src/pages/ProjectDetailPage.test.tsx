import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ProjectVersionDetailResponse } from '../lib/api/types'
import { ProjectDetailPage } from './ProjectDetailPage'

const frontendRole = {
  id: 'role-frontend',
  code: 'FRONTEND_DEVELOPER',
  name: 'Frontend Developer',
}

const backendRole = {
  id: 'role-backend',
  code: 'BACKEND_DEVELOPER',
  name: 'Backend Developer',
}

const designerRole = {
  id: 'role-designer',
  code: 'PRODUCT_DESIGNER',
  name: 'Product Designer',
}

const reactStack = {
  id: 'stack-react',
  code: 'react-typescript-vite',
  name: 'React + TypeScript + Vite',
}

const djangoStack = {
  id: 'stack-django',
  code: 'django-drf',
  name: 'Django + Django REST Framework',
}

const firstSprint = {
  id: 'sprint-1',
  sequence: 1,
  title: 'API supplied Sprint',
  brief: 'A brief returned by the exact version API.',
  planned_start_offset_days: 0,
  planned_duration_days: 7,
  planned_end_offset_days: 7,
}

const sharedWorkItem = {
  id: 'work-shared',
  title: 'Shared API work',
  description: 'Coordinate the real shared increment.',
  position: 1,
  role: null,
  technology_stack: null,
  sprint_template: {
    id: firstSprint.id,
    sequence: firstSprint.sequence,
    title: firstSprint.title,
  },
}

const frontendWorkItem = {
  id: 'work-frontend',
  title: 'Selected role API work',
  description: 'Build the interface from the supplied contract.',
  position: 2,
  role: frontendRole,
  technology_stack: null,
  sprint_template: sharedWorkItem.sprint_template,
}

const backendWorkItem = {
  id: 'work-backend',
  title: 'Other role API work',
  description: 'This is not relevant to the selected role context.',
  position: 3,
  role: backendRole,
  technology_stack: null,
  sprint_template: sharedWorkItem.sprint_template,
}

function projectResponse(): ProjectVersionDetailResponse {
  return {
    project_template: {
      id: 'template-api-project',
      slug: 'api-project',
      name: 'API Project',
      level: { id: 'level-2', number: 2, name: 'Level 2' },
    },
    id: 'version-42',
    version_number: 4,
    summary: 'Summary returned by the exact version API.',
    full_description: 'شرح کامل پروژه از API. '.repeat(30),
    duration_weeks: 6,
    sprint_count: 2,
    weekly_effort_hours_min: 8,
    weekly_effort_hours_max: 12,
    participant_database: '',
    published_at: '2026-08-30T12:00:00Z',
    sprint_templates: [
      firstSprint,
      {
        id: 'sprint-2',
        sequence: 2,
        title: 'Second API Sprint',
        brief: 'Second brief from the API.',
        planned_start_offset_days: 7,
        planned_duration_days: 7,
        planned_end_offset_days: 14,
      },
    ],
    role_requirements: [
      {
        id: 'requirement-frontend',
        role: frontendRole,
        requires_stack: true,
        stack_policy: 'FIXED',
        context: 'Frontend context returned by the API.',
        configured_stacks: [reactStack],
        prerequisites: [
          {
            id: 'prerequisite-frontend',
            title: 'Frontend API prerequisite',
            description: 'Required frontend knowledge.',
            position: 1,
          },
        ],
      },
      {
        id: 'requirement-backend',
        role: backendRole,
        requires_stack: true,
        stack_policy: 'ALLOWLIST',
        context: 'Backend context returned by the API.',
        configured_stacks: [djangoStack],
        prerequisites: [
          {
            id: 'prerequisite-backend',
            title: 'Other role prerequisite',
            description: '',
            position: 1,
          },
        ],
      },
      {
        id: 'requirement-designer',
        role: designerRole,
        requires_stack: false,
        stack_policy: null,
        context: '',
        configured_stacks: [],
        prerequisites: [],
      },
    ],
    work_items: [sharedWorkItem, frontendWorkItem, backendWorkItem],
    role_context: {
      id: 'requirement-frontend',
      role: frontendRole,
      requires_stack: true,
      stack_policy: 'FIXED',
      context: 'Frontend context returned by the API.',
      compatible_stacks: [reactStack],
      auto_selected_stack: reactStack,
      selected_stack: reactStack,
      prerequisites: [
        {
          id: 'prerequisite-frontend',
          title: 'Frontend API prerequisite',
          description: 'Required frontend knowledge.',
          position: 1,
        },
      ],
      work_items: [frontendWorkItem],
    },
    shared_work_items: [sharedWorkItem],
  }
}

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderDetail(versionId = 'version-42') {
  return render(
    <MemoryRouter initialEntries={[`/projects/${versionId}`]}>
      <Routes>
        <Route
          path="/projects/:projectVersionId"
          element={<ProjectDetailPage />}
        />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('ProjectDetailPage', () => {
  it('uses the exact-version API and renders interactive API-backed sections', async () => {
    const user = userEvent.setup()
    const api = vi.fn(async (input: RequestInfo | URL) => {
      void input
      return jsonResponse(projectResponse())
    })
    vi.stubGlobal('fetch', api)

    renderDetail()

    expect(screen.getByRole('status')).toHaveTextContent(
      'در حال دریافت جزئیات نسخه پروژه...',
    )
    expect(
      await screen.findByRole('heading', { level: 1, name: 'API Project' }),
    ).toBeInTheDocument()
    expect(api).toHaveBeenCalledTimes(1)
    expect(api).toHaveBeenCalledWith(
      '/api/v1/project-versions/version-42/',
      expect.objectContaining({ method: 'GET', credentials: 'include' }),
    )
    expect(
      api.mock.calls.some(([url]) => String(url).includes('/api/v1/projects/version-42/')),
    ).toBe(false)

    expect(screen.getByText('8 تا 12 ساعت در هفته')).toBeInTheDocument()
    expect(screen.getByText('FIXED · ثابت')).toBeInTheDocument()
    expect(screen.getByText('ALLOWLIST · فهرست مجاز')).toBeInTheDocument()
    expect(screen.getByText('بدون استک فنی')).toBeInTheDocument()
    expect(screen.getByText('Frontend API prerequisite')).toBeInTheDocument()
    expect(screen.queryByText('Other role prerequisite')).not.toBeInTheDocument()

    const descriptionToggle = screen.getByRole('button', {
      name: 'مشاهده بیشتر',
    })
    expect(descriptionToggle).toHaveAttribute('aria-expanded', 'false')
    await user.click(descriptionToggle)
    expect(
      screen.getByRole('button', { name: 'مشاهده کمتر' }),
    ).toHaveAttribute('aria-expanded', 'true')

    const sprintTrigger = screen.getByRole('button', {
      name: /Sprint 1.*API supplied Sprint/,
    })
    expect(sprintTrigger).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getByText('Shared API work')).not.toBeVisible()
    await user.click(sprintTrigger)
    expect(sprintTrigger).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Shared API work')).toBeInTheDocument()
    expect(screen.getByText('Selected role API work')).toBeInTheDocument()
    expect(screen.queryByText('Other role API work')).not.toBeInTheDocument()

    expect(screen.getByRole('link', { name: 'ادامه با این پروژه' })).toHaveAttribute(
      'href',
      '/projects/version-42/stack-selection',
    )
  })

  it('shows the unpublished/not-found state for a 404 response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse({ detail: 'Published project version not found.' }, 404),
      ),
    )

    renderDetail('missing-version')

    expect(
      await screen.findByRole('heading', {
        name: 'این نسخه پروژه در دسترس نیست',
      }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'تلاش دوباره' })).not.toBeInTheDocument()
  })

  it('shows an API error and retries the same exact-version request', async () => {
    const user = userEvent.setup()
    const api = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: 'Temporary outage.' }, 503))
      .mockResolvedValueOnce(jsonResponse(projectResponse()))
    vi.stubGlobal('fetch', api)

    renderDetail()

    expect(
      await screen.findByRole('heading', {
        name: 'دریافت جزئیات پروژه ممکن نشد',
      }),
    ).toBeInTheDocument()
    expect(screen.getByText('Temporary outage.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'تلاش دوباره' }))
    expect(
      await screen.findByRole('heading', { level: 1, name: 'API Project' }),
    ).toBeInTheDocument()
    expect(api).toHaveBeenCalledTimes(2)
  })

  it('renders explicit empty states when optional API content is absent', async () => {
    const response = projectResponse()
    response.full_description = ''
    response.sprint_templates = []
    response.role_requirements = []
    response.work_items = []
    response.role_context = null
    response.shared_work_items = []
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(response)))

    renderDetail()

    expect(
      await screen.findByRole('heading', { name: 'توضیح کامل ثبت نشده است' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Sprint ثبت نشده است' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'سیاست استک ثبت نشده است' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'نقشی ثبت نشده است' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'پیش‌نیازی ثبت نشده است' })).toBeInTheDocument()
  })
})
