import { createBrowserRouter, type RouteObject } from 'react-router-dom'
import { ProtectedRoute } from '../auth/ProtectedRoute'
import { AppLayout } from '../layouts/AppLayout'
import { PublicLayout } from '../layouts/PublicLayout'
import { DashboardPage } from '../pages/DashboardPage'
import { HomePage } from '../pages/HomePage'
import { LoginPage } from '../pages/LoginPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { ProfileSetupPage } from '../pages/ProfileSetupPage'
import { ProjectCatalogPage } from '../pages/ProjectCatalogPage'
import { ProjectDetailPage } from '../pages/ProjectDetailPage'
import { ReadyCheckPage } from '../pages/ReadyCheckPage'
import { RegisterPage } from '../pages/RegisterPage'
import { SprintDetailPage } from '../pages/SprintDetailPage'
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
