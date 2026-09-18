import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { Alert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { LoadingState } from '../components/ui/LoadingState'
import { StatusBadge } from '../components/ui/StatusBadge'
import { isMissingSession } from '../lib/api/auth'
import { ApiError } from '../lib/api/client'
import {
  loadSprintDetail,
  SprintDetailContractError,
  submitSprintEvidence,
} from '../lib/api/sprintDetail'
import type {
  ProjectWorkItem,
  SprintRunDetailResponse,
  SprintSubmissionResponse,
} from '../lib/api/types'
import { loadWorkspace } from '../lib/api/workspace'
import {
  buildSprintDetailViewModel,
  type SprintDetailAction,
  type SprintDetailViewModel,
} from '../lib/sprintDetailView'
import '../styles/sprint-detail.css'

type LoadState =
  | { status: 'loading'; requestedId: string | null }
  | { status: 'not-found'; requestedId: string }
  | { status: 'error'; requestedId: string; error: unknown }
  | { status: 'success'; requestedId: string; data: SprintRunDetailResponse }

const dateFormatter = new Intl.DateTimeFormat('fa-IR', {
  dateStyle: 'medium',
  timeStyle: 'short',
})
const numberFormatter = new Intl.NumberFormat('fa-IR')

function sprintDetailErrorMessage(error: unknown) {
  if (error instanceof SprintDetailContractError) {
    return 'اطلاعات اسپرینت با قرارداد فعلی SprintRun هماهنگ نیست. صفحه را دوباره بارگذاری کنید.'
  }
  if (error instanceof ApiError) {
    if (isMissingSession(error)) {
      return 'نشست شما پایان یافته است. برای ادامه دوباره وارد شوید.'
    }
    if (error.status === 403) {
      return 'اجازه دسترسی به این اسپرینت برای حساب شما وجود ندارد.'
    }
    return 'دریافت اطلاعات اسپرینت ممکن نشد. کمی بعد دوباره تلاش کنید.'
  }
  return 'ارتباط با سرور برقرار نشد. اتصال اینترنت را بررسی و دوباره تلاش کنید.'
}

function missingDesignWorkspaceMessage(memberRoleCode: string | null) {
  if (memberRoleCode === 'PRODUCT_DESIGNER') {
    return 'فضای طراحی پروژه هنوز تنظیم نشده است. شما می‌توانید لینک آن را در Workspace ثبت کنید.'
  }
  if (memberRoleCode) {
    return 'طراح محصول هنوز فضای طراحی پروژه را تنظیم نکرده است. شما امکان تغییر آن را ندارید؛ پس از ثبت لینک، ارسال مدارک اسپرینت ممکن می‌شود.'
  }
  return 'فضای طراحی پروژه هنوز تنظیم نشده است. طراح محصول می‌تواند لینک آن را در Workspace ثبت کند.'
}

function isBasicHttpUrl(value: string) {
  try {
    const parsed = new URL(value)
    return (
      (parsed.protocol === 'http:' || parsed.protocol === 'https:') &&
      Boolean(parsed.hostname) &&
      !parsed.username &&
      !parsed.password
    )
  } catch {
    return false
  }
}

function submissionFieldError(finalCommitUrl: string, deploymentUrl: string) {
  if (!finalCommitUrl) return 'آدرس کامیت نهایی الزامی است.'
  if (finalCommitUrl.length > 500 || !isBasicHttpUrl(finalCommitUrl)) {
    return 'آدرس کامیت نهایی باید یک URL کامل HTTP یا HTTPS باشد.'
  }
  if (!deploymentUrl) return 'آدرس نسخه استقرار الزامی است.'
  if (deploymentUrl.length > 500 || !isBasicHttpUrl(deploymentUrl)) {
    return 'آدرس نسخه استقرار باید یک URL کامل HTTP یا HTTPS باشد.'
  }
  return null
}

function submissionErrorMessage(error: unknown, memberRoleCode: string | null) {
  if (error instanceof SprintDetailContractError) {
    return 'شناسه ProjectRun جاری از پاسخ سرور قابل دریافت نبود. صفحه را دوباره بارگذاری کنید.'
  }
  if (error instanceof ApiError) {
    if (isMissingSession(error)) {
      return 'نشست شما پایان یافته است. برای ادامه دوباره وارد شوید.'
    }
    if (error.status === 400) {
      if (error.data && typeof error.data === 'object') {
        if ('final_commit_url' in error.data) {
          return 'آدرس کامیت نهایی باید به یک کامیت معتبر در مخزن همین ProjectRun اشاره کند.'
        }
        if ('deployment_url' in error.data) {
          return 'آدرس نسخه استقرار معتبر نیست. یک URL کامل HTTP یا HTTPS وارد کنید.'
        }
      }
      return 'اطلاعات ارسال معتبر نیست. آدرس کامیت نهایی و نسخه استقرار را بررسی کنید.'
    }
    if (error.status === 403 || error.status === 404) {
      return 'عضویت یا دسترسی شما برای این اسپرینت تأیید نشد.'
    }
    if (error.status === 409) {
      const payload = JSON.stringify(error.data ?? '').toLowerCase()
      if (payload.includes('deadline')) {
        return 'مهلت ProjectRun به پایان رسیده و ارسال جدید پذیرفته نشد.'
      }
      if (payload.includes('repository')) {
        return 'مخزن رسمی ProjectRun هنوز تنظیم نشده است؛ با تیم PROLEARN هماهنگ کنید.'
      }
      if (payload.includes('design workspace')) {
        return missingDesignWorkspaceMessage(memberRoleCode)
      }
      return 'وضعیت اسپرینت تغییر کرده و این ارسال دیگر مجاز نیست. اطلاعات تازه از سرور دریافت شد.'
    }
    return 'ثبت ارسال در حال حاضر ممکن نیست. کمی بعد دوباره تلاش کنید.'
  }
  return 'ارتباط با سرور برقرار نشد و ارسال ثبت نشد.'
}

function DateValue({ value, empty }: { value: string | null; empty: string }) {
  if (!value) return <span>{empty}</span>
  const timestamp = Date.parse(value)
  return (
    <time dateTime={value} dir="ltr">
      {Number.isNaN(timestamp) ? 'زمان نامعتبر' : dateFormatter.format(timestamp)}
    </time>
  )
}

function SprintHeader({ view }: { view: SprintDetailViewModel }) {
  const { sprint } = view
  return (
    <section className="sprint-detail__identity" aria-labelledby="sprint-detail-title">
      <header>
        <div>
          <p className="sprint-detail__eyebrow">
            اسپرینت {numberFormatter.format(sprint.sequence)}
          </p>
          <h1 id="sprint-detail-title" dir="auto">
            {sprint.title}
          </h1>
        </div>
        <StatusBadge
          className={`sprint-detail__status sprint-detail__status--${view.status.tone}`}
          status={`وضعیت اسپرینت: ${view.status.label}`}
        />
      </header>
      {sprint.brief && (
        <p className="sprint-detail__brief" dir="auto">{sprint.brief}</p>
      )}
      <dl className="sprint-detail__timing">
        <div>
          <dt>شروع برنامه‌ریزی‌شده</dt>
          <dd><DateValue value={sprint.planned_start_at} empty="ثبت نشده" /></dd>
        </div>
        <div>
          <dt>پایان برنامه‌ریزی‌شده اسپرینت</dt>
          <dd><DateValue value={sprint.planned_end_at} empty="ثبت نشده" /></dd>
        </div>
        <div>
          <dt>زمان بازشدن</dt>
          <dd><DateValue value={sprint.opened_at} empty="هنوز باز نشده" /></dd>
        </div>
        <div>
          <dt>زمان تکمیل</dt>
          <dd><DateValue value={sprint.completed_at} empty="هنوز تکمیل نشده" /></dd>
        </div>
      </dl>
    </section>
  )
}

function ProjectRepository({ repositoryUrl }: { repositoryUrl: string | null }) {
  return (
    <section
      className="sprint-detail__repository"
      aria-labelledby="sprint-repository-title"
    >
      <div>
        <p className="sprint-detail__section-kicker">مرجع کد ProjectRun</p>
        <h2 id="sprint-repository-title">مخزن پروژه</h2>
      </div>
      {repositoryUrl ? (
        <a href={repositoryUrl} target="_blank" rel="noreferrer" dir="ltr">
          {repositoryUrl}
        </a>
      ) : (
        <p>مخزن پروژه در حال آماده‌سازی توسط تیم PROLEARN است.</p>
      )}
    </section>
  )
}

function ProjectDesignWorkspace({
  designWorkspaceUrl,
  memberRoleCode,
}: {
  designWorkspaceUrl: string | null
  memberRoleCode: string | null
}) {
  return (
    <section className="sprint-detail__repository" aria-labelledby="sprint-design-title">
      <div>
        <p className="sprint-detail__section-kicker">مرجع طراحی جاری ProjectRun</p>
        <h2 id="sprint-design-title">فضای طراحی پروژه</h2>
      </div>
      {designWorkspaceUrl ? (
        <a href={designWorkspaceUrl} target="_blank" rel="noopener noreferrer" dir="ltr">
          {designWorkspaceUrl}
        </a>
      ) : (
        <p>{missingDesignWorkspaceMessage(memberRoleCode)}</p>
      )}
    </section>
  )
}

function WorkItemMetadata({ item }: { item: ProjectWorkItem }) {
  if (!item.role && !item.technology_stack) return null
  return (
    <dl className="sprint-detail__work-meta">
      {item.role && (
        <div>
          <dt>Role</dt>
          <dd dir="auto">{item.role.name}</dd>
        </div>
      )}
      {item.technology_stack && (
        <div>
          <dt>Stack</dt>
          <dd dir="auto">{item.technology_stack.name}</dd>
        </div>
      )}
    </dl>
  )
}

function WorkItems({ items }: { items: ProjectWorkItem[] }) {
  return (
    <section className="sprint-detail__work" aria-labelledby="sprint-work-title">
      <header>
        <p className="sprint-detail__section-kicker">محتوای قابل‌مشاهده برای عضویت شما</p>
        <h2 id="sprint-work-title">کارهای این اسپرینت</h2>
        <p>این موارد راهنمای ثابت پروژه‌اند و وضعیت انجام یا تکمیل مستقل ندارند.</p>
      </header>
      {items.length ? (
        <div className="sprint-detail__work-list">
          {items.map((item) => (
            <article key={item.id} className="sprint-detail__work-item">
              <h3 dir="auto">{item.title}</h3>
              {item.description && <p dir="auto">{item.description}</p>}
              <WorkItemMetadata item={item} />
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          title="کار قابل‌نمایشی برای این اسپرینت وجود ندارد"
          description="API برای عضویت فعلی شما work itemای برنگردانده است. این وضعیت به‌تنهایی خطای سیستم نیست."
        />
      )}
    </section>
  )
}

function SubmissionItem({ submission }: { submission: SprintSubmissionResponse }) {
  const review = submission.review_decision
  return (
    <li>
      <header>
        <div>
          <strong dir="auto">{submission.submitted_by.user.email}</strong>
          <span dir="auto">{submission.submitted_by.role.name}</span>
        </div>
        <DateValue value={submission.submitted_at} empty="زمان ثبت نشده" />
      </header>
      <dl className="sprint-detail__submission-links">
        {submission.final_commit_url && (
          <div>
            <dt>کامیت نهایی</dt>
            <dd>
              <a href={submission.final_commit_url} target="_blank" rel="noreferrer" dir="ltr">
                {submission.final_commit_url}
              </a>
            </dd>
          </div>
        )}
        {submission.deployment_url && (
          <div>
            <dt>نسخه استقرار</dt>
            <dd>
              <a href={submission.deployment_url} target="_blank" rel="noreferrer" dir="ltr">
                {submission.deployment_url}
              </a>
            </dd>
          </div>
        )}
        {submission.design_url_snapshot && (
          <div>
            <dt>نسخه فضای طراحی</dt>
            <dd>
              <a href={submission.design_url_snapshot} target="_blank" rel="noreferrer" dir="ltr">
                {submission.design_url_snapshot}
              </a>
            </dd>
          </div>
        )}
      </dl>
      <p dir="auto">
        {submission.evidence || 'برای این ارسال توضیح یا مدرکی ثبت نشده است.'}
      </p>
      {review && (
        <section className="sprint-detail__review" aria-label="نتیجه بررسی این ارسال">
          <h4>
            {review.decision === 'CHANGES_REQUESTED'
              ? 'اصلاحات درخواست‌شده'
              : 'ارسال تأیید شد'}
          </h4>
          <p>زمان بررسی: <DateValue value={review.reviewed_at} empty="ثبت نشده" /></p>
          {review.feedback.trim() && <p dir="auto">بازخورد: {review.feedback}</p>}
        </section>
      )}
    </li>
  )
}

function SubmissionHistory({
  latestSubmission,
  historicalSubmissions,
}: {
  latestSubmission: SprintSubmissionResponse | null
  historicalSubmissions: SprintSubmissionResponse[]
}) {
  return (
    <section className="sprint-detail__history" aria-labelledby="sprint-history-title">
      <header>
        <p className="sprint-detail__section-kicker">سابقه ثبت‌شده در SprintRun</p>
        <h2 id="sprint-history-title">ارسال‌ها</h2>
      </header>
      {latestSubmission ? (
        <>
          <div
            className="sprint-detail__latest-submission"
            aria-label="آخرین ارسال ثبت‌شده"
          >
            <h3>آخرین ارسال</h3>
            <ol>
              <SubmissionItem submission={latestSubmission} />
            </ol>
          </div>
          <div className="sprint-detail__previous-submissions">
            <h3>ارسال‌های پیشین</h3>
            {historicalSubmissions.length ? (
              <ol>
                {historicalSubmissions.map((submission) => (
                  <SubmissionItem key={submission.id} submission={submission} />
                ))}
              </ol>
            ) : (
              <p className="sprint-detail__empty-copy">
                ارسال پیشین دیگری برای این اسپرینت ثبت نشده است.
              </p>
            )}
          </div>
        </>
      ) : (
        <p className="sprint-detail__empty-copy">هنوز ارسالی برای این اسپرینت ثبت نشده است.</p>
      )}
    </section>
  )
}

function SubmissionForm({
  action,
  repositoryUrl,
  designWorkspaceUrl,
  pending,
  onSubmit,
}: {
  action: Exclude<SprintDetailAction, null>
  repositoryUrl: string | null
  designWorkspaceUrl: string | null
  pending: boolean
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}) {
  const isResubmission = action === 'resubmit'
  const isUpdate = action === 'update'
  const missingPrerequisite = !repositoryUrl || !designWorkspaceUrl
  return (
    <Card className="sprint-detail__submission">
      <form onSubmit={onSubmit} aria-busy={pending} noValidate>
        <div>
          <p className="sprint-detail__section-kicker">اقدام عضو تیم</p>
          <h2>
            {isResubmission
              ? 'ارسال مجدد اسپرینت'
              : isUpdate
                ? 'به‌روزرسانی ارسال'
                : 'ارسال اسپرینت'}
          </h2>
          <p>
            هویت ارسال‌کننده از نشست شما تعیین می‌شود. متن مدرک اختیاری است و هیچ شناسه یا زمان‌بندی‌ای از مرورگر ارسال نمی‌شود.
          </p>
          {isUpdate && <p>به‌روزرسانی، یک ارسال جدید می‌سازد و ارسال‌های قبلی را تغییر نمی‌دهد.</p>}
        </div>
        <p className="sprint-detail__submission-context">
          کامیت باید از مخزن همین ProjectRun باشد. Snapshot طراحی هنگام ثبت از فضای طراحی جاری پروژه توسط سرور گرفته می‌شود.
        </p>
        {!repositoryUrl && <Alert tone="info">مخزن رسمی پروژه هنوز توسط تیم PROLEARN تنظیم نشده است. پس از آماده‌شدن آن می‌توانید مدارک اسپرینت را ارسال کنید.</Alert>}
        {!designWorkspaceUrl && <Alert tone="info">ارسال مدارک تا ثبت فضای طراحی پروژه غیرفعال است.</Alert>}
        {!designWorkspaceUrl && <Link to="/workspace">بررسی فضای طراحی در Workspace</Link>}
        <label htmlFor="sprint-final-commit">آدرس کامیت نهایی</label>
        <input
          id="sprint-final-commit"
          name="final_commit_url"
          type="url"
          placeholder="https://github.com/org/repository/commit/..."
          required
          maxLength={500}
          disabled={pending}
          dir="ltr"
        />
        <label htmlFor="sprint-deployment">آدرس نسخه استقرار</label>
        <input
          id="sprint-deployment"
          name="deployment_url"
          type="url"
          placeholder="https://project.example.com"
          required
          maxLength={500}
          disabled={pending}
          dir="ltr"
        />
        <label htmlFor="sprint-evidence">یادداشت اختیاری</label>
        <textarea
          id="sprint-evidence"
          name="evidence"
          placeholder="در صورت نیاز، توضیح کوتاهی برای این ارسال بنویسید"
          rows={5}
          disabled={pending}
          dir="auto"
        />
        <Button type="submit" disabled={pending || missingPrerequisite}>
          {pending
            ? 'در حال ثبت...'
            : isResubmission
              ? 'ثبت ارسال مجدد'
              : isUpdate
                ? 'ثبت نسخه جدیدتر'
                : 'ثبت ارسال اسپرینت'}
        </Button>
      </form>
    </Card>
  )
}

function SprintDetailContent({
  data,
  pending,
  submissionError,
  submissionSuccess,
  designWorkspaceRole,
  onSubmit,
}: {
  data: SprintRunDetailResponse
  pending: boolean
  submissionError: string | null
  submissionSuccess: string | null
  designWorkspaceRole: string | null
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}) {
  const view = useMemo(() => buildSprintDetailViewModel(data), [data])
  return (
    <div className="sprint-detail-page" dir="rtl">
      <SprintHeader view={view} />
      <Alert
        className={`sprint-detail__notice sprint-detail__notice--${view.status.tone}`}
        tone={view.status.tone === 'danger' ? 'error' : 'info'}
        role="status"
      >
        {view.notice}
      </Alert>
      <ProjectRepository repositoryUrl={view.sprint.repository_url} />
      <ProjectDesignWorkspace
        designWorkspaceUrl={view.sprint.design_workspace_url}
        memberRoleCode={designWorkspaceRole}
      />
      <WorkItems items={view.workItems} />
      <SubmissionHistory
        latestSubmission={view.latestSubmission}
        historicalSubmissions={view.historicalSubmissions}
      />
      {view.currentChangesDecision && (
        <section
          className="sprint-detail__current-feedback"
          aria-label="بازخورد اصلاحات جاری"
        >
          <h2>اصلاحات درخواست‌شده</h2>
          <p dir="auto">{view.currentChangesDecision.feedback}</p>
          <p>پس از انجام اصلاحات، نسخه جدید را با فرم ارسال مجدد ثبت کنید.</p>
        </section>
      )}
      {submissionError && <Alert tone="error">{submissionError}</Alert>}
      {submissionSuccess && (
        <Alert tone="success" role="status">{submissionSuccess}</Alert>
      )}
      {view.action && (
        <SubmissionForm
          key={view.sprint.id}
          action={view.action}
          repositoryUrl={view.sprint.repository_url}
          designWorkspaceUrl={view.sprint.design_workspace_url}
          pending={pending}
          onSubmit={onSubmit}
        />
      )}
      <nav className="sprint-detail__navigation" aria-label="ناوبری SprintRun">
        <Link to="/workspace">بازگشت به Workspace</Link>
        <Link to="/dashboard">مشاهده Dashboard</Link>
      </nav>
    </div>
  )
}

export function SprintDetailPage() {
  const auth = useAuth()
  const { sprintRunId } = useParams<{ sprintRunId: string }>()
  const [loadState, setLoadState] = useState<LoadState>({
    status: 'loading',
    requestedId: sprintRunId ?? null,
  })
  const [reloadKey, setReloadKey] = useState(0)
  const [submissionPending, setSubmissionPending] = useState(false)
  const [submissionError, setSubmissionError] = useState<string | null>(null)
  const [submissionSuccess, setSubmissionSuccess] = useState<string | null>(null)
  const [designWorkspaceRoleContext, setDesignWorkspaceRoleContext] = useState<{
    sprintRunId: string
    code: string
  } | null>(null)
  const submissionPendingRef = useRef(false)
  const submissionControllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!sprintRunId) return
    const controller = new AbortController()

    void loadSprintDetail(sprintRunId, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setLoadState({ status: 'success', requestedId: sprintRunId, data })
        }
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof ApiError && error.status === 404) {
          setLoadState({ status: 'not-found', requestedId: sprintRunId })
        } else {
          setLoadState({ status: 'error', requestedId: sprintRunId, error })
        }
        if (isMissingSession(error)) void auth.refreshSession()
      })

    return () => controller.abort()
  }, [auth, reloadKey, sprintRunId])

  useEffect(() => () => submissionControllerRef.current?.abort(), [])

  const needsDesignWorkspaceRole =
    loadState.status === 'success' &&
    loadState.requestedId === sprintRunId &&
    loadState.data.design_workspace_url === null

  useEffect(() => {
    if (!needsDesignWorkspaceRole || !sprintRunId) return
    const controller = new AbortController()
    void loadWorkspace(controller.signal)
      .then((workspace) => {
        if (!controller.signal.aborted && workspace?.sprints.some((item) => item.id === sprintRunId)) {
          setDesignWorkspaceRoleContext({
            sprintRunId,
            code: workspace.membership.role.code,
          })
        }
      })
      .catch(() => {
        // Sprint Detail remains readable if supplemental Workspace context is unavailable.
      })
    return () => controller.abort()
  }, [needsDesignWorkspaceRole, sprintRunId])

  const designWorkspaceRole =
    designWorkspaceRoleContext && designWorkspaceRoleContext.sprintRunId === sprintRunId
      ? designWorkspaceRoleContext.code
      : null

  function retry() {
    setSubmissionError(null)
    setSubmissionSuccess(null)
    setLoadState({ status: 'loading', requestedId: sprintRunId ?? null })
    setReloadKey((current) => current + 1)
  }

  async function revalidateAfterAction(signal: AbortSignal) {
    if (!sprintRunId) return
    try {
      const data = await loadSprintDetail(sprintRunId, signal)
      if (!signal.aborted) {
        setLoadState({ status: 'success', requestedId: sprintRunId, data })
      }
    } catch (error) {
      if (signal.aborted) return
      if (error instanceof ApiError && error.status === 404) {
        setLoadState({ status: 'not-found', requestedId: sprintRunId })
      } else if (isMissingSession(error)) {
        setLoadState({ status: 'error', requestedId: sprintRunId, error })
        void auth.refreshSession()
      }
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!sprintRunId || submissionPendingRef.current || loadState.status !== 'success') return
    if (!buildSprintDetailViewModel(loadState.data).action) return
    if (!loadState.data.repository_url || !loadState.data.design_workspace_url) return
    const form = event.currentTarget
    const fields = new FormData(form)
    const normalizedCommitUrl = String(fields.get('final_commit_url') ?? '').trim()
    const normalizedDeploymentUrl = String(fields.get('deployment_url') ?? '').trim()
    const evidence = String(fields.get('evidence') ?? '')
    const fieldError = submissionFieldError(normalizedCommitUrl, normalizedDeploymentUrl)
    if (fieldError) {
      setSubmissionError(fieldError)
      return
    }
    submissionPendingRef.current = true
    setSubmissionPending(true)
    setSubmissionError(null)
    setSubmissionSuccess(null)
    const controller = new AbortController()
    submissionControllerRef.current = controller
    const action =
      loadState.status === 'success'
        ? buildSprintDetailViewModel(loadState.data).action
        : null

    try {
      await submitSprintEvidence({
        sprintRunId,
        finalCommitUrl: normalizedCommitUrl,
        deploymentUrl: normalizedDeploymentUrl,
        evidence,
        signal: controller.signal,
      })
      const refreshed = await loadSprintDetail(sprintRunId, controller.signal)
      if (controller.signal.aborted) return
      form.reset()
      setLoadState({ status: 'success', requestedId: sprintRunId, data: refreshed })
      setSubmissionSuccess(
        action === 'resubmit'
          ? 'ارسال مجدد ثبت شد و وضعیت تازه از سرور دریافت شد.'
          : action === 'update'
            ? 'نسخه جدیدتر ثبت شد و سابقه تازه از سرور دریافت شد.'
            : 'ارسال اسپرینت ثبت شد و وضعیت تازه از سرور دریافت شد.',
      )
    } catch (error) {
      if (controller.signal.aborted) return
      setSubmissionError(submissionErrorMessage(error, designWorkspaceRole))
      if (
        error instanceof ApiError &&
        [403, 404, 409].includes(error.status)
      ) {
        await revalidateAfterAction(controller.signal)
      }
      if (isMissingSession(error)) void auth.refreshSession()
    } finally {
      if (!controller.signal.aborted) {
        submissionPendingRef.current = false
        setSubmissionPending(false)
      }
      if (submissionControllerRef.current === controller) {
        submissionControllerRef.current = null
      }
    }
  }

  if (!sprintRunId) {
    return (
      <div className="sprint-detail-page sprint-detail__page-state" dir="rtl">
        <EmptyState
          title="شناسه اسپرینت مشخص نیست"
          description="برای مشاهده جزئیات، یک SprintRun معتبر را از Workspace انتخاب کنید."
        />
        <Link to="/workspace">بازگشت به Workspace</Link>
      </div>
    )
  }

  if (
    loadState.requestedId !== sprintRunId
  ) {
    return (
      <div className="sprint-detail-page sprint-detail__page-state" dir="rtl" aria-busy="true">
        <LoadingState message="در حال دریافت جزئیات اسپرینت از سرور..." />
      </div>
    )
  }

  if (loadState.status === 'loading') {
    return (
      <div className="sprint-detail-page sprint-detail__page-state" dir="rtl" aria-busy="true">
        <LoadingState message="در حال دریافت جزئیات اسپرینت از سرور..." />
      </div>
    )
  }

  if (loadState.status === 'not-found') {
    return (
      <div className="sprint-detail-page sprint-detail__page-state" dir="rtl">
        <EmptyState
          title="اسپرینت قابل دسترسی نیست"
          description="این شناسه به اسپرینت قابل‌مشاهده‌ای در ProjectRun جاری شما تعلق ندارد."
        />
        <div className="sprint-detail__state-actions">
          <Link to="/workspace">بازگشت به Workspace</Link>
          <Button variant="secondary" onClick={retry}>بررسی دوباره</Button>
        </div>
      </div>
    )
  }

  if (loadState.status === 'error') {
    return (
      <div className="sprint-detail-page sprint-detail__page-state" dir="rtl">
        <Alert tone="error">
          <h1>دریافت جزئیات اسپرینت ممکن نشد</h1>
          <p>{sprintDetailErrorMessage(loadState.error)}</p>
        </Alert>
        <div className="sprint-detail__state-actions">
          <Button variant="secondary" onClick={retry}>تلاش دوباره</Button>
          <Link to="/workspace">بازگشت به Workspace</Link>
        </div>
      </div>
    )
  }

  return (
    <SprintDetailContent
      data={loadState.data}
      pending={submissionPending}
      submissionError={submissionError}
      submissionSuccess={submissionSuccess}
      designWorkspaceRole={designWorkspaceRole}
      onSubmit={handleSubmit}
    />
  )
}
