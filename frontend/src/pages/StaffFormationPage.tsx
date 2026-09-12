import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useAuth } from '../auth/useAuth'
import { isMissingSession } from '../lib/api/auth'
import { Alert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { LoadingState } from '../components/ui/LoadingState'
import { StatusBadge } from '../components/ui/StatusBadge'
import { ProjectRunRepositorySection } from '../components/staff/ProjectRunRepositorySection'
import { ApiError } from '../lib/api/client'
import {
  createTeamFormation,
  loadActiveReadinessCandidates,
  loadStaffFormationProjectVersions,
  REQUIRED_FORMATION_ROLE_CODES,
  staffFormationErrorMessage,
  type RequiredFormationRoleCode,
} from '../lib/api/staffFormation'
import type {
  ProjectReadinessResponse,
  StaffFormationProjectVersion,
  TeamFormationResponse,
} from '../lib/api/types'
import '../styles/staff-formation.css'

const ROLE_LABELS: Record<RequiredFormationRoleCode, string> = {
  BACKEND_DEVELOPER: 'توسعه‌دهنده Backend',
  FRONTEND_DEVELOPER: 'توسعه‌دهنده Frontend',
  PRODUCT_DESIGNER: 'طراح محصول',
}

type SelectedReadiness = Partial<Record<RequiredFormationRoleCode, string>>

function CandidateChoice({
  candidate,
  checked,
  onChange,
}: {
  candidate: ProjectReadinessResponse
  checked: boolean
  onChange: () => void
}) {
  return (
    <label
      className={
        checked
          ? 'staff-formation__candidate is-selected'
          : 'staff-formation__candidate'
      }
    >
      <input
        type="radio"
        name={`readiness-${candidate.role.code}`}
        value={candidate.id}
        checked={checked}
        onChange={onChange}
      />
      <span className="staff-formation__candidate-body">
        <strong dir="ltr">{candidate.user.email}</strong>
        <span className="staff-formation__candidate-meta">
          <span dir="ltr">{candidate.role.name}</span>
          <span dir="ltr">{candidate.role.code}</span>
        </span>
        <span className="staff-formation__candidate-stack">
          Stack:{' '}
          <b dir="ltr">
            {candidate.technology_stack?.name ?? 'بدون Stack'}
          </b>
        </span>
      </span>
      <StatusBadge status="آمادگی فعال" />
    </label>
  )
}

function RoleSlot({
  candidates,
  roleCode,
  selectedId,
  select,
}: {
  candidates: ProjectReadinessResponse[]
  roleCode: RequiredFormationRoleCode
  selectedId?: string
  select: (readinessId: string) => void
}) {
  const roleCandidates = candidates.filter(
    (candidate) => candidate.role.code === roleCode,
  )
  const headingId = `staff-formation-${roleCode.toLowerCase()}`

  return (
    <Card className="staff-formation__role-slot">
      <header>
        <div>
          <h2 id={headingId}>{ROLE_LABELS[roleCode]}</h2>
          <span dir="ltr">{roleCode}</span>
        </div>
        <span>{roleCandidates.length} نفر</span>
      </header>

      {roleCandidates.length ? (
        <fieldset aria-labelledby={headingId}>
          <legend className="sr-only">انتخاب {ROLE_LABELS[roleCode]}</legend>
          {roleCandidates.map((candidate) => (
            <CandidateChoice
              key={candidate.id}
              candidate={candidate}
              checked={selectedId === candidate.id}
              onChange={() => select(candidate.id)}
            />
          ))}
        </fieldset>
      ) : (
        <EmptyState
          title="آمادگی فعالی وجود ندارد"
          description="برای این نقش و همین نسخه دقیق پروژه، کاربر واجد شرایطی در API موجود نیست."
        />
      )}
    </Card>
  )
}

function keepAvailableSelections(
  selected: SelectedReadiness,
  candidates: ProjectReadinessResponse[],
) {
  const availableIds = new Set(candidates.map((candidate) => candidate.id))
  return Object.fromEntries(
    Object.entries(selected).filter(([, readinessId]) =>
      availableIds.has(readinessId),
    ),
  ) as SelectedReadiness
}

export function StaffFormationPage() {
  const auth = useAuth()
  const [versions, setVersions] = useState<StaffFormationProjectVersion[]>([])
  const [versionsLoading, setVersionsLoading] = useState(true)
  const [versionsError, setVersionsError] = useState('')
  const [versionsReloadKey, setVersionsReloadKey] = useState(0)
  const [selectedVersionId, setSelectedVersionId] = useState('')
  const [candidates, setCandidates] = useState<ProjectReadinessResponse[]>([])
  const [candidatesLoading, setCandidatesLoading] = useState(false)
  const [candidatesError, setCandidatesError] = useState('')
  const [accessDenied, setAccessDenied] = useState(false)
  const [candidatesReloadKey, setCandidatesReloadKey] = useState(0)
  const [selected, setSelected] = useState<SelectedReadiness>({})
  const [submitting, setSubmitting] = useState(false)
  const submittingRef = useRef(false)
  const [submitError, setSubmitError] = useState('')
  const [refreshError, setRefreshError] = useState('')
  const [createdFormation, setCreatedFormation] =
    useState<TeamFormationResponse | null>(null)

  useEffect(() => {
    const controller = new AbortController()

    void loadStaffFormationProjectVersions(controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return
        setVersions(result)
        setCandidates([])
        setCandidatesLoading(result.length > 0)
        setCandidatesError('')
        setAccessDenied(false)
        setSelectedVersionId((current) =>
          result.some((version) => version.projectVersionId === current)
            ? current
            : (result[0]?.projectVersionId ?? ''),
        )
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setVersionsError(staffFormationErrorMessage(error))
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setVersionsLoading(false)
      })

    return () => controller.abort()
  }, [versionsReloadKey])

  useEffect(() => {
    if (!selectedVersionId) return

    const controller = new AbortController()

    void loadActiveReadinessCandidates(selectedVersionId, controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return
        setCandidates(result)
        setSelected((current) => keepAvailableSelections(current, result))
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setCandidatesError(staffFormationErrorMessage(error))
        setAccessDenied(error instanceof ApiError && error.status === 403)
        if (isMissingSession(error)) {
          void auth.refreshSession()
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setCandidatesLoading(false)
      })

    return () => controller.abort()
  }, [auth, candidatesReloadKey, selectedVersionId])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submittingRef.current || !selectedVersionId) return

    const readinessIds = REQUIRED_FORMATION_ROLE_CODES.map(
      (roleCode) => selected[roleCode],
    )
    if (readinessIds.some((readinessId) => !readinessId)) return

    submittingRef.current = true
    setSubmitting(true)
    setSubmitError('')
    setRefreshError('')
    setCreatedFormation(null)
    try {
      const formation = await createTeamFormation(readinessIds as string[])
      setCreatedFormation(formation)
      setSelected({})
      try {
        const refreshed = await loadActiveReadinessCandidates(selectedVersionId)
        setCandidates(refreshed)
      } catch (error: unknown) {
        setRefreshError(
          `Formation ساخته شد، اما تازه‌سازی فهرست ممکن نشد. ${staffFormationErrorMessage(error)}`,
        )
      }
    } catch (error: unknown) {
      setSubmitError(staffFormationErrorMessage(error))
      try {
        const refreshed = await loadActiveReadinessCandidates(selectedVersionId)
        setCandidates(refreshed)
        setSelected((current) => keepAvailableSelections(current, refreshed))
      } catch {
        // Preserve the last authoritative list already shown when revalidation fails.
      }
      if (isMissingSession(error)) {
        void auth.refreshSession()
      }
    } finally {
      submittingRef.current = false
      setSubmitting(false)
    }
  }

  const selectedVersion = versions.find(
    (version) => version.projectVersionId === selectedVersionId,
  )
  const versionNumber = candidates[0]?.version_number ?? null
  const selectionComplete = REQUIRED_FORMATION_ROLE_CODES.every(
    (roleCode) => selected[roleCode],
  )

  if (versionsLoading) {
    return (
      <div className="staff-formation-page" dir="rtl" aria-busy="true">
        <LoadingState message="در حال دریافت نسخه‌های پروژه..." />
      </div>
    )
  }

  if (versionsError) {
    return (
      <div className="staff-formation-page" dir="rtl">
        <Alert tone="error">
          <h1>دریافت پروژه‌ها ممکن نشد</h1>
          <p>{versionsError}</p>
        </Alert>
        <Button
          variant="secondary"
          onClick={() => {
            setVersionsLoading(true)
            setVersionsError('')
            setVersionsReloadKey((current) => current + 1)
          }}
        >
          تلاش دوباره
        </Button>
      </div>
    )
  }

  if (accessDenied) {
    return (
      <div className="staff-formation-page" dir="rtl">
        <Alert className="staff-formation__permission" tone="error">
          <h1>دسترسی Staff لازم است</h1>
          <p>{candidatesError}</p>
        </Alert>
      </div>
    )
  }

  return (
    <div className="staff-formation-page" dir="rtl">
      <header className="staff-formation__intro">
        <p dir="ltr">PROLEARN · STAFF · MANUAL FORMATION</p>
        <h1>تشکیل دستی تیم</h1>
        <span>
          برای یک نسخه دقیق پروژه، از هر نقش یک آمادگی فعال را انتخاب کنید.
        </span>
      </header>

      {versions.length ? (
        <Card className="staff-formation__version-card">
          <label htmlFor="staff-project-version">نسخه دقیق پروژه</label>
          <select
            id="staff-project-version"
            value={selectedVersionId}
            disabled={submitting}
            onChange={(event) => {
              setCandidates([])
              setCandidatesLoading(true)
              setCandidatesError('')
              setAccessDenied(false)
              setSelectedVersionId(event.target.value)
              setSelected({})
              setSubmitError('')
              setRefreshError('')
              setCreatedFormation(null)
            }}
          >
            {versions.map((version) => (
              <option
                key={version.projectVersionId}
                value={version.projectVersionId}
              >
                {version.projectName} — {version.projectVersionId}
              </option>
            ))}
          </select>
          <div className="staff-formation__version-identity">
            <div>
              <span>پروژه</span>
              <strong>{selectedVersion?.projectName}</strong>
            </div>
            <div>
              <span>نسخه</span>
              <strong>{versionNumber === null ? 'نسخه دقیق انتخاب‌شده' : versionNumber}</strong>
            </div>
            <div>
              <span>شناسه ProjectVersion</span>
              <code>{selectedVersionId}</code>
            </div>
          </div>
        </Card>
      ) : (
        <EmptyState
          title="نسخه منتشرشده‌ای در دسترس نیست"
          description="API در حال حاضر نسخه دقیقی برای تشکیل تیم برنگردانده است."
        />
      )}

      {candidatesLoading ? (
        <div className="staff-formation__loading" aria-busy="true">
          <LoadingState message="در حال دریافت آمادگی‌های فعال..." />
        </div>
      ) : candidatesError ? (
        <Alert tone="error">
          <h2>دریافت آمادگی‌های فعال ممکن نشد</h2>
          <p>{candidatesError}</p>
          <Button
            variant="secondary"
            onClick={() => {
              setCandidatesLoading(true)
              setCandidatesError('')
              setAccessDenied(false)
              setCandidatesReloadKey((current) => current + 1)
            }}
          >
            تلاش دوباره
          </Button>
        </Alert>
      ) : selectedVersionId ? (
        <form className="staff-formation__form" onSubmit={handleSubmit}>
          {createdFormation ? (
            <Alert tone="success">
              <strong>Formation با موفقیت ساخته شد.</strong>
              <span>
                Ready Check برای سه عضو انتخاب‌شده آغاز شد.
              </span>
            </Alert>
          ) : null}
          {refreshError ? <Alert tone="error">{refreshError}</Alert> : null}
          {submitError ? (
            <Alert tone="error">
              <strong>ساخت Formation ممکن نشد.</strong>
              <span>{submitError}</span>
            </Alert>
          ) : null}

          <div className="staff-formation__roles">
            {REQUIRED_FORMATION_ROLE_CODES.map((roleCode) => (
              <RoleSlot
                key={roleCode}
                roleCode={roleCode}
                candidates={candidates}
                selectedId={selected[roleCode]}
                select={(readinessId) => {
                  setSelected((current) => ({
                    ...current,
                    [roleCode]: readinessId,
                  }))
                  setSubmitError('')
                  setCreatedFormation(null)
                }}
              />
            ))}
          </div>

          <div className="staff-formation__actions">
            <div>
              <strong>سه انتخاب لازم است</strong>
              <span>یک Backend، یک Frontend و یک Product Designer</span>
            </div>
            <Button type="submit" disabled={!selectionComplete || submitting}>
              {submitting ? 'در حال ساخت Formation...' : 'ساخت Formation'}
            </Button>
          </div>
        </form>
      ) : null}
      <ProjectRunRepositorySection />
    </div>
  )
}
