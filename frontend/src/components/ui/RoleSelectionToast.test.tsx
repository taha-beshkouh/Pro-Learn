import { useState } from 'react'
import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { RoleSelectionToast } from './RoleSelectionToast'

afterEach(() => {
  vi.useRealTimers()
})

describe('RoleSelectionToast', () => {
  it('shows the selected role, tracks five seconds, and removes itself', () => {
    vi.useFakeTimers()
    const onDismiss = vi.fn()

    function ToastHarness() {
      const [visible, setVisible] = useState(true)
      return visible ? (
        <RoleSelectionToast
          roleLabel="Front-end Developer"
          onDismiss={() => {
            onDismiss()
            setVisible(false)
          }}
        />
      ) : null
    }

    const { container } = render(
      <ToastHarness />,
    )

    expect(screen.getByRole('status')).toHaveTextContent(
      'نقش Front-end Developer انتخاب شد',
    )
    expect(screen.getByTestId('role-selection-toast-progress')).toBeVisible()
    expect(screen.getByRole('status')).toHaveStyle(
      '--role-toast-duration: 5000ms',
    )

    act(() => vi.advanceTimersByTime(4_820))
    expect(container.querySelector('.role-selection-toast')).toHaveClass(
      'is-exiting',
    )
    expect(onDismiss).not.toHaveBeenCalled()

    act(() => vi.advanceTimersByTime(180))
    expect(onDismiss).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
