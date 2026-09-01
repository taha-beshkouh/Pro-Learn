import { Link } from 'react-router-dom'

export function HomeFooter() {
  return (
    <footer className="home-footer">
      <p className="home-footer__wordmark" dir="ltr" aria-label="PROLEARN">
        PROLEARN
      </p>
      <nav aria-label="پیوندهای پایین صفحه">
        <Link to="/projects">پروژه‌ها</Link>
        <a href="#how-it-works">مسیر پلتفرم</a>
        <a href="#roles">نقش‌ها</a>
        <a href="#faq">سوالات</a>
        <Link to="/login">ورود</Link>
        <Link to="/register">ثبت نام</Link>
      </nav>
    </footer>
  )
}
