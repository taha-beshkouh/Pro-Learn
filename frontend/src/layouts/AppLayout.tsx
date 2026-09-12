import { NavLink, Outlet } from 'react-router-dom'
import { SessionActions } from '../auth/SessionActions'

export function AppLayout() {
  return (
    <div className="site-shell">
      <header className="site-header">
        <NavLink className="brand" to="/dashboard" aria-label="PROLEARN dashboard">
          PROLEARN
        </NavLink>
        <nav className="site-nav" aria-label="Participant navigation">
          <NavLink to="/dashboard">Dashboard</NavLink>
          <NavLink to="/workspace">Workspace</NavLink>
          <NavLink to="/projects">Projects</NavLink>
        </nav>
        <SessionActions />
      </header>
      <main className="page-container">
        <Outlet />
      </main>
    </div>
  )
}
