import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
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
  confirmReadyCheck,
  declineReadyCheck,
  loadReadyCheckPageData,
  type ReadyCheckPageData,
} from '../lib/api/readyCheck'
import type {
  ProjectVersionDetailResponse,
  ReadyCheckResponse,
  ReadyCheckStatus,
} from '../lib/api/types'
import '../styles/ready-check.css'

type LoadState =
  | { status: 'loading' }
  | { status: 'success'; data: ReadyCheckPageData }
  | { status: 'error'; error: Error }

type ReadyCheckAction = 'confirm' | 'decline'

const GITHUB_USERNAME_PATTERN = /^(?=.{1,39}$)[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$/

const numberFormatter = new Intl.NumberFormat('fa-IR', { useGrouping: false })
const paddedNumberFormatter = new Intl.NumberFormat('fa-IR', {
  minimumIntegerDigits: 2,
  useGrouping: false,
})
const deadlineFormatter = new Intl.DateTimeFormat('fa-IR', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

const statusCopy: Record<
  ReadyCheckStatus,
  { label: string; description: string }
> = {
  PENDING: {
    label: 'در انتظار پاسخ',
    description: 'هنوز تصمیمی برای این دعوت ثبت نشده است.',
  },
  CONFIRMED: {
    label: 'تأیید شده',
    description: 'آمادگی شما برای حضور در این پروژه ثبت شده است.',
  },
  DECLINED: {
    label: 'رد شده',
    description: 'رد مشارکت شما برای این دعوت ثبت شده است.',
  },
  EXPIRED: {
    label: 'مهلت تمام شده',
    description: 'بازه پاسخ این Ready Check به پایان رسیده است.',
  },
}

function asError(error: unknown) {
  return error instanceof Error
    ? error
    : new Error('دریافت Ready Check ممکن نشد.')
}

function readyCheckErrorMessage(error: unknown) {
  if (!(error instanceof ApiError)) {
    return 'ارتباط با سرور برقرار نشد. اتصال اینترنت را بررسی و دوباره تلاش کنید.'
  }

  const payload = JSON.stringify(error.data ?? '')
  if (error.status === 401) {
    return 'نشست شما پایان یافته است. دوباره وارد شوید.'
  }
  if (error.status === 403) {
    return /csrf|<!DOCTYPE|<html/i.test(payload)
      ? 'اعتبار امنیتی درخواست تأیید نشد. دوباره تلاش کنید.'
      : 'اجازه دسترسی به این Ready Check را ندارید.'
  }
  if (error.status === 404) {
    return 'این Ready Check برای حساب شما پیدا نشد یا دیگر جاری نیست.'
  }
  if (payload.includes('This Ready Check has expired.')) {
    return 'مهلت پاسخ این Ready Check به پایان رسیده است. وضعیت از سرور دوباره بررسی می‌شود.'
  }
  if (payload.includes('This Ready Check is no longer pending.')) {
    return 'این Ready Check قبلاً پاسخ داده شده یا دیگر در انتظار پاسخ نیست.'
  }
  if (payload.includes('GitHub username')) {
    return 'برای تأیید این نقش، نام کاربری معتبر GitHub لازم است.'
  }
  if (payload.includes('active project run')) {
    return 'به‌دلیل وجود یک پروژه فعال، این تصمیم اکنون قابل ثبت نیست.'
  }
  if (error.status === 409) {
    return 'وضعیت تشکیل تیم هم‌زمان تغییر کرده است. وضعیت تازه را بررسی و دوباره اقدام کنید.'
  }
  if (error.status === 400) {
    return 'این اقدام با وضعیت فعلی Ready Check قابل انجام نیست.'
  }
  return 'سرور اکنون نمی‌تواند این درخواست را انجام دهد. دوباره تلاش کنید.'
}

function readyCheckLoadErrorMessage(error: Error) {
  if (!(error instanceof ApiError)) {
    return 'ارتباط با سرور برقرار نشد. اتصال اینترنت را بررسی و دوباره تلاش کنید.'
  }
  if (error.status === 401) return 'نشست شما پایان یافته است. دوباره وارد شوید.'
  if (error.status === 403) return 'اجازه مشاهده این Ready Check را ندارید.'
  if (error.status === 404) {
    return 'نسخه پروژه مرتبط با این Ready Check در دسترس نیست.'
  }
  return 'دریافت وضعیت Ready Check از سرور ممکن نشد. دوباره تلاش کنید.'
}

function formatRemaining(expiresAt: string, now: number) {
  const remainingMinutes = Math.max(
    0,
    Math.ceil((Date.parse(expiresAt) - now) / 60_000),
  )
  const hours = Math.floor(remainingMinutes / 60)
  const minutes = remainingMinutes % 60
  return `${numberFormatter.format(hours)} ساعت و ${paddedNumberFormatter.format(minutes)} دقیقه`
}

function useCountdownNow(expiresAt: string) {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 1_000)
    return () => window.clearInterval(interval)
  }, [expiresAt])

  return now
}

function Countdown({ readyCheck }: { readyCheck: ReadyCheckResponse }) {
  const now = useCountdownNow(readyCheck.expires_at)
  const startedAt = Date.parse(readyCheck.started_at)
  const expiresAt = Date.parse(readyCheck.expires_at)
  const duration = Math.max(1, expiresAt - startedAt)
  const progress = Math.min(
    100,
    Math.max(0, ((now - startedAt) / duration) * 100),
  )
  const remaining = formatRemaining(readyCheck.expires_at, now)

  return (
    <Card className="ready-check__countdown">
      <div className="ready-check__countdown-heading">
        <div>
          <span>زمان باقی‌مانده برای پاسخ</span>
          <strong data-testid="ready-check-countdown">{remaining}</strong>
        </div>
        <StatusBadge
          className={`ready-check__status ready-check__status--${readyCheck.effective_status.toLowerCase()}`}
          status={statusCopy[readyCheck.effective_status].label}
        />
      </div>
      <progress
        aria-label="میزان سپری‌شدن بازه پاسخ"
        max={100}
        value={progress}
      />
      <div className="ready-check__deadline-row">
        <span>مهلت ثبت‌شده در سرور</span>
        <time dateTime={readyCheck.expires_at}>
          {deadlineFormatter.format(new Date(readyCheck.expires_at))}
        </time>
      </div>
      <p>
        این شمارش فقط برای نمایش است؛ وضعیت و امکان ثبت پاسخ را سرور تعیین می‌کند.
      </p>
    </Card>
  )
}

function ProjectSummary({
  project,
  readyCheck,
}: {
  project: ProjectVersionDetailResponse
  readyCheck: ReadyCheckResponse
}) {
  return (
    <Card className="ready-check__project-card">
      <header>
        <span className="ready-check__section-index" aria-hidden="true">
          ۰۱
        </span>
        <div>
          <p>خلاصه پروژه</p>
          <h2 dir="auto">{project.project_template.name}</h2>
        </div>
      </header>
      <p className="ready-check__project-summary" dir="auto">
        {project.summary}
      </p>
      <dl className="ready-check__facts">
        <div>
          <dt>نسخه دقیق</dt>
          <dd>{numberFormatter.format(project.version_number)}</dd>
        </div>
        <div>
          <dt>سطح</dt>
          <dd dir="auto">{project.project_template.level.name}</dd>
        </div>
        <div>
          <dt>مدت پروژه</dt>
          <dd>
            {project.duration_weeks === null
              ? 'در دسترس نیست'
              : `${numberFormatter.format(project.duration_weeks)} هفته`}
          </dd>
        </div>
        <div>
          <dt>تعداد Sprint</dt>
          <dd>
            {project.sprint_count === null
              ? 'در دسترس نیست'
              : numberFormatter.format(project.sprint_count)}
          </dd>
        </div>
        <div>
          <dt>نقش شما</dt>
          <dd dir="auto">{readyCheck.role.name}</dd>
        </div>
        <div>
          <dt>Stack شما</dt>
          <dd dir="auto">
            {readyCheck.technology_stack?.name ?? 'برای این نقش نیاز نیست'}
          </dd>
        </div>
      </dl>
    </Card>
  )
}

function TeamStatus({
  projectRunState,
  readyCheck,
}: {
  projectRunState: string | null
  readyCheck: ReadyCheckResponse
}) {
  const effective = readyCheck.effective_status
  return (
    <section className="ready-check__team" aria-labelledby="team-status-title">
      <div className="ready-check__section-heading">
        <span className="ready-check__section-index" aria-hidden="true">
          ۰۲
        </span>
        <div>
          <p>وضعیت تیم</p>
          <h2 id="team-status-title">پاسخ اعضا</h2>
        </div>
      </div>

      <div className="ready-check__member-row">
        <div>
          <span className="ready-check__you-label">شما</span>
          <strong dir="auto">{readyCheck.user.email}</strong>
          <small dir="auto">{readyCheck.role.name}</small>
        </div>
        <StatusBadge
          className={`ready-check__status ready-check__status--${effective.toLowerCase()}`}
          status={statusCopy[effective].label}
        />
      </div>

      {projectRunState ? (
        <div className="ready-check__team-started" role="status">
          <strong>هر سه عضو تأیید کرده‌اند.</strong>
          <span>
            ProjectRun با وضعیت {projectRunState} در سرور ایجاد شده است.
          </span>
        </div>
      ) : (
        <div className="ready-check__team-fallback">
          <strong>وضعیت سایر اعضا</strong>
          <p>اطلاعات این بخش فعلاً در دسترس نیست.</p>
        </div>
      )}
    </section>
  )
}

function weeklyEffort(project: ProjectVersionDetailResponse) {
  const minimum = project.weekly_effort_hours_min
  const maximum = project.weekly_effort_hours_max
  if (minimum === null || maximum === null) {
    return 'در اطلاعات این نسخه درج نشده است'
  }
  if (minimum === maximum) {
    return `${numberFormatter.format(minimum)} ساعت در هفته`
  }
  return `${numberFormatter.format(minimum)} تا ${numberFormatter.format(maximum)} ساعت در هفته`
}

function sprintCadence(project: ProjectVersionDetailResponse) {
  const durations = project.sprint_templates.map(
    (sprint) => sprint.planned_duration_days,
  )
  if (
    durations.length > 0 &&
    durations.every((duration) => duration === durations[0])
  ) {
    return `هر Sprint، ${numberFormatter.format(durations[0])} روز`
  }
  return 'طبق برنامه ثبت‌شده همین نسخه پروژه'
}

function DecisionPanel({
  action,
  actionError,
  canAct,
  onCancelDecline,
  onConfirm,
  onDecline,
  onRequestDecline,
  githubUsername,
  onGithubUsernameChange,
  projectRunState,
  readyCheck,
  showDeclineConfirmation,
}: {
  action: ReadyCheckAction | null
  actionError: string
  canAct: boolean
  onCancelDecline: () => void
  onConfirm: () => void
  onDecline: () => void
  onRequestDecline: () => void
  githubUsername: string
  onGithubUsernameChange: (value: string) => void
  projectRunState: string | null
  readyCheck: ReadyCheckResponse
  showDeclineConfirmation: boolean
}) {
  const status = readyCheck.effective_status
  const copy = statusCopy[status]
  const githubRequired =
    readyCheck.role.code === 'BACKEND_DEVELOPER' ||
    readyCheck.role.code === 'FRONTEND_DEVELOPER'
  const trimmedGithubUsername = githubUsername.trim()
  const githubValid =
    (!githubRequired && trimmedGithubUsername === '') ||
    GITHUB_USERNAME_PATTERN.test(trimmedGithubUsername)

  if (projectRunState) {
    return (
      <section className="ready-check__decision ready-check__decision--complete">
        <StatusBadge
          className="ready-check__status ready-check__status--confirmed"
          status={`ProjectRun · ${projectRunState}`}
        />
        <h2>پروژه شروع شده است</h2>
        <p>
          تأیید هر سه عضو ثبت شده و ProjectRun از همان زمان آغاز شده است. مقصد کامل پس از Ready Check هنوز در رابط کاربری این فاز آماده نیست.
        </p>
      </section>
    )
  }

  if (status !== 'PENDING') {
    return (
      <section
        className={`ready-check__decision ready-check__decision--${status.toLowerCase()}`}
      >
        <StatusBadge
          className={`ready-check__status ready-check__status--${status.toLowerCase()}`}
          status={copy.label}
        />
        <h2>{status === 'CONFIRMED' ? 'تأیید شما ثبت شد' : copy.label}</h2>
        <p>
          {status === 'CONFIRMED'
            ? 'منتظر پاسخ سایر اعضای تیم هستیم. اگر همه زودتر تأیید کنند، پروژه همان زمان شروع می‌شود.'
            : copy.description}
        </p>
        {status === 'EXPIRED' ? (
          <div
            className="ready-check__closed-actions"
            aria-label="اقدام‌ها غیرفعال هستند"
          >
            <Button disabled>تأیید مشارکت</Button>
            <Button variant="danger" disabled>
              رد مشارکت
            </Button>
          </div>
        ) : null}
      </section>
    )
  }

  return (
    <section className="ready-check__decision" aria-labelledby="decision-title">
      <div>
        <p className="ready-check__decision-label">تصمیم شما</p>
        <h2 id="decision-title">برای این پروژه آماده‌اید؟</h2>
        <p>
          تأیید، آمادگی شما برای مشارکت با نقش و Stack ثبت‌شده بالاست. رد کردن فقط همین جایگاه را برای جایگزینی آزاد می‌کند.
        </p>
      </div>

      <div className="ready-check__github-field">
        <label htmlFor="ready-check-github-username">
          نام کاربری GitHub
          <span>{githubRequired ? 'ضروری' : 'اختیاری'}</span>
        </label>
        <input
          id="ready-check-github-username"
          name="github_username"
          type="text"
          dir="ltr"
          autoComplete="username"
          maxLength={39}
          required={githubRequired}
          value={githubUsername}
          onChange={(event) => onGithubUsernameChange(event.target.value)}
          aria-describedby="ready-check-github-help ready-check-github-warning"
          aria-invalid={!githubValid}
          disabled={action !== null}
          placeholder="octocat"
        />
        <p id="ready-check-github-help">
          برای دسترسی به مخزن خصوصی پروژه؛ فقط نام کاربری را وارد کنید، نه URL یا @.
        </p>
        {!githubValid ? (
          <p className="ready-check__github-error" role="alert">
            نام کاربری باید ۱ تا ۳۹ نویسه و شامل حروف انگلیسی، عدد یا خط تیره تکی باشد.
          </p>
        ) : null}
        <p id="ready-check-github-warning" className="ready-check__github-warning">
          حساب GitHub مورد استفاده در پروژه فعال را بدون هماهنگی با Staff/پشتیبانی PROLEARN تغییر ندهید؛ تغییر این مقدار دسترسی GitHub را منتقل نمی‌کند.
        </p>
      </div>

      {actionError ? (
        <Alert className="ready-check__action-error" tone="error">
          {actionError}
        </Alert>
      ) : null}

      {showDeclineConfirmation ? (
        <div
          className="ready-check__decline-confirmation"
          role="group"
          aria-labelledby="decline-confirmation-title"
        >
          <div>
            <strong id="decline-confirmation-title">
              رد مشارکت را ثبت می‌کنید؟
            </strong>
            <p>با رد Ready Check، از Formation جاری کنار می‌روید و تیم می‌تواند جایگاه نقش شما را جایگزین کند. این تصمیم در این صفحه قابل بازگردانی نیست؛ هنوز ProjectRun فعالی شروع نشده است.</p>
          </div>
          <div>
            <Button
              autoFocus
              variant="danger"
              onClick={onDecline}
              disabled={!canAct}
            >
              {action === 'decline' ? 'در حال ثبت...' : 'بله، رد می‌کنم'}
            </Button>
            <Button
              variant="secondary"
              onClick={onCancelDecline}
              disabled={action !== null}
            >
              بازگشت
            </Button>
          </div>
        </div>
      ) : (
        <div className="ready-check__actions">
          <Button
            className="ready-check__confirm-button"
            onClick={onConfirm}
            disabled={!canAct || !githubValid}
            aria-busy={action === 'confirm'}
          >
            {action === 'confirm' ? 'در حال ثبت تأیید...' : 'تأیید مشارکت'}
          </Button>
          <Button
            className="ready-check__decline-button"
            variant="danger"
            onClick={onRequestDecline}
            disabled={!canAct}
          >
            رد مشارکت
          </Button>
        </div>
      )}
    </section>
  )
}

export function ReadyCheckPage() {
  const auth = useAuth()
  const [loadState, setLoadState] = useState<LoadState>({ status: 'loading' })
  const [reloadKey, setReloadKey] = useState(0)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshError, setRefreshError] = useState('')
  const [action, setAction] = useState<ReadyCheckAction | null>(null)
  const [actionError, setActionError] = useState('')
  const [showDeclineConfirmation, setShowDeclineConfirmation] = useState(false)
  const [githubUsername, setGithubUsername] = useState('')
  const hasLoadedRef = useRef(false)
  const actionRef = useRef<ReadyCheckAction | null>(null)
  const revalidatedExpiryRef = useRef<string | null>(null)
  const githubReadyCheckRef = useRef<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    const isBackgroundRefresh = hasLoadedRef.current
    if (isBackgroundRefresh) setRefreshing(true)

    void loadReadyCheckPageData(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return
        const loadedReadyCheck =
          data.readyChecks.length === 1 ? data.readyChecks[0] : null
        if (loadedReadyCheck?.id !== githubReadyCheckRef.current) {
          githubReadyCheckRef.current = loadedReadyCheck?.id ?? null
          setGithubUsername(loadedReadyCheck?.github_username ?? '')
        }
        hasLoadedRef.current = true
        setLoadState({ status: 'success', data })
        setRefreshError('')
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        const normalized = asError(error)
        if (isBackgroundRefresh) {
          setRefreshError(readyCheckLoadErrorMessage(normalized))
        } else {
          setLoadState({ status: 'error', error: normalized })
        }
        if (isMissingSession(error)) void auth.refreshSession()
      })
      .finally(() => {
        if (!controller.signal.aborted) setRefreshing(false)
      })

    return () => controller.abort()
  }, [auth, reloadKey])

  const revalidate = useCallback(() => {
    if (hasLoadedRef.current) setRefreshing(true)
    setReloadKey((current) => current + 1)
  }, [])

  const data = loadState.status === 'success' ? loadState.data : null
  const readyCheck = data?.readyChecks.length === 1 ? data.readyChecks[0] : null

  useEffect(() => {
    if (!readyCheck || readyCheck.effective_status !== 'PENDING') return
    if (revalidatedExpiryRef.current === readyCheck.expires_at) return

    const refreshAtExpiry = () => {
      revalidatedExpiryRef.current = readyCheck.expires_at
      revalidate()
    }
    const delay = Date.parse(readyCheck.expires_at) - Date.now()
    if (delay <= 0) {
      refreshAtExpiry()
      return
    }
    const timeout = window.setTimeout(refreshAtExpiry, delay + 50)
    return () => window.clearTimeout(timeout)
  }, [readyCheck, revalidate])

  useEffect(() => {
    if (
      !readyCheck ||
      readyCheck.effective_status !== 'CONFIRMED' ||
      data?.projectRun
    ) {
      return
    }
    const interval = window.setInterval(revalidate, 30_000)
    return () => window.clearInterval(interval)
  }, [data?.projectRun, readyCheck, revalidate])

  function applyAuthoritativeResponse(response: ReadyCheckResponse) {
    setGithubUsername(response.github_username ?? '')
    setLoadState((current) => {
      if (current.status !== 'success') return current
      return {
        status: 'success',
        data: {
          ...current.data,
          readyChecks: current.data.readyChecks.map((item) =>
            item.id === response.id ? response : item,
          ),
        },
      }
    })
  }

  async function performAction(nextAction: ReadyCheckAction) {
    if (
      !readyCheck ||
      readyCheck.effective_status !== 'PENDING' ||
      actionRef.current ||
      refreshing
    ) {
      return
    }

    actionRef.current = nextAction
    setAction(nextAction)
    setActionError('')
    try {
      const response = await (nextAction === 'confirm'
        ? confirmReadyCheck(
            readyCheck.id,
            githubUsername.trim() &&
              githubUsername.trim() !== readyCheck.github_username
              ? githubUsername.trim()
              : undefined,
          )
        : declineReadyCheck(readyCheck.id))
      applyAuthoritativeResponse(response)
      setShowDeclineConfirmation(false)
      revalidate()
    } catch (error: unknown) {
      setActionError(readyCheckErrorMessage(error))
      if (isMissingSession(error)) void auth.refreshSession()
      if (
        error instanceof ApiError &&
        [400, 404, 409].includes(error.status)
      ) {
        revalidate()
      }
    } finally {
      actionRef.current = null
      setAction(null)
    }
  }

  if (loadState.status === 'loading') {
    return (
      <div
        className="ready-check-page ready-check__state"
        dir="rtl"
        aria-busy="true"
      >
        <LoadingState message="در حال دریافت Ready Check از سرور..." />
      </div>
    )
  }

  if (loadState.status === 'error') {
    return (
      <div className="ready-check-page ready-check__state" dir="rtl">
        <Alert tone="error">
          <h1>دریافت Ready Check ممکن نشد</h1>
          <p>{readyCheckLoadErrorMessage(loadState.error)}</p>
        </Alert>
        <Button
          variant="secondary"
          onClick={() => {
            hasLoadedRef.current = false
            setLoadState({ status: 'loading' })
            revalidate()
          }}
        >
          تلاش دوباره
        </Button>
      </div>
    )
  }

  if (loadState.data.readyChecks.length === 0) {
    const run = loadState.data.projectRun
    return (
      <div className="ready-check-page ready-check__state" dir="rtl">
        {run ? (
          <Alert tone="success">
            <h1>پروژه شروع شده است</h1>
            <p dir="auto">
              ProjectRun پروژه «{run.project.name}» با وضعیت {run.state} در سرور ثبت شده است.
            </p>
          </Alert>
        ) : (
          <EmptyState
            title="Ready Check فعالی وجود ندارد"
            description="در حال حاضر دعوت جاری‌ای برای این حساب ثبت نشده است."
          />
        )}
      </div>
    )
  }

  if (
    loadState.data.readyChecks.length !== 1 ||
    !loadState.data.projectVersion
  ) {
    return (
      <div className="ready-check-page ready-check__state" dir="rtl">
        <Alert tone="error">
          <h1>وضعیت Ready Check قابل نمایش نیست</h1>
          <p>
            اطلاعات جاری این حساب با قرارداد مورد انتظار سازگار نیست. هیچ اقدامی ثبت نشد.
          </p>
        </Alert>
        <Button variant="secondary" onClick={revalidate} disabled={refreshing}>
          {refreshing ? 'در حال بررسی...' : 'بررسی دوباره'}
        </Button>
      </div>
    )
  }

  const currentReadyCheck = loadState.data.readyChecks[0]
  const project = loadState.data.projectVersion
  const projectRun = loadState.data.projectRun
  const projectRunMatches =
    projectRun?.project.version_id === currentReadyCheck.project_version_id
  const invalidRunState = Boolean(projectRun && !projectRunMatches)
  const projectStarted = Boolean(projectRun && projectRunMatches)
  const canAct =
    currentReadyCheck.is_current &&
    currentReadyCheck.effective_status === 'PENDING' &&
    !invalidRunState &&
    !refreshing &&
    action === null

  return (
    <div className="ready-check-page" dir="rtl">
      <div className="ready-check__layout">
        <section
          className="ready-check__main"
          aria-labelledby="ready-check-title"
        >
          <header className="ready-check__intro">
            <p className="ready-check__eyebrow" dir="ltr">
              PROLEARN · READY CHECK
            </p>
            <h1 id="ready-check-title">تأیید نهایی پیش از شروع پروژه</h1>
            <p>
              برای اعلام آمادگی تا ۴۸ ساعت فرصت دارید. این زمان حداکثر مهلت پاسخ است؛ اگر هر سه عضو زودتر تأیید کنند، پروژه همان زمان شروع می‌شود.
            </p>
          </header>

          <Countdown readyCheck={currentReadyCheck} />

          <section
            className="ready-check__meaning"
            aria-labelledby="confirmation-meaning-title"
          >
            <div className="ready-check__section-heading">
              <span className="ready-check__section-index" aria-hidden="true">
                ۰۳
              </span>
              <div>
                <p>پیش از تصمیم</p>
                <h2 id="confirmation-meaning-title">
                  تأیید مشارکت یعنی چه؟
                </h2>
              </div>
            </div>
            <ul>
              <li>
                آمادگی برای همکاری در همین نسخه پروژه با نقش و Stack ثبت‌شده
              </li>
              <li>زمان مورد انتظار: {weeklyEffort(project)}</li>
              <li>ریتم پروژه: {sprintCadence(project)}</li>
              <li>
                بررسی Sprintها در MVP دستی است؛ انتظار عملیاتی حدود ۸ ساعت است، تضمین زمانی نیست و به مهلت پروژه اضافه نمی‌شود.
              </li>
            </ul>
          </section>

          <section className="ready-check__next" aria-labelledby="next-title">
            <span className="ready-check__next-line" aria-hidden="true" />
            <div>
              <p>بعد از تأیید چه می‌شود؟</p>
              <h2 id="next-title">شروع به محض آماده‌بودن همه</h2>
              <p>
                وقتی هر سه عضو تأیید کنند، Team و ProjectRun همان لحظه در سرور ساخته می‌شوند؛ لازم نیست تا پایان ۴۸ ساعت صبر کنید.
              </p>
            </div>
          </section>

          <section
            className="ready-check__decline-note"
            aria-labelledby="decline-note-title"
          >
            <h2 id="decline-note-title">اگر رد کنید یا پاسخ ندهید</h2>
            <p>
              با رد یا پایان مهلت، جایگاه همین نقش می‌تواند با عضو دیگری جایگزین شود و دو عضو دیگر در Formation می‌مانند.
            </p>
          </section>
        </section>

        <aside
          className="ready-check__support"
          aria-label="اطلاعات پروژه و تیم"
        >
          <ProjectSummary project={project} readyCheck={currentReadyCheck} />
          <TeamStatus
            projectRunState={projectStarted ? projectRun?.state ?? null : null}
            readyCheck={currentReadyCheck}
          />
        </aside>

        <div className="ready-check__decision-area">
          {invalidRunState ? (
            <Alert tone="error">
              وضعیت ProjectRun فعال با نسخه این Ready Check سازگار نیست؛ اقدام‌ها برای جلوگیری از ثبت تصمیم نادرست غیرفعال شده‌اند.
            </Alert>
          ) : null}
          {refreshError ? (
            <Alert tone="error">
              {refreshError}
              <Button
                variant="secondary"
                onClick={revalidate}
                disabled={refreshing}
              >
                بررسی دوباره
              </Button>
            </Alert>
          ) : null}
          {refreshing ? (
            <p className="ready-check__sync" role="status" aria-live="polite">
              در حال همگام‌سازی وضعیت با سرور...
            </p>
          ) : null}
          <DecisionPanel
            action={action}
            actionError={actionError}
            canAct={canAct}
            onCancelDecline={() => setShowDeclineConfirmation(false)}
            onConfirm={() => void performAction('confirm')}
            onDecline={() => void performAction('decline')}
            onRequestDecline={() => {
              setActionError('')
              setShowDeclineConfirmation(true)
            }}
            githubUsername={githubUsername}
            onGithubUsernameChange={(value) => {
              setGithubUsername(value)
              setActionError('')
            }}
            projectRunState={projectStarted ? projectRun?.state ?? null : null}
            readyCheck={currentReadyCheck}
            showDeclineConfirmation={showDeclineConfirmation}
          />
        </div>
      </div>
    </div>
  )
}
