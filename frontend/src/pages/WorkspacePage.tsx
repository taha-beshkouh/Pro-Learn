import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { DesignWorkspaceSection } from '../components/workspace/DesignWorkspaceSection'
import { Alert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { LoadingState } from '../components/ui/LoadingState'
import { StatusBadge } from '../components/ui/StatusBadge'
import { isMissingSession } from '../lib/api/auth'
import { ApiError } from '../lib/api/client'
import type {
  ProjectRunWorkspaceResponse,
  ProjectWorkItem,
} from '../lib/api/types'
import {
  loadWorkspace,
  WorkspaceContractError,
} from '../lib/api/workspace'
import {
  buildWorkspaceViewModel,
  type WorkspaceResourceGroup,
  type WorkspaceSprintView,
  type WorkspaceViewModel,
} from '../lib/workspaceView'
import '../styles/workspace.css'

type LoadState =
  | { status: 'loading' }
  | { status: 'empty' }
  | { status: 'error'; error: unknown }
  | { status: 'success'; data: ProjectRunWorkspaceResponse }

const dateFormatter = new Intl.DateTimeFormat('fa-IR', {
  dateStyle: 'medium',
  timeStyle: 'short',
})
const numberFormatter = new Intl.NumberFormat('fa-IR')

function sprintPath(sprintRunId: string) {
  return `/workspace/sprints/${encodeURIComponent(sprintRunId)}`
}

function workspaceErrorMessage(error: unknown) {
  if (error instanceof WorkspaceContractError) {
    return 'اطلاعات Workspace با قرارداد فعلی ProjectRun هماهنگ نیست. صفحه را دوباره بارگذاری کنید.'
  }
  if (error instanceof ApiError) {
    if (isMissingSession(error)) {
      return 'نشست شما پایان یافته است. برای ادامه دوباره وارد شوید.'
    }
    if (error.status === 403) {
      return 'اجازه دسترسی به این Workspace برای حساب شما وجود ندارد.'
    }
    return 'دریافت اطلاعات Workspace ممکن نشد. کمی بعد دوباره تلاش کنید.'
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

function ProjectContext({ view }: { view: WorkspaceViewModel }) {
  return (
    <section className="workspace__project-context" aria-labelledby="workspace-title">
      <header className="workspace__project-header">
        <div>
          <p className="workspace__eyebrow">PARTICIPANT WORKSPACE</p>
          <h1 id="workspace-title" dir="auto">
            {view.project.name}
          </h1>
          {view.project.summary && <p dir="auto">{view.project.summary}</p>}
        </div>
        <StatusBadge
          className={`workspace__status workspace__status--${view.projectRun.status.tone}`}
          status={`وضعیت ProjectRun: ${view.projectRun.status.label}`}
        />
      </header>

      <dl className="workspace__project-facts">
        <div>
          <dt>نقش شما در ProjectRun</dt>
          <dd dir="auto">{view.membership.role.name}</dd>
        </div>
        <div>
          <dt>Stack ثبت‌شده در عضویت</dt>
          <dd dir="auto">
            {view.membership.technology_stack?.name ?? 'برای این نقش ثبت نشده'}
          </dd>
        </div>
        <div>
          <dt>نسخه دقیق پروژه</dt>
          <dd>
            نسخه {numberFormatter.format(view.project.version_number)}
            <code title="شناسه ProjectVersion">{view.project.version_id}</code>
          </dd>
        </div>
        <div>
          <dt>مهلت پروژه</dt>
          <dd>
            <DateValue value={view.projectRun.deadlineAt} />
          </dd>
        </div>
      </dl>
    </section>
  )
}

function ProjectRepository({ repositoryUrl }: { repositoryUrl: string | null }) {
  return (
    <section
      className="workspace__repository"
      aria-labelledby="workspace-repository-title"
    >
      <div>
        <p className="workspace__section-kicker">دسترسی اجرای پروژه</p>
        <h2 id="workspace-repository-title">مخزن پروژه</h2>
      </div>
      {repositoryUrl ? (
        <a href={repositoryUrl} target="_blank" rel="noreferrer" dir="ltr">
          {repositoryUrl}
        </a>
      ) : (
        <p>در حال آماده‌سازی توسط تیم PROLEARN</p>
      )}
    </section>
  )
}

function CurrentSprint({ view }: { view: WorkspaceViewModel }) {
  const sprint = view.currentSprint
  if (!sprint) {
    return (
      <Card className="workspace__current-sprint">
        <p className="workspace__section-kicker">وضعیت اجرا</p>
        <h2>اسپرینت جاری</h2>
        <p className="workspace__muted">
          در پاسخ فعلی Workspace اسپرینت جاری وجود ندارد.
        </p>
      </Card>
    )
  }

  return (
    <Card className="workspace__current-sprint">
      <header>
        <div>
          <p className="workspace__section-kicker">
            اسپرینت {numberFormatter.format(sprint.sequence)} از{' '}
            {numberFormatter.format(view.sprints.length)}
          </p>
          <h2 dir="auto">{sprint.title}</h2>
        </div>
        <StatusBadge
          className={`workspace__status workspace__status--${sprint.status.tone}`}
          status={`وضعیت اسپرینت: ${sprint.status.label}`}
        />
      </header>
      {sprint.brief && <p className="workspace__muted" dir="auto">{sprint.brief}</p>}
      <dl className="workspace__sprint-dates">
        <div>
          <dt>شروع برنامه‌ریزی‌شده</dt>
          <dd><DateValue value={sprint.planned_start_at} /></dd>
        </div>
        <div>
          <dt>پایان برنامه‌ریزی‌شده اسپرینت</dt>
          <dd><DateValue value={sprint.planned_end_at} /></dd>
        </div>
      </dl>
      <Link className="workspace__primary-link" to={sprintPath(sprint.id)}>
        مشاهده جزئیات همین اسپرینت
      </Link>
    </Card>
  )
}

function SprintJourneyItem({ sprint }: { sprint: WorkspaceSprintView }) {
  return (
    <li className={`workspace__sprint-item workspace__sprint-item--${sprint.status.tone}`}>
      <Link
        to={sprintPath(sprint.id)}
        aria-current={sprint.isCurrent ? 'step' : undefined}
      >
        <span className="workspace__sprint-marker" aria-hidden="true" />
        <span>
          <small>اسپرینت {numberFormatter.format(sprint.sequence)}</small>
          <strong dir="auto">{sprint.title}</strong>
          <span>
            {sprint.status.label}
            {sprint.isCurrent ? ' · جاری' : ''}
          </span>
        </span>
      </Link>
    </li>
  )
}

function SprintJourney({ view }: { view: WorkspaceViewModel }) {
  return (
    <section className="workspace__sprints" aria-labelledby="workspace-sprints-title">
      <header>
        <p className="workspace__section-kicker">مسیر پروژه</p>
        <h2 id="workspace-sprints-title">فهرست اسپرینت‌ها</h2>
      </header>
      {view.sprints.length > 0 ? (
        <ol aria-label="اسپرینت‌های ProjectRun">
          {view.sprints.map((sprint) => (
            <SprintJourneyItem key={sprint.id} sprint={sprint} />
          ))}
        </ol>
      ) : (
        <p className="workspace__fallback">
          اطلاعات اسپرینت‌ها فعلاً در دسترس نیست.
        </p>
      )}
    </section>
  )
}

function ResourceMetadata({ item }: { item: ProjectWorkItem }) {
  return (
    <dl className="workspace__resource-meta">
      <div>
        <dt>محدوده</dt>
        <dd dir="auto">
          {item.sprint_template
            ? `اسپرینت ${numberFormatter.format(item.sprint_template.sequence)} — ${item.sprint_template.title}`
            : 'کل پروژه'}
        </dd>
      </div>
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

function ResourceGroup({ group }: { group: WorkspaceResourceGroup }) {
  if (group.items.length === 0) return null

  return (
    <section
      className={`workspace__resource-group workspace__resource-group--${group.kind}`}
      aria-labelledby={`workspace-resource-${group.kind}`}
    >
      <header>
        <h3 id={`workspace-resource-${group.kind}`}>{group.title}</h3>
        <p>{group.description}</p>
      </header>
      <div className="workspace__resource-list">
        {group.items.map((item) => (
          <article key={item.id} className="workspace__resource-item">
            <h4 dir="auto">{item.title}</h4>
            {item.description && <p dir="auto">{item.description}</p>}
            <ResourceMetadata item={item} />
          </article>
        ))}
      </div>
    </section>
  )
}

function VisibleWork({ view }: { view: WorkspaceViewModel }) {
  return (
    <section className="workspace__work" aria-labelledby="workspace-work-title">
      <header className="workspace__work-header">
        <div>
          <p className="workspace__section-kicker">محتوای ثابت نسخه پروژه</p>
          <h2 id="workspace-work-title">کارهای پروژه</h2>
        </div>
        <p>
          این موارد راهنمای ثابت پروژه‌اند و وضعیت انجام یا تکمیل مستقل ندارند.
        </p>
      </header>
      {view.resourceCount > 0 ? (
        <div className="workspace__resource-groups">
          {view.resourceGroups.map((group) => (
            <ResourceGroup key={group.kind} group={group} />
          ))}
        </div>
      ) : (
        <EmptyState
          title="کار قابل‌نمایشی وجود ندارد"
          description="Workspace API برای عضویت فعلی شما محتوای کاری برنگردانده است. این وضعیت به‌تنهایی خطای سیستم نیست."
        />
      )}
    </section>
  )
}

function TeamSummary({ view }: { view: WorkspaceViewModel }) {
  return (
    <section className="workspace__team" aria-labelledby="workspace-team-title">
      <header>
        <p className="workspace__section-kicker">snapshot عضویت ProjectRun</p>
        <h2 id="workspace-team-title">تیم</h2>
      </header>
      {view.team.length > 0 ? (
        <ul>
          {view.team.map((member) => (
            <li key={member.id}>
              <div>
                {member.id === view.membership.id && <span>شما</span>}
                <strong dir="auto">{member.user.email}</strong>
              </div>
              <dl>
                <div>
                  <dt>Role</dt>
                  <dd dir="auto">{member.role.name}</dd>
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
        <p className="workspace__fallback">
          اطلاعات اعضای تیم فعلاً در دسترس نیست.
        </p>
      )}
    </section>
  )
}

function WorkspaceNavigation({ view }: { view: WorkspaceViewModel }) {
  return (
    <nav className="workspace__navigation" aria-label="ناوبری ProjectRun">
      <Link className="workspace__secondary-link" to="/dashboard">
        بازگشت به Dashboard
      </Link>
      {view.currentSprint && (
        <Link
          className="workspace__primary-link"
          to={sprintPath(view.currentSprint.id)}
        >
          جزئیات اسپرینت جاری
        </Link>
      )}
    </nav>
  )
}

function WorkspaceContent({
  data,
  onDesignWorkspaceSaved,
}: {
  data: ProjectRunWorkspaceResponse
  onDesignWorkspaceSaved: () => void
}) {
  const view = useMemo(() => buildWorkspaceViewModel(data), [data])
  return (
    <div className="workspace-page" dir="rtl">
      <ProjectContext view={view} />
      <ProjectRepository repositoryUrl={data.repository_url} />
      <DesignWorkspaceSection
        projectRunId={data.id}
        url={data.design_workspace_url}
        memberRoleCode={data.membership.role.code}
        runState={data.state}
        onSaved={onDesignWorkspaceSaved}
      />
      <div className="workspace__sprint-layout">
        <CurrentSprint view={view} />
        <SprintJourney view={view} />
      </div>
      <VisibleWork view={view} />
      <TeamSummary view={view} />
      <WorkspaceNavigation view={view} />
    </div>
  )
}

export function WorkspacePage() {
  const auth = useAuth()
  const [loadState, setLoadState] = useState<LoadState>({ status: 'loading' })
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()

    void loadWorkspace(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return
        setLoadState(data ? { status: 'success', data } : { status: 'empty' })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setLoadState({ status: 'error', error })
        if (isMissingSession(error)) void auth.refreshSession()
      })

    return () => controller.abort()
  }, [auth, reloadKey])

  function retry() {
    setLoadState({ status: 'loading' })
    setReloadKey((current) => current + 1)
  }

  if (loadState.status === 'loading') {
    return (
      <div className="workspace-page workspace__page-state" dir="rtl" aria-busy="true">
        <LoadingState message="در حال دریافت Workspace از سرور..." />
      </div>
    )
  }

  if (loadState.status === 'empty') {
    return (
      <div className="workspace-page workspace__page-state" dir="rtl">
        <EmptyState
          title="ProjectRun فعالی برای Workspace ندارید"
          description="در پاسخ فعلی سرور Workspace فعالی برای این حساب وجود ندارد."
        />
        <div className="workspace__state-actions">
          <Button onClick={retry}>بررسی دوباره</Button>
          <Link to="/dashboard">بازگشت به Dashboard</Link>
          <Link to="/ready-check">مشاهده Ready Check</Link>
        </div>
      </div>
    )
  }

  if (loadState.status === 'error') {
    return (
      <div className="workspace-page workspace__page-state" dir="rtl">
        <Alert tone="error">
          <h1>دریافت Workspace ممکن نشد</h1>
          <p>{workspaceErrorMessage(loadState.error)}</p>
        </Alert>
        <Button variant="secondary" onClick={retry}>تلاش دوباره</Button>
      </div>
    )
  }

  return <WorkspaceContent data={loadState.data} onDesignWorkspaceSaved={retry} />
}
