import { useLayoutEffect, useRef, useState } from 'react'
import { faqItems } from './homeData'

export function FaqSection() {
  const [openItemIndexes, setOpenItemIndexes] = useState<Set<number>>(
    () => new Set(),
  )
  const [answerHeights, setAnswerHeights] = useState<number[]>([])
  const answerContentRefs = useRef<Array<HTMLDivElement | null>>([])

  useLayoutEffect(() => {
    function updateAnswerHeights() {
      const measuredHeights = faqItems.map(
        (_, index) => answerContentRefs.current[index]?.scrollHeight ?? 0,
      )

      setAnswerHeights((currentHeights) => {
        const measurementsAreCurrent =
          currentHeights.length === measuredHeights.length &&
          currentHeights.every(
            (height, index) => height === measuredHeights[index],
          )

        return measurementsAreCurrent ? currentHeights : measuredHeights
      })
    }

    updateAnswerHeights()
    window.addEventListener('resize', updateAnswerHeights)

    const answerResizeObserver =
      typeof ResizeObserver === 'function'
        ? new ResizeObserver(updateAnswerHeights)
        : null

    answerContentRefs.current.forEach((answer) => {
      if (answer) {
        answerResizeObserver?.observe(answer)
      }
    })

    return () => {
      answerResizeObserver?.disconnect()
      window.removeEventListener('resize', updateAnswerHeights)
    }
  }, [])

  function toggleItem(index: number) {
    const isOpening = !openItemIndexes.has(index)

    if (isOpening) {
      const measuredHeight = answerContentRefs.current[index]?.scrollHeight ?? 0

      setAnswerHeights((currentHeights) => {
        const nextHeights = [...currentHeights]
        nextHeights[index] = measuredHeight
        return nextHeights
      })
    }

    setOpenItemIndexes((currentIndexes) => {
      const nextIndexes = new Set(currentIndexes)

      if (nextIndexes.has(index)) {
        nextIndexes.delete(index)
      } else {
        nextIndexes.add(index)
      }

      return nextIndexes
    })
  }

  return (
    <section className="home-faq" id="faq" aria-labelledby="faq-title">
      <div className="home-faq__intro">
        <h2 id="faq-title">سوالات متداول درباره پلتفرم</h2>
      </div>
      <div className="faq-list">
        {faqItems.map((item, index) => {
          const isOpen = openItemIndexes.has(index)
          const triggerId = `faq-trigger-${index}`
          const answerId = `faq-answer-${index}`

          return (
            <article
              className={`faq-list__item${isOpen ? ' faq-list__item--open' : ''}`}
              key={item.question}
            >
              <h3 className="faq-list__heading">
                <button
                  className="faq-list__trigger"
                  id={triggerId}
                  type="button"
                  aria-expanded={isOpen}
                  aria-controls={answerId}
                  onClick={() => toggleItem(index)}
                >
                  <span>{item.question}</span>
                  <span className="faq-list__symbol" aria-hidden="true">
                    +
                  </span>
                </button>
              </h3>
              <div
                className="faq-list__answer"
                id={answerId}
                role="region"
                aria-labelledby={triggerId}
                aria-hidden={!isOpen}
                style={{ height: isOpen ? `${answerHeights[index] ?? 0}px` : '0px' }}
              >
                <div
                  className="faq-list__answer-inner"
                  ref={(element) => {
                    answerContentRefs.current[index] = element
                  }}
                >
                  <p>{item.answer}</p>
                </div>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}
