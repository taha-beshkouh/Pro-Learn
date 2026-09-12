import { loadProjectVersionDetail } from './projectDetail'
import { ApiError, apiClient } from './client'
import { API_ENDPOINTS } from './endpoints'
import type {
  CurrentProjectRunSummary,
  ProjectVersionDetailResponse,
  ReadyCheckResponse,
} from './types'

export type ReadyCheckPageData = {
  readyChecks: ReadyCheckResponse[]
  projectVersion: ProjectVersionDetailResponse | null
  projectRun: CurrentProjectRunSummary | null
}

export function loadCurrentReadyChecks(signal?: AbortSignal) {
  return apiClient.get<ReadyCheckResponse[]>(API_ENDPOINTS.readyChecks.mine, {
    signal,
  })
}

export async function loadCurrentProjectRun(signal?: AbortSignal) {
  try {
    return await apiClient.get<CurrentProjectRunSummary>(
      API_ENDPOINTS.projectRuns.dashboard,
      { signal },
    )
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}

export async function loadReadyCheckPageData(
  signal?: AbortSignal,
): Promise<ReadyCheckPageData> {
  const [readyChecks, projectRun] = await Promise.all([
    loadCurrentReadyChecks(signal),
    loadCurrentProjectRun(signal),
  ])

  const projectVersion =
    readyChecks.length === 1
      ? await loadProjectVersionDetail(
          readyChecks[0].project_version_id,
          signal ?? new AbortController().signal,
        )
      : null

  if (
    projectVersion &&
    projectVersion.id !== readyChecks[0].project_version_id
  ) {
    throw new Error('Ready Check project version response mismatch.')
  }

  return { readyChecks, projectVersion, projectRun }
}

export function confirmReadyCheck(
  readyCheckId: string,
  githubUsername?: string,
) {
  return apiClient.post<ReadyCheckResponse>(
    API_ENDPOINTS.readyChecks.confirm(readyCheckId),
    githubUsername ? { github_username: githubUsername } : {},
  )
}

export function declineReadyCheck(readyCheckId: string) {
  return apiClient.post<ReadyCheckResponse>(
    API_ENDPOINTS.readyChecks.decline(readyCheckId),
  )
}
