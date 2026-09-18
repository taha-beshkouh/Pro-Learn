import { authErrorMessage } from './auth'
import { ApiError, apiClient } from './client'
import { API_ENDPOINTS } from './endpoints'
import type {
  SprintRunResponse,
  StaffSprintRunDetailResponse,
  StaffSprintRunListItem,
} from './types'

export function loadStaffSprintRuns(
  projectRunId: string,
  signal?: AbortSignal,
) {
  return apiClient.get<StaffSprintRunListItem[]>(
    API_ENDPOINTS.projectRuns.staffSprints(projectRunId),
    { signal },
  )
}

export function loadStaffSprintDetail(
  projectRunId: string,
  sprintRunId: string,
  signal?: AbortSignal,
) {
  return apiClient.get<StaffSprintRunDetailResponse>(
    API_ENDPOINTS.projectRuns.staffSprint(projectRunId, sprintRunId),
    { signal },
  )
}

export function openStaffSprint(projectRunId: string, sprintRunId: string) {
  return apiClient.post<SprintRunResponse>(
    API_ENDPOINTS.projectRuns.openSprint(projectRunId, sprintRunId),
    {},
  )
}

export function startStaffSprintReview(
  projectRunId: string,
  sprintRunId: string,
) {
  return apiClient.post<SprintRunResponse>(
    API_ENDPOINTS.projectRuns.startSprintReview(projectRunId, sprintRunId),
    {},
  )
}

export function requestStaffSprintChanges(
  projectRunId: string,
  sprintRunId: string,
  feedback: string,
) {
  return apiClient.post<SprintRunResponse>(
    API_ENDPOINTS.projectRuns.requestSprintChanges(projectRunId, sprintRunId),
    { feedback },
  )
}

export function completeStaffSprint(
  projectRunId: string,
  sprintRunId: string,
  feedback?: string,
) {
  return apiClient.post<SprintRunResponse>(
    API_ENDPOINTS.projectRuns.completeSprint(projectRunId, sprintRunId),
    feedback ? { feedback } : {},
  )
}

function firstFieldMessage(data: unknown): string | null {
  if (typeof data === 'string' && data.trim()) return data
  if (Array.isArray(data)) {
    for (const item of data) {
      const message = firstFieldMessage(item)
      if (message) return message
    }
  }
  if (data && typeof data === 'object') {
    for (const value of Object.values(data)) {
      const message = firstFieldMessage(value)
      if (message) return message
    }
  }
  return null
}

export function staffSprintReviewErrorMessage(error: unknown) {
  if (!(error instanceof ApiError)) {
    return error instanceof Error
      ? error.message
      : 'ارتباط با سرور برقرار نشد. دوباره تلاش کنید.'
  }
  if (error.status === 401) {
    return 'نشست شما پایان یافته است. دوباره وارد شوید.'
  }
  if (error.status === 403) {
    return 'این بخش فقط برای Staff/Admin فعال در دسترس است.'
  }
  if (error.status === 404) {
    return 'ProjectRun یا Sprint موردنظر پیدا نشد.'
  }
  if (error.status === 409) {
    return `${error.message} وضعیت Sprint تغییر کرده است؛ اطلاعات تازه بارگذاری می‌شود.`
  }
  return firstFieldMessage(error.data) ?? authErrorMessage(error)
}
