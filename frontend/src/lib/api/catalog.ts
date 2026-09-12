import { apiClient } from './client'
import { API_ENDPOINTS } from './endpoints'
import type {
  GuestParticipationContext,
  PlatformRole,
  ProfileRoleResponse,
  ProjectCatalogEntry,
  ProjectDetailResponse,
  ProjectLevel,
  ProjectListItem,
} from './types'

type CatalogAuthStatus = 'authenticated' | 'anonymous'

type LoadProjectCatalogOptions = {
  authStatus: CatalogAuthStatus
  levelNumber: number | null
  signal: AbortSignal
}

export type ProjectCatalogResult = {
  levels: ProjectLevel[]
  projects: ProjectCatalogEntry[]
  selectedRole: PlatformRole | null
}

function projectListEndpoint(levelNumber: number | null) {
  if (levelNumber === null) {
    return API_ENDPOINTS.projects.list
  }

  const params = new URLSearchParams({ level: String(levelNumber) })
  return `${API_ENDPOINTS.projects.list}?${params.toString()}`
}

async function selectedRoleForCatalog(
  authStatus: CatalogAuthStatus,
  signal: AbortSignal,
) {
  if (authStatus === 'authenticated') {
    const profile = await apiClient.get<ProfileRoleResponse>(
      API_ENDPOINTS.profiles.current,
      { signal },
    )
    return profile.selected_role
  }

  const context = await apiClient.get<GuestParticipationContext>(
    API_ENDPOINTS.profiles.guestContext,
    { signal },
  )
  if (!context.selected_role_id) {
    return null
  }

  const roles = await apiClient.get<PlatformRole[]>(API_ENDPOINTS.profiles.roles, {
    signal,
  })
  const selectedRole = roles.find((role) => role.id === context.selected_role_id)
  if (!selectedRole) {
    throw new Error('The selected platform role is no longer available.')
  }
  return selectedRole
}

export async function loadProjectCatalog({
  authStatus,
  levelNumber,
  signal,
}: LoadProjectCatalogOptions): Promise<ProjectCatalogResult> {
  const [levels, selectedRole, templates] = await Promise.all([
    apiClient.get<ProjectLevel[]>(API_ENDPOINTS.projects.levels, { signal }),
    selectedRoleForCatalog(authStatus, signal),
    apiClient.get<ProjectListItem[]>(projectListEndpoint(levelNumber), { signal }),
  ])

  const publishedTemplates = templates.filter(
    (template) => template.published_version_id !== null,
  )
  const details = await Promise.all(
    publishedTemplates.map((template) =>
      apiClient.get<ProjectDetailResponse>(
        API_ENDPOINTS.projects.detail(template.id),
        { signal },
      ),
    ),
  )

  const projects = details.flatMap<ProjectCatalogEntry>((project) => {
    const version = project.published_version
    if (!version) {
      return []
    }

    if (selectedRole && version.role_context?.role.id !== selectedRole.id) {
      return []
    }

    return [
      {
        templateId: project.id,
        versionId: version.id,
        name: project.name,
        slug: project.slug,
        level: project.level,
        summary: version.summary,
        durationWeeks: version.duration_weeks,
        sprintCount: version.sprint_count,
        role: version.role_context?.role ?? null,
      },
    ]
  })

  return { levels, projects, selectedRole }
}
