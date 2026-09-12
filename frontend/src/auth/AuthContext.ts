import { createContext } from 'react'
import type { CurrentUser } from '../lib/api/types'
import type { Credentials } from '../lib/api/auth'

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous' | 'error'

export type AuthContextValue = {
  status: AuthStatus
  user: CurrentUser | null
  error: Error | null
  refreshSession: () => Promise<void>
  logout: () => Promise<void>
  authenticate: (mode: 'login' | 'register', credentials: Credentials) => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
