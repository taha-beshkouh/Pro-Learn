import { authErrorMessage } from './auth'
import { ApiError, apiClient } from './client'
import { API_ENDPOINTS } from './endpoints'
import type {
  ProjectListItem,
  ProjectReadinessResponse,
  FormationReadyCheckResponse,
  StaffFormationProjectVersion,
  TeamFormationResponse,
} from './types'

export const REQUIRED_FORMATION_ROLE_CODES = [
  'BACKEND_DEVELOPER',
  'FRONTEND_DEVELOPER',
  'PRODUCT_DESIGNER',
] as const

export type RequiredFormationRoleCode =
  (typeof REQUIRED_FORMATION_ROLE_CODES)[number]

export async function loadStaffFormationProjectVersions(
  signal?: AbortSignal,
): Promise<StaffFormationProjectVersion[]> {
  const projects = await apiClient.get<ProjectListItem[]>(
    API_ENDPOINTS.projects.list,
    { signal },
  )
  const versions = new Map<string, StaffFormationProjectVersion>()

  for (const project of projects) {
    if (project.published_version_id) {
      versions.set(project.published_version_id, {
        projectVersionId: project.published_version_id,
        projectName: project.name,
        level: project.level,
      })
    }
  }

  return [...versions.values()]
}

export async function loadActiveReadinessCandidates(
  projectVersionId: string,
  signal?: AbortSignal,
) {
  const candidates = await apiClient.get<ProjectReadinessResponse[]>(
    API_ENDPOINTS.readiness.candidates(projectVersionId),
    { signal },
  )
  if (
    candidates.some(
      (candidate) =>
        candidate.project_version_id !== projectVersionId ||
        candidate.consumed_at !== null,
    )
  ) {
    throw new Error(
      'پاسخ آمادگی‌ها با نسخه دقیق پروژه یا وضعیت فعال مورد انتظار مطابقت ندارد.',
    )
  }
  return candidates
}

export function createTeamFormation(readinessIds: string[]) {
  return apiClient.post<TeamFormationResponse>(
    API_ENDPOINTS.teamFormations.listCreate,
    { readiness_ids: readinessIds },
  )
}

export function loadTeamFormations(signal?: AbortSignal) {
  return apiClient.get<TeamFormationResponse[]>(
    API_ENDPOINTS.teamFormations.listCreate,
    { signal },
  )
}

export function replaceFormationReadyCheck(
  formationId: string,
  readyCheckId: string,
  readinessId: string,
) {
  return apiClient.post<FormationReadyCheckResponse>(
    API_ENDPOINTS.teamFormations.replaceReadyCheck(formationId, readyCheckId),
    { readiness_id: readinessId },
  )
}

export function staffFormationErrorMessage(error: unknown) {
  if (!(error instanceof ApiError)) {
    return error instanceof Error
      ? error.message
      : 'ارتباط با سرور برقرار نشد. دوباره تلاش کنید.'
  }

  const payload = JSON.stringify(error.data ?? '')
  if (error.status === 401) {
    return 'نشست شما پایان یافته است. دوباره وارد شوید.'
  }
  if (error.status === 403) {
    return 'این بخش فقط برای Staff/Admin در دسترس است.'
  }
  if (error.status === 404) {
    return 'نسخه دقیق پروژه پیدا نشد یا دیگر منتشرشده نیست.'
  }
  if (payload.includes('Active readiness for the required exact ProjectVersion')) {
    return 'یکی از آمادگی‌های انتخاب‌شده دیگر برای این نسخه پروژه فعال نیست.'
  }
  if (payload.includes('unique active users with the required roles')) {
    return 'ترکیب انتخاب‌شده باید شامل سه کاربر فعال و نقش‌های موردنیاز باشد.'
  }
  if (payload.includes('readiness stack is not valid')) {
    return 'Stack یکی از آمادگی‌های انتخاب‌شده برای نقش پروژه معتبر نیست.'
  }
  if (payload.includes('same role') || payload.includes('required roles')) {
    return 'داوطلب جایگزین باید نقش همین جایگاه را داشته باشد و شرایط مشارکت را برآورده کند.'
  }
  if (payload.includes('Only a declined or expired slot')) {
    return 'فقط جایگاه ردشده یا منقضی‌شده قابل جایگزینی است. وضعیت تازه را بررسی کنید.'
  }
  if (payload.includes('current proposed formation')) {
    return 'یکی از کاربران انتخاب‌شده هم‌اکنون در یک Formation جاری قرار دارد.'
  }
  if (payload.includes('active ProjectRun')) {
    return 'یکی از کاربران انتخاب‌شده هم‌اکنون ProjectRun فعال دارد.'
  }
  if (error.status === 409) {
    return 'وضعیت یکی از آمادگی‌ها تغییر کرده است. فهرست تازه را بررسی کنید.'
  }
  return authErrorMessage(error)
}
