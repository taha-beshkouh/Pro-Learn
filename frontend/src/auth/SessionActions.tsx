import { useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from './useAuth'
import { Button } from '../components/ui/Button'
import { Alert } from '../components/ui/Alert'
import { authErrorMessage } from '../lib/api/auth'
import '../styles/auth.css'

export function SessionActions() {
  const auth = useAuth()
  const navigate = useNavigate()
  const busy = useRef(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  async function logout() {
    if (busy.current) return
    busy.current = true
    setPending(true)
    setError('')
    try {
      await auth.logout()
      navigate('/login', { replace: true })
    } catch (cause) { setError(authErrorMessage(cause)) }
    finally { setPending(false); busy.current = false }
  }
  return <div className="session-actions" dir="rtl">
    {auth.status === 'anonymous' && <Link to="/login">ورود / ثبت نام</Link>}
    {auth.status === 'authenticated' && <Button variant="secondary" onClick={() => void logout()} disabled={pending}>{pending ? 'در حال خروج...' : 'خروج'}</Button>}
    {error && <Alert className="session-actions__error" tone="error">{error}</Alert>}
  </div>
}
