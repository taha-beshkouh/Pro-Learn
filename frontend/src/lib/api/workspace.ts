import { ApiError, apiClient } from './client'
import { API_ENDPOINTS } from './endpoints'
import type { ProjectRunWorkspaceResponse } from './types'

export class WorkspaceContractError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'WorkspaceContractError'
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function hasString(record: Record<string, unknown>, key: string) {
  return typeof record[key] === 'string'
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

function isTeamMember(value: unknown) {
  return (
    isRecord(value) &&
    hasString(value, 'id') &&
    isRecord(value.user) &&
    hasString(value.user, 'id') &&
    hasString(value.user, 'email') &&
    isRole(value.role) &&
    isStack(value.technology_stack)
  )
}

function isSprint(
  value: unknown,
): value is ProjectRunWorkspaceResponse['sprints'][number] {
  return (
    isRecord(value) &&
    hasString(value, 'id') &&
    hasString(value, 'sprint_template_id') &&
    hasString(value, 'title') &&
    hasString(value, 'brief') &&
    hasString(value, 'state') &&
    hasString(value, 'planned_start_at') &&
    hasString(value, 'planned_end_at') &&
    typeof value.sequence === 'number'
  )
}

function isSprintSummary(value: unknown) {
  return value === null || (
    isRecord(value) &&
    hasString(value, 'id') &&
    hasString(value, 'title') &&
    typeof value.sequence === 'number'
  )
}

function isResource(value: unknown) {
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

function assertWorkspaceContract(value: unknown): asserts value is ProjectRunWorkspaceResponse {
  if (!isRecord(value)) {
    throw new WorkspaceContractError('Workspace response is not an object.')
  }

  const project = value.project
  const membership = value.membership
  if (
    !hasString(value, 'id') ||
    !hasString(value, 'state') ||
    !hasString(value, 'deadline_at') ||
    !(value.repository_url === null || typeof value.repository_url === 'string') ||
    !isRecord(project) ||
    !hasString(project, 'id') ||
    !hasString(project, 'name') ||
    !hasString(project, 'version_id') ||
    !hasString(project, 'summary') ||
    typeof project.version_number !== 'number' ||
    !isTeamMember(membership) ||
    !Array.isArray(value.sprints) ||
    !Array.isArray(value.resources) ||
    !Array.isArray(value.team) ||
    !value.team.every(isTeamMember)
  ) {
    throw new WorkspaceContractError('Workspace response is missing runtime fields.')
  }

  for (const sprint of value.sprints) {
    if (!isSprint(sprint)) {
      throw new WorkspaceContractError('Workspace contains an invalid SprintRun.')
    }
  }

  for (const resource of value.resources) {
    if (!isResource(resource)) {
      throw new WorkspaceContractError('Workspace contains an invalid resource.')
    }
  }

  const currentSprint = value.current_sprint
  if (currentSprint !== null) {
    if (
      !isSprint(currentSprint) ||
      !value.sprints.some((sprint) => sprint.id === currentSprint.id)
    ) {
      throw new WorkspaceContractError(
        'The current Sprint is missing from the Workspace Sprint list.',
      )
    }
  }
}

export async function loadWorkspace(
  signal?: AbortSignal,
): Promise<ProjectRunWorkspaceResponse | null> {
  try {
    const response = await apiClient.get<unknown>(
      API_ENDPOINTS.projectRuns.workspace,
      { signal },
    )
    assertWorkspaceContract(response)
    return response
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}
