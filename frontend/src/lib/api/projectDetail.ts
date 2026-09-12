import { apiClient } from './client'
import { API_ENDPOINTS } from './endpoints'
import type { ProjectVersionDetailResponse } from './types'

export function loadProjectVersionDetail(
  projectVersionId: string,
  signal: AbortSignal,
) {
  return apiClient.get<ProjectVersionDetailResponse>(
    API_ENDPOINTS.projects.versionDetail(projectVersionId),
    { signal },
  )
}
