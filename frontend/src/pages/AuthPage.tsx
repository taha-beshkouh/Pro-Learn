import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { ContinuationNotice } from '../auth/ContinuationNotice'
import { HomeFooter } from '../components/home/HomeFooter'
import { Alert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { LoadingState } from '../components/ui/LoadingState'
import { authErrorMessage, isMissingSession, resolveContinuation, type ContinuationResult } from '../lib/api/auth'
import '../styles/auth.css'

export function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const auth = useAuth()
  const { refreshSession } = auth
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [pending, setPending] = useState(false)
  const submitting = useRef(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<{ userId: string | undefined; value: ContinuationResult } | null>(null)
  const [retry, setRetry] = useState(0)
  const register = mode === 'register'

  useEffect(() => {
    if (auth.status !== 'authenticated') return
    const controller = new AbortController()
    void resolveContinuation(undefined, controller.signal).then((value) => {
      if (controller.signal.aborted) return
      if (value.destination && !value.message) navigate(value.destination, { replace: true })
      else setResult({ userId: auth.user?.id, value })
    }).catch((cause: unknown) => {
      if (!controller.signal.aborted) {
        setError(authErrorMessage(cause))
        if (isMissingSession(cause)) void refreshSession()
      }
    })
    return () => controller.abort()
  }, [auth.status, auth.user?.id, navigate, retry, refreshSession])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting.current || auth.status !== 'anonymous') return
    submitting.current = true
    setPending(true)
    setError('')
    try {
      await auth.authenticate(mode, { email: email.trim(), password })
    } catch (cause) {
      setError(authErrorMessage(cause))
    } finally {
      setPassword('')
      setPending(false)
      submitting.current = false
    }
  }

  return <div className="auth-page" dir="rtl">
    <Card className="auth-card">
      <header>
        <p className="auth-eyebrow" dir="ltr">PROLEARN</p>
        <h1>{auth.status === 'authenticated' ? 'ادامه مسیر' : register ? 'ساخت حساب' : 'ورود به حساب'}</h1>
        {auth.status === 'anonymous' && <p>{register ? 'با ایمیل و رمز عبور حساب خود را بساز.' : 'برای ادامه مسیر پروژه وارد حساب خود شو.'}</p>}
      </header>
      {auth.status === 'loading' && <LoadingState message="در حال بررسی نشست..." />}
      {error && <Alert tone="error">{error}</Alert>}
      {auth.status === 'error' && <Alert tone="error">{authErrorMessage(auth.error)}</Alert>}
      {(auth.status === 'error' || (auth.status === 'authenticated' && error)) && <Button onClick={() => { setError(''); setRetry((value) => value + 1); void auth.refreshSession() }}>تلاش دوباره</Button>}
      {auth.status === 'authenticated' && !error && (result?.userId === auth.user?.id && result
        ? <ContinuationNotice result={result.value} />
        : <LoadingState message="در حال بررسی مسیر ادامه..." />)}
      {auth.status === 'anonymous' && <form onSubmit={submit} aria-busy={pending}>
        <label htmlFor="auth-email">ایمیل</label>
        <input id="auth-email" name="email" type="email" dir="ltr" autoComplete="username" required maxLength={254} value={email} onChange={(event) => setEmail(event.target.value)} disabled={pending} />
        <label htmlFor="auth-password">رمز عبور</label>
        <input id="auth-password" name="password" type="password" dir="ltr" autoComplete={register ? 'new-password' : 'current-password'} required maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} disabled={pending} />
        <Button type="submit" disabled={pending}>{pending ? 'در حال ارسال...' : register ? 'ثبت نام' : 'ورود'}</Button>
        {!pending && <p className="auth-switch">{register ? 'حساب داری؟ ' : 'هنوز حساب نداری؟ '}<Link to={register ? '/login' : '/register'}>{register ? 'ورود به حساب' : 'ساخت حساب'}</Link></p>}
      </form>}
    </Card>
    <HomeFooter />
  </div>
}
