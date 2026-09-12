import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useAuth } from '../../auth/useAuth'
import { Alert } from '../ui/Alert'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { EmptyState } from '../ui/EmptyState'
import { LoadingState } from '../ui/LoadingState'
import { isMissingSession } from '../../lib/api/auth'
import {
  loadStaffProjectRunRepositories,
  saveProjectRunRepository,
  staffRepositoryErrorMessage,
} from '../../lib/api/staffRepository'
import type { StaffProjectRunRepository } from '../../lib/api/types'

function isHttpUrl(value: string) {
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

export function ProjectRunRepositorySection() {
  const auth = useAuth()
  const [runs, setRuns] = useState<StaffProjectRunRepository[]>([])
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [savingId, setSavingId] = useState<string | null>(null)
  const savingRef = useRef<string | null>(null)
  const [saveError, setSaveError] = useState<Record<string, string>>({})
  const [savedId, setSavedId] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setLoadError('')
    void loadStaffProjectRunRepositories(controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return
        setRuns(result)
        setDrafts(
          Object.fromEntries(
            result.map((run) => [run.id, run.repository_url ?? '']),
          ),
        )
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setLoadError(staffRepositoryErrorMessage(error))
        if (isMissingSession(error)) void auth.refreshSession()
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [auth, reloadKey])

  async function save(event: FormEvent<HTMLFormElement>, projectRunId: string) {
    event.preventDefault()
    if (savingRef.current) return
    const repositoryUrl = (drafts[projectRunId] ?? '').trim()
    if (!isHttpUrl(repositoryUrl)) {
      setSaveError((current) => ({
        ...current,
        [projectRunId]: 'یک نشانی کامل HTTP یا HTTPS وارد کنید.',
      }))
      return
    }

    savingRef.current = projectRunId
    setSavingId(projectRunId)
    setSavedId(null)
    setSaveError((current) => ({ ...current, [projectRunId]: '' }))
    try {
      const updated = await saveProjectRunRepository(projectRunId, repositoryUrl)
      setRuns((current) =>
        current.map((run) => (run.id === updated.id ? updated : run)),
      )
      setDrafts((current) => ({
        ...current,
        [updated.id]: updated.repository_url ?? '',
      }))
      setSavedId(updated.id)
    } catch (error: unknown) {
      setSaveError((current) => ({
        ...current,
        [projectRunId]: staffRepositoryErrorMessage(error),
      }))
      if (isMissingSession(error)) void auth.refreshSession()
    } finally {
      savingRef.current = null
      setSavingId(null)
    }
  }

  return (
    <section
      className="staff-repository"
      aria-labelledby="staff-repository-title"
    >
      <header>
        <p dir="ltr">PROLEARN · STAFF · REPOSITORY SETUP</p>
        <h2 id="staff-repository-title">ثبت مخزن ProjectRun</h2>
        <span>
          ساخت مخزن خصوصی و دعوت اعضا در GitHub به‌صورت دستی انجام می‌شود؛ این بخش فقط نشانی canonical را ثبت می‌کند.
        </span>
      </header>

      {loading ? (
        <LoadingState message="در حال دریافت ProjectRunهای فعال..." />
      ) : loadError ? (
        <Alert tone="error">
          <p>{loadError}</p>
          <Button
            variant="secondary"
            onClick={() => setReloadKey((current) => current + 1)}
          >
            تلاش دوباره
          </Button>
        </Alert>
      ) : runs.length === 0 ? (
        <EmptyState
          title="ProjectRun فعالی وجود ندارد"
          description="پس از تأیید کامل Ready Check، ProjectRun فعال برای تنظیم مخزن در این بخش نمایش داده می‌شود."
        />
      ) : (
        <div className="staff-repository__runs">
          {runs.map((run) => (
            <Card key={run.id} className="staff-repository__run">
              <header>
                <div>
                  <h3 dir="auto">{run.project.name}</h3>
                  <span>
                    نسخه {run.project.version_number} · Team {run.team_id}
                  </span>
                </div>
                <code title="ProjectVersion ID">{run.project.version_id}</code>
              </header>

              <ul aria-label={`اعضای ${run.project.name}`}>
                {run.members.map((member) => (
                  <li key={member.id}>
                    <strong dir="ltr">{member.user.email}</strong>
                    <span dir="auto">{member.role.name}</span>
                    <span dir="ltr">
                      GitHub: {member.github_username ?? 'ثبت نشده'}
                    </span>
                  </li>
                ))}
              </ul>

              <form onSubmit={(event) => void save(event, run.id)}>
                <label htmlFor={`repository-${run.id}`}>
                  نشانی canonical مخزن پروژه
                </label>
                <div>
                  <input
                    id={`repository-${run.id}`}
                    type="url"
                    dir="ltr"
                    required
                    placeholder="https://github.com/organization/repository"
                    value={drafts[run.id] ?? ''}
                    onChange={(event) => {
                      setDrafts((current) => ({
                        ...current,
                        [run.id]: event.target.value,
                      }))
                      setSavedId(null)
                      setSaveError((current) => ({ ...current, [run.id]: '' }))
                    }}
                    disabled={savingId !== null}
                  />
                  <Button type="submit" disabled={savingId !== null}>
                    {savingId === run.id ? 'در حال ذخیره...' : 'ذخیره نشانی مخزن'}
                  </Button>
                </div>
                {saveError[run.id] ? (
                  <p className="staff-repository__error" role="alert">
                    {saveError[run.id]}
                  </p>
                ) : null}
                {savedId === run.id ? (
                  <p className="staff-repository__success" role="status">
                    نشانی مخزن ProjectRun ثبت شد.
                  </p>
                ) : null}
              </form>
            </Card>
          ))}
        </div>
      )}
    </section>
  )
}
