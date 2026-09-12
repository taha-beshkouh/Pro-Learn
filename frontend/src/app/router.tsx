import { createBrowserRouter, type RouteObject } from 'react-router-dom'
import { ProtectedRoute } from '../auth/ProtectedRoute'
import { ParticipationRoute } from '../auth/ParticipationRoute'
import { AppLayout } from '../layouts/AppLayout'
import { PublicLayout } from '../layouts/PublicLayout'
import { DashboardPage } from '../pages/DashboardPage'
import { HomePage } from '../pages/HomePage'
import { LoginPage } from '../pages/LoginPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { ProfileSetupPage } from '../pages/ProfileSetupPage'
import { ProjectCatalogPage } from '../pages/ProjectCatalogPage'
import { ProjectDetailPage } from '../pages/ProjectDetailPage'
import { ProjectStackSelectionPage } from '../pages/ProjectStackSelectionPage'
import { ReadyCheckPage } from '../pages/ReadyCheckPage'
import { RegisterPage } from '../pages/RegisterPage'
import { SprintDetailPage } from '../pages/SprintDetailPage'
import { StaffFormationPage } from '../pages/StaffFormationPage'
import { WorkspacePage } from '../pages/WorkspacePage'

export const appRoutes: RouteObject[] = [
  {
    element: <PublicLayout />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/login', element: <LoginPage /> },
      { path: '/register', element: <RegisterPage /> },
      { path: '/projects', element: <ProjectCatalogPage /> },
      {
        path: '/projects/:projectVersionId',
        element: <ProjectDetailPage />,
      },
      {
        element: <ParticipationRoute />,
        children: [{ path: '/projects/:projectVersionId/stack-selection', element: <ProjectStackSelectionPage /> }],
      },
    ],
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: 'profile/setup', element: <ProfileSetupPage /> },
          { path: 'ready-check', element: <ReadyCheckPage /> },
          { path: 'dashboard', element: <DashboardPage /> },
          { path: 'workspace', element: <WorkspacePage /> },
          { path: 'staff/formations', element: <StaffFormationPage /> },
          {
            path: 'workspace/sprints/:sprintRunId',
            element: <SprintDetailPage />,
          },
        ],
      },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
]

export function createAppRouter() {
  return createBrowserRouter(appRoutes)
}

export const appRouter = createAppRouter()
