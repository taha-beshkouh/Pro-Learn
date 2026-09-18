import { apiClient } from './client'
import { API_ENDPOINTS } from './endpoints'

export type DesignWorkspaceUpdateResponse = {
  id: string
  design_workspace_url: string
}

export function updateDesignWorkspace(projectRunId: string, designWorkspaceUrl: string) {
  return apiClient.patch<DesignWorkspaceUpdateResponse>(
    API_ENDPOINTS.projectRuns.designWorkspace(projectRunId),
    { design_workspace_url: designWorkspaceUrl },
  )
}
