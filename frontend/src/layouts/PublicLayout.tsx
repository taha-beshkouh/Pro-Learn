import { NavLink, Outlet } from 'react-router-dom'

export function PublicLayout() {
  return (
    <div className="site-shell">
      <header className="site-header">
        <NavLink className="brand" to="/" aria-label="PROLEARN home">
          PROLEARN
        </NavLink>
        <nav className="site-nav" aria-label="Public navigation">
          <NavLink to="/projects">Projects</NavLink>
          <NavLink to="/login">Login</NavLink>
          <NavLink to="/register">Register</NavLink>
        </nav>
      </header>
      <main className="page-container">
        <Outlet />
      </main>
    </div>
  )
}
