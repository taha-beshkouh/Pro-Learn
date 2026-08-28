import { Card } from './ui/Card'
import { StatusBadge } from './ui/StatusBadge'

type PlaceholderPageProps = {
  name: string
  path: string
  purpose: string
}

export function PlaceholderPage({ name, path, purpose }: PlaceholderPageProps) {
  return (
    <section className="placeholder-page" aria-labelledby="page-title">
      <div className="placeholder-page__eyebrow">
        <StatusBadge status="Foundation placeholder" />
        <code dir="ltr">{path}</code>
      </div>
      <h1 id="page-title">{name}</h1>
      <Card>
        <h2>Route purpose</h2>
        <p>{purpose}</p>
        <p className="placeholder-page__pending">
          Real product-page implementation is pending a later frontend phase.
        </p>
      </Card>
    </section>
  )
}
