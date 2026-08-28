import type { HTMLAttributes } from 'react'

type AlertTone = 'info' | 'error' | 'success'

type AlertProps = HTMLAttributes<HTMLDivElement> & {
  tone?: AlertTone
}

export function Alert({
  className = '',
  role = 'alert',
  tone = 'info',
  ...props
}: AlertProps) {
  const classes = ['alert', `alert--${tone}`, className]
    .filter(Boolean)
    .join(' ')
  return <div className={classes} role={role} {...props} />
}
