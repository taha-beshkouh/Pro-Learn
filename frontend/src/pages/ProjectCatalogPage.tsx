import { useCallback, useDeferredValue, useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { HomeFooter } from '../components/home/HomeFooter'
import { ProjectCatalogCard } from '../components/projects/ProjectCatalogCard'
import { ProjectCatalogPagination } from '../components/projects/ProjectCatalogPagination'
import { ProjectCatalogToolbar } from '../components/projects/ProjectCatalogToolbar'
import { Alert } from '../components/ui/Alert'
import { EmptyState } from '../components/ui/EmptyState'
import { LoadingState } from '../components/ui/LoadingState'
import { RoleSelectionToast } from '../components/ui/RoleSelectionToast'
import {
  loadProjectCatalog,
  type ProjectCatalogResult,
} from '../lib/api/catalog'
import { roleSelectionNoticeFromState } from '../lib/api/roleSelection'
import '../styles/catalog.css'

const PAGE_SIZE = 6

type LoadStatus = 'loading' | 'success' | 'error'

const emptyCatalog: ProjectCatalogResult = {
  levels: [],
  projects: [],
  selectedRole: null,
}

function asError(error: unknown) {
  return error instanceof Error
    ? error
    : new Error('Unable to load the project catalog.')
}

export function ProjectCatalogPage() {
  const auth = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [roleSelectionNotice, setRoleSelectionNotice] = useState(() =>
    roleSelectionNoticeFromState(location.state),
  )
  const [catalog, setCatalog] = useState(emptyCatalog)
  const [status, setStatus] = useState<LoadStatus>('loading')
  const [error, setError] = useState<Error | null>(null)
  const [levelNumber, setLevelNumber] = useState<number | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [reloadKey, setReloadKey] = useState(0)
  const deferredSearchTerm = useDeferredValue(searchTerm)
  const dismissRoleSelectionNotice = useCallback(
    () => setRoleSelectionNotice(null),
    [],
  )

  useEffect(() => {
    if (!roleSelectionNotice || location.state === null) return

    void navigate(
      {
        pathname: location.pathname,
        search: location.search,
        hash: location.hash,
      },
      { replace: true, state: null },
    )
  }, [
    location.hash,
    location.pathname,
    location.search,
    location.state,
    navigate,
    roleSelectionNotice,
  ])

  useEffect(() => {
    if (auth.status === 'loading' || auth.status === 'error') {
      return
    }

    const controller = new AbortController()
    let active = true

    void loadProjectCatalog({
      authStatus: auth.status,
      levelNumber,
      signal: controller.signal,
    })
      .then((result) => {
        if (!active) {
          return
        }
        setCatalog(result)
        setError(null)
        setStatus('success')
      })
      .catch((loadError: unknown) => {
        if (!active || controller.signal.aborted) {
          return
        }
        setError(asError(loadError))
        setStatus('error')
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [auth.status, levelNumber, reloadKey])

  const normalizedSearch = deferredSearchTerm.trim().toLocaleLowerCase('fa-IR')
  const filteredProjects = catalog.projects.filter((project) => {
    if (!normalizedSearch) {
      return true
    }
    return `${project.name} ${project.summary}`
      .toLocaleLowerCase('fa-IR')
      .includes(normalizedSearch)
  })
  const totalPages = Math.max(1, Math.ceil(filteredProjects.length / PAGE_SIZE))
  const safePage = Math.min(currentPage, totalPages)
  const visibleProjects = filteredProjects.slice(
    (safePage - 1) * PAGE_SIZE,
    safePage * PAGE_SIZE,
  )
  const loading =
    auth.status === 'loading' ||
    (auth.status !== 'error' && status === 'loading')
  const pageError = auth.status === 'error' ? auth.error : error

  function handleSearchChange(value: string) {
    setSearchTerm(value)
    setCurrentPage(1)
  }

  function handleLevelChange(nextLevel: number | null) {
    setLevelNumber(nextLevel)
    setCurrentPage(1)
    setStatus('loading')
  }

  function handlePageChange(page: number) {
    setCurrentPage(page)
    document.querySelector('.project-catalog__results')?.scrollIntoView?.({
      behavior: 'auto',
      block: 'start',
    })
  }

  function handleRetry() {
    setStatus('loading')
    if (auth.status === 'error') {
      void auth.refreshSession()
      return
    }
    setReloadKey((value) => value + 1)
  }

  return (
    <div className="project-catalog-page" dir="rtl">
      {roleSelectionNotice ? (
        <RoleSelectionToast
          roleLabel={roleSelectionNotice.roleLabel}
          onDismiss={dismissRoleSelectionNotice}
        />
      ) : null}
      <section className="project-catalog__content" aria-labelledby="catalog-title">
        <header className="project-catalog__intro">
          <h1 id="catalog-title">
            {catalog.selectedRole
              ? `پروژه‌های مناسب نقش ${catalog.selectedRole.name}`
              : 'پروژه‌های منتشرشده PROLEARN'}
          </h1>
        </header>

        <ProjectCatalogToolbar
          disabled={loading}
          levels={catalog.levels}
          levelNumber={levelNumber}
          resultCount={filteredProjects.length}
          searchTerm={searchTerm}
          onLevelChange={handleLevelChange}
          onSearchChange={handleSearchChange}
        />

        <div className="project-catalog__results" aria-busy={loading}>
          {loading ? (
            <LoadingState message="در حال دریافت پروژه‌های منتشرشده..." />
          ) : null}

          {!loading && pageError ? (
            <Alert className="project-catalog__error" tone="error">
              <h2>دریافت پروژه‌ها ممکن نشد</h2>
              <p>{pageError.message}</p>
              <button type="button" onClick={handleRetry}>
                تلاش دوباره
              </button>
            </Alert>
          ) : null}

          {!loading && !pageError && filteredProjects.length === 0 ? (
            <EmptyState
              title="پروژه‌ای پیدا نشد"
              description={
                searchTerm
                  ? 'عبارت جست‌وجو یا سطح انتخاب‌شده را تغییر بده.'
                  : 'در حال حاضر پروژه منتشرشده‌ای برای این مسیر وجود ندارد.'
              }
            />
          ) : null}

          {!loading && !pageError && visibleProjects.length > 0 ? (
            <>
              <div className="project-catalog-grid">
                {visibleProjects.map((project) => (
                  <ProjectCatalogCard project={project} key={project.versionId} />
                ))}
              </div>
              <ProjectCatalogPagination
                currentPage={safePage}
                totalPages={totalPages}
                onPageChange={handlePageChange}
              />
            </>
          ) : null}
        </div>
      </section>
      <HomeFooter />
    </div>
  )
}
