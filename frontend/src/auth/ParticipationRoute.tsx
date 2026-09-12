import { useEffect, useState } from 'react'
import { Navigate, Outlet, useParams } from 'react-router-dom'
import { useAuth } from './useAuth'
import { ContinuationNotice } from './ContinuationNotice'
import { Alert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { LoadingState } from '../components/ui/LoadingState'
import { authErrorMessage, isMissingSession, preserveProjectContinuation, resolveContinuation, stackPath, type ContinuationResult } from '../lib/api/auth'

export function ParticipationRoute() {
  const auth = useAuth()
  const { refreshSession } = auth
  const { projectVersionId } = useParams()
  const [result, setResult] = useState<{ key: string; value: ContinuationResult } | null>(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const key = `${auth.status}:${auth.user?.id}:${projectVersionId}:${retry}`
  useEffect(() => {
    if (!projectVersionId || !['authenticated', 'anonymous'].includes(auth.status)) return
    const controller = new AbortController()
    const request = auth.status === 'anonymous'
      ? preserveProjectContinuation(projectVersionId).then(() => ({ destination: '/login' }))
      : resolveContinuation(projectVersionId, controller.signal)
    void request.then((value) => {
      if (!controller.signal.aborted) setResult({ key, value })
    }).catch((cause: unknown) => {
      if (controller.signal.aborted) return
      setError(authErrorMessage(cause))
      if (isMissingSession(cause)) void refreshSession()
    })
    return () => controller.abort()
  }, [key, projectVersionId, auth.status, refreshSession])
  if (auth.status === 'error' || error) return <div className="route-state" dir="rtl">
    <Alert tone="error">{error || authErrorMessage(auth.error)}</Alert>
    <Button onClick={() => { setError(''); setRetry((value) => value + 1); if (auth.status === 'error') void auth.refreshSession() }}>تلاش دوباره</Button>
  </div>
  if (!projectVersionId || result?.key !== key) return <LoadingState message="در حال بررسی مسیر ادامه..." />
  if (result.value.message) return <ContinuationNotice result={result.value} />
  if (result.value.destination !== stackPath(projectVersionId)) return <Navigate to={result.value.destination!} replace />
  return <Outlet />
}
