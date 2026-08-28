import type { PropsWithChildren } from 'react'
import { AuthProvider } from '../auth/AuthProvider'

export function AppProviders({ children }: PropsWithChildren) {
  return <AuthProvider>{children}</AuthProvider>
}
