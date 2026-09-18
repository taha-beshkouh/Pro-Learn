import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { FaqSection } from './FaqSection'
import { faqItems } from './homeData'

function answer(index: number) {
  const region = document.getElementById(`faq-answer-${index}`)
  if (!region) throw new Error(`FAQ answer ${index} was not rendered`)
  return region
}

function expandedHeight(index: number) {
  return Number.parseFloat(answer(index).style.height)
}

describe('FAQ expansion', () => {
  beforeEach(() => {
    vi.spyOn(Element.prototype, 'scrollHeight', 'get').mockImplementation(
      function (this: Element) {
        return this.textContent?.includes(faqItems[0].answer) ? 180 : 96
      },
    )
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('starts collapsed, reveals the answer, and closes it again', () => {
    render(<FaqSection />)

    const trigger = screen.getByRole('button', { name: faqItems[0].question })
    const region = answer(0)
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(trigger).toHaveAttribute('aria-controls', region.id)
    expect(region).toHaveAttribute('aria-hidden', 'true')
    expect(region).toHaveStyle({ height: '0px' })

    fireEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(region).toHaveAttribute('aria-hidden', 'false')
    expect(region).toHaveTextContent(faqItems[0].answer)
    expect(expandedHeight(0)).toBeGreaterThan(0)

    fireEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(region).toHaveAttribute('aria-hidden', 'true')
    expect(region).toHaveStyle({ height: '0px' })
  })

  it('keeps multiple opened items visible with their own content heights', () => {
    render(<FaqSection />)

    const first = screen.getByRole('button', { name: faqItems[0].question })
    const second = screen.getByRole('button', { name: faqItems[1].question })

    fireEvent.click(first)
    fireEvent.click(second)
    expect(first).toHaveAttribute('aria-expanded', 'true')
    expect(second).toHaveAttribute('aria-expanded', 'true')
    expect(expandedHeight(0)).toBeGreaterThan(expandedHeight(1))
    expect(expandedHeight(1)).toBeGreaterThan(0)

    fireEvent.click(first)
    expect(first).toHaveAttribute('aria-expanded', 'false')
    expect(second).toHaveAttribute('aria-expanded', 'true')
    expect(answer(0)).toHaveStyle({ height: '0px' })
    expect(expandedHeight(1)).toBeGreaterThan(0)
  })
})
