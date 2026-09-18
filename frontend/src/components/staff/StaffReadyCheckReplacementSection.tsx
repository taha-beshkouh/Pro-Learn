import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useAuth } from '../../auth/useAuth'
import { isMissingSession } from '../../lib/api/auth'
import {
  loadActiveReadinessCandidates,
  loadTeamFormations,
  replaceFormationReadyCheck,
  staffFormationErrorMessage,
} from '../../lib/api/staffFormation'
import type {
  FormationReadyCheckResponse,
  ProjectReadinessResponse,
  TeamFormationResponse,
} from '../../lib/api/types'
import { Alert } from '../ui/Alert'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { EmptyState } from '../ui/EmptyState'
import { LoadingState } from '../ui/LoadingState'

const STATUS_LABELS = {
  PENDING: 'در انتظار پاسخ',
  CONFIRMED: 'تأیید شده',
  DECLINED: 'رد شده',
  EXPIRED: 'مهلت پایان یافته',
} as const

type SelectedSlot = {
  formation: TeamFormationResponse
  readyCheck: FormationReadyCheckResponse
}

function currentSlots(formation: TeamFormationResponse) {
  return formation.ready_checks.filter((check) => check.is_current)
}

export function StaffReadyCheckReplacementSection() {
  const auth = useAuth()
  const [opened, setOpened] = useState(false)
  const [formations, setFormations] = useState<TeamFormationResponse[]>([])
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const [selected, setSelected] = useState<SelectedSlot | null>(null)
  const [candidates, setCandidates] = useState<ProjectReadinessResponse[]>([])
  const [candidatesLoading, setCandidatesLoading] = useState(false)
  const [candidatesError, setCandidatesError] = useState('')
  const [readinessId, setReadinessId] = useState('')
  const [saving, setSaving] = useState(false)
  const savingRef = useRef(false)
  const [saveError, setSaveError] = useState('')

  useEffect(() => {
    if (!opened) return
    const controller = new AbortController()
    void loadTeamFormations(controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) setFormations(items)
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setLoadError(staffFormationErrorMessage(error))
        if (isMissingSession(error)) void auth.refreshSession()
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [auth, opened, reloadKey])

  useEffect(() => {
    if (!selected) return
    const controller = new AbortController()
    void loadActiveReadinessCandidates(
      selected.formation.project_version_id,
      controller.signal,
    )
      .then((items) => {
        if (!controller.signal.aborted) setCandidates(items)
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setCandidatesError(staffFormationErrorMessage(error))
        if (isMissingSession(error)) void auth.refreshSession()
      })
      .finally(() => {
        if (!controller.signal.aborted) setCandidatesLoading(false)
      })
    return () => controller.abort()
  }, [auth, selected])

  function selectSlot(formation: TeamFormationResponse, readyCheck: FormationReadyCheckResponse) {
    setSelected({ formation, readyCheck })
    setCandidates([])
    setCandidatesLoading(true)
    setCandidatesError('')
    setReadinessId('')
    setSaveError('')
  }

  async function submitReplacement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selected || !readinessId || savingRef.current) return
    savingRef.current = true
    setSaving(true)
    setSaveError('')
    try {
      await replaceFormationReadyCheck(
        selected.formation.id,
        selected.readyCheck.id,
        readinessId,
      )
      const refreshed = await loadTeamFormations()
      setFormations(refreshed)
      setSelected(null)
      setCandidates([])
      setReadinessId('')
    } catch (error: unknown) {
      setSaveError(staffFormationErrorMessage(error))
      if (isMissingSession(error)) void auth.refreshSession()
      try {
        const refreshed = await loadTeamFormations()
        setFormations(refreshed)
        const current = refreshed
          .find((formation) => formation.id === selected.formation.id)
          ?.ready_checks.find((check) => check.id === selected.readyCheck.id)
        if (
          !current?.is_current ||
          !['DECLINED', 'EXPIRED'].includes(current.effective_status)
        ) {
          setSelected(null)
        }
      } catch {
        // Preserve the mutation error if authoritative revalidation also fails.
      }
    } finally {
      savingRef.current = false
      setSaving(false)
    }
  }

  const unresolved = formations.filter((formation) => formation.project_run_id === null)

  return (
    <section className="staff-ready-checks" aria-labelledby="staff-ready-checks-title">
      <header>
        <h2 id="staff-ready-checks-title">مدیریت Ready Check</h2>
        <p>جایگاه ردشده یا منقضی‌شده را با آمادگی معتبر همان نسخه پروژه جایگزین کنید.</p>
      </header>
      {!opened ? (
        <Button onClick={() => { setOpened(true); setLoading(true) }}>
          مشاهده Formationها و Ready Checkها
        </Button>
      ) : loading ? (
        <LoadingState message="در حال دریافت Formationها..." />
      ) : loadError ? (
        <Alert tone="error">
          <p>{loadError}</p>
          <Button variant="secondary" onClick={() => {
            setLoadError('')
            setLoading(true)
            setReloadKey((value) => value + 1)
          }}>تلاش دوباره</Button>
        </Alert>
      ) : unresolved.length === 0 ? (
        <EmptyState
          title="Formation در انتظار Ready Check وجود ندارد"
          description="Formationهای تکمیل‌شده در بخش Sprintها قابل مشاهده‌اند."
        />
      ) : (
        <div className="staff-ready-checks__formations">
          {unresolved.map((formation) => (
            <Card key={formation.id} className="staff-ready-checks__formation">
              <h3>{formation.project_name}</h3>
              <p dir="ltr">ProjectVersion: {formation.project_version_id}</p>
              <ul>
                {currentSlots(formation).map((check) => {
                  const replaceable = check.effective_status === 'DECLINED' || check.effective_status === 'EXPIRED'
                  return (
                    <li key={check.id}>
                      <strong>{check.role.name}</strong>
                      <span dir="ltr">{check.user.email}</span>
                      <span>{STATUS_LABELS[check.effective_status]}</span>
                      {replaceable ? (
                        <Button
                          variant="secondary"
                          disabled={saving}
                          onClick={() => selectSlot(formation, check)}
                        >جایگزینی عضو</Button>
                      ) : null}
                    </li>
                  )
                })}
              </ul>
              {formation.ready_checks.some((check) => !check.is_current) ? (
                <details>
                  <summary>سابقه جایگاه‌های جایگزین‌شده</summary>
                  <ul>
                    {formation.ready_checks.filter((check) => !check.is_current).map((check) => (
                      <li key={check.id}>
                        {check.role.name} — <span dir="ltr">{check.user.email}</span> — {STATUS_LABELS[check.effective_status]}
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
            </Card>
          ))}
        </div>
      )}

      {!selected && saveError ? <Alert tone="error">{saveError}</Alert> : null}

      {selected ? (
        <Card className="staff-ready-checks__replacement">
          <h3>جایگزینی {selected.readyCheck.role.name}</h3>
          <p>داوطلبان از API آمادگیِ همین ProjectVersion دریافت می‌شوند. سرور تطابق نقش، Stack و شرایط مشارکت را هنگام ثبت دوباره بررسی می‌کند.</p>
          {candidatesLoading ? (
            <LoadingState message="در حال دریافت داوطلبان..." />
          ) : candidatesError ? (
            <Alert tone="error">{candidatesError}</Alert>
          ) : candidates.length === 0 ? (
            <EmptyState title="داوطلب فعالی وجود ندارد" description="پس از ثبت آمادگی معتبر، دوباره این جایگاه را بررسی کنید." />
          ) : (
            <form onSubmit={(event) => void submitReplacement(event)}>
              <label htmlFor="staff-replacement-readiness">آمادگی داوطلب جایگزین</label>
              <select
                id="staff-replacement-readiness"
                required
                value={readinessId}
                disabled={saving}
                onChange={(event) => setReadinessId(event.target.value)}
              >
                <option value="">انتخاب کنید</option>
                {candidates.map((candidate) => (
                  <option key={candidate.id} value={candidate.id}>
                    {candidate.user.email} — {candidate.role.name}
                    {candidate.technology_stack ? ` — ${candidate.technology_stack.name}` : ''}
                  </option>
                ))}
              </select>
              {saveError ? <Alert tone="error">{saveError}</Alert> : null}
              <div className="staff-ready-checks__actions">
                <Button type="submit" disabled={!readinessId || saving}>
                  {saving ? 'در حال جایگزینی...' : 'ثبت جایگزینی'}
                </Button>
                <Button variant="secondary" disabled={saving} onClick={() => setSelected(null)}>
                  انصراف
                </Button>
              </div>
            </form>
          )}
        </Card>
      ) : null}
    </section>
  )
}
