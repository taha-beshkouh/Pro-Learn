import type { ProjectLevel } from '../../lib/api/types'

type ProjectCatalogToolbarProps = {
  disabled: boolean
  levels: ProjectLevel[]
  levelNumber: number | null
  resultCount: number
  searchTerm: string
  onLevelChange: (levelNumber: number | null) => void
  onSearchChange: (value: string) => void
}

export function ProjectCatalogToolbar({
  disabled,
  levels,
  levelNumber,
  resultCount,
  searchTerm,
  onLevelChange,
  onSearchChange,
}: ProjectCatalogToolbarProps) {
  return (
    <form
      className="project-catalog-toolbar"
      role="search"
      onSubmit={(event) => event.preventDefault()}
    >
      <label className="project-catalog-toolbar__search">
        <span>جست‌وجوی پروژه</span>
        <input
          type="search"
          value={searchTerm}
          disabled={disabled}
          placeholder="نام یا خلاصه پروژه"
          onChange={(event) => onSearchChange(event.target.value)}
        />
      </label>

      <label className="project-catalog-toolbar__level">
        <span>سطح پروژه</span>
        <select
          value={levelNumber ?? ''}
          disabled={disabled}
          onChange={(event) =>
            onLevelChange(
              event.target.value ? Number(event.target.value) : null,
            )
          }
        >
          <option value="">همه سطح‌ها</option>
          {levels.map((level) => (
            <option value={level.number} key={level.id}>
              {level.name}
            </option>
          ))}
        </select>
      </label>

      <p className="project-catalog-toolbar__count" aria-live="polite">
        {resultCount.toLocaleString('fa-IR')} پروژه
      </p>
    </form>
  )
}
