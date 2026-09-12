import { useEffect, useState, type CSSProperties } from 'react'

const DEFAULT_DURATION_MS = 5_000
const EXIT_DURATION_MS = 180

type ToastStyle = CSSProperties & {
  '--role-toast-duration': string
}

type RoleSelectionToastProps = {
  durationMs?: number
  onDismiss: () => void
  roleLabel: string
}

export function RoleSelectionToast({
  durationMs = DEFAULT_DURATION_MS,
  onDismiss,
  roleLabel,
}: RoleSelectionToastProps) {
  const [exiting, setExiting] = useState(false)

  useEffect(() => {
    const exitTimer = window.setTimeout(
      () => setExiting(true),
      Math.max(0, durationMs - EXIT_DURATION_MS),
    )
    const dismissTimer = window.setTimeout(onDismiss, durationMs)

    return () => {
      window.clearTimeout(exitTimer)
      window.clearTimeout(dismissTimer)
    }
  }, [durationMs, onDismiss])

  const style: ToastStyle = {
    '--role-toast-duration': `${durationMs}ms`,
  }

  return (
    <div
      className={`role-selection-toast${exiting ? ' is-exiting' : ''}`}
      role="status"
      aria-atomic="true"
      aria-live="polite"
      style={style}
    >
      <div className="role-selection-toast__content">
        <span className="role-selection-toast__mark" aria-hidden="true" />
        <p>نقش {roleLabel} انتخاب شد</p>
      </div>
      <span className="role-selection-toast__timer" aria-hidden="true">
        <span
          className="role-selection-toast__progress"
          data-testid="role-selection-toast-progress"
        />
      </span>
    </div>
  )
}
