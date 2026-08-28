import { Outlet } from 'react-router-dom'

export function ProtectedRoute() {
  // TODO: Enforce the backend session once the real authentication pages are wired.
  return <Outlet />
}
