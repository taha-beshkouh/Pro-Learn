import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { HomeFooter } from '../components/home/HomeFooter'
import { Alert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { LoadingState } from '../components/ui/LoadingState'
import { StatusBadge } from '../components/ui/StatusBadge'
import { ApiError } from '../lib/api/client'
import { loadProjectVersionDetail } from '../lib/api/projectDetail'
import type {
  ProjectRoleRequirement,
  ProjectVersionDetailResponse,
  ProjectWorkItem,
  SprintTemplate,
  TechnologyStack,
} from '../lib/api/types'
import '../styles/project-detail.css'

type LoadState =
  | { status: 'loading'; project: null; error: null }
  | { status: 'success'; project: ProjectVersionDetailResponse; error: null }
  | { status: 'error'; project: null; error: Error }

type WorkItemGroup = {
  id: string
  label: string
  items: ProjectWorkItem[]
}

const initialLoadState: LoadState = {
  status: 'loading',
  project: null,
  error: null,
}

const descriptionCollapseThreshold = 420

function asError(error: unknown) {
  return error instanceof Error
    ? error
    : new Error('دریافت جزئیات پروژه ممکن نشد.')
}

function formatWeeklyEffort(
  minimum: number | null,
  maximum: number | null,
) {
  if (minimum === null && maximum === null) {
    return null
  }
  if (minimum !== null && maximum !== null) {
    return minimum === maximum
      ? `${minimum} ساعت در هفته`
      : `${minimum} تا ${maximum} ساعت در هفته`
  }
  return minimum !== null
    ? `از ${minimum} ساعت در هفته`
    : `تا ${maximum} ساعت در هفته`
}

function policyPresentation(policy: ProjectRoleRequirement['stack_policy']) {
  switch (policy) {
    case 'FIXED':
      return {
        label: 'FIXED · ثابت',
        description: 'استک این نقش از قبل برای پروژه مشخص شده است.',
      }
    case 'ALLOWLIST':
      return {
        label: 'ALLOWLIST · فهرست مجاز',
        description: 'استک این نقش از میان گزینه‌های پیکربندی‌شده انتخاب می‌شود.',
      }
    case 'OPEN':
      return {
        label: 'OPEN · انتخاب باز',
        description: 'گزینه‌های این نقش از استک‌های سازگار ثبت‌شده کاربر تعیین می‌شوند.',
      }
    default:
      return {
        label: 'بدون استک فنی',
        description: 'این نقش برای حضور در پروژه به انتخاب استک فنی نیاز ندارد.',
      }
  }
}

function sprintWorkGroups(
  project: ProjectVersionDetailResponse,
  sprint: SprintTemplate,
) {
  const groups: WorkItemGroup[] = []
  const sharedItems = project.shared_work_items.filter(
    (item) => item.sprint_template?.id === sprint.id,
  )

  if (sharedItems.length > 0) {
    groups.push({ id: 'shared', label: 'کارهای مشترک تیم', items: sharedItems })
  }

  if (project.role_context) {
    const roleItems = project.role_context.work_items.filter(
      (item) => item.sprint_template?.id === sprint.id,
    )
    if (roleItems.length > 0) {
      groups.push({
        id: project.role_context.role.id,
        label: `کارهای نقش ${project.role_context.role.name}`,
        items: roleItems,
      })
    }
    return groups
  }

  const roleGroups = new Map<string, WorkItemGroup>()
  for (const item of project.work_items) {
    if (!item.role || item.sprint_template?.id !== sprint.id) {
      continue
    }
    const stackKey = item.technology_stack?.id ?? 'any-stack'
    const groupId = `${item.role.id}:${stackKey}`
    const existingGroup = roleGroups.get(groupId)
    if (existingGroup) {
      existingGroup.items.push(item)
      continue
    }
    roleGroups.set(groupId, {
      id: groupId,
      label: item.technology_stack
        ? `${item.role.name} · ${item.technology_stack.name}`
        : item.role.name,
      items: [item],
    })
  }

  groups.push(...roleGroups.values())
  return groups
}

function StackList({ stacks }: { stacks: TechnologyStack[] }) {
  if (stacks.length === 0) {
    return null
  }

  return (
    <ul className="project-detail__stack-list" aria-label="استک‌های ثبت‌شده">
      {stacks.map((stack) => (
        <li key={stack.id} dir="ltr" title={stack.code}>
          {stack.name}
        </li>
      ))}
    </ul>
  )
}

function SprintAccordion({ project }: { project: ProjectVersionDetailResponse }) {
  const [expandedSprintIds, setExpandedSprintIds] = useState<Set<string>>(
    () => new Set(),
  )

  function toggleSprint(sprintId: string) {
    setExpandedSprintIds((current) => {
      const next = new Set(current)
      if (next.has(sprintId)) {
        next.delete(sprintId)
      } else {
        next.add(sprintId)
      }
      return next
    })
  }

  if (project.sprint_templates.length === 0) {
    return (
      <EmptyState
        title="Sprint ثبت نشده است"
        description="برای این نسخه هنوز Sprint منتشرشده‌ای در دسترس نیست."
      />
    )
  }

  return (
    <div className="project-detail__sprint-list">
      {project.sprint_templates.map((sprint) => {
        const expanded = expandedSprintIds.has(sprint.id)
        const panelId = `sprint-panel-${sprint.id}`
        const triggerId = `sprint-trigger-${sprint.id}`
        const groups = sprintWorkGroups(project, sprint)

        return (
          <article className="project-detail__sprint" key={sprint.id}>
            <button
              className="project-detail__sprint-trigger"
              id={triggerId}
              type="button"
              aria-controls={panelId}
              aria-expanded={expanded}
              onClick={() => toggleSprint(sprint.id)}
            >
              <span className="project-detail__sprint-number" dir="ltr">
                Sprint {sprint.sequence}
              </span>
              <span className="project-detail__sprint-copy">
                <strong dir="auto">{sprint.title}</strong>
                {sprint.brief.trim() ? <span dir="auto">{sprint.brief}</span> : null}
              </span>
              <span className="project-detail__sprint-caret" aria-hidden="true">
                {expanded ? '−' : '+'}
              </span>
            </button>

            <div
              className="project-detail__sprint-panel"
              id={panelId}
              role="region"
              aria-labelledby={triggerId}
              hidden={!expanded}
            >
              {groups.length > 0 ? (
                groups.map((group) => (
                  <section className="project-detail__work-group" key={group.id}>
                    <h4 dir="auto">{group.label}</h4>
                    <ol>
                      {group.items.map((item) => (
                        <li key={item.id}>
                          <strong dir="auto">{item.title}</strong>
                          {item.description.trim() ? (
                            <p dir="auto">{item.description}</p>
                          ) : null}
                        </li>
                      ))}
                    </ol>
                  </section>
                ))
              ) : (
                <p className="project-detail__inline-empty">
                  برای این Sprint محتوای کاری مرتبطی ثبت نشده است.
                </p>
              )}
            </div>
          </article>
        )
      })}
    </div>
  )
}

function SectionHeading({
  eyebrow,
  id,
  title,
}: {
  eyebrow: string
  id: string
  title: string
}) {
  return (
    <header className="project-detail__section-heading">
      <span aria-hidden="true">{eyebrow}</span>
      <h2 id={id}>{title}</h2>
    </header>
  )
}

export function ProjectDetailPage() {
  const { projectVersionId } = useParams()
  const [loadState, setLoadState] = useState<LoadState>(initialLoadState)
  const [reloadKey, setReloadKey] = useState(0)
  const [descriptionExpanded, setDescriptionExpanded] = useState(false)

  useEffect(() => {
    if (!projectVersionId) {
      return
    }

    const controller = new AbortController()
    let active = true

    void loadProjectVersionDetail(projectVersionId, controller.signal)
      .then((project) => {
        if (active) {
          setLoadState({ status: 'success', project, error: null })
        }
      })
      .catch((error: unknown) => {
        if (active && !controller.signal.aborted) {
          setLoadState({ status: 'error', project: null, error: asError(error) })
        }
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [projectVersionId, reloadKey])

  function retry() {
    setLoadState(initialLoadState)
    setDescriptionExpanded(false)
    setReloadKey((current) => current + 1)
  }

  if (loadState.status === 'loading') {
    return (
      <div className="project-detail-page" dir="rtl">
        <div className="project-detail__state" aria-busy="true">
          <LoadingState message="در حال دریافت جزئیات نسخه پروژه..." />
        </div>
        <HomeFooter />
      </div>
    )
  }

  if (loadState.status === 'error') {
    const notFound =
      loadState.error instanceof ApiError && loadState.error.status === 404

    return (
      <div className="project-detail-page" dir="rtl">
        <div className="project-detail__state">
          {notFound ? (
            <EmptyState
              title="این نسخه پروژه در دسترس نیست"
              description="نسخه درخواستی پیدا نشد یا هنوز منتشر نشده است."
            />
          ) : (
            <Alert className="project-detail__error" tone="error">
              <h1>دریافت جزئیات پروژه ممکن نشد</h1>
              <p>{loadState.error.message}</p>
              <Button variant="secondary" onClick={retry}>
                تلاش دوباره
              </Button>
            </Alert>
          )}
          <Link className="project-detail__back-link" to="/projects">
            بازگشت به پروژه‌ها
          </Link>
        </div>
        <HomeFooter />
      </div>
    )
  }

  const project = loadState.project
  const fullDescription = project.full_description.trim()
  const descriptionIsLong =
    fullDescription.length > descriptionCollapseThreshold
  const weeklyEffort = formatWeeklyEffort(
    project.weekly_effort_hours_min,
    project.weekly_effort_hours_max,
  )
  const meta = [
    {
      label: 'سطح پروژه',
      value: `${project.project_template.level.name} · ${project.project_template.level.number}`,
      ltr: true,
    },
    project.duration_weeks !== null
      ? { label: 'مدت پروژه', value: `${project.duration_weeks} هفته` }
      : null,
    project.sprint_count !== null
      ? { label: 'تعداد Sprint', value: `${project.sprint_count} Sprint`, ltr: true }
      : null,
    weeklyEffort ? { label: 'زمان هفتگی', value: weeklyEffort } : null,
  ].filter((item): item is { label: string; value: string; ltr?: boolean } => Boolean(item))

  const prerequisiteGroups = project.role_context
    ? [
        {
          role: project.role_context.role,
          prerequisites: project.role_context.prerequisites,
        },
      ]
    : project.role_requirements
        .filter((requirement) => requirement.prerequisites.length > 0)
        .map((requirement) => ({
          role: requirement.role,
          prerequisites: requirement.prerequisites,
        }))

  return (
    <div className="project-detail-page" dir="rtl">
      <div className="project-detail__content">
        <Link className="project-detail__breadcrumb" to="/projects">
          <span aria-hidden="true">→</span>
          همه پروژه‌ها
        </Link>

        <header className="project-detail__hero">
          <div className="project-detail__hero-copy">
            <p className="project-detail__eyebrow">
              <span>جزئیات پروژه</span>
              <span dir="ltr">Version {project.version_number}</span>
            </p>
            <h1 dir="auto">{project.project_template.name}</h1>
            {project.summary.trim() ? (
              <p className="project-detail__summary" dir="auto">
                {project.summary}
              </p>
            ) : (
              <p className="project-detail__summary project-detail__summary--empty">
                خلاصه‌ای برای این نسخه ثبت نشده است.
              </p>
            )}
            <dl className="project-detail__meta">
              {meta.map((item) => (
                <div key={item.label}>
                  <dt>{item.label}</dt>
                  <dd dir={item.ltr ? 'ltr' : 'auto'}>{item.value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </header>

        <main>
          <section
            className="project-detail__section project-detail__description"
            aria-labelledby="project-description-title"
          >
            <SectionHeading
              eyebrow="01"
              id="project-description-title"
              title="توضیح پروژه"
            />
            {fullDescription ? (
              <Card className="project-detail__description-card">
                <div
                  className={
                    descriptionIsLong && !descriptionExpanded
                      ? 'project-detail__description-copy is-collapsed'
                      : 'project-detail__description-copy'
                  }
                  id="project-full-description"
                >
                  <p dir="auto">{fullDescription}</p>
                </div>
                {descriptionIsLong ? (
                  <button
                    className="project-detail__text-toggle"
                    type="button"
                    aria-controls="project-full-description"
                    aria-expanded={descriptionExpanded}
                    onClick={() => setDescriptionExpanded((current) => !current)}
                  >
                    {descriptionExpanded ? 'مشاهده کمتر' : 'مشاهده بیشتر'}
                  </button>
                ) : null}
              </Card>
            ) : (
              <EmptyState
                title="توضیح کامل ثبت نشده است"
                description="برای این نسخه محتوای تکمیلی در دسترس نیست."
              />
            )}
          </section>

          <section
            className="project-detail__section"
            aria-labelledby="project-sprints-title"
          >
            <SectionHeading
              eyebrow="02"
              id="project-sprints-title"
              title="Sprintهای پروژه"
            />
            <SprintAccordion project={project} />
          </section>

          <section
            className="project-detail__section"
            aria-labelledby="project-stacks-title"
          >
            <SectionHeading
              eyebrow="03"
              id="project-stacks-title"
              title="تکنولوژی‌ها و سیاست استک"
            />
            {project.role_requirements.length > 0 ? (
              <div className="project-detail__stack-grid">
                {project.role_requirements.map((requirement) => {
                  const policy = policyPresentation(requirement.stack_policy)
                  const roleContext =
                    project.role_context?.role.id === requirement.role.id
                      ? project.role_context
                      : null
                  const availableStacks =
                    requirement.stack_policy === 'OPEN' && roleContext
                      ? roleContext.compatible_stacks
                      : requirement.configured_stacks

                  return (
                    <Card className="project-detail__stack-card" key={requirement.id}>
                      <div className="project-detail__stack-card-heading">
                        <h3 dir="ltr">{requirement.role.name}</h3>
                        <StatusBadge status={policy.label} dir="ltr" />
                      </div>
                      <p>{policy.description}</p>
                      <StackList stacks={availableStacks} />
                      {roleContext?.selected_stack ? (
                        <p className="project-detail__selected-stack">
                          انتخاب فعلی:
                          <b dir="ltr">{roleContext.selected_stack.name}</b>
                        </p>
                      ) : null}
                      {requirement.requires_stack && availableStacks.length === 0 ? (
                        <p className="project-detail__inline-empty">
                          استک قابل نمایش برای این نقش از API دریافت نشد.
                        </p>
                      ) : null}
                    </Card>
                  )
                })}
              </div>
            ) : (
              <EmptyState
                title="سیاست استک ثبت نشده است"
                description="برای این نسخه نقش یا تنظیمات استکی در دسترس نیست."
              />
            )}
          </section>

          <section
            className="project-detail__section"
            aria-labelledby="project-roles-title"
          >
            <SectionHeading
              eyebrow="04"
              id="project-roles-title"
              title="نقش‌های تیم"
            />
            {project.role_requirements.length > 0 ? (
              <div className="project-detail__role-grid">
                {project.role_requirements.map((requirement) => {
                  const selected =
                    project.role_context?.role.id === requirement.role.id
                  return (
                    <Card className="project-detail__role-card" key={requirement.id}>
                      <div>
                        <span className="project-detail__role-mark" aria-hidden="true" />
                        <h3 dir="ltr">{requirement.role.name}</h3>
                      </div>
                      {selected ? (
                        <StatusBadge status="نقش انتخابی شما" />
                      ) : null}
                      {requirement.context.trim() ? (
                        <p dir="auto">{requirement.context}</p>
                      ) : null}
                    </Card>
                  )
                })}
              </div>
            ) : (
              <EmptyState
                title="نقشی ثبت نشده است"
                description="برای این نسخه نقش موردنیازی در دسترس نیست."
              />
            )}
          </section>

          <section
            className="project-detail__section"
            aria-labelledby="project-prerequisites-title"
          >
            <SectionHeading
              eyebrow="05"
              id="project-prerequisites-title"
              title="پیش‌نیازهای نقش"
            />
            {prerequisiteGroups.length > 0 &&
            prerequisiteGroups.some((group) => group.prerequisites.length > 0) ? (
              <div className="project-detail__prerequisite-grid">
                {prerequisiteGroups
                  .filter((group) => group.prerequisites.length > 0)
                  .map((group) => (
                    <Card
                      className="project-detail__prerequisite-card"
                      key={group.role.id}
                    >
                      <h3 dir="ltr">{group.role.name}</h3>
                      <ol>
                        {group.prerequisites.map((prerequisite) => (
                          <li key={prerequisite.id}>
                            <strong dir="auto">{prerequisite.title}</strong>
                            {prerequisite.description.trim() ? (
                              <p dir="auto">{prerequisite.description}</p>
                            ) : null}
                          </li>
                        ))}
                      </ol>
                    </Card>
                  ))}
              </div>
            ) : (
              <EmptyState
                title="پیش‌نیازی ثبت نشده است"
                description={
                  project.role_context
                    ? `برای نقش ${project.role_context.role.name} پیش‌نیازی در API ثبت نشده است.`
                    : 'برای نقش‌های این نسخه پیش‌نیازی در API ثبت نشده است.'
                }
              />
            )}
          </section>

          <section
            className="project-detail__final-cta"
            aria-labelledby="project-detail-cta-title"
          >
            <div>
              <span className="project-detail__final-kicker">PROLEARN PROJECTS</span>
              <h2 id="project-detail-cta-title">با این پروژه ادامه بده</h2>
              <p>
                برای انتخاب و تأیید Stack همین نسخه، ابتدا وارد حساب خود شو.
              </p>
            </div>
            <Link className="home-button home-button--primary" to={`/projects/${encodeURIComponent(project.id)}/stack-selection`}>
              <span className="home-button__label">ادامه با این پروژه</span>
            </Link>
          </section>
        </main>
      </div>
      <HomeFooter />
    </div>
  )
}
