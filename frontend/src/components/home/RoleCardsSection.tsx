import { useRef, useState, type MouseEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/useAuth'
import { isMissingSession } from '../../lib/api/auth'
import {
  roleSelectionErrorMessage,
  selectRoleFromHome,
  type MvpRoleCode,
  type RoleSelectionNavigationState,
} from '../../lib/api/roleSelection'
import { Alert } from '../ui/Alert'
import ctaBrush from '../../assets/home/cta.svg'
import backendIcon from '../../assets/home/skills-icon-backend.svg'
import checkIcon from '../../assets/home/skills-check.svg'
import cardFrame from '../../assets/home/skills-card-frame.svg'
import frontendIcon from '../../assets/home/skills-icon-frontend.svg'
import productIcon from '../../assets/home/skills-icon-product.svg'

const roleCards = [
  {
    id: 'frontend',
    code: 'FRONTEND_DEVELOPER' as MvpRoleCode,
    title: 'Front-end developer',
    titleLines: ['Front-end', 'developer'],
    icon: frontendIcon,
    skills: [
      'رابط کاربری',
      'اتصال به API',
      'Responsive UI',
      'فرم‌ها و State',
      'تجربه کاربر',
      'تعاملات کاربری',
    ],
  },
  {
    id: 'product',
    code: 'PRODUCT_DESIGNER' as MvpRoleCode,
    title: 'Product Designer',
    titleLines: ['Product', 'Designer'],
    icon: productIcon,
    skills: [
      'تحلیل مسئله',
      'User Flow',
      'وایرفریم',
      'Design System',
      'تجربه کاربر',
      'تحویل طراحی',
    ],
  },
  {
    id: 'backend',
    code: 'BACKEND_DEVELOPER' as MvpRoleCode,
    title: 'Back-end developer',
    titleLines: ['Back-end', 'developer'],
    icon: backendIcon,
    skills: [
      'طراحی API',
      'دیتابیس',
      'احراز هویت',
      'سطح دسترسی',
      'منطق بک‌اند',
      'تست و امنیت',
    ],
  },
] as const

const roleHelper =
  'بعد از انتخاب، پروژه‌های مناسب این مسیر بهت پیشنهاد می‌شن.'

export function RoleCardsSection() {
  const auth = useAuth()
  const navigate = useNavigate()
  const busy = useRef(false)
  const [pendingRole, setPendingRole] = useState<MvpRoleCode | null>(null)
  const [error, setError] = useState('')

  async function selectRole(
    event: MouseEvent<HTMLAnchorElement>,
    code: MvpRoleCode,
  ) {
    event.preventDefault()
    if (busy.current || auth.status === 'loading') return
    if (auth.status === 'error') {
      setError(roleSelectionErrorMessage(auth.error))
      void auth.refreshSession()
      return
    }

    if (auth.status !== 'authenticated' && auth.status !== 'anonymous') return

    busy.current = true
    setPendingRole(code)
    setError('')

    try {
      await selectRoleFromHome(auth.status, code)
      const state: RoleSelectionNavigationState = {
        roleSelection: { roleCode: code },
      }
      navigate('/projects', { state })
    } catch (cause) {
      setError(roleSelectionErrorMessage(cause))
      if (isMissingSession(cause)) void auth.refreshSession()
    } finally {
      busy.current = false
      setPendingRole(null)
    }
  }

  const selectionPending = pendingRole !== null || auth.status === 'loading'

  return (
    <section className="home-roles" id="roles" aria-labelledby="roles-title">
      <h2 id="roles-title">
        با انتخاب یکی از نقش‌های زیر
        <span>به پروژه‌های مختلف دست پیدا کن</span>
      </h2>
      {error && (
        <Alert className="home-roles__error" tone="error">
          {error}
        </Alert>
      )}

      <div className="role-card-grid">
        {roleCards.map((role) => (
          <article
            className={`role-card role-card--${role.id}${
              pendingRole === role.code ? ' is-pending' : ''
            }`}
            key={role.id}
          >
            <Link
              className="role-card__link"
              to="/projects"
              aria-busy={pendingRole === role.code}
              aria-disabled={selectionPending}
              onClick={(event) => void selectRole(event, role.code)}
              aria-label={`${role.title} - دیدن پروژه‌ها`}
            >
              <img className="role-card__frame" src={cardFrame} alt="" />
              <img className="role-card__icon" src={role.icon} alt="" />
              <h3 dir="ltr" aria-label={role.title}>
                {role.titleLines.map((line) => (
                  <span key={line}>{line}</span>
                ))}
              </h3>

              <div className="role-card__skills">
                <p className="role-card__skills-title">در پروژه تقویت می‌کنی:</p>
                <ul>
                  {role.skills.map((skill) => (
                    <li key={skill}>
                      <img src={checkIcon} alt="" aria-hidden="true" />
                      <span>{skill}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="role-card__footer">
                <span className="role-card__cta">
                  <span className="role-card__cta-fill" aria-hidden="true" />
                  <img src={ctaBrush} alt="" aria-hidden="true" />
                  <span className="role-card__cta-label">
                    {pendingRole === role.code
                      ? 'در حال انتخاب...'
                      : 'دیدن پروژه‌ها'}
                  </span>
                </span>
                <span className="role-card__helper">{roleHelper}</span>
              </div>
            </Link>
          </article>
        ))}
      </div>
    </section>
  )
}
