import { useEffect, useRef } from 'react'

const whyUsItems = [
  {
    id: 'start',
    title: 'از جایی شروع کن که مناسب توست',
    description:
      'توانایی‌هایت را بشناس، جایگاهت را انتخاب کن و در مسیری قدم بگذار که هم شدنی باشد و هم تو را جلو ببرد.',
  },
  {
    id: 'work',
    title: 'تجربه‌ای نزدیک به دنیای کار',
    description:
      'در یک فضای شبیه‌سازی‌شده، روی پروژه‌ای کاربردی کار می‌کنی، نقش مشخصی داری و مثل عضوی از یک گروه واقعی پیش می‌روی.',
  },
  {
    id: 'collaboration',
    title: 'رشد، میان همکاری شکل می‌گیرد',
    description:
      'هماهنگی، گفت‌وگو، مسئولیت‌پذیری و تحویل به‌موقع، تجربه‌هایی هستند که فقط در کنار دیگران به‌درستی آموخته می‌شوند.',
  },
  {
    id: 'outcome',
    title: 'چیزی بساز که از نشان‌دادنش لذت ببری',
    description:
      'گام‌به‌گام پیش برو، بازخورد بگیر و در پایان کاری داشته باش که سهم تو در آن روشن، واقعی و دیدنی باشد.',
  },
] as const

export function WhyUsSection() {
  const sectionRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const section = sectionRef.current

    if (!section) {
      return
    }

    const items = Array.from(
      section.querySelectorAll<HTMLElement>('.why-us__item'),
    )
    const reducedMotion =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches

    if (reducedMotion || typeof IntersectionObserver !== 'function') {
      items.forEach((item) => item.classList.add('is-visible'))
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) {
            return
          }

          entry.target.classList.add('is-visible')
          observer.unobserve(entry.target)
        })
      },
      {
        rootMargin: '0px 0px -12% 0px',
        threshold: 0.8,
      },
    )

    items.forEach((item) => observer.observe(item))

    return () => observer.disconnect()
  }, [])

  return (
    <section
      className="home-why-us"
      aria-labelledby="why-us-title"
      ref={sectionRef}
    >
      <h2 className="sr-only" id="why-us-title">
        چرا PROLEARN؟
      </h2>
      <div className="why-us__canvas">
        {whyUsItems.map((item) => (
          <article
            className={`why-us__item why-us__item--${item.id}`}
            key={item.id}
          >
            <span className="why-us__art" aria-hidden="true" />
            <h3 className="why-us__title">{item.title}</h3>
            <p className="why-us__description">{item.description}</p>
          </article>
        ))}
      </div>
    </section>
  )
}
