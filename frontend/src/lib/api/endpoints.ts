function segment(value: string) {
  return encodeURIComponent(value)
}

export const API_ENDPOINTS = {
  auth: {
    csrf: '/auth/csrf/',
    register: '/auth/register/',
    login: '/auth/login/',
    logout: '/auth/logout/',
    me: '/auth/me/',
  },
  profiles: {
    roles: '/roles/',
    technologyStacks: '/technology-stacks/',
    current: '/profile/',
    selectRole: '/profile/select-role/',
    links: '/profile/links/',
    link: (linkId: string) => `/profile/links/${segment(linkId)}/`,
    skills: '/profile/skills/',
    skill: (skillId: string) => `/profile/skills/${segment(skillId)}/`,
    guestContext: '/guest-context/',
  },
  projects: {
    levels: '/levels/',
    list: '/projects/',
    detail: (projectId: string) => `/projects/${segment(projectId)}/`,
    versionDetail: (projectVersionId: string) =>
      `/project-versions/${segment(projectVersionId)}/`,
    stackSelection: (projectVersionId: string) =>
      `/project-versions/${segment(projectVersionId)}/stack-selection/`,
  },
  readiness: {
    mine: '/project-readiness/me/',
    candidates: (projectVersionId: string) => {
      const params = new URLSearchParams({ project_version_id: projectVersionId })
      return `/project-readiness/?${params.toString()}`
    },
  },
  teamFormations: {
    listCreate: '/team-formations/',
    replaceReadyCheck: (formationId: string, readyCheckId: string) =>
      `/team-formations/${segment(formationId)}/ready-checks/${segment(readyCheckId)}/replace/`,
  },
  readyChecks: {
    mine: '/ready-checks/me/',
    confirm: (readyCheckId: string) =>
      `/ready-checks/${segment(readyCheckId)}/confirm/`,
    decline: (readyCheckId: string) =>
      `/ready-checks/${segment(readyCheckId)}/decline/`,
  },
  projectRuns: {
    staffList: '/project-runs/',
    markIncomplete: (projectRunId: string) =>
      `/project-runs/${segment(projectRunId)}/incomplete/`,
    repository: (projectRunId: string) =>
      `/project-runs/${segment(projectRunId)}/repository/`,
    designWorkspace: (projectRunId: string) =>
      `/project-runs/${segment(projectRunId)}/design-workspace/`,
    dashboard: '/project-runs/me/dashboard/',
    workspace: '/project-runs/me/workspace/',
    sprints: '/project-runs/me/sprints/',
    sprint: (sprintRunId: string) =>
      `/project-runs/me/sprints/${segment(sprintRunId)}/`,
    submitSprint: (projectRunId: string, sprintRunId: string) =>
      `/project-runs/${segment(projectRunId)}/sprints/${segment(sprintRunId)}/submit/`,
    staffSprints: (projectRunId: string) =>
      `/project-runs/${segment(projectRunId)}/sprints/`,
    staffSprint: (projectRunId: string, sprintRunId: string) =>
      `/project-runs/${segment(projectRunId)}/sprints/${segment(sprintRunId)}/`,
    openSprint: (projectRunId: string, sprintRunId: string) =>
      `/project-runs/${segment(projectRunId)}/sprints/${segment(sprintRunId)}/open/`,
    startSprintReview: (projectRunId: string, sprintRunId: string) =>
      `/project-runs/${segment(projectRunId)}/sprints/${segment(sprintRunId)}/under-review/`,
    requestSprintChanges: (projectRunId: string, sprintRunId: string) =>
      `/project-runs/${segment(projectRunId)}/sprints/${segment(sprintRunId)}/request-changes/`,
    completeSprint: (projectRunId: string, sprintRunId: string) =>
      `/project-runs/${segment(projectRunId)}/sprints/${segment(sprintRunId)}/complete/`,
  },
} as const
