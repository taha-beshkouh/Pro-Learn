import { Link } from 'react-router-dom'
import heroArtwork from '../../assets/home/hero-chalkboard.png'

export function HeroSection() {
  return (
    <section className="home-hero" aria-labelledby="home-title">
      <img
        className="home-hero__art"
        src={heroArtwork}
        alt=""
        aria-hidden="true"
      />
      <div className="home-hero__content">
        <h1 id="home-title">
          <span>کشف کن</span>
          <span>متصل شو</span>
          <span>خلق کن</span>
        </h1>
        <p className="home-hero__lead">
          مسیر تبدیل مهارت به تجربه واقعی از اینجا شروع می‌شود
        </p>
        <div className="home-actions">
          <Link className="home-button home-button--primary" to="/projects">
            <span className="home-button__label">دیدن پروژه‌ها</span>
          </Link>
          <a className="home-button home-button--ghost" href="#how-it-works">
            <span className="home-button__label">مسیر پلتفرم</span>
          </a>
        </div>
      </div>
    </section>
  )
}
