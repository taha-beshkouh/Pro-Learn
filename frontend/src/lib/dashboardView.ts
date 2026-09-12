import type {
  ProjectRunNextAction,
  ProjectRunState,
  SprintRunResponse,
  SprintRunState,
  TeamMemberSnapshot,
} from './api/types'
import type { DashboardPageData } from './api/dashboard'

type StatusPresentation = {
  label: string
  tone: 'info' | 'success' | 'warning' | 'danger' | 'muted'
}

const projectRunStatuses: Record<ProjectRunState, StatusPresentation> = {
  ACTIVE: { label: 'فعال', tone: 'success' },
  COMPLETED: { label: 'تکمیل‌شده', tone: 'success' },
  INCOMPLETE: { label: 'ناتمام', tone: 'danger' },
}

const sprintStatuses: Record<SprintRunState, StatusPresentation> = {
  LOCKED: { label: 'قفل‌شده', tone: 'muted' },
  ACTIVE: { label: 'فعال', tone: 'info' },
  SUBMITTED: { label: 'ارسال‌شده', tone: 'warning' },
  UNDER_REVIEW: { label: 'در حال بررسی', tone: 'warning' },
  CHANGES_REQUESTED: { label: 'نیازمند اصلاح', tone: 'danger' },
  COMPLETED: { label: 'تکمیل‌شده', tone: 'success' },
}

const submitSprintAction = {
  title: 'برای ارسال اسپرینت آماده شوید',
  description:
    'هر عضو فعلی تیم در این ProjectRun می‌تواند اسپرینت را ارسال کند. سرور هنگام اقدام، عضویت فعلی، وضعیت و مهلت پروژه را دوباره بررسی می‌کند.',
}

const resubmitSprintAction = {
  title: 'اصلاحات را برای ارسال مجدد آماده کنید',
  description:
    'هر عضو فعلی تیم در این ProjectRun می‌تواند اصلاحات اسپرینت را دوباره ارسال کند. سرور هنگام اقدام، عضویت فعلی، وضعیت و مهلت پروژه را دوباره بررسی می‌کند.',
}

const nextActions: Record<
  ProjectRunNextAction,
  { title: string; description: string }
> = {
  WAIT_FOR_FACILITATOR: {
    title: 'منتظر فعال‌شدن اسپرینت بمانید',
    description:
      'اسپرینت جاری هنوز توسط Facilitator باز نشده است. وضعیت سرور مبنای شروع کار است.',
  },
  SUBMIT_SPRINT: submitSprintAction,
  COLLABORATE: submitSprintAction,
  WAIT_FOR_REVIEW: {
    title: 'منتظر بررسی Facilitator بمانید',
    description:
      'ارسال اسپرینت ثبت شده و اکنون نتیجه بررسی سرور تعیین‌کننده مرحله بعد است.',
  },
  RESUBMIT_SPRINT: resubmitSprintAction,
  ADDRESS_CHANGES: resubmitSprintAction,
  SPRINTS_COMPLETED: {
    title: 'مسیر اسپرینت‌ها تکمیل شده است',
    description:
      'در حال حاضر اسپرینت باز دیگری در پاسخ سرور وجود ندارد.',
  },
  NO_SPRINT_AVAILABLE: {
    title: 'اسپرینتی برای اجرا در دسترس نیست',
    description:
      'برای این ProjectRun هنوز SprintRun قابل نمایش در پاسخ سرور وجود ندارد.',
  },
}

function knownPresentation<T extends string>(
  mapping: Record<T, StatusPresentation>,
  value: T,
): StatusPresentation {
  return mapping[value] ?? { label: 'وضعیت نامشخص', tone: 'muted' }
}

function nextActionPresentation(value: ProjectRunNextAction) {
  return (
    nextActions[value] ?? {
      title: 'مرحله بعد مشخص نیست',
      description: 'پاسخ فعلی سرور برای مرحله بعد قابل شناسایی نیست.',
    }
  )
}

export type DashboardSprintView = SprintRunResponse & {
  isCurrent: boolean
  status: StatusPresentation
}

export type DashboardViewModel = {
  project: {
    id: string
    name: string
    summary: string
    versionId: string
    versionNumber: number
    levelName: string
    durationWeeks: number | null
  }
  projectRun: {
    id: string
    state: ProjectRunState
    status: StatusPresentation
    startedAt: string
    deadlineAt: string
  }
  membership: TeamMemberSnapshot
  currentSprint: DashboardSprintView | null
  sprints: DashboardSprintView[]
  nextAction: {
    code: ProjectRunNextAction
    title: string
    description: string
  }
  team: TeamMemberSnapshot[]
}

export function buildDashboardViewModel(
  data: DashboardPageData,
): DashboardViewModel {
  const { dashboard, projectVersion } = data
  const currentSprintId = dashboard.current_sprint?.id ?? null
  const sprints = [...data.sprints]
    .sort((left, right) => left.sequence - right.sequence)
    .map((sprint) => ({
      ...sprint,
      isCurrent: sprint.id === currentSprintId,
      status: knownPresentation(sprintStatuses, sprint.state),
    }))
  const currentSprint = currentSprintId
    ? (sprints.find((sprint) => sprint.id === currentSprintId) ?? null)
    : null
  const action = nextActionPresentation(dashboard.next_action)

  return {
    project: {
      id: dashboard.project.id,
      name: dashboard.project.name,
      summary: dashboard.project.summary,
      versionId: dashboard.project.version_id,
      versionNumber: dashboard.project.version_number,
      levelName: projectVersion.project_template.level.name,
      durationWeeks: projectVersion.duration_weeks,
    },
    projectRun: {
      id: dashboard.id,
      state: dashboard.state,
      status: knownPresentation(projectRunStatuses, dashboard.state),
      startedAt: dashboard.started_at,
      deadlineAt: dashboard.deadline_at,
    },
    membership: dashboard.membership,
    currentSprint,
    sprints,
    nextAction: {
      code: dashboard.next_action,
      ...action,
    },
    team: dashboard.team ?? [],
  }
}
