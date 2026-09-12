import { loadProjectVersionDetail } from './projectDetail'
import { ApiError, apiClient } from './client'
import { API_ENDPOINTS } from './endpoints'
import type {
  ProjectRunDashboardResponse,
  ProjectVersionDetailResponse,
  SprintRunResponse,
} from './types'

export type DashboardPageData = {
  dashboard: ProjectRunDashboardResponse
  projectVersion: ProjectVersionDetailResponse
  sprints: SprintRunResponse[]
}

export class DashboardContractError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'DashboardContractError'
  }
}

export async function loadDashboardPageData(
  signal?: AbortSignal,
): Promise<DashboardPageData | null> {
  let dashboard: ProjectRunDashboardResponse

  try {
    dashboard = await apiClient.get<ProjectRunDashboardResponse>(
      API_ENDPOINTS.projectRuns.dashboard,
      { signal },
    )
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }

  const requestSignal = signal ?? new AbortController().signal
  const [sprints, projectVersion] = await Promise.all([
    apiClient.get<SprintRunResponse[]>(API_ENDPOINTS.projectRuns.sprints, {
      signal,
    }),
    loadProjectVersionDetail(dashboard.project.version_id, requestSignal),
  ])

  if (
    projectVersion.id !== dashboard.project.version_id ||
    projectVersion.project_template.id !== dashboard.project.id ||
    projectVersion.version_number !== dashboard.project.version_number
  ) {
    throw new DashboardContractError(
      'ProjectRun and ProjectVersion identity do not match.',
    )
  }

  if (
    dashboard.current_sprint &&
    !sprints.some((sprint) => sprint.id === dashboard.current_sprint?.id)
  ) {
    throw new DashboardContractError(
      'The current Sprint is missing from the ProjectRun Sprint list.',
    )
  }

  return { dashboard, projectVersion, sprints }
}
