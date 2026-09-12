type ProjectCatalogPaginationProps = {
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
}

type PaginationItem = number | 'start-gap' | 'end-gap'

function paginationItems(currentPage: number, totalPages: number) {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1)
  }

  const visiblePages = new Set([1, totalPages, currentPage - 1, currentPage, currentPage + 1])
  if (currentPage <= 4) {
    for (let page = 1; page <= 5; page += 1) {
      visiblePages.add(page)
    }
  }
  if (currentPage >= totalPages - 3) {
    for (let page = totalPages - 4; page <= totalPages; page += 1) {
      visiblePages.add(page)
    }
  }

  const pages = [...visiblePages]
    .filter((page) => page >= 1 && page <= totalPages)
    .sort((left, right) => left - right)
  const items: PaginationItem[] = []
  for (const page of pages) {
    const previous = items.at(-1)
    if (typeof previous === 'number' && page - previous > 1) {
      items.push(previous === 1 ? 'start-gap' : 'end-gap')
    }
    items.push(page)
  }
  return items
}

export function ProjectCatalogPagination({
  currentPage,
  totalPages,
  onPageChange,
}: ProjectCatalogPaginationProps) {
  const items = paginationItems(currentPage, totalPages)

  return (
    <nav className="project-catalog-pagination" aria-label="صفحه‌بندی پروژه‌ها">
      <button
        type="button"
        disabled={currentPage === 1}
        onClick={() => onPageChange(currentPage - 1)}
      >
        <span aria-hidden="true">&#8592;</span>
        Previous
      </button>

      <div className="project-catalog-pagination__pages">
        {items.map((item) =>
          typeof item === 'number' ? (
            <button
              type="button"
              className={item === currentPage ? 'is-current' : undefined}
              aria-current={item === currentPage ? 'page' : undefined}
              aria-label={`صفحه ${item}`}
              onClick={() => onPageChange(item)}
              key={item}
            >
              {item}
            </button>
          ) : (
            <span aria-hidden="true" key={item}>
              ...
            </span>
          ),
        )}
      </div>

      <button
        type="button"
        disabled={currentPage === totalPages}
        onClick={() => onPageChange(currentPage + 1)}
      >
        Next
        <span aria-hidden="true">&#8594;</span>
      </button>
    </nav>
  )
}
