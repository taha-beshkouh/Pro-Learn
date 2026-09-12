import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { Alert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { LoadingState } from '../components/ui/LoadingState'
import { StatusBadge } from '../components/ui/StatusBadge'
import {
  DashboardContractError,
  loadDashboardPageData,
  type DashboardPageData,
} from '../lib/api/dashboard'
import { isMissingSession } from '../lib/api/auth'
import { ApiError } from '../lib/api/client'
import {
  buildDashboardViewModel,
  type DashboardSprintView,
  type DashboardViewModel,
} from '../lib/dashboardView'
import '../styles/dashboard.css'

type LoadState =
  | { status: 'loading' }
  | { status: 'empty' }
  | { status: 'error'; error: unknown }
  | { status: 'success'; data: DashboardPageData }

const dateFormatter = new Intl.DateTimeFormat('fa-IR', {
  dateStyle: 'medium',
  timeStyle: 'short',
})
const numberFormatter = new Intl.NumberFormat('fa-IR')

function dashboardErrorMessage(error: unknown) {
  if (error instanceof DashboardContractError) {
    return 'اطلاعات ProjectRun با نسخه یا اسپرینت‌های آن هماهنگ نیست. صفحه را دوباره بارگذاری کنید.'
  }
  if (error instanceof ApiError) {
    if (isMissingSession(error)) {
      return 'نشست شما پایان یافته است. برای ادامه دوباره وارد شوید.'
    }
    if (error.status === 403) {
      return 'اجازه دسترسی به این ProjectRun برای حساب شما وجود ندارد.'
    }
    return 'دریافت اطلاعات پروژه فعال ممکن نشد. کمی بعد دوباره تلاش کنید.'
  }
  return 'ارتباط با سرور برقرار نشد. اتصال اینترنت را بررسی و دوباره تلاش کنید.'
}

function DateValue({ value }: { value: string }) {
  const timestamp = Date.parse(value)
  return (
    <time dateTime={value} dir="ltr">
      {Number.isNaN(timestamp) ? 'زمان نامعتبر' : dateFormatter.format(timestamp)}
    </time>
  )
}

function ProjectIdentity({ view }: { view: DashboardViewModel }) {
  const duration =
    view.project.durationWeeks === null
      ? 'در API ثبت نشده'
      : `${numberFormatter.format(view.project.durationWeeks)} هفته`

  return (
    <section className="dashboard__identity" aria-labelledby="dashboard-title">
      <header className="dashboard__headline">
        <div>
          <p className="dashboard__eyebrow">PROJECT RUN</p>
          <h1 id="dashboard-title" dir="auto">
            {view.project.name}
          </h1>
          {view.project.summary && <p dir="auto">{view.project.summary}</p>}
        </div>
        <StatusBadge
          className={`dashboard__status dashboard__status--${view.projectRun.status.tone}`}
          status={`وضعیت پروژه: ${view.projectRun.status.label}`}
        />
      </header>

      <dl className="dashboard__facts">
        <div>
          <dt>نقش شما در این ProjectRun</dt>
          <dd dir="auto">{view.membership.role.name}</dd>
        </div>
        <div>
          <dt>Stack ثبت‌شده در ProjectRun</dt>
          <dd dir="auto">
            {view.membership.technology_stack?.name ?? 'برای این نقش ثبت نشده'}
          </dd>
        </div>
        <div>
          <dt>نسخه دقیق پروژه</dt>
          <dd>
            نسخه {numberFormatter.format(view.project.versionNumber)}
            <code title="شناسه ProjectVersion">{view.project.versionId}</code>
          </dd>
        </div>
        <div>
          <dt>سطح</dt>
          <dd dir="auto">{view.project.levelName}</dd>
        </div>
        <div>
          <dt>مدت پروژه</dt>
          <dd>{duration}</dd>
        </div>
        <div className="dashboard__deadline-fact">
          <dt>مهلت پروژه</dt>
          <dd>
            <DateValue value={view.projectRun.deadlineAt} />
          </dd>
        </div>
      </dl>
    </section>
  )
}

function NextAction({ view }: { view: DashboardViewModel }) {
  return (
    <section className="dashboard__next-action" aria-labelledby="next-action-title">
      <div className="dashboard__next-marker" aria-hidden="true" />
      <div>
        <p>الان چه کاری انجام بدهم؟</p>
        <h2 id="next-action-title">{view.nextAction.title}</h2>
        <p>{view.nextAction.description}</p>
        <Link className="dashboard__primary-link" to="/workspace">
          ادامه در Workspace
        </Link>
      </div>
    </section>
  )
}

function CurrentSprint({ view }: { view: DashboardViewModel }) {
  const sprint = view.currentSprint
  if (!sprint) {
    return (
      <Card className="dashboard__current-sprint">
        <h2>اسپرینت جاری</h2>
        <p>در پاسخ فعلی سرور اسپرینت جاری وجود ندارد.</p>
      </Card>
    )
  }

  return (
    <Card className="dashboard__current-sprint">
      <header>
        <div>
          <p>
            اسپرینت {numberFormatter.format(sprint.sequence)} از{' '}
            {numberFormatter.format(view.sprints.length)}
          </p>
          <h2 dir="auto">{sprint.title}</h2>
        </div>
        <StatusBadge
          className={`dashboard__status dashboard__status--${sprint.status.tone}`}
          status={`وضعیت اسپرینت: ${sprint.status.label}`}
        />
      </header>
      {sprint.brief && (
        <p className="dashboard__sprint-brief" dir="auto">
          {sprint.brief}
        </p>
      )}
      <dl className="dashboard__sprint-dates">
        <div>
          <dt>شروع برنامه‌ریزی‌شده</dt>
          <dd>
            <DateValue value={sprint.planned_start_at} />
          </dd>
        </div>
        <div>
          <dt>مهلت اسپرینت جاری (برنامه‌ریزی‌شده)</dt>
          <dd>
            <DateValue value={sprint.planned_end_at} />
          </dd>
        </div>
      </dl>
    </Card>
  )
}

function SprintJourneyItem({ sprint }: { sprint: DashboardSprintView }) {
  return (
    <li
      className={`dashboard__journey-item dashboard__journey-item--${sprint.status.tone}`}
      aria-current={sprint.isCurrent ? 'step' : undefined}
    >
      <span className="dashboard__journey-dot" aria-hidden="true" />
      <div>
        <span>اسپرینت {numberFormatter.format(sprint.sequence)}</span>
        <strong dir="auto">{sprint.title}</strong>
        <small>
          {sprint.status.label}
          {sprint.isCurrent ? ' · جاری' : ''}
        </small>
      </div>
    </li>
  )
}

function SprintJourney({ view }: { view: DashboardViewModel }) {
  return (
    <section className="dashboard__journey" aria-labelledby="sprint-journey-title">
      <header>
        <p>مسیر اجرا</p>
        <h2 id="sprint-journey-title">اسپرینت‌ها</h2>
      </header>
      {view.sprints.length > 0 ? (
        <ol aria-label="مسیر اسپرینت‌های ProjectRun">
          {view.sprints.map((sprint) => (
            <SprintJourneyItem key={sprint.id} sprint={sprint} />
          ))}
        </ol>
      ) : (
        <p className="dashboard__fallback">
          اطلاعات اسپرینت‌ها فعلاً در دسترس نیست.
        </p>
      )}
    </section>
  )
}

function TeamSummary({ view }: { view: DashboardViewModel }) {
  return (
    <section className="dashboard__team" aria-labelledby="team-title">
      <header>
        <p>اعضای ProjectRun</p>
        <h2 id="team-title">تیم شما</h2>
      </header>
      {view.team.length > 0 ? (
        <ul>
          {view.team.map((member) => (
            <li key={member.id}>
              <div>
                {member.id === view.membership.id && <span>شما</span>}
                <strong dir="auto">
                  {member.user?.email ??
                    'اطلاعات این عضو فعلاً در دسترس نیست'}
                </strong>
              </div>
              <dl>
                <div>
                  <dt>نقش</dt>
                  <dd dir="auto">{member.role?.name ?? 'ثبت نشده'}</dd>
                </div>
                <div>
                  <dt>Stack</dt>
                  <dd dir="auto">
                    {member.technology_stack?.name ?? 'برای این نقش ثبت نشده'}
                  </dd>
                </div>
              </dl>
            </li>
          ))}
        </ul>
      ) : (
        <p className="dashboard__fallback">
          اطلاعات اعضای تیم فعلاً در دسترس نیست.
        </p>
      )}
    </section>
  )
}

function RoleState({ view }: { view: DashboardViewModel }) {
  return (
    <Card className="dashboard__role-state">
      <p>مدیریت نقش</p>
      <h2 dir="auto">نقش فعلی ProjectRun: {view.membership.role.name}</h2>
      <p>
        تا زمانی که در یک ProjectRun فعال حضور دارید، امکان تغییر نقش وجود ندارد.
        نقش این پروژه از snapshot عضویت تیم خوانده می‌شود و با نقش پروفایل جایگزین
        نمی‌شود.
      </p>
    </Card>
  )
}

function DashboardContent({ data }: { data: DashboardPageData }) {
  const view = useMemo(() => buildDashboardViewModel(data), [data])
  return (
    <div className="dashboard-page" dir="rtl">
      <ProjectIdentity view={view} />
      <NextAction view={view} />
      <div className="dashboard__runtime-grid">
        <CurrentSprint view={view} />
        <SprintJourney view={view} />
      </div>
      <div className="dashboard__people-grid">
        <TeamSummary view={view} />
        <RoleState view={view} />
      </div>
      <section
        className="dashboard__workspace-entry"
        aria-labelledby="workspace-entry-title"
      >
        <div>
          <p>محل ادامه اجرای پروژه</p>
          <h2 id="workspace-entry-title">Workspace</h2>
          <span>
            منابع و کارهای پروژه در Workspace قرار می‌گیرند؛ Dashboard فقط وضعیت و
            مسیر بعدی را نشان می‌دهد.
          </span>
        </div>
        <Link className="dashboard__secondary-link" to="/workspace">
          ورود به Workspace
        </Link>
      </section>
    </div>
  )
}

export function DashboardPage() {
  const auth = useAuth()
  const [loadState, setLoadState] = useState<LoadState>({ status: 'loading' })
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()

    void loadDashboardPageData(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return
        setLoadState(data ? { status: 'success', data } : { status: 'empty' })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setLoadState({ status: 'error', error })
        if (isMissingSession(error)) {
          void auth.refreshSession()
        }
      })

    return () => controller.abort()
  }, [auth, reloadKey])

  function retry() {
    setLoadState({ status: 'loading' })
    setReloadKey((current) => current + 1)
  }

  if (loadState.status === 'loading') {
    return (
      <div
        className="dashboard-page dashboard__page-state"
        dir="rtl"
        aria-busy="true"
      >
        <LoadingState message="در حال دریافت ProjectRun از سرور..." />
      </div>
    )
  }

  if (loadState.status === 'empty') {
    return (
      <div className="dashboard-page dashboard__page-state" dir="rtl">
        <EmptyState
          title="ProjectRun فعالی ندارید"
          description="در حال حاضر پروژه فعالی برای این حساب در پاسخ سرور وجود ندارد. اگر Ready Check شما به‌تازگی تکمیل شده، وضعیت را دوباره بررسی کنید."
        />
        <div className="dashboard__state-actions">
          <Button onClick={retry}>بررسی دوباره</Button>
          <Link to="/ready-check">مشاهده Ready Check</Link>
          <Link to="/projects">مشاهده پروژه‌ها</Link>
        </div>
      </div>
    )
  }

  if (loadState.status === 'error') {
    return (
      <div className="dashboard-page dashboard__page-state" dir="rtl">
        <Alert tone="error">
          <h1>دریافت Dashboard ممکن نشد</h1>
          <p>{dashboardErrorMessage(loadState.error)}</p>
        </Alert>
        <Button variant="secondary" onClick={retry}>
          تلاش دوباره
        </Button>
      </div>
    )
  }

  return <DashboardContent data={loadState.data} />
}
