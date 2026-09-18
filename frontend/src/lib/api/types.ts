export type ApiErrorPayload =
  | Record<string, unknown>
  | unknown[]
  | string
  | null

export type CurrentUser = {
  id: string
  email: string
}

export type CsrfResponse = {
  csrfToken: string
}

export type PlatformRole = {
  id: string
  code: string
  name: string
}

export type ProjectLevel = {
  id: string
  number: number
  name: string
}

export type ProjectListItem = {
  id: string
  slug: string
  name: string
  level: ProjectLevel
  published_version_id: string | null
}

export type ProjectRoleContext = {
  role: PlatformRole
  requires_stack: boolean
  stack_policy: 'FIXED' | 'ALLOWLIST' | 'OPEN' | null
}

export type ProjectVersionCatalogDetail = {
  id: string
  version_number: number
  summary: string
  duration_weeks: number | null
  sprint_count: number | null
  role_context: ProjectRoleContext | null
}

export type ProjectDetailResponse = ProjectListItem & {
  published_version: ProjectVersionCatalogDetail | null
}

export type GuestParticipationContext = {
  selected_role_id?: string | null
  project_version_id?: string | null
  intended_action?: string | null
  return_path?: string | null
}

export type ProfileRoleResponse = {
  selected_role: PlatformRole | null
}

export type ProjectCatalogEntry = {
  templateId: string
  versionId: string
  name: string
  slug: string
  level: ProjectLevel
  summary: string
  durationWeeks: number | null
  sprintCount: number | null
  role: PlatformRole | null
}

export type TechnologyStack = {
  id: string
  code: string
  name: string
}

export type RolePrerequisite = {
  id: string
  title: string
  description: string
  position: number
}

export type SprintTemplateSummary = {
  id: string
  sequence: number
  title: string
}

export type SprintTemplate = SprintTemplateSummary & {
  brief: string
  planned_start_offset_days: number
  planned_duration_days: number
  planned_end_offset_days: number
}

export type ProjectWorkItem = {
  id: string
  title: string
  description: string
  position: number
  role: PlatformRole | null
  technology_stack: TechnologyStack | null
  sprint_template: SprintTemplateSummary | null
}

export type ProjectRoleRequirement = {
  id: string
  role: PlatformRole
  requires_stack: boolean
  stack_policy: 'FIXED' | 'ALLOWLIST' | 'OPEN' | null
  context: string
  configured_stacks: TechnologyStack[]
  prerequisites: RolePrerequisite[]
}

export type ProjectVersionRoleContext = {
  id: string
  role: PlatformRole
  requires_stack: boolean
  stack_policy: 'FIXED' | 'ALLOWLIST' | 'OPEN' | null
  context: string
  compatible_stacks: TechnologyStack[]
  auto_selected_stack: TechnologyStack | null
  selected_stack: TechnologyStack | null
  prerequisites: RolePrerequisite[]
  work_items: ProjectWorkItem[]
}

export type ProjectTemplateIdentity = {
  id: string
  slug: string
  name: string
  level: ProjectLevel
}

export type ProjectVersionDetailResponse = {
  project_template: ProjectTemplateIdentity
  id: string
  version_number: number
  summary: string
  full_description: string
  duration_weeks: number | null
  sprint_count: number | null
  weekly_effort_hours_min: number | null
  weekly_effort_hours_max: number | null
  participant_database: string
  published_at: string
  sprint_templates: SprintTemplate[]
  role_requirements: ProjectRoleRequirement[]
  work_items: ProjectWorkItem[]
  role_context: ProjectVersionRoleContext | null
  shared_work_items: ProjectWorkItem[]
}

export type ProjectStackSelectionResponse = {
  project_version_id: string
  selected_role_id: string
  selected_stack_id: string | null
}

export type ProjectReadinessResponse = {
  id: string
  user: CurrentUser
  role: PlatformRole
  project_version_id: string
  project_name: string
  version_number: number
  technology_stack: TechnologyStack | null
  created_at: string
  consumed_at: string | null
}

export type StaffFormationProjectVersion = {
  projectVersionId: string
  projectName: string
  level: ProjectLevel
}

export type ReadyCheckStatus =
  | 'PENDING'
  | 'CONFIRMED'
  | 'DECLINED'
  | 'EXPIRED'

export type ReadyCheckResponse = {
  formation_id: string
  project_version_id: string
  project_name: string
  id: string
  user: CurrentUser
  role: PlatformRole
  technology_stack: TechnologyStack | null
  github_username: string | null
  status: ReadyCheckStatus
  effective_status: ReadyCheckStatus
  is_current: boolean
  started_at: string
  expires_at: string
  responded_at: string | null
}

export type FormationReadyCheckResponse = Omit<
  ReadyCheckResponse,
  'formation_id' | 'project_version_id' | 'project_name'
>

export type TeamFormationResponse = {
  id: string
  project_version_id: string
  project_name: string
  created_by: CurrentUser
  created_at: string
  ready_confirmed_at: string | null
  team_id: string | null
  project_run_id: string | null
  ready_checks: FormationReadyCheckResponse[]
}

export type ProjectRunState = 'ACTIVE' | 'COMPLETED' | 'INCOMPLETE'

export type CurrentProjectRunSummary = {
  id: string
  project: ProjectRunProjectIdentity
  state: ProjectRunState
  started_at: string
  deadline_at: string
  ended_at: string | null
}

export type ProjectRunLifecycleResponse = Pick<
  CurrentProjectRunSummary,
  'id' | 'state' | 'started_at' | 'deadline_at' | 'ended_at'
>

export type ProjectRunProjectIdentity = {
  id: string
  name: string
  version_id: string
  version_number: number
  summary: string
}

export type SprintRunState =
  | 'LOCKED'
  | 'ACTIVE'
  | 'SUBMITTED'
  | 'UNDER_REVIEW'
  | 'CHANGES_REQUESTED'
  | 'COMPLETED'

export type ProjectRunNextAction =
  | 'WAIT_FOR_FACILITATOR'
  | 'SUBMIT_SPRINT'
  | 'COLLABORATE'
  | 'WAIT_FOR_REVIEW'
  | 'RESUBMIT_SPRINT'
  | 'ADDRESS_CHANGES'
  | 'SPRINTS_COMPLETED'
  | 'NO_SPRINT_AVAILABLE'

export type TeamMemberSnapshot = {
  id: string
  user: CurrentUser
  role: PlatformRole
  technology_stack: TechnologyStack | null
  ended_at: string | null
}

export type SprintRunResponse = {
  id: string
  sprint_template_id: string
  sequence: number
  title: string
  brief: string
  state: SprintRunState
  planned_start_at: string
  planned_end_at: string
  opened_at: string | null
  completed_at: string | null
  designated_submitter: TeamMemberSnapshot | null
}

export type SprintSubmissionResponse = {
  id: string
  submitted_by: TeamMemberSnapshot
  final_commit_url: string | null
  deployment_url: string | null
  design_url_snapshot: string | null
  evidence: string
  submitted_at: string
  review_decision: ParticipantReviewDecisionResponse | null
}

export type SprintRunDetailResponse = SprintRunResponse & {
  repository_url: string | null
  design_workspace_url: string | null
  work_items: ProjectWorkItem[]
  latest_submission: SprintSubmissionResponse | null
  submissions: SprintSubmissionResponse[]
}

export type ProjectRunDashboardResponse = CurrentProjectRunSummary & {
  membership: TeamMemberSnapshot
  current_sprint: SprintRunResponse | null
  deadline: string
  team: TeamMemberSnapshot[]
  next_action: ProjectRunNextAction
}

export type ProjectRunWorkspaceResponse = ProjectRunDashboardResponse & {
  repository_url: string | null
  design_workspace_url: string | null
  sprints: SprintRunResponse[]
  resources: ProjectWorkItem[]
}

export type StaffRepositoryTeamMember = TeamMemberSnapshot & {
  github_username: string | null
}

export type StaffProjectRunRepository = {
  id: string
  project: {
    id: string
    name: string
    version_id: string
    version_number: number
  }
  team_id: string
  state: ProjectRunState
  started_at: string
  deadline_at: string
  can_mark_incomplete: boolean
  repository_url: string | null
  design_workspace_url: string | null
  members: StaffRepositoryTeamMember[]
}

export type ReviewDecisionType = 'CHANGES_REQUESTED' | 'COMPLETED'

export type ParticipantReviewDecisionResponse = {
  decision: ReviewDecisionType
  feedback: string
  reviewed_at: string
}

export type StaffReviewDecisionResponse = {
  id: string
  decision: ReviewDecisionType
  feedback: string
  reviewed_by: CurrentUser
  reviewed_at: string
}

export type StaffSprintSubmissionSummaryResponse = {
  id: string
  submitted_by: TeamMemberSnapshot
  submitted_at: string
  review_decision: StaffReviewDecisionResponse | null
}

export type StaffSprintSubmissionResponse = Omit<SprintSubmissionResponse, 'review_decision'> & {
  review_decision: StaffReviewDecisionResponse | null
}

export type StaffSprintRunListItem = {
  id: string
  project_run_id: string
  sprint_template_id: string
  sequence: number
  title: string
  state: SprintRunState
  planned_start_at: string
  planned_end_at: string
  opened_at: string | null
  completed_at: string | null
  latest_submission: StaffSprintSubmissionSummaryResponse | null
}

export type StaffSprintRunDetailResponse = Omit<
  StaffSprintRunListItem,
  'latest_submission'
> & {
  brief: string
  latest_submission: StaffSprintSubmissionResponse | null
  submissions: StaffSprintSubmissionResponse[]
}
