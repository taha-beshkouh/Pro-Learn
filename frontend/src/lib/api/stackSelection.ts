import { apiClient } from './client'
import { API_ENDPOINTS } from './endpoints'
import { loadProjectVersionDetail } from './projectDetail'
import type {
  ProjectReadinessResponse,
  ProjectStackSelectionResponse,
} from './types'

export type StackSelectionPageData = {
  projectVersion: Awaited<ReturnType<typeof loadProjectVersionDetail>>
}

export async function loadStackSelectionPageData(
  projectVersionId: string,
  signal: AbortSignal,
): Promise<StackSelectionPageData> {
  const projectVersion = await loadProjectVersionDetail(projectVersionId, signal)
  return {
    projectVersion,
  }
}

export function persistProjectStackSelection(
  projectVersionId: string,
  technologyStackId: string | null,
) {
  return apiClient.post<ProjectStackSelectionResponse>(
    API_ENDPOINTS.projects.stackSelection(projectVersionId),
    technologyStackId ? { technology_stack_id: technologyStackId } : {},
  )
}

export function createProjectReadiness() {
  return apiClient.post<ProjectReadinessResponse>(
    API_ENDPOINTS.readiness.mine,
    {},
  )
}
