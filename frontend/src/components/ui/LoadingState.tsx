type LoadingStateProps = {
  message?: string
}

export function LoadingState({
  message = 'Loading session...',
}: LoadingStateProps) {
  return (
    <div className="state-panel" role="status" aria-live="polite">
      <span className="state-panel__marker" aria-hidden="true" />
      <p>{message}</p>
    </div>
  )
}
