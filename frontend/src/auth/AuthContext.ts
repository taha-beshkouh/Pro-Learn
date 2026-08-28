import { createContext } from 'react'
import type { CurrentUser } from '../lib/api/types'

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous' | 'error'

export type AuthContextValue = {
  status: AuthStatus
  user: CurrentUser | null
  error: Error | null
  refreshSession: () => Promise<void>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
