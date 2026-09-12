import { authErrorMessage } from './auth'
import { ApiError, apiClient } from './client'
import { API_ENDPOINTS } from './endpoints'
import type {
  GuestParticipationContext,
  PlatformRole,
  ProfileRoleResponse,
} from './types'

export type MvpRoleCode =
  | 'FRONTEND_DEVELOPER'
  | 'PRODUCT_DESIGNER'
  | 'BACKEND_DEVELOPER'

export const ROLE_SELECTION_LABELS: Record<MvpRoleCode, string> = {
  FRONTEND_DEVELOPER: 'Front-end Developer',
  PRODUCT_DESIGNER: 'Product Designer',
  BACKEND_DEVELOPER: 'Back-end Developer',
}

export type RoleSelectionNotice = {
  roleCode: MvpRoleCode
  roleLabel: string
}

export type RoleSelectionNavigationState = {
  roleSelection: {
    roleCode: MvpRoleCode
  }
}

class RoleSelectionContractError extends Error {}

function isMvpRoleCode(value: unknown): value is MvpRoleCode {
  return (
    typeof value === 'string' &&
    Object.hasOwn(ROLE_SELECTION_LABELS, value)
  )
}

export function roleSelectionNoticeFromState(
  state: unknown,
): RoleSelectionNotice | null {
  if (!state || typeof state !== 'object' || !('roleSelection' in state)) {
    return null
  }

  const selection = state.roleSelection
  if (
    !selection ||
    typeof selection !== 'object' ||
    !('roleCode' in selection) ||
    !isMvpRoleCode(selection.roleCode)
  ) {
    return null
  }

  return {
    roleCode: selection.roleCode,
    roleLabel: ROLE_SELECTION_LABELS[selection.roleCode],
  }
}

export async function selectRoleFromHome(
  authStatus: 'authenticated' | 'anonymous',
  roleCode: MvpRoleCode,
): Promise<PlatformRole> {
  const roles = await apiClient.get<PlatformRole[]>(
    API_ENDPOINTS.profiles.roles,
  )
  const requestedRole = roles.find((role) => role.code === roleCode)

  if (!requestedRole) {
    throw new RoleSelectionContractError(
      'The requested platform role is not available.',
    )
  }

  if (authStatus === 'authenticated') {
    const profile = await apiClient.post<ProfileRoleResponse>(
      API_ENDPOINTS.profiles.selectRole,
      { role_id: requestedRole.id },
    )

    if (profile.selected_role?.id !== requestedRole.id) {
      throw new RoleSelectionContractError(
        'The role-selection response did not confirm the requested role.',
      )
    }

    return profile.selected_role
  }

  const context = await apiClient.patch<GuestParticipationContext>(
    API_ENDPOINTS.profiles.guestContext,
    { selected_role_id: requestedRole.id },
  )

  if (context.selected_role_id !== requestedRole.id) {
    throw new RoleSelectionContractError(
      'The guest context did not confirm the requested role.',
    )
  }

  return requestedRole
}

export function roleSelectionErrorMessage(error: unknown): string {
  if (error instanceof RoleSelectionContractError) {
    return 'این نقش اکنون در دسترس نیست. لطفاً دوباره تلاش کنید.'
  }

  if (
    error instanceof ApiError &&
    error.status === 409 &&
    error.data &&
    typeof error.data === 'object' &&
    !Array.isArray(error.data) &&
    error.data.code === 'role_change_blocked'
  ) {
    switch (error.data.reason) {
      case 'active_readiness':
        return 'تا زمانی که آمادگی فعال پروژه دارید، تغییر نقش ممکن نیست.'
      case 'current_formation_or_ready_check':
        return 'تا پایان وضعیت فعلی تشکیل تیم یا Ready Check، تغییر نقش ممکن نیست.'
      case 'active_project_run':
        return 'در زمان اجرای یک پروژه فعال، تغییر نقش ممکن نیست.'
      default:
        return 'به‌دلیل وضعیت فعلی مشارکت شما، تغییر نقش ممکن نیست.'
    }
  }

  return authErrorMessage(error)
}
