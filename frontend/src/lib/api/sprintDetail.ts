import { apiClient } from './client'
import { API_ENDPOINTS } from './endpoints'
import type {
  ProjectRunDashboardResponse,
  ProjectWorkItem,
  SprintRunDetailResponse,
  SprintRunState,
  SprintSubmissionResponse,
  TeamMemberSnapshot,
} from './types'

export class SprintDetailContractError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'SprintDetailContractError'
  }
}

const sprintStates = new Set<SprintRunState>([
  'LOCKED',
  'ACTIVE',
  'SUBMITTED',
  'UNDER_REVIEW',
  'CHANGES_REQUESTED',
  'COMPLETED',
])

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function hasString(record: Record<string, unknown>, key: string) {
  return typeof record[key] === 'string'
}

function isNullableString(value: unknown) {
  return value === null || typeof value === 'string'
}

function isRole(value: unknown) {
  return (
    isRecord(value) &&
    hasString(value, 'id') &&
    hasString(value, 'code') &&
    hasString(value, 'name')
  )
}

function isStack(value: unknown) {
  return value === null || isRole(value)
}

function isTeamMember(value: unknown): value is TeamMemberSnapshot {
  return (
    isRecord(value) &&
    hasString(value, 'id') &&
    isRecord(value.user) &&
    hasString(value.user, 'id') &&
    hasString(value.user, 'email') &&
    isRole(value.role) &&
    isStack(value.technology_stack) &&
    isNullableString(value.ended_at)
  )
}

function isSprintSummary(value: unknown) {
  return (
    value === null ||
    (isRecord(value) &&
      hasString(value, 'id') &&
      hasString(value, 'title') &&
      typeof value.sequence === 'number')
  )
}

function isWorkItem(value: unknown): value is ProjectWorkItem {
  return (
    isRecord(value) &&
    hasString(value, 'id') &&
    hasString(value, 'title') &&
    hasString(value, 'description') &&
    typeof value.position === 'number' &&
    (value.role === null || isRole(value.role)) &&
    isStack(value.technology_stack) &&
    isSprintSummary(value.sprint_template)
  )
}

function isSubmission(value: unknown): value is SprintSubmissionResponse {
  return (
    isRecord(value) &&
    hasString(value, 'id') &&
    isTeamMember(value.submitted_by) &&
    hasString(value, 'evidence') &&
    hasString(value, 'submitted_at')
  )
}

function assertSprintDetailContract(
  value: unknown,
): asserts value is SprintRunDetailResponse {
  if (
    !isRecord(value) ||
    !hasString(value, 'id') ||
    !hasString(value, 'sprint_template_id') ||
    typeof value.sequence !== 'number' ||
    !hasString(value, 'title') ||
    !hasString(value, 'brief') ||
    !hasString(value, 'state') ||
    !sprintStates.has(value.state as SprintRunState) ||
    !hasString(value, 'planned_start_at') ||
    !hasString(value, 'planned_end_at') ||
    !isNullableString(value.opened_at) ||
    !isNullableString(value.completed_at) ||
    !isNullableString(value.repository_url) ||
    !Array.isArray(value.work_items) ||
    !value.work_items.every(isWorkItem) ||
    !Array.isArray(value.submissions) ||
    !value.submissions.every(isSubmission) ||
    (value.latest_submission !== null &&
      !isSubmission(value.latest_submission))
  ) {
    throw new SprintDetailContractError(
      'Sprint detail response is missing authoritative runtime fields.',
    )
  }

  if (
    value.designated_submitter !== null &&
    !isTeamMember(value.designated_submitter)
  ) {
    throw new SprintDetailContractError(
      'Legacy Sprint designation has an invalid response shape.',
    )
  }

  const latest = value.submissions.at(-1) ?? null
  if (
    (latest === null && value.latest_submission !== null) ||
    (latest !== null && value.latest_submission?.id !== latest.id)
  ) {
    throw new SprintDetailContractError(
      'Sprint detail latest submission does not match its append-only history.',
    )
  }
}

export async function loadSprintDetail(
  sprintRunId: string,
  signal?: AbortSignal,
): Promise<SprintRunDetailResponse> {
  const response = await apiClient.get<unknown>(
    API_ENDPOINTS.projectRuns.sprint(sprintRunId),
    { signal },
  )
  assertSprintDetailContract(response)
  if (response.id !== sprintRunId) {
    throw new SprintDetailContractError(
      'Sprint detail response does not match the requested SprintRun.',
    )
  }
  return response
}

async function loadCurrentProjectRunId(signal?: AbortSignal) {
  const response = await apiClient.get<unknown>(
    API_ENDPOINTS.projectRuns.dashboard,
    { signal },
  )
  if (!isRecord(response) || !hasString(response, 'id')) {
    throw new SprintDetailContractError(
      'Current ProjectRun response does not contain its identifier.',
    )
  }
  return (response as Pick<ProjectRunDashboardResponse, 'id'>).id
}

export async function submitSprintEvidence({
  sprintRunId,
  evidence,
  signal,
}: {
  sprintRunId: string
  evidence: string
  signal?: AbortSignal
}) {
  const projectRunId = await loadCurrentProjectRunId(signal)
  await apiClient.post<unknown>(
    API_ENDPOINTS.projectRuns.submitSprint(projectRunId, sprintRunId),
    { evidence },
    { signal },
  )
}
