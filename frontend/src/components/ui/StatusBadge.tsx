import type { HTMLAttributes } from 'react'

type StatusBadgeProps = HTMLAttributes<HTMLSpanElement> & {
  status: string
}

export function StatusBadge({
  className = '',
  status,
  ...props
}: StatusBadgeProps) {
  const classes = ['status-badge', className].filter(Boolean).join(' ')
  return (
    <span className={classes} {...props}>
      {status}
    </span>
  )
}
