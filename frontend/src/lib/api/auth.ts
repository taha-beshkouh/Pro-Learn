import { ApiError, apiClient } from './client'
import { API_ENDPOINTS as endpoints } from './endpoints'
import type { CurrentUser, GuestParticipationContext, ProfileRoleResponse } from './types'

export type Credentials = { email: string; password: string }
export const authenticate = (mode: 'login' | 'register', credentials: Credentials) =>
  apiClient.post<CurrentUser>(endpoints.auth[mode], credentials)

export function isMissingSession(error: unknown) {
  return error instanceof ApiError && (error.status === 401 || (
    error.status === 403 && JSON.stringify(error.data).includes('Authentication credentials were not provided.')
  ))
}

export const stackPath = (versionId: string) =>
  `/projects/${encodeURIComponent(versionId)}/stack-selection`

export function preserveProjectContinuation(versionId: string) {
  // PATCH preserves the session's existing role. No participation stack is written.
  return apiClient.patch<GuestParticipationContext>(endpoints.profiles.guestContext, {
    project_version_id: versionId,
    intended_action: 'join_project',
    return_path: stackPath(versionId),
  })
}

export type ContinuationResult = {
  destination?: string
  message?: string
  projectVersionId?: string
}

async function optionalRecord<T>(path: string, signal?: AbortSignal) {
  try {
    return await apiClient.get<T>(path, { signal })
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}

export async function resolveContinuation(
  requestedVersionId?: string,
  signal?: AbortSignal,
): Promise<ContinuationResult> {
  const [context, profile, readiness, checks, run] = await Promise.all([
    apiClient.get<GuestParticipationContext>(endpoints.profiles.guestContext, { signal }),
    apiClient.get<ProfileRoleResponse>(endpoints.profiles.current, { signal }),
    optionalRecord<{ project_version_id: string; project_name: string }>(endpoints.readiness.mine, signal),
    apiClient.get<{ id: string; project_version_id: string }[]>(endpoints.readyChecks.mine, { signal }),
    optionalRecord<{ id: string }>(endpoints.projectRuns.dashboard, signal),
  ])
  if (run) return { destination: '/dashboard' }
  if (readiness) return {
    message: `آمادگی شما برای پروژه «${readiness.project_name}» ثبت شده است. منتظر تشکیل تیم بمانید.`,
    projectVersionId: readiness.project_version_id,
  }
  // This API lists is_current invitations, including confirmed historical ones.
  // It does not expose whether their Formation has finished. Never assume eligibility.
  if (checks.length) return {
    message: 'دعوت Ready Check در حساب شما وجود دارد. ادامه مشارکت جدید تا مشخص شدن وضعیت آن در دسترس نیست.',
    destination: '/ready-check',
  }
  const versionId = context.project_version_id || requestedVersionId
  if (context.selected_role_id && context.selected_role_id !== profile.selected_role?.id) {
    return {
      message: 'نقش انتخاب‌شده پیش از ورود با نقش حساب شما یکسان نیست. ادامه پروژه متوقف است؛ تغییر یا تأیید نقش در حال حاضر در دسترس نیست.',
      projectVersionId: versionId,
    }
  }
  if (requestedVersionId && context.project_version_id && requestedVersionId !== context.project_version_id) {
    return { message: 'نسخه این صفحه با نسخه ذخیره‌شده برای ادامه یکسان نیست.', projectVersionId: context.project_version_id }
  }
  if (!versionId) return { message: 'با موفقیت وارد حساب خود شده‌اید.' }
  if (!profile.selected_role) return {
    message: 'هنوز نقشی در حساب شما ثبت نشده است. ادامه پروژه تا تکمیل نقش حساب در دسترس نیست.',
    projectVersionId: versionId,
  }
  // Only the known exact-version route is resumable. Never navigate arbitrary session URLs.
  if (!requestedVersionId && (
    context.intended_action !== 'join_project' || context.return_path !== stackPath(versionId)
  )) return { message: 'نسخه پروژه حفظ شده است، اما مسیر ادامه مشخص نیست.', projectVersionId: versionId }
  return { destination: stackPath(versionId), projectVersionId: versionId }
}

export function authErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return 'ارتباط با سرور برقرار نشد. اتصال اینترنت را بررسی و دوباره تلاش کنید.'
  const data = JSON.stringify(error.data || '')
  if (error.status === 401) return 'نشست شما پایان یافته است. دوباره وارد شوید.'
  if (error.status === 403) return /csrf|<!DOCTYPE|<html/i.test(data)
    ? 'اعتبار امنیتی درخواست تأیید نشد. دوباره تلاش کنید.'
    : 'دسترسی به این درخواست ممکن نیست. وضعیت ورود خود را بررسی کنید.'
  if (error.status === 429) return 'تعداد تلاش‌ها بیش از حد مجاز است. کمی بعد دوباره تلاش کنید.'
  if (data.includes('Unable to log in with the provided credentials.')) return 'ایمیل یا رمز عبور درست نیست.'
  if (data.includes('A user with this email already exists.')) return 'این ایمیل قبلاً ثبت شده است. وارد حساب خود شوید.'
  if (data.includes('continuation role does not match')) return 'نقش انتخاب‌شده پیش از ورود با نقش حساب شما یکسان نیست. ادامه پروژه متوقف است.'
  if (data.includes('requested version does not match')) return 'نسخه پروژه با نسخه ذخیره‌شده برای ادامه یکسان نیست.'
  if (data.includes('technology_stack_id')) return 'این Stack برای نقش شما در این نسخه قابل انتخاب نیست.'
  if (data.includes('Published project version not found.')) return 'نسخه پروژه پیدا نشد یا دیگر منتشرشده نیست.'
  if (error.status === 400) {
    const messages: string[] = []
    if (data.includes('email')) messages.push('یک نشانی ایمیل معتبر وارد کنید.')
    if (data.includes('password')) {
      if (data.includes('too short')) {
        const minimum = data.match(/at least (\d+) characters/)
        messages.push(minimum ? `رمز عبور باید حداقل ${minimum[1]} نویسه داشته باشد.` : 'رمز عبور کوتاه است؛ رمز طولانی‌تری وارد کنید.')
      }
      if (data.includes('too common')) messages.push('رمز عبور بسیار رایج است؛ رمز دیگری انتخاب کنید.')
      if (data.includes('entirely numeric')) messages.push('رمز عبور نباید فقط از عدد تشکیل شده باشد.')
      if (data.includes('too similar')) messages.push('رمز عبور نباید شبیه اطلاعات حساب باشد.')
      if (!messages.length) messages.push('رمز عبور معتبر وارد کنید (حداکثر ۱۲۸ نویسه).')
    }
    return messages.join(' ') || 'اطلاعات درخواست معتبر نیست. ورودی‌ها را بررسی کنید.'
  }
  if (error.status === 404) return 'اطلاعات موردنیاز پیدا نشد.'
  return 'سرور اکنون نمی‌تواند درخواست را انجام دهد. دوباره تلاش کنید.'
}
