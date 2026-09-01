import { Link } from 'react-router-dom'

export function FinalCtaSection() {
  return (
    <section className="home-final-cta" aria-labelledby="final-cta-title">
      <div className="home-final-cta__copy">
        <h2 id="final-cta-title">پروژه بعدیت رو تنها نساز</h2>
        <p>
          چیزی که بلدی رو این بار کنار یک تیم، روی یک محصول مشترک تجربه کن.
          <span>آمادگی‌ات را کامل کن و قدم بعدی را با یک تیم واقعی‌تر بردار.</span>
        </p>
      </div>
      <div className="home-final-cta__action">
        <Link className="home-button home-button--primary" to="/projects">
          <span className="home-button__label">دیدن پروژه‌ها</span>
        </Link>
      </div>
    </section>
  )
}
