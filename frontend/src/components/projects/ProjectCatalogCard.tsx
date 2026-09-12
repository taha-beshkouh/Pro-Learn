import { Link } from 'react-router-dom'
import catalogCardArtwork from '../../assets/home/PROJECT_CATALOG_CARD.svg'
import type { ProjectCatalogEntry } from '../../lib/api/types'

type ProjectCatalogCardProps = {
  project: ProjectCatalogEntry
}

const designRoleLabels = ['backend', 'frontend', 'product design']

function levelMarker(levelNumber: number) {
  return ['I', 'II', 'III'][levelNumber - 1] ?? String(levelNumber)
}

export function ProjectCatalogCard({ project }: ProjectCatalogCardProps) {
  const summary =
    project.summary.trim() ||
    'یک سیستم ساده مدیریت درخواست‌های پشتیبانی که در آن کاربران می‌توانند درخواست ثبت کنند و Agentها درخواست‌ها را دریافت، پیگیری و تا حل‌شدن مدیریت کنند.'

  return (
    <article className="project-catalog-card">
      <Link
        className="project-catalog-card__link"
        to={`/projects/${encodeURIComponent(project.versionId)}`}
        aria-label={`مشاهده جزئیات پروژه ${project.name}`}
      >
        <header className="project-catalog-card__header">
          <h2 dir="auto">{project.name}</h2>
          <div className="project-catalog-card__meta">
            <span className="project-catalog-card__level">
              <span aria-hidden="true">{levelMarker(project.level.number)}</span>
              <span dir="auto">{project.level.name}</span>
            </span>
            {project.durationWeeks !== null ? (
              <>
                <span className="project-catalog-card__divider" aria-hidden="true" />
                <span className="project-catalog-card__duration">
                  <span className="project-catalog-card__clock" aria-hidden="true" />
                  {project.durationWeeks} هفته
                </span>
              </>
            ) : null}
          </div>
        </header>

        <div className="project-catalog-card__body">
          <div className="project-catalog-card__visual" aria-hidden="true">
            <img src={catalogCardArtwork} alt="" />
          </div>
          <div className="project-catalog-card__summary">
            <h3>خلاصه پروژه</h3>
            <p dir="auto">{summary}</p>
          </div>
        </div>

        <div className="project-catalog-card__roles">
          <span className="project-catalog-card__roles-label">تشکیل شده از:</span>
          <div className="project-catalog-card__role-list" aria-label="نقش‌های پروژه">
            {designRoleLabels.map((role) => (
              <span className="project-catalog-card__role" dir="ltr" key={role}>
                {role}
              </span>
            ))}
          </div>
        </div>

        <footer className="project-catalog-card__footer">
          <span className="project-catalog-card__hint">
            <span aria-hidden="true">&#8592;</span>
            مشاهده جزئیات پروژه
          </span>
        </footer>
      </Link>
    </article>
  )
}
