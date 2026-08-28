import { useEffect, useState, type PropsWithChildren } from 'react'
import { AuthContext, type AuthStatus } from './AuthContext'
import { API_ENDPOINTS } from '../lib/api/endpoints'
import { ApiError, apiClient } from '../lib/api/client'
import type { CurrentUser } from '../lib/api/types'

type AuthState = {
  status: AuthStatus
  user: CurrentUser | null
  error: Error | null
}

const initialState: AuthState = {
  status: 'loading',
  user: null,
  error: null,
}

async function resolveSession(): Promise<AuthState> {
  try {
    const user = await apiClient.get<CurrentUser>(API_ENDPOINTS.auth.me)
    return { status: 'authenticated', user, error: null }
  } catch (error) {
    if (error instanceof ApiError && [401, 403].includes(error.status)) {
      return { status: 'anonymous', user: null, error: null }
    }

    return {
      status: 'error',
      user: null,
      error: error instanceof Error ? error : new Error('Unable to resolve session.'),
    }
  }
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [state, setState] = useState<AuthState>(initialState)

  useEffect(() => {
    let active = true

    void resolveSession().then((nextState) => {
      if (active) {
        setState(nextState)
      }
    })

    return () => {
      active = false
    }
  }, [])

  async function refreshSession() {
    setState(initialState)
    setState(await resolveSession())
  }

  async function logout() {
    await apiClient.post<void>(API_ENDPOINTS.auth.logout)
    setState({ status: 'anonymous', user: null, error: null })
  }

  return (
    <AuthContext.Provider
      value={{
        ...state,
        refreshSession,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
