import type {
  ProjectRunState,
  ProjectRunWorkspaceResponse,
  ProjectWorkItem,
  SprintRunResponse,
  SprintRunState,
  TeamMemberSnapshot,
} from './api/types'

export type RuntimeStatusPresentation = {
  label: string
  tone: 'info' | 'success' | 'warning' | 'danger' | 'muted'
}

const projectRunStatuses: Record<ProjectRunState, RuntimeStatusPresentation> = {
  ACTIVE: { label: 'فعال', tone: 'success' },
  COMPLETED: { label: 'تکمیل‌شده', tone: 'success' },
  INCOMPLETE: { label: 'ناتمام', tone: 'danger' },
}

const sprintStatuses: Record<SprintRunState, RuntimeStatusPresentation> = {
  LOCKED: { label: 'قفل‌شده', tone: 'muted' },
  ACTIVE: { label: 'فعال', tone: 'info' },
  SUBMITTED: { label: 'ارسال‌شده', tone: 'warning' },
  UNDER_REVIEW: { label: 'در حال بررسی', tone: 'warning' },
  CHANGES_REQUESTED: { label: 'نیازمند اصلاح', tone: 'danger' },
  COMPLETED: { label: 'تکمیل‌شده', tone: 'success' },
}

function knownStatus<T extends string>(
  map: Record<T, RuntimeStatusPresentation>,
  value: T,
) {
  return map[value] ?? { label: 'وضعیت نامشخص', tone: 'muted' as const }
}

export type WorkspaceSprintView = SprintRunResponse & {
  isCurrent: boolean
  status: RuntimeStatusPresentation
}

export type WorkspaceResourceGroup = {
  kind: 'shared' | 'role' | 'stack'
  title: string
  description: string
  items: ProjectWorkItem[]
}

export type WorkspaceViewModel = {
  project: ProjectRunWorkspaceResponse['project']
  projectRun: {
    id: string
    state: ProjectRunState
    deadlineAt: string
    status: RuntimeStatusPresentation
  }
  membership: TeamMemberSnapshot
  currentSprint: WorkspaceSprintView | null
  sprints: WorkspaceSprintView[]
  resourceGroups: WorkspaceResourceGroup[]
  resourceCount: number
  team: TeamMemberSnapshot[]
}

export function buildWorkspaceViewModel(
  workspace: ProjectRunWorkspaceResponse,
): WorkspaceViewModel {
  const currentSprintId = workspace.current_sprint?.id ?? null
  const sprints = workspace.sprints.map((sprint) => ({
    ...sprint,
    isCurrent: sprint.id === currentSprintId,
    status: knownStatus(sprintStatuses, sprint.state),
  }))

  const shared: ProjectWorkItem[] = []
  const role: ProjectWorkItem[] = []
  const stack: ProjectWorkItem[] = []

  for (const resource of workspace.resources) {
    if (resource.technology_stack !== null) stack.push(resource)
    else if (resource.role !== null) role.push(resource)
    else shared.push(resource)
  }

  return {
    project: workspace.project,
    projectRun: {
      id: workspace.id,
      state: workspace.state,
      deadlineAt: workspace.deadline_at,
      status: knownStatus(projectRunStatuses, workspace.state),
    },
    membership: workspace.membership,
    currentSprint:
      sprints.find((sprint) => sprint.id === currentSprintId) ?? null,
    sprints,
    resourceGroups: [
      {
        kind: 'shared',
        title: 'کارهای مشترک تیم',
        description: 'محتوای مشترکی که API برای عضویت فعلی شما برگردانده است.',
        items: shared,
      },
      {
        kind: 'role',
        title: 'کارهای مرتبط با نقش شما',
        description: 'محتوای دارای Role که API برای این ProjectRun قابل‌مشاهده کرده است.',
        items: role,
      },
      {
        kind: 'stack',
        title: 'کارهای مرتبط با Stack شما',
        description: 'محتوای دارای Stack که API برای snapshot عضویت فعلی برگردانده است.',
        items: stack,
      },
    ],
    resourceCount: workspace.resources.length,
    team: workspace.team,
  }
}
