import { Card } from './Card'

type EmptyStateProps = {
  title: string
  description: string
}

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <Card className="state-panel">
      <h2>{title}</h2>
      <p>{description}</p>
    </Card>
  )
}
