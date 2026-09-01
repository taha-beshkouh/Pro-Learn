import { useEffect, useRef } from 'react'
import { roadmapSteps } from './homeData'

const roadmapPathSegments = [
  'vertical-start',
  'horizontal-first',
  'vertical-middle',
  'horizontal-second',
  'vertical-end',
  'horizontal-end',
] as const

function RoadmapPathSegments() {
  return roadmapPathSegments.map((segment) => (
    <span
      className={`roadmap-path__segment roadmap-path__segment--${segment}`}
      key={segment}
    />
  ))
}

export function HowItWorksSection() {
  const roadmapFrameRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const roadmapFrame = roadmapFrameRef.current

    if (!roadmapFrame) {
      return
    }

    const reducedMotionQuery =
      typeof window.matchMedia === 'function'
        ? window.matchMedia('(prefers-reduced-motion: reduce)')
        : null
    let animationFrameId: number | null = null

    const updateProgress = () => {
      animationFrameId = null

      if (reducedMotionQuery?.matches) {
        roadmapFrame.style.setProperty('--roadmap-progress-stop', '100%')
        return
      }

      const bounds = roadmapFrame.getBoundingClientRect()
      const viewportCenter = window.innerHeight / 2
      const progress = Math.min(
        1,
        Math.max(0, (viewportCenter - bounds.top) / Math.max(bounds.height, 1)),
      )

      roadmapFrame.style.setProperty(
        '--roadmap-progress-stop',
        `${progress * 100}%`,
      )
    }

    const queueProgressUpdate = () => {
      if (animationFrameId !== null) {
        return
      }

      if (typeof window.requestAnimationFrame === 'function') {
        animationFrameId = window.requestAnimationFrame(updateProgress)
      } else {
        updateProgress()
      }
    }

    const stepElements = Array.from(
      roadmapFrame.querySelectorAll<HTMLElement>('.roadmap-list__step'),
    )
    let stepObserver: IntersectionObserver | null = null

    if (typeof IntersectionObserver === 'function') {
      stepObserver = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            entry.target.classList.toggle('is-active', entry.isIntersecting)
          })
        },
        {
          rootMargin: '-42% 0px -42% 0px',
          threshold: 0,
        },
      )
      stepElements.forEach((step) => stepObserver?.observe(step))
    } else {
      stepElements.forEach((step) => step.classList.add('is-active'))
    }

    queueProgressUpdate()
    window.addEventListener('scroll', queueProgressUpdate, { passive: true })
    window.addEventListener('resize', queueProgressUpdate)
    reducedMotionQuery?.addEventListener('change', queueProgressUpdate)

    return () => {
      if (animationFrameId !== null) {
        window.cancelAnimationFrame(animationFrameId)
      }
      stepObserver?.disconnect()
      window.removeEventListener('scroll', queueProgressUpdate)
      window.removeEventListener('resize', queueProgressUpdate)
      reducedMotionQuery?.removeEventListener('change', queueProgressUpdate)
    }
  }, [])

  return (
    <section
      className="home-roadmap"
      id="how-it-works"
      aria-labelledby="roadmap-title"
    >
      <h2 id="roadmap-title">نقشه راه پلتفرم</h2>

      <div className="roadmap-frame" ref={roadmapFrameRef}>
        <div className="roadmap-path" aria-hidden="true">
          <div className="roadmap-path__layer roadmap-path__layer--base">
            <RoadmapPathSegments />
          </div>
          <div className="roadmap-path__progress">
            <div className="roadmap-path__layer roadmap-path__layer--active">
              <RoadmapPathSegments />
            </div>
          </div>
        </div>

        <ol className="roadmap-list">
          {roadmapSteps.map((step) => (
            <li className="roadmap-list__step" key={step.title}>
              <div className="roadmap-list__copy">
                <h3>{step.title}</h3>
                <p>{step.description}</p>
              </div>
              <img src={step.image} alt="" aria-hidden="true" />
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
