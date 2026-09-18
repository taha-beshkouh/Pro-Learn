import { useState, type FormEvent } from 'react'
import { useAuth } from '../../auth/useAuth'
import { isMissingSession } from '../../lib/api/auth'
import { ApiError } from '../../lib/api/client'
import { updateDesignWorkspace } from '../../lib/api/designWorkspace'
import type { ProjectRunState } from '../../lib/api/types'
import { Alert } from '../ui/Alert'
import { Button } from '../ui/Button'

type Props = {
  projectRunId: string
  url: string | null
  memberRoleCode: string
  runState: ProjectRunState
  onSaved: () => void
}

function isHttpUrl(value: string) {
  try {
    const parsed = new URL(value)
    return (
      (parsed.protocol === 'https:' || parsed.protocol === 'http:') &&
      Boolean(parsed.hostname) &&
      !parsed.username &&
      !parsed.password
    )
  } catch {
    return false
  }
}

function saveErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (isMissingSession(error)) return 'نشست شما پایان یافته است. دوباره وارد شوید.'
    if (error.status === 400) return 'آدرس فضای طراحی معتبر نیست. یک آدرس کامل HTTP یا HTTPS وارد کنید.'
    if (error.status === 403 || error.status === 404) {
      return 'دسترسی یا وضعیت پروژه تغییر کرده است. صفحه را دوباره بارگذاری کنید.'
    }
  }
  return 'ذخیرهٔ فضای طراحی ممکن نشد. اتصال را بررسی و دوباره تلاش کنید.'
}

export function DesignWorkspaceSection({
  projectRunId,
  url,
  memberRoleCode,
  runState,
  onSaved,
}: Props) {
  const auth = useAuth()
  const isDesigner = memberRoleCode === 'PRODUCT_DESIGNER'
  const canEdit = isDesigner && runState === 'ACTIVE'
  const [editing, setEditing] = useState(false)
  const [input, setInput] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function startEditing() {
    setInput(url ?? '')
    setError(null)
    setEditing(true)
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canEdit || pending) return
    const normalized = input.trim()
    if (!normalized || normalized.length > 500 || !isHttpUrl(normalized)) {
      setError('یک آدرس کامل و معتبر HTTP یا HTTPS برای فضای طراحی وارد کنید.')
      return
    }
    setPending(true)
    setError(null)
    try {
      await updateDesignWorkspace(projectRunId, normalized)
      setEditing(false)
      setInput('')
      onSaved()
    } catch (requestError) {
      setError(saveErrorMessage(requestError))
      if (isMissingSession(requestError)) void auth.refreshSession()
    } finally {
      setPending(false)
    }
  }

  return (
    <section className="workspace__design" aria-labelledby="workspace-design-title">
      <header>
        <p className="workspace__section-kicker">مرجع طراحی پروژه</p>
        <h2 id="workspace-design-title">فضای طراحی</h2>
      </header>
      {url ? (
        <div className="workspace__design-current">
          <span dir="ltr">{url}</span>
          {isHttpUrl(url) && (
            <a href={url} target="_blank" rel="noopener noreferrer">
              باز کردن فضای طراحی
            </a>
          )}
        </div>
      ) : isDesigner && runState === 'ACTIVE' ? (
        <p>فضای طراحی پروژه هنوز تنظیم نشده است. لینک آن را اضافه کنید تا تیم بتواند مدارک اسپرینت را ارسال کند.</p>
      ) : (
        <p>طراح محصول هنوز فضای طراحی پروژه را تنظیم نکرده است. پس از ثبت آن، ارسال مدارک اسپرینت ممکن می‌شود.</p>
      )}
      {runState !== 'ACTIVE' && (
        <p className="workspace__design-note">این ProjectRun پایان یافته و فضای طراحی فقط برای مشاهده است.</p>
      )}
      {canEdit && !editing && (
        <Button variant="secondary" onClick={startEditing}>
          {url ? 'تغییر لینک' : 'افزودن فضای طراحی'}
        </Button>
      )}
      {canEdit && editing && (
        <form className="workspace__design-form" onSubmit={(event) => void submit(event)} noValidate>
          <label htmlFor="workspace-design-url">آدرس فضای طراحی</label>
          <input
            id="workspace-design-url"
            type="url"
            dir="ltr"
            value={input}
            maxLength={500}
            onChange={(event) => setInput(event.target.value)}
            disabled={pending}
            required
          />
          {url && (
            <p className="workspace__design-note">
              تغییر لینک جاری بر Snapshot ارسال‌های آینده اثر می‌گذارد؛ مدارک ثبت‌شدهٔ قبلی تغییر نمی‌کنند.
            </p>
          )}
          {error && <Alert tone="error">{error}</Alert>}
          <div className="workspace__design-actions">
            <Button type="submit" disabled={pending}>{pending ? 'در حال ذخیره...' : 'ذخیره'}</Button>
            <Button variant="secondary" disabled={pending} onClick={() => setEditing(false)}>انصراف</Button>
          </div>
        </form>
      )}
    </section>
  )
}
