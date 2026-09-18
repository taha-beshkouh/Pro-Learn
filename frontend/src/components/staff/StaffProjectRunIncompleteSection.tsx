import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../../auth/useAuth'
import { isMissingSession } from '../../lib/api/auth'
import {
  loadStaffProjectRunRepositories,
  markStaffProjectRunIncomplete,
  staffIncompleteErrorMessage,
} from '../../lib/api/staffRepository'
import type { StaffProjectRunRepository } from '../../lib/api/types'
import { Alert } from '../ui/Alert'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { EmptyState } from '../ui/EmptyState'
import { LoadingState } from '../ui/LoadingState'

const dateFormatter = new Intl.DateTimeFormat('fa-IR', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

function formatDeadline(value: string) {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : dateFormatter.format(parsed)
}

export function StaffProjectRunIncompleteSection() {
  const auth = useAuth()
  const [opened, setOpened] = useState(false)
  const [runs, setRuns] = useState<StaffProjectRunRepository[]>([])
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const [confirmingId, setConfirmingId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const savingRef = useRef(false)
  const [actionError, setActionError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    if (!opened) return
    const controller = new AbortController()
    void loadStaffProjectRunRepositories(controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setRuns(result)
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setLoadError(staffIncompleteErrorMessage(error))
        if (isMissingSession(error)) void auth.refreshSession()
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [auth, opened, reloadKey])

  async function markIncomplete(projectRunId: string) {
    if (savingRef.current) return
    savingRef.current = true
    setSaving(true)
    setActionError('')
    setSuccess('')

    let actionSucceeded = false
    try {
      await markStaffProjectRunIncomplete(projectRunId)
      actionSucceeded = true
    } catch (error: unknown) {
      setActionError(staffIncompleteErrorMessage(error))
      if (isMissingSession(error)) void auth.refreshSession()
    }

    try {
      const refreshed = await loadStaffProjectRunRepositories()
      setRuns(refreshed)
      if (actionSucceeded) {
        setSuccess('ProjectRun طبق وضعیت قطعی سرور ناتمام شد.')
        setConfirmingId(null)
      } else if (!refreshed.some(
        (run) => run.id === projectRunId && run.can_mark_incomplete,
      )) {
        setConfirmingId(null)
      }
    } catch (error: unknown) {
      setRuns([])
      setConfirmingId(null)
      setLoadError(
        actionSucceeded
          ? 'عملیات ثبت شد، اما تازه‌سازی وضعیت ممکن نشد. دوباره بارگذاری کنید.'
          : 'تازه‌سازی وضعیت ProjectRun ممکن نشد. دوباره بارگذاری کنید.',
      )
      if (isMissingSession(error)) void auth.refreshSession()
    } finally {
      savingRef.current = false
      setSaving(false)
    }
  }

  return (
    <section className="staff-incomplete" aria-labelledby="staff-incomplete-title">
      <header>
        <h2 id="staff-incomplete-title">بستن ProjectRun ناتمام</h2>
        <p>ProjectRunهای فعال را بررسی کنید. فقط سرور مشخص می‌کند کدام اجرا برای ثبت وضعیت ناتمام مجاز است.</p>
      </header>
      {!opened ? (
        <Button onClick={() => { setOpened(true); setLoading(true) }}>
          مشاهده ProjectRunهای فعال
        </Button>
      ) : loading ? (
        <LoadingState message="در حال دریافت ProjectRunها..." />
      ) : loadError ? (
        <Alert tone="error">
          <p>{loadError}</p>
          <Button variant="secondary" onClick={() => {
            setLoadError('')
            setLoading(true)
            setReloadKey((value) => value + 1)
          }}>تلاش دوباره</Button>
        </Alert>
      ) : (
        <>
          {actionError ? <Alert tone="error" role="alert">{actionError}</Alert> : null}
          {success ? <Alert tone="success" role="status">{success}</Alert> : null}
          {runs.length === 0 ? (
            <EmptyState
              title="ProjectRun فعالی وجود ندارد"
              description="تاریخچه اجراهای پایان‌یافته از بخش بررسی اسپرینت‌ها قابل مشاهده است."
            />
          ) : (
            <div className="staff-incomplete__runs">
              {runs.map((run) => (
                <Card key={run.id} className="staff-incomplete__run">
                  <h3 dir="auto">{run.project.name}</h3>
                  <p>نسخه {run.project.version_number} · Team {run.team_id}</p>
                  <dl>
                    <div><dt>وضعیت ProjectRun</dt><dd>{run.state}</dd></div>
                    <div><dt>مهلت ProjectRun</dt><dd>{formatDeadline(run.deadline_at)}</dd></div>
                  </dl>
                  {run.can_mark_incomplete ? (
                    confirmingId === run.id ? (
                      <div className="staff-incomplete__confirmation" role="alert">
                        <p>این ProjectRun ناتمام و نهایی می‌شود. پس از آن هیچ تغییر وضعیت Sprint مجاز نیست.</p>
                        <div>
                          <Button
                            variant="danger"
                            disabled={saving}
                            onClick={() => void markIncomplete(run.id)}
                          >{saving ? 'در حال ثبت...' : 'تأیید ثبت وضعیت ناتمام'}</Button>
                          <Button
                            variant="secondary"
                            disabled={saving}
                            onClick={() => setConfirmingId(null)}
                          >انصراف</Button>
                        </div>
                      </div>
                    ) : (
                      <Button
                        variant="danger"
                        disabled={saving}
                        onClick={() => {
                          setActionError('')
                          setSuccess('')
                          setConfirmingId(run.id)
                        }}
                      >ثبت ProjectRun ناتمام</Button>
                    )
                  ) : (
                    <p>ثبت وضعیت ناتمام در حال حاضر از سوی سرور مجاز نیست.</p>
                  )}
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  )
}
