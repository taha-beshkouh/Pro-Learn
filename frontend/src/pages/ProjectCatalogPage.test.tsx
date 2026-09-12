import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import { ProjectCatalogPage } from './ProjectCatalogPage'

const frontendRole = {
  id: 'role-frontend',
  code: 'FRONTEND_DEVELOPER',
  name: 'Frontend Developer',
}

const levels = [
  { id: 'level-1', number: 1, name: 'Level 1' },
  { id: 'level-2', number: 2, name: 'Level 2' },
]

type MockProject = {
  compatible?: boolean
  levelNumber?: number
  name: string
  published?: boolean
  summary?: string
  templateId: string
  versionId: string
}

type MockApiOptions = {
  failList?: boolean
  projects: MockProject[]
  selectedRole?: boolean
}

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function projectLevel(project: MockProject) {
  const number = project.levelNumber ?? 1
  return levels.find((level) => level.number === number) ?? levels[0]
}

function installCatalogApi({
  failList = false,
  projects,
  selectedRole = false,
}: MockApiOptions) {
  const api = vi.fn(async (input: RequestInfo | URL) => {
    const rawUrl = input instanceof Request ? input.url : String(input)
    const url = new URL(rawUrl, 'http://frontend.test')

    if (url.pathname === '/api/v1/levels/') {
      return jsonResponse(levels)
    }
    if (url.pathname === '/api/v1/guest-context/') {
      return jsonResponse(
        selectedRole ? { selected_role_id: frontendRole.id } : {},
      )
    }
    if (url.pathname === '/api/v1/roles/') {
      return jsonResponse([frontendRole])
    }
    if (url.pathname === '/api/v1/projects/') {
      if (failList) {
        return jsonResponse({ detail: 'Catalog unavailable.' }, 503)
      }
      const requestedLevel = url.searchParams.get('level')
      const matchingProjects = requestedLevel
        ? projects.filter(
            (project) => String(project.levelNumber ?? 1) === requestedLevel,
          )
        : projects
      return jsonResponse(
        matchingProjects.map((project) => ({
          id: project.templateId,
          slug: project.name.toLocaleLowerCase().replaceAll(' ', '-'),
          name: project.name,
          level: projectLevel(project),
          published_version_id:
            project.published === false ? null : project.versionId,
        })),
      )
    }

    const detailMatch = url.pathname.match(/^\/api\/v1\/projects\/([^/]+)\/$/)
    if (detailMatch) {
      const project = projects.find(
        (candidate) => candidate.templateId === detailMatch[1],
      )
      if (!project) {
        return jsonResponse({ detail: 'Project not found.' }, 404)
      }
      const level = projectLevel(project)
      return jsonResponse({
        id: project.templateId,
        slug: project.name.toLocaleLowerCase().replaceAll(' ', '-'),
        name: project.name,
        level,
        published_version_id: project.versionId,
        published_version: {
          id: project.versionId,
          version_number: 1,
          summary: project.summary ?? `${project.name} summary`,
          duration_weeks: 6,
          sprint_count: 6,
          role_context:
            selectedRole && project.compatible !== false
              ? {
                  role: frontendRole,
                  requires_stack: true,
                  stack_policy: 'FIXED',
                }
              : null,
        },
      })
    }

    return jsonResponse({ detail: 'Unexpected test endpoint.' }, 404)
  })

  vi.stubGlobal('fetch', api)
  return api
}

const anonymousAuth: AuthContextValue = {
  authenticate: vi.fn(async () => undefined),
  status: 'anonymous',
  user: null,
  error: null,
  refreshSession: vi.fn(async () => undefined),
  logout: vi.fn(async () => undefined),
}

function renderCatalog() {
  return render(
    <AuthContext.Provider value={anonymousAuth}>
      <MemoryRouter>
        <ProjectCatalogPage />
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('ProjectCatalogPage', () => {
  it('renders API projects generically, links by version id, and paginates real results', async () => {
    const user = userEvent.setup()
    const projects: MockProject[] = Array.from({ length: 7 }, (_, index) => ({
      templateId: `template-${index + 1}`,
      versionId: `version-${index + 1}`,
      name: `Generated Project ${index + 1}`,
    }))
    projects.push({
      templateId: 'template-unpublished',
      versionId: 'unused-version',
      name: 'Unpublished Project',
      published: false,
    })
    installCatalogApi({ projects })

    renderCatalog()

    expect(screen.getByRole('status')).toHaveTextContent(
      'در حال دریافت پروژه‌های منتشرشده...',
    )
    const firstCard = await screen.findByRole('link', {
      name: 'مشاهده جزئیات پروژه Generated Project 1',
    })
    expect(firstCard).toHaveAttribute('href', '/projects/version-1')
    expect(
      screen.queryByRole('heading', { name: 'Generated Project 7' }),
    ).not.toBeInTheDocument()
    expect(screen.queryByText('Unpublished Project')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Next/ }))
    expect(
      screen.getByRole('heading', { name: 'Generated Project 7' }),
    ).toBeInTheDocument()

    await user.type(screen.getByLabelText('جست‌وجوی پروژه'), 'Project 1')
    expect(
      await screen.findByRole('heading', { name: 'Generated Project 1' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'صفحه 1' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('uses backend role context and server-supported level filtering', async () => {
    const user = userEvent.setup()
    const api = installCatalogApi({
      selectedRole: true,
      projects: [
        {
          templateId: 'compatible-level-1',
          versionId: 'version-level-1',
          name: 'Compatible One',
        },
        {
          templateId: 'incompatible',
          versionId: 'version-incompatible',
          name: 'Wrong Role',
          compatible: false,
        },
        {
          templateId: 'compatible-level-2',
          versionId: 'version-level-2',
          name: 'Compatible Two',
          levelNumber: 2,
        },
      ],
    })

    renderCatalog()

    expect(
      await screen.findByRole('heading', {
        name: 'پروژه‌های مناسب نقش Frontend Developer',
      }),
    ).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Compatible One' })).toBeInTheDocument()
    expect(screen.queryByText('Wrong Role')).not.toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('سطح پروژه'), '2')
    expect(
      await screen.findByRole('heading', { name: 'Compatible Two' }),
    ).toBeInTheDocument()
    expect(screen.queryByText('Compatible One')).not.toBeInTheDocument()
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/projects/?level=2'),
        expect.anything(),
      ),
    )
  })

  it('shows the empty state when the API has no published project version', async () => {
    installCatalogApi({
      projects: [
        {
          templateId: 'template-unpublished',
          versionId: 'unused-version',
          name: 'Unpublished Project',
          published: false,
        },
      ],
    })

    renderCatalog()

    expect(
      await screen.findByRole('heading', { name: 'پروژه‌ای پیدا نشد' }),
    ).toBeInTheDocument()
  })

  it('shows the API error state without fabricating project cards', async () => {
    installCatalogApi({ projects: [], failList: true })

    renderCatalog()

    expect(
      await screen.findByRole('heading', { name: 'دریافت پروژه‌ها ممکن نشد' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Catalog unavailable.')).toBeInTheDocument()
    expect(screen.queryByRole('article')).not.toBeInTheDocument()
  })
})
