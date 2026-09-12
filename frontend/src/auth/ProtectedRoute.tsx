import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './useAuth'
import { LoadingState } from '../components/ui/LoadingState'
import { Alert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { authErrorMessage } from '../lib/api/auth'

export function ProtectedRoute() {
  const auth = useAuth()
  if (auth.status === 'loading') return <LoadingState message="در حال بررسی نشست..." />
  if (auth.status === 'error') return <div className="route-state" dir="rtl">
    <Alert tone="error">{authErrorMessage(auth.error)}</Alert>
    <Button onClick={() => void auth.refreshSession()}>تلاش دوباره</Button>
  </div>
  if (auth.status === 'anonymous') return <Navigate to="/login" replace />
  return <Outlet />
}
