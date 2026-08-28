import type { createAppRouter } from './app/router'
import { appRouter } from './app/router'
import { AppProviders } from './app/providers'
import { RouterProvider } from 'react-router-dom'

type AppProps = {
  router?: ReturnType<typeof createAppRouter>
}

function App({ router = appRouter }: AppProps) {
  return (
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  )
}

export default App
