import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { authErrorMessage, isMissingSession, resolveContinuation, stackPath, type ContinuationResult } from '../lib/api/auth'
import { ContinuationNotice } from '../auth/ContinuationNotice'
import { HomeFooter } from '../components/home/HomeFooter'
import { Alert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { LoadingState } from '../components/ui/LoadingState'
import { StatusBadge } from '../components/ui/StatusBadge'
import { ApiError } from '../lib/api/client'
import {
  createProjectReadiness,
  loadStackSelectionPageData,
  persistProjectStackSelection,
  type StackSelectionPageData,
} from '../lib/api/stackSelection'
import type {
  ProjectReadinessResponse,
  ProjectRoleRequirement,
  ProjectVersionRoleContext,
  TechnologyStack,
} from '../lib/api/types'
import '../styles/stack-selection.css'

type StackPolicy = 'FIXED' | 'ALLOWLIST' | 'OPEN'

type LoadState =
  | { status: 'loading' }
  | {
      status: 'success'
      requestedVersionId: string
      data: StackSelectionPageData
    }
  | { status: 'error'; requestedVersionId: string; error: Error }

const initialLoadState: LoadState = { status: 'loading' }

function asError(error: unknown) {
  return error instanceof Error
    ? error
    : new Error('دریافت اطلاعات انتخاب Stack ممکن نشد.')
}

function mutationError(error: unknown) {
  return new Error(authErrorMessage(error))
}

function readinessMutationError(error: unknown) {
  if (!(error instanceof ApiError)) {
    return error instanceof Error
      ? error
      : new Error('ثبت آمادگی پروژه ممکن نشد.')
  }

  const payload = JSON.stringify(error.data ?? '')
  if (payload.includes('already has an active project readiness')) {
    return new Error('برای این حساب از قبل یک آمادگی پروژه فعال ثبت شده است.')
  }
  if (payload.includes('current proposed formation')) {
    return new Error('این حساب هم‌اکنون در یک Formation جاری قرار دارد.')
  }
  if (payload.includes('active ProjectRun')) {
    return new Error('این حساب هم‌اکنون یک ProjectRun فعال دارد.')
  }
  if (payload.includes('valid exact-version stack confirmation')) {
    return new Error('تأیید معتبر Stack برای همین نسخه پروژه پیدا نشد.')
  }
  return mutationError(error)
}

function isSupportedPolicy(policy: unknown): policy is StackPolicy {
  return policy === 'FIXED' || policy === 'ALLOWLIST' || policy === 'OPEN'
}

function selectedStackIdForContext(
  context: ProjectVersionRoleContext | null,
) {
  return context?.selected_stack?.id ?? context?.auto_selected_stack?.id ?? null
}

function policyCopy(policy: StackPolicy) {
  switch (policy) {
    case 'FIXED':
      return {
        title: 'Stack این نقش از قبل مشخص شده است',
        description:
          'این ProjectVersion یک Stack ثابت برای نقش شما دارد و انتخاب دیگری لازم نیست.',
      }
    case 'ALLOWLIST':
      return {
        title: 'Stack موردنظرت را انتخاب کن',
        description:
          'فقط گزینه‌های مجاز همین ProjectVersion برای نقش شما نمایش داده می‌شوند.',
      }
    case 'OPEN':
      return {
        title: 'Stack سازگار پروفایلت را انتخاب کن',
        description:
          'این گزینه‌ها مستقیماً از Stackهای سازگار با نقش و مهارت‌های ثبت‌شده شما می‌آیند.',
      }
  }
}

function StackIdentity({ stack }: { stack: TechnologyStack }) {
  return (
    <span className="stack-selection__stack-identity">
      <strong dir="ltr">{stack.name}</strong>
      <span dir="ltr">{stack.code}</span>
    </span>
  )
}

function ChoiceList({
  choices,
  onChange,
  policy,
  selectedStackId,
}: {
  choices: TechnologyStack[]
  onChange: (stackId: string) => void
  policy: 'ALLOWLIST' | 'OPEN'
  selectedStackId: string | null
}) {
  if (choices.length === 0) {
    return (
      <EmptyState
        title="Stack قابل انتخابی در دسترس نیست"
        description={
          policy === 'OPEN'
            ? 'API برای نقش و پروفایل فعلی شما Stack سازگاری برنگردانده است.'
            : 'API برای این نقش گزینه مجاز پیکربندی‌شده‌ای برنگردانده است.'
        }
      />
    )
  }

  return (
    <fieldset className="stack-selection__choices">
      <legend className="sr-only">انتخاب Stack پروژه</legend>
      {choices.map((stack) => {
        const selected = selectedStackId === stack.id
        return (
          <label
            className={
              selected
                ? 'stack-selection__choice is-selected'
                : 'stack-selection__choice'
            }
            key={stack.id}
          >
            <input
              type="radio"
              name="technology-stack"
              value={stack.id}
              checked={selected}
              onChange={() => onChange(stack.id)}
            />
            <StackIdentity stack={stack} />
            {selected ? <StatusBadge status="انتخاب‌شده" /> : null}
          </label>
        )
      })}
    </fieldset>
  )
}

function PolicyPanel({
  context,
  onChange,
  policy,
  requirement,
  selectedStackId,
}: {
  context: ProjectVersionRoleContext
  onChange: (stackId: string) => void
  policy: StackPolicy
  requirement: ProjectRoleRequirement
  selectedStackId: string | null
}) {
  const copy = policyCopy(policy)

  if (policy === 'FIXED') {
    const fixedStack = requirement.configured_stacks[0] ?? null
    return (
      <Card className="stack-selection__policy-card">
        <header className="stack-selection__policy-heading">
          <div>
            <StatusBadge status="FIXED" dir="ltr" />
            <h2 id="stack-policy-title">{copy.title}</h2>
            <p>{copy.description}</p>
          </div>
        </header>
        {fixedStack ? (
          <div className="stack-selection__fixed-stack">
            <StackIdentity stack={fixedStack} />
            <StatusBadge status="Stack ثابت" />
          </div>
        ) : (
          <EmptyState
            title="Stack ثابت در دسترس نیست"
            description="API برای سیاست FIXED یک Stack پیکربندی‌شده برنگردانده است."
          />
        )}
      </Card>
    )
  }

  return (
    <Card className="stack-selection__policy-card">
      <header className="stack-selection__policy-heading">
        <div>
          <StatusBadge status={policy} dir="ltr" />
          <h2 id="stack-policy-title">{copy.title}</h2>
          <p>{copy.description}</p>
        </div>
      </header>
      <ChoiceList
        choices={context.compatible_stacks}
        onChange={onChange}
        policy={policy}
        selectedStackId={selectedStackId}
      />
    </Card>
  )
}

export function ProjectStackSelectionPage() {
  const { projectVersionId } = useParams()
  const auth = useAuth()
  const [loadState, setLoadState] = useState<LoadState>(initialLoadState)
  const [reloadKey, setReloadKey] = useState(0)
  const [selectedStackId, setSelectedStackId] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<{
    title: string
    error: Error
  } | null>(null)
  const submittingRef = useRef(false)
  const [stackConfirmed, setStackConfirmed] = useState(false)
  const [readiness, setReadiness] = useState<ProjectReadinessResponse | null>(
    null,
  )
  const [blocked, setBlocked] = useState<ContinuationResult | null>(null)

  useEffect(() => {
    if (!projectVersionId) {
      return
    }

    const controller = new AbortController()
    let active = true

    void loadStackSelectionPageData(projectVersionId, controller.signal)
      .then((data) => {
        if (!active) {
          return
        }
        setLoadState({
          status: 'success',
          requestedVersionId: projectVersionId,
          data,
        })
        setSelectedStackId(
          selectedStackIdForContext(data.projectVersion.role_context),
        )
        setSubmitError(null)
      })
      .catch((error: unknown) => {
        if (active && !controller.signal.aborted) {
          setLoadState({
            status: 'error',
            requestedVersionId: projectVersionId,
            error: asError(error),
          })
        }
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [projectVersionId, reloadKey])

  function retry() {
    setLoadState(initialLoadState)
    setSelectedStackId(null)
    setSubmitError(null)
    setStackConfirmed(false)
    setReadiness(null)
    setReloadKey((current) => current + 1)
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (
      loadState.status !== 'success' ||
      auth.status !== 'authenticated' ||
      submittingRef.current ||
      stackConfirmed ||
      readiness
    ) {
      return
    }

    const project = loadState.data.projectVersion
    const context = project.role_context
    if (!context) {
      return
    }

    const stackId = context.requires_stack ? selectedStackId : null
    if (context.requires_stack && !stackId) {
      return
    }

    submittingRef.current = true
    setSubmitting(true)
    setSubmitError(null)
    let failedStep: 'stack' | 'readiness' = 'stack'
    try {
      const continuation = await resolveContinuation(project.id)
      if (continuation.message || continuation.destination !== stackPath(project.id)) {
        setBlocked(continuation)
        return
      }
      const result = await persistProjectStackSelection(
        project.id,
        stackId,
      )
      if (
        result.project_version_id !== project.id ||
        result.selected_role_id !== context.role.id ||
        result.selected_stack_id !== stackId
      ) {
        throw new Error('پاسخ ثبت Stack با انتخاب فعلی مطابقت ندارد.')
      }
      setStackConfirmed(true)
      failedStep = 'readiness'
      const createdReadiness = await createProjectReadiness()
      if (createdReadiness.project_version_id !== project.id) {
        throw new Error('پاسخ آمادگی با نسخه تأییدشده پروژه مطابقت ندارد.')
      }
      setReadiness(createdReadiness)
    } catch (error: unknown) {
      setSubmitError({
        title:
          failedStep === 'readiness'
            ? 'ثبت آمادگی ممکن نشد.'
            : 'ثبت Stack ممکن نشد.',
        error:
          failedStep === 'readiness'
            ? readinessMutationError(error)
            : mutationError(error),
      })
      if (isMissingSession(error)) void auth.refreshSession()
    } finally {
      setSubmitting(false)
      submittingRef.current = false
    }
  }

  if (!projectVersionId) {
    return (
      <div className="stack-selection-page" dir="rtl">
        <div className="stack-selection__state">
          <EmptyState
            title="ProjectVersion مشخص نیست"
            description="شناسه نسخه پروژه در نشانی صفحه وجود ندارد."
          />
        </div>
        <HomeFooter />
      </div>
    )
  }

  const requestPending =
    loadState.status === 'loading' ||
    loadState.requestedVersionId !== projectVersionId

  if (requestPending) {
    return (
      <div className="stack-selection-page" dir="rtl">
        <div className="stack-selection__state" aria-busy="true">
          <LoadingState message="در حال دریافت نقش و سیاست Stack..." />
        </div>
        <HomeFooter />
      </div>
    )
  }

  if (loadState.status === 'error') {
    const notFound =
      loadState.error instanceof ApiError && loadState.error.status === 404
    return (
      <div className="stack-selection-page" dir="rtl">
        <div className="stack-selection__state">
          {notFound ? (
            <EmptyState
              title="ProjectVersion در دسترس نیست"
              description="نسخه درخواستی پیدا نشد یا هنوز منتشر نشده است."
            />
          ) : (
            <Alert className="stack-selection__error" tone="error">
              <h1>دریافت اطلاعات Stack ممکن نشد</h1>
              <p>{authErrorMessage(loadState.error)}</p>
              <Button variant="secondary" onClick={retry}>
                تلاش دوباره
              </Button>
            </Alert>
          )}
          <Link className="stack-selection__back-link" to="/projects">
            بازگشت به پروژه‌ها
          </Link>
        </div>
        <HomeFooter />
      </div>
    )
  }

  const { projectVersion: project } = loadState.data
  const context = project.role_context
  const requirement = context
    ? project.role_requirements.find(
        (item) => item.id === context.id || item.role.id === context.role.id,
      ) ?? null
    : null
  const policy = context?.stack_policy
  const supportedPolicy = isSupportedPolicy(policy) ? policy : null
  const fixedStack =
    supportedPolicy === 'FIXED' && requirement?.configured_stacks.length === 1
      ? requirement.configured_stacks[0]
      : null
  const choices =
    supportedPolicy === 'ALLOWLIST' || supportedPolicy === 'OPEN'
      ? context?.compatible_stacks ?? []
      : []
  const validSelection = selectedStackId
    ? supportedPolicy === 'FIXED'
      ? fixedStack?.id === selectedStackId
      : choices.some((stack) => stack.id === selectedStackId)
    : false
  const decisionReady = context
    ? context.requires_stack
      ? Boolean(requirement && supportedPolicy && validSelection)
      : Boolean(requirement)
    : false
  const canContinue =
    decisionReady &&
    auth.status === 'authenticated' &&
    !submitting &&
    !stackConfirmed &&
    !readiness &&
    !blocked

  return (
    <div className="stack-selection-page" dir="rtl">
      <main className="stack-selection__content">
        <Link
          className="stack-selection__back-link"
          to={`/projects/${encodeURIComponent(project.id)}`}
        >
          <span aria-hidden="true">→</span>
          بازگشت به جزئیات پروژه
        </Link>

        <header className="stack-selection__intro">
          <p className="stack-selection__eyebrow" dir="ltr">
            PROLEARN · STACK SELECTION
          </p>
          <h1>انتخاب تکنولوژی / Stack</h1>
          <p>
            نقش و Stack نهایی این ProjectVersion را پیش از رفتن به مرحله بعد بررسی کن.
          </p>
        </header>

        <Card className="stack-selection__context-card">
          <dl>
            <div>
              <dt>پروژه</dt>
              <dd dir="auto">{project.project_template.name}</dd>
            </div>
            <div>
              <dt>نقش انتخابی</dt>
              <dd dir="ltr">{context?.role.name ?? '—'}</dd>
            </div>
            <div>
              <dt>سطح</dt>
              <dd dir="ltr">{project.project_template.level.name}</dd>
            </div>
            {project.duration_weeks !== null ? (
              <div>
                <dt>مدت پروژه</dt>
                <dd>{project.duration_weeks} هفته</dd>
              </div>
            ) : null}
          </dl>
        </Card>

        {blocked ? <ContinuationNotice result={blocked} /> : readiness ? (
          <Alert className="stack-selection__submit-error" tone="success">
            <strong>آمادگی شما ثبت شد</strong>
            <span>
              در انتظار تشکیل تیم هستید. پس از تشکیل تیم، Ready Check برای شما فعال می‌شود.
            </span>
          </Alert>
        ) : !context ? (
          <section className="stack-selection__blocking-state">
            <EmptyState
              title="نقش انتخابی پیدا نشد"
              description="API برای کاربر یا مهمان فعلی، نقش مرتبطی با این ProjectVersion برنگردانده است."
            />
          </section>
        ) : !requirement ? (
          <section className="stack-selection__blocking-state">
            <EmptyState
              title="نیازمندی نقش پیدا نشد"
              description="نقش انتخابی در role_requirements همین ProjectVersion وجود ندارد."
            />
          </section>
        ) : context.requires_stack && !supportedPolicy ? (
          <section className="stack-selection__blocking-state">
            <EmptyState
              title="سیاست Stack پشتیبانی نمی‌شود"
              description="API برای نقشی که به Stack نیاز دارد، سیاست FIXED، ALLOWLIST یا OPEN برنگردانده است."
            />
          </section>
        ) : (
          <form className="stack-selection__form" onSubmit={handleSubmit}>
            {context.requires_stack && supportedPolicy ? (
              <section aria-labelledby="stack-policy-title">
                <PolicyPanel
                  context={context}
                  requirement={requirement}
                  policy={supportedPolicy}
                  selectedStackId={selectedStackId}
                  onChange={(stackId) => {
                    setSelectedStackId(stackId)
                    setSubmitError(null)
                  }}
                />
              </section>
            ) : (
              <Card className="stack-selection__policy-card">
                <header className="stack-selection__policy-heading">
                  <div>
                    <StatusBadge status="بدون Stack" />
                    <h2 id="stack-policy-title">این نقش به Stack فنی نیاز ندارد</h2>
                    <p>
                      API این نقش را بدون نیاز به انتخاب Stack تعریف کرده است؛ مقدار ساختگی ثبت نمی‌شود.
                    </p>
                  </div>
                </header>
              </Card>
            )}

            {submitError ? (
              <Alert className="stack-selection__submit-error" tone="error">
                <strong>{submitError.title}</strong>
                <span>{submitError.error.message}</span>
              </Alert>
            ) : null}

            <aside className="stack-selection__next-step" aria-labelledby="next-step-title">
              <span className="stack-selection__next-number" aria-hidden="true">
                02
              </span>
              <div>
                <h2 id="next-step-title">مسیر رسیدن به Ready Check</h2>
                <p>
                  پس از تأیید Stack و ثبت آمادگی پروژه، تیم به‌صورت دستی تشکیل می‌شود. Ready Check فقط پس از تشکیل تیم آغاز می‌شود.
                </p>
              </div>
            </aside>

            <div className="stack-selection__actions">
              <Button type="submit" disabled={!canContinue}>
                {submitting
                  ? stackConfirmed
                    ? 'در حال ثبت آمادگی...'
                    : 'در حال ثبت Stack...'
                  : stackConfirmed
                    ? 'Stack تأیید شد'
                    : 'تأیید Stack'}
              </Button>
              {!decisionReady ? (
                <span>برای ادامه باید یک انتخاب معتبر از API در دسترس باشد.</span>
              ) : null}
            </div>
          </form>
        )}
      </main>
      <HomeFooter />
    </div>
  )
}
