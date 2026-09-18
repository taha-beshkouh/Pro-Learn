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

function isCanonicalGithubRoot(value: string) {
  try {
    const url = new URL(value)
    const hostname = url.hostname.toLowerCase()
    const path = url.pathname.endsWith('/')
      ? url.pathname.slice(0, -1)
      : url.pathname
    const parts = path.split('/')
    const owner = parts[1] ?? ''
    const repository = (parts[2] ?? '').replace(/\.git$/i, '')
    return (
      (url.protocol === 'http:' || url.protocol === 'https:') &&
      (hostname === 'github.com' || hostname === 'www.github.com') &&
      !url.port &&
      !url.username &&
      !url.password &&
      !url.search &&
      !url.hash &&
      parts.length === 3 &&
      /^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$/.test(owner) &&
      repository !== '.' &&
      repository !== '..' &&
      /^[A-Za-z0-9._-]+$/.test(repository)
    )
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
  const [success, setSuccess] = useState<{ id: string; message: string } | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [confirmingClearId, setConfirmingClearId] = useState<string | null>(null)
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

  async function persist(
    projectRunId: string,
    repositoryUrl: string | null,
    successMessage: string,
  ) {
    if (savingRef.current) return

    savingRef.current = projectRunId
    setSavingId(projectRunId)
    setSuccess(null)
    setSaveError((current) => ({ ...current, [projectRunId]: '' }))
    try {
      await saveProjectRunRepository(projectRunId, repositoryUrl)
      const refreshed = await loadStaffProjectRunRepositories()
      setRuns(refreshed)
      setDrafts(
        Object.fromEntries(
          refreshed.map((run) => [run.id, run.repository_url ?? '']),
        ),
      )
      setEditingId(null)
      setConfirmingClearId(null)
      setSuccess({ id: projectRunId, message: successMessage })
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

  async function save(event: FormEvent<HTMLFormElement>, projectRunId: string) {
    event.preventDefault()
    const repositoryUrl = (drafts[projectRunId] ?? '').trim()
    if (!isCanonicalGithubRoot(repositoryUrl)) {
      setSaveError((current) => ({
        ...current,
        [projectRunId]: 'نشانی ریشه مخزن GitHub را وارد کنید.',
      }))
      return
    }
    await persist(
      projectRunId,
      repositoryUrl,
      'نشانی canonical مخزن ProjectRun ذخیره شد.',
    )
  }

  function cancelEdit(run: StaffProjectRunRepository) {
    setDrafts((current) => ({
      ...current,
      [run.id]: run.repository_url ?? '',
    }))
    setEditingId(null)
    setSaveError((current) => ({ ...current, [run.id]: '' }))
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
          {runs.map((run) => {
            const isEditing = editingId === run.id
            const isConfirmingClear = confirmingClearId === run.id
            return (
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

                {run.repository_url && !isEditing ? (
                  <div className="staff-repository__current">
                    <span>مخزن canonical فعلی</span>
                    <a
                      href={run.repository_url}
                      target="_blank"
                      rel="noreferrer"
                      dir="ltr"
                    >
                      {run.repository_url}
                    </a>
                    <div className="staff-repository__actions">
                      <Button
                        variant="secondary"
                        disabled={savingId !== null}
                        onClick={() => {
                          setEditingId(run.id)
                          setConfirmingClearId(null)
                          setSuccess(null)
                        }}
                      >
                        ویرایش نشانی
                      </Button>
                      <Button
                        variant="danger"
                        disabled={savingId !== null}
                        onClick={() => {
                          setConfirmingClearId(run.id)
                          setEditingId(null)
                          setSuccess(null)
                        }}
                      >
                        حذف ارجاع مخزن
                      </Button>
                    </div>
                    {isConfirmingClear ? (
                      <div className="staff-repository__clear-confirmation" role="alert">
                        <p>
                          فقط ارجاع مخزن از PROLEARN حذف می‌شود. مخزن GitHub، دسترسی‌ها و اعضای آن حذف یا تغییر نمی‌کنند.
                        </p>
                        <div>
                          <Button
                            variant="danger"
                            disabled={savingId !== null}
                            onClick={() =>
                              void persist(
                                run.id,
                                null,
                                'ارجاع مخزن از PROLEARN حذف شد.',
                              )
                            }
                          >
                            {savingId === run.id
                              ? 'در حال حذف ارجاع...'
                              : 'تأیید حذف ارجاع'}
                          </Button>
                          <Button
                            variant="secondary"
                            disabled={savingId !== null}
                            onClick={() => setConfirmingClearId(null)}
                          >
                            انصراف
                          </Button>
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <form onSubmit={(event) => void save(event, run.id)}>
                    <label htmlFor={`repository-${run.id}`}>
                      {run.repository_url
                        ? 'نشانی جدید مخزن canonical'
                        : 'نشانی canonical مخزن پروژه'}
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
                          setSuccess(null)
                          setSaveError((current) => ({ ...current, [run.id]: '' }))
                        }}
                        disabled={savingId !== null}
                      />
                      <Button type="submit" disabled={savingId !== null}>
                        {savingId === run.id
                          ? 'در حال ذخیره...'
                          : run.repository_url
                            ? 'ذخیره تغییرات'
                            : 'افزودن مخزن'}
                      </Button>
                      {run.repository_url ? (
                        <Button
                          variant="secondary"
                          disabled={savingId !== null}
                          onClick={() => cancelEdit(run)}
                        >
                          انصراف
                        </Button>
                      ) : null}
                    </div>
                  </form>
                )}
                {saveError[run.id] ? (
                  <p className="staff-repository__error" role="alert">
                    {saveError[run.id]}
                  </p>
                ) : null}
                {success?.id === run.id ? (
                  <p className="staff-repository__success" role="status">
                    {success.message}
                  </p>
                ) : null}
              </Card>
            )
          })}
        </div>
      )}
    </section>
  )
}
