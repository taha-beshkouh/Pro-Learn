import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from 'react'
import { useAuth } from '../../auth/useAuth'
import { isMissingSession } from '../../lib/api/auth'
import { loadTeamFormations } from '../../lib/api/staffFormation'
import {
  completeStaffSprint,
  loadStaffSprintDetail,
  loadStaffSprintRuns,
  openStaffSprint,
  requestStaffSprintChanges,
  staffSprintReviewErrorMessage,
  startStaffSprintReview,
} from '../../lib/api/staffSprintReview'
import { loadStaffProjectRunRepositories } from '../../lib/api/staffRepository'
import type {
  SprintRunState,
  StaffProjectRunRepository,
  StaffSprintRunDetailResponse,
  StaffSprintRunListItem,
  StaffSprintSubmissionResponse,
  TeamFormationResponse,
} from '../../lib/api/types'
import { Alert } from '../ui/Alert'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { EmptyState } from '../ui/EmptyState'
import { LoadingState } from '../ui/LoadingState'
import { StatusBadge } from '../ui/StatusBadge'

const STATE_LABELS: Record<SprintRunState, string> = {
  LOCKED: 'قفل',
  ACTIVE: 'فعال',
  SUBMITTED: 'ارسال‌شده',
  UNDER_REVIEW: 'در حال بررسی',
  CHANGES_REQUESTED: 'نیازمند اصلاح',
  COMPLETED: 'تکمیل‌شده',
}

type ReviewProjectRun = {
  id: string
  projectName: string
  projectVersionId: string
  versionNumber: number | null
  state: StaffProjectRunRepository['state'] | null
  repositoryUrl: string | null
  teamId: string | null
  mutable: boolean
}

function buildProjectRunOptions(
  activeRuns: StaffProjectRunRepository[],
  formations: TeamFormationResponse[],
): ReviewProjectRun[] {
  const active = activeRuns.map((run) => ({
    id: run.id,
    projectName: run.project.name,
    projectVersionId: run.project.version_id,
    versionNumber: run.project.version_number,
    state: run.state,
    repositoryUrl: run.repository_url,
    teamId: run.team_id,
    mutable: run.state === 'ACTIVE',
  }))
  const knownIds = new Set(active.map((run) => run.id))
  const historical: ReviewProjectRun[] = []

  for (const formation of formations) {
    if (!formation.project_run_id || knownIds.has(formation.project_run_id)) {
      continue
    }
    knownIds.add(formation.project_run_id)
    historical.push({
      id: formation.project_run_id,
      projectName: formation.project_name,
      projectVersionId: formation.project_version_id,
      versionNumber: null,
      state: null,
      repositoryUrl: null,
      teamId: formation.team_id,
      mutable: false,
    })
  }

  return [...active, ...historical]
}

const dateFormatter = new Intl.DateTimeFormat('fa-IR', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

function formatDate(value: string | null) {
  if (!value) return 'ثبت نشده'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : dateFormatter.format(parsed)
}

function EvidenceLink({ href, label }: { href: string | null; label: string }) {
  return (
    <div className="staff-review__evidence-row">
      <dt>{label}</dt>
      <dd>
        {href ? (
          <a href={href} target="_blank" rel="noopener noreferrer" dir="ltr">
            {href}
          </a>
        ) : (
          <span>ثبت نشده</span>
        )}
      </dd>
    </div>
  )
}

function SubmissionDetails({
  submission,
  heading,
}: {
  submission: StaffSprintSubmissionResponse
  heading: string
}) {
  return (
    <Card className="staff-review__submission">
      <header>
        <h4>{heading}</h4>
        <span>{formatDate(submission.submitted_at)}</span>
      </header>
      <dl>
        <div className="staff-review__evidence-row">
          <dt>ارسال‌کننده واقعی</dt>
          <dd dir="ltr">{submission.submitted_by.user.email}</dd>
        </div>
        <EvidenceLink href={submission.final_commit_url} label="Commit نهایی" />
        <EvidenceLink href={submission.deployment_url} label="نسخه Deploy‌شده" />
        <EvidenceLink
          href={submission.design_url_snapshot}
          label="Snapshot فضای طراحی این ارسال"
        />
        <div className="staff-review__evidence-row">
          <dt>یادداشت تیم</dt>
          <dd>{submission.evidence || 'یادداشتی ثبت نشده است.'}</dd>
        </div>
      </dl>

      {submission.review_decision ? (
        <section
          className="staff-review__decision"
          aria-label={`نتیجه بررسی ${heading}`}
        >
          <div>
            <strong>نتیجه بررسی</strong>
            <StatusBadge
              status={
                submission.review_decision.decision === 'COMPLETED'
                  ? 'تأیید و تکمیل'
                  : 'درخواست اصلاح'
              }
            />
          </div>
          <p>
            {submission.review_decision.feedback || 'بازخوردی ثبت نشده است.'}
          </p>
          <small>
            بررسی توسط{' '}
            <b dir="ltr">{submission.review_decision.reviewed_by.email}</b>
            {' · '}
            {formatDate(submission.review_decision.reviewed_at)}
          </small>
        </section>
      ) : (
        <p className="staff-review__pending-decision">تصمیم نهایی برای این ارسال ثبت نشده است.</p>
      )}
    </Card>
  )
}

type ActionPanel = 'request-changes' | 'complete' | null

export function StaffSprintReviewSection() {
  const auth = useAuth()
  const [opened, setOpened] = useState(false)
  const [activeRuns, setActiveRuns] = useState<StaffProjectRunRepository[]>([])
  const [formations, setFormations] = useState<TeamFormationResponse[]>([])
  const [discoveryLoading, setDiscoveryLoading] = useState(false)
  const [discoveryError, setDiscoveryError] = useState('')
  const [discoveryReloadKey, setDiscoveryReloadKey] = useState(0)
  const [selectedProjectRunId, setSelectedProjectRunId] = useState('')
  const [sprints, setSprints] = useState<StaffSprintRunListItem[]>([])
  const [sprintsLoading, setSprintsLoading] = useState(false)
  const [sprintsError, setSprintsError] = useState('')
  const [selectedSprintId, setSelectedSprintId] = useState('')
  const [detail, setDetail] = useState<StaffSprintRunDetailResponse | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState('')
  const [mutating, setMutating] = useState(false)
  const mutationRef = useRef(false)
  const [mutationError, setMutationError] = useState('')
  const [actionPanel, setActionPanel] = useState<ActionPanel>(null)
  const [changesFeedback, setChangesFeedback] = useState('')
  const [completeFeedback, setCompleteFeedback] = useState('')
  const [feedbackError, setFeedbackError] = useState('')

  const projectRuns = useMemo(
    () => buildProjectRunOptions(activeRuns, formations),
    [activeRuns, formations],
  )
  const selectedProjectRun = projectRuns.find(
    (run) => run.id === selectedProjectRunId,
  )
  const isFinalSprint =
    sprints.length > 0 && sprints[sprints.length - 1]?.id === selectedSprintId

  useEffect(() => {
    if (!opened) return
    const controller = new AbortController()
    void Promise.all([
      loadStaffProjectRunRepositories(controller.signal),
      loadTeamFormations(controller.signal),
    ])
      .then(([runs, formationItems]) => {
        if (controller.signal.aborted) return
        setActiveRuns(runs)
        setFormations(formationItems)
        const options = buildProjectRunOptions(runs, formationItems)
        setSelectedProjectRunId((current) =>
          options.some((run) => run.id === current)
            ? current
            : (options[0]?.id ?? ''),
        )
        setSprintsLoading(options.length > 0)
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setDiscoveryError(staffSprintReviewErrorMessage(error))
        if (isMissingSession(error)) void auth.refreshSession()
      })
      .finally(() => {
        if (!controller.signal.aborted) setDiscoveryLoading(false)
      })
    return () => controller.abort()
  }, [auth, discoveryReloadKey, opened])

  useEffect(() => {
    if (!selectedProjectRunId) return
    const controller = new AbortController()
    void loadStaffSprintRuns(selectedProjectRunId, controller.signal)
      .then((items) => {
        if (controller.signal.aborted) return
        setSprints(items)
        setDetailLoading(items.length > 0)
        setSelectedSprintId((current) => {
          if (items.some((item) => item.id === current)) return current
          const actionable = items.find((item) =>
            ['SUBMITTED', 'UNDER_REVIEW'].includes(item.state),
          )
          return actionable?.id ?? items[0]?.id ?? ''
        })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setSprintsError(staffSprintReviewErrorMessage(error))
        if (isMissingSession(error)) void auth.refreshSession()
      })
      .finally(() => {
        if (!controller.signal.aborted) setSprintsLoading(false)
      })
    return () => controller.abort()
  }, [auth, selectedProjectRunId])

  useEffect(() => {
    if (!selectedProjectRunId || !selectedSprintId) return
    const controller = new AbortController()
    void loadStaffSprintDetail(
      selectedProjectRunId,
      selectedSprintId,
      controller.signal,
    )
      .then((result) => {
        if (!controller.signal.aborted) setDetail(result)
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setDetailError(staffSprintReviewErrorMessage(error))
        if (isMissingSession(error)) void auth.refreshSession()
      })
      .finally(() => {
        if (!controller.signal.aborted) setDetailLoading(false)
      })
    return () => controller.abort()
  }, [auth, selectedProjectRunId, selectedSprintId])

  async function refreshRuntime() {
    if (!selectedProjectRunId || !selectedSprintId) return
    const [nextSprints, nextDetail, nextActiveRuns] = await Promise.all([
      loadStaffSprintRuns(selectedProjectRunId),
      loadStaffSprintDetail(selectedProjectRunId, selectedSprintId),
      loadStaffProjectRunRepositories(),
    ])
    setSprints(nextSprints)
    setDetail(nextDetail)
    setActiveRuns(nextActiveRuns)
  }

  async function runMutation(
    action: () => Promise<unknown>,
    onSuccess?: () => void,
  ) {
    if (mutationRef.current) return
    mutationRef.current = true
    setMutating(true)
    setMutationError('')
    try {
      await action()
    } catch (error: unknown) {
      setMutationError(staffSprintReviewErrorMessage(error))
      try {
        await refreshRuntime()
      } catch {
        // Keep the actionable mutation error when authoritative revalidation also fails.
      }
      if (isMissingSession(error)) void auth.refreshSession()
      mutationRef.current = false
      setMutating(false)
      return
    }

    onSuccess?.()
    try {
      await refreshRuntime()
    } catch (error: unknown) {
      setMutationError(
        `عملیات ثبت شد، اما تازه‌سازی اطلاعات ممکن نشد. ${staffSprintReviewErrorMessage(error)}`,
      )
    } finally {
      mutationRef.current = false
      setMutating(false)
    }
  }

  function selectSprint(sprintRunId: string) {
    setSelectedSprintId(sprintRunId)
    setDetailLoading(true)
    setDetailError('')
    setActionPanel(null)
    setChangesFeedback('')
    setCompleteFeedback('')
    setFeedbackError('')
    setMutationError('')
  }

  function submitChanges(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const feedback = changesFeedback.trim()
    if (!feedback) {
      setFeedbackError('برای درخواست اصلاح، بازخورد معنادار وارد کنید.')
      return
    }
    setFeedbackError('')
    void runMutation(
      () =>
        requestStaffSprintChanges(
          selectedProjectRunId,
          selectedSprintId,
          feedback,
        ),
      () => {
        setActionPanel(null)
        setChangesFeedback('')
      },
    )
  }

  function submitComplete(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const feedback = completeFeedback.trim()
    void runMutation(
      () =>
        completeStaffSprint(
          selectedProjectRunId,
          selectedSprintId,
          feedback || undefined,
        ),
      () => {
        setActionPanel(null)
        setCompleteFeedback('')
      },
    )
  }

  return (
    <section className="staff-review" aria-labelledby="staff-review-title">
      <header>
        <p dir="ltr">PROLEARN · STAFF · SPRINT REVIEW</p>
        <h2 id="staff-review-title">بررسی اسپرینت‌ها</h2>
        <span>
          ارسال‌های واقعی تیم را بررسی کنید، بازخورد ثبت کنید و چرخه Sprint را با پاسخ قطعی سرور پیش ببرید.
        </span>
      </header>

      {!opened ? (
        <Button
          onClick={() => {
            setOpened(true)
            setDiscoveryLoading(true)
            setDiscoveryError('')
          }}
        >
          ورود به بررسی اسپرینت‌ها
        </Button>
      ) : discoveryLoading ? (
        <LoadingState message="در حال دریافت ProjectRunها..." />
      ) : discoveryError ? (
        <Alert tone="error">
          <p>{discoveryError}</p>
          <Button
            variant="secondary"
            onClick={() => {
              setDiscoveryLoading(true)
              setDiscoveryError('')
              setDiscoveryReloadKey((current) => current + 1)
            }}
          >
            تلاش دوباره
          </Button>
        </Alert>
      ) : projectRuns.length === 0 ? (
        <EmptyState
          title="ProjectRun قابل بررسی وجود ندارد"
          description="پس از ایجاد ProjectRun، اسپرینت‌های آن در این بخش نمایش داده می‌شوند."
        />
      ) : (
        <>
          <Card className="staff-review__run-picker">
            <label htmlFor="staff-review-project-run">ProjectRun</label>
            <select
              id="staff-review-project-run"
              value={selectedProjectRunId}
              disabled={mutating}
              onChange={(event) => {
                setSelectedProjectRunId(event.target.value)
                setSelectedSprintId('')
                setSprints([])
                setDetail(null)
                setSprintsLoading(true)
                setSprintsError('')
                setDetailError('')
                setActionPanel(null)
                setMutationError('')
              }}
            >
              {projectRuns.map((run) => (
                <option key={run.id} value={run.id}>
                  {run.projectName} — {run.mutable ? 'ACTIVE' : 'تاریخی / فقط خواندنی'}
                </option>
              ))}
            </select>
            {selectedProjectRun ? (
              <div className="staff-review__run-context">
                <div>
                  <span>پروژه</span>
                  <strong>{selectedProjectRun.projectName}</strong>
                </div>
                <div>
                  <span>وضعیت ProjectRun</span>
                  <strong>
                    {selectedProjectRun.state ?? 'تاریخی / فقط خواندنی'}
                  </strong>
                </div>
                <div>
                  <span>مخزن canonical پروژه</span>
                  {selectedProjectRun.repositoryUrl ? (
                    <a
                      href={selectedProjectRun.repositoryUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      dir="ltr"
                    >
                      {selectedProjectRun.repositoryUrl}
                    </a>
                  ) : (
                    <span>
                      {selectedProjectRun.mutable
                        ? 'هنوز ثبت نشده است.'
                        : 'در قرارداد فهرست تاریخی ارائه نشده است.'}
                    </span>
                  )}
                </div>
              </div>
            ) : null}
          </Card>

          {sprintsLoading ? (
            <LoadingState message="در حال دریافت Sprintها..." />
          ) : sprintsError ? (
            <Alert tone="error">{sprintsError}</Alert>
          ) : sprints.length === 0 ? (
            <EmptyState
              title="Sprintی برای این ProjectRun وجود ندارد"
              description="فهرست SprintRun از API خالی است."
            />
          ) : (
            <div className="staff-review__workspace">
              <nav className="staff-review__sprint-list" aria-label="فهرست Sprintها">
                {sprints.map((sprint) => (
                  <button
                    key={sprint.id}
                    type="button"
                    className={sprint.id === selectedSprintId ? 'is-selected' : ''}
                    aria-current={sprint.id === selectedSprintId ? 'true' : undefined}
                    disabled={mutating}
                    onClick={() => selectSprint(sprint.id)}
                  >
                    <span>Sprint {sprint.sequence}</span>
                    <strong>{sprint.title}</strong>
                    <StatusBadge status={`${STATE_LABELS[sprint.state]} · ${sprint.state}`} />
                  </button>
                ))}
              </nav>

              <section className="staff-review__detail" aria-live="polite">
                {detailLoading ? (
                  <LoadingState message="در حال دریافت جزئیات Sprint..." />
                ) : detailError ? (
                  <Alert tone="error">{detailError}</Alert>
                ) : !detail ? (
                  <EmptyState
                    title="Sprintی انتخاب نشده است"
                    description="برای مشاهده ارسال‌ها و تاریخچه، یک Sprint را انتخاب کنید."
                  />
                ) : (
                  <>
                    <header className="staff-review__detail-heading">
                      <div>
                        <span>Sprint {detail.sequence}</span>
                        <h3>{detail.title}</h3>
                        <p>{detail.brief}</p>
                      </div>
                      <StatusBadge status={`${STATE_LABELS[detail.state]} · ${detail.state}`} />
                    </header>

                    <dl className="staff-review__timing">
                      <div>
                        <dt>شروع برنامه‌ریزی‌شده</dt>
                        <dd>{formatDate(detail.planned_start_at)}</dd>
                      </div>
                      <div>
                        <dt>پایان برنامه‌ریزی‌شده</dt>
                        <dd>{formatDate(detail.planned_end_at)}</dd>
                      </div>
                      <div>
                        <dt>زمان بازشدن</dt>
                        <dd>{formatDate(detail.opened_at)}</dd>
                      </div>
                    </dl>

                    {mutationError ? (
                      <Alert tone="error" role="alert">
                        {mutationError}
                      </Alert>
                    ) : null}

                    {selectedProjectRun?.mutable ? (
                      <div className="staff-review__actions">
                        {detail.state === 'LOCKED' ? (
                          <Button
                            disabled={mutating}
                            onClick={() =>
                              void runMutation(() =>
                                openStaffSprint(selectedProjectRunId, selectedSprintId),
                              )
                            }
                          >
                            {mutating ? 'در حال بازکردن...' : 'بازکردن Sprint'}
                          </Button>
                        ) : null}
                        {detail.state === 'SUBMITTED' ? (
                          <Button
                            disabled={mutating}
                            onClick={() =>
                              void runMutation(() =>
                                startStaffSprintReview(
                                  selectedProjectRunId,
                                  selectedSprintId,
                                ),
                              )
                            }
                          >
                            {mutating ? 'در حال شروع بررسی...' : 'شروع بررسی'}
                          </Button>
                        ) : null}
                        {detail.state === 'UNDER_REVIEW' ? (
                          <>
                            <Button
                              variant="secondary"
                              disabled={mutating}
                              onClick={() => {
                                setActionPanel('request-changes')
                                setFeedbackError('')
                              }}
                            >
                              درخواست اصلاح
                            </Button>
                            <Button
                              disabled={mutating}
                              onClick={() => setActionPanel('complete')}
                            >
                              تکمیل Sprint
                            </Button>
                          </>
                        ) : null}
                      </div>
                    ) : (
                      <Alert tone="info">
                        این ProjectRun تاریخی است؛ اطلاعات قابل مشاهده است اما عملیات تغییردهنده نمایش داده نمی‌شود.
                      </Alert>
                    )}

                    {actionPanel === 'request-changes' &&
                    detail.state === 'UNDER_REVIEW' &&
                    selectedProjectRun?.mutable ? (
                      <form className="staff-review__feedback-form" onSubmit={submitChanges}>
                        <label htmlFor="staff-review-changes-feedback">
                          بازخورد موردنیاز برای اصلاح
                        </label>
                        <textarea
                          id="staff-review-changes-feedback"
                          rows={4}
                          value={changesFeedback}
                          disabled={mutating}
                          onChange={(event) => {
                            setChangesFeedback(event.target.value)
                            setFeedbackError('')
                          }}
                        />
                        {feedbackError ? <p role="alert">{feedbackError}</p> : null}
                        <div>
                          <Button type="submit" variant="danger" disabled={mutating}>
                            {mutating ? 'در حال ثبت...' : 'ثبت درخواست اصلاح'}
                          </Button>
                          <Button
                            variant="secondary"
                            disabled={mutating}
                            onClick={() => setActionPanel(null)}
                          >
                            انصراف
                          </Button>
                        </div>
                      </form>
                    ) : null}

                    {actionPanel === 'complete' &&
                    detail.state === 'UNDER_REVIEW' &&
                    selectedProjectRun?.mutable ? (
                      <form className="staff-review__feedback-form" onSubmit={submitComplete}>
                        <strong>تأیید تکمیل Sprint</strong>
                        {isFinalSprint ? (
                          <Alert tone="info">
                            تکمیل این آخرین Sprint، ProjectRun را نیز طبق پاسخ قطعی backend تکمیل می‌کند.
                          </Alert>
                        ) : null}
                        <label htmlFor="staff-review-complete-feedback">
                          بازخورد (اختیاری)
                        </label>
                        <textarea
                          id="staff-review-complete-feedback"
                          rows={3}
                          value={completeFeedback}
                          disabled={mutating}
                          onChange={(event) => setCompleteFeedback(event.target.value)}
                        />
                        <div>
                          <Button type="submit" disabled={mutating}>
                            {mutating ? 'در حال تکمیل...' : 'تأیید تکمیل'}
                          </Button>
                          <Button
                            variant="secondary"
                            disabled={mutating}
                            onClick={() => setActionPanel(null)}
                          >
                            انصراف
                          </Button>
                        </div>
                      </form>
                    ) : null}

                    <section className="staff-review__current" aria-labelledby="current-submission-title">
                      <h3 id="current-submission-title">ارسال فعلی برای بررسی</h3>
                      {detail.latest_submission ? (
                        <SubmissionDetails
                          submission={detail.latest_submission}
                          heading="آخرین ارسال قطعی backend"
                        />
                      ) : (
                        <EmptyState
                          title="هنوز ارسالی وجود ندارد"
                          description="پس از ارسال تیم، آخرین submission در این بخش نمایش داده می‌شود."
                        />
                      )}
                    </section>

                    <section className="staff-review__history" aria-labelledby="submission-history-title">
                      <h3 id="submission-history-title">تاریخچه ارسال و بررسی</h3>
                      {detail.submissions.length ? (
                        <div>
                          {detail.submissions.map((submission, index) => (
                            <SubmissionDetails
                              key={submission.id}
                              submission={submission}
                              heading={`ارسال شماره ${index + 1}`}
                            />
                          ))}
                        </div>
                      ) : (
                        <EmptyState
                          title="تاریخچه ارسال خالی است"
                          description="این Sprint هنوز SprintSubmission ثبت‌شده‌ای ندارد."
                        />
                      )}
                    </section>
                  </>
                )}
              </section>
            </div>
          )}
        </>
      )}
    </section>
  )
}
