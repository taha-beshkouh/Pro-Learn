import { use } from 'react'
import { AuthContext } from './AuthContext'

export function useAuth() {
  const context = use(AuthContext)

  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider.')
  }

  return context
}
