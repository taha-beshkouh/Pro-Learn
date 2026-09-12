import { NavLink, Outlet } from 'react-router-dom'
import { SessionActions } from '../auth/SessionActions'

export function PublicLayout() {
  return (
    <div className="site-shell">
      <header className="site-header public-header">
        <NavLink className="brand" to="/" aria-label="PROLEARN home">
          <span className="brand-mark" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <span>PROLEARN</span>
        </NavLink>
        <nav className="site-nav public-nav" aria-label="ناوبری عمومی">
          <a href="/#roles">SKILLS</a>
          <NavLink to="/projects">PROJECTS</NavLink>
          <a href="/#how-it-works">WHAT IS PROLEARN</a>
        </nav>
        <nav className="public-header__actions" aria-label="دسترسی سریع">
          <SessionActions />
          <NavLink className="public-header__cta" to="/projects">
            دیدن پروژه‌ها
          </NavLink>
        </nav>
      </header>
      <main className="page-container">
        <Outlet />
      </main>
    </div>
  )
}
