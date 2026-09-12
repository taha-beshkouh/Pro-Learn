import { Link } from 'react-router-dom'
import { Alert } from '../components/ui/Alert'
import type { ContinuationResult } from '../lib/api/auth'

export function ContinuationNotice({ result }: { result: ContinuationResult }) {
  return <div className="auth-notice" dir="rtl">
    {result.message && <Alert tone="info">{result.message}</Alert>}
    {result.projectVersionId && <Link to={`/projects/${encodeURIComponent(result.projectVersionId)}`}>مشاهده همان نسخه پروژه</Link>}
    {result.destination && <Link to={result.destination}>{result.destination === '/dashboard' ? 'مشاهده پروژه فعال' : 'مشاهده Ready Check'}</Link>}
    <Link to="/projects">دیدن پروژه‌ها</Link>
  </div>
}
