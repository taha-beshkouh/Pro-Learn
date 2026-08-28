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
    stackSelection: (projectId: string) =>
      `/projects/${segment(projectId)}/stack-selection/`,
  },
  readyChecks: {
    mine: '/ready-checks/me/',
    confirm: (readyCheckId: string) =>
      `/ready-checks/${segment(readyCheckId)}/confirm/`,
    decline: (readyCheckId: string) =>
      `/ready-checks/${segment(readyCheckId)}/decline/`,
  },
  projectRuns: {
    dashboard: '/project-runs/me/dashboard/',
    workspace: '/project-runs/me/workspace/',
    sprints: '/project-runs/me/sprints/',
    sprint: (sprintRunId: string) =>
      `/project-runs/me/sprints/${segment(sprintRunId)}/`,
    submitSprint: (projectRunId: string, sprintRunId: string) =>
      `/project-runs/${segment(projectRunId)}/sprints/${segment(sprintRunId)}/submit/`,
  },
} as const
