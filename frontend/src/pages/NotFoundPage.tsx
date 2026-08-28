import { Card } from '../components/ui/Card'

export function NotFoundPage() {
  return (
    <section className="placeholder-page" aria-labelledby="page-title">
      <h1 id="page-title">Page not found</h1>
      <Card>
        <p>The requested frontend route does not exist.</p>
      </Card>
    </section>
  )
}
