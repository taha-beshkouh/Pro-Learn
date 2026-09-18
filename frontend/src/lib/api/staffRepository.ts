import { authErrorMessage } from './auth'
import { ApiError, apiClient } from './client'
import { API_ENDPOINTS } from './endpoints'
import type { ProjectRunLifecycleResponse, StaffProjectRunRepository } from './types'

export function loadStaffProjectRunRepositories(signal?: AbortSignal) {
  return apiClient.get<StaffProjectRunRepository[]>(
    API_ENDPOINTS.projectRuns.staffList,
    { signal },
  )
}

export function markStaffProjectRunIncomplete(projectRunId: string) {
  return apiClient.post<ProjectRunLifecycleResponse>(
    API_ENDPOINTS.projectRuns.markIncomplete(projectRunId),
    {},
  )
}

export function staffIncompleteErrorMessage(error: unknown) {
  if (!(error instanceof ApiError)) {
    return 'ارتباط با سرور برقرار نشد. دوباره تلاش کنید.'
  }
  if (error.status === 409) {
    return `${error.message} وضعیت ProjectRun دوباره بارگذاری می‌شود.`
  }
  if (error.status === 404) {
    return 'ProjectRun موردنظر پیدا نشد یا دیگر فعال نیست.'
  }
  if (error.status === 403) {
    return 'این عملیات فقط برای Staff/Admin فعال در دسترس است.'
  }
  if (error.status === 400) {
    return error.message || 'درخواست ثبت وضعیت ناتمام معتبر نیست.'
  }
  return staffRepositoryErrorMessage(error)
}

export function saveProjectRunRepository(
  projectRunId: string,
  repositoryUrl: string | null,
) {
  return apiClient.patch<StaffProjectRunRepository>(
    API_ENDPOINTS.projectRuns.repository(projectRunId),
    { repository_url: repositoryUrl },
  )
}

export function staffRepositoryErrorMessage(error: unknown) {
  if (!(error instanceof ApiError)) {
    return 'ارتباط با سرور برقرار نشد. دوباره تلاش کنید.'
  }
  if (error.status === 401) {
    return 'نشست شما پایان یافته است. دوباره وارد شوید.'
  }
  if (error.status === 403) {
    return 'این بخش فقط برای Staff/Admin در دسترس است.'
  }
  if (error.status === 404) {
    return 'ProjectRun فعال پیدا نشد یا وضعیت آن تغییر کرده است.'
  }
  if (error.status === 400) {
    const repositoryErrors =
      error.data &&
      typeof error.data === 'object' &&
      !Array.isArray(error.data) &&
      Array.isArray(error.data.repository_url)
        ? error.data.repository_url
        : []
    if (
      repositoryErrors.some(
        (message) =>
          typeof message === 'string' &&
          message.includes('already assigned to another ProjectRun'),
      )
    ) {
      return 'این مخزن قبلاً برای ProjectRun دیگری ثبت شده است.'
    }
    return 'آدرس معتبر نیست. نشانی ریشه مخزن GitHub را وارد کنید.'
  }
  return authErrorMessage(error)
}
