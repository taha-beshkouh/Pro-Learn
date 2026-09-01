import { Link } from 'react-router-dom'
import ctaBrush from '../../assets/home/cta.svg'
import backendIcon from '../../assets/home/skills-icon-backend.svg'
import checkIcon from '../../assets/home/skills-check.svg'
import cardFrame from '../../assets/home/skills-card-frame.svg'
import frontendIcon from '../../assets/home/skills-icon-frontend.svg'
import productIcon from '../../assets/home/skills-icon-product.svg'

const roleCards = [
  {
    id: 'frontend',
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
  return (
    <section className="home-roles" id="roles" aria-labelledby="roles-title">
      <h2 id="roles-title">
        با انتخاب یکی از نقش‌های زیر
        <span>به پروژه‌های مختلف دست پیدا کن</span>
      </h2>

      <div className="role-card-grid">
        {roleCards.map((role) => (
          <article className={`role-card role-card--${role.id}`} key={role.id}>
            <Link
              className="role-card__link"
              to="/projects"
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
                  <span className="role-card__cta-label">دیدن پروژه‌ها</span>
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
