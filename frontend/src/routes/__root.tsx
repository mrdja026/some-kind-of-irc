import { useEffect, useMemo } from 'react'
import { HeadContent, Scripts, createRootRoute, useRouterState } from '@tanstack/react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { TanStackRouterDevtoolsPanel } from '@tanstack/react-router-devtools'
import { TanStackDevtools } from '@tanstack/react-devtools'

import appCss from '../styles.css?url'

const BUILD_ID = import.meta.env.VITE_BUILD_ID || ''

export const Route = createRootRoute({
  head: () => ({
    meta: [
      {
        charSet: 'utf-8',
      },
      {
        name: 'viewport',
        content: 'width=device-width, initial-scale=1, maximum-scale=5.0, user-scalable=yes, viewport-fit=cover',
      },
      {
        title: 'TanStack Start Starter',
      },
      ...(BUILD_ID
        ? [
            {
              name: 'build-id',
              content: BUILD_ID,
            },
          ]
        : []),
    ],
    links: [
      {
        rel: 'stylesheet',
        href: appCss,
      },
    ],
  }),

  shellComponent: RootDocument,
})

function RootDocument({ children }: { children: React.ReactNode }) {
  // QueryClient should be created per-request for SSR
  const queryClient = useMemo(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            gcTime: 5 * 60_000,
          },
        },
      }),
    [],
  )

  const locationSearch = useRouterState({
    select: (state) => state.location.searchStr ?? state.location.search,
  })

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    let debugValue: string | null = null

    if (typeof locationSearch === 'string') {
      const params = new URLSearchParams(locationSearch)
      if (params.has('debug')) {
        debugValue = params.get('debug')
      }
    } else if (locationSearch && typeof locationSearch === 'object') {
      const value = (locationSearch as Record<string, unknown>).debug
      if (value !== undefined && value !== null) {
        debugValue = String(value)
      }
    }

    if (debugValue === null) {
      return
    }

    const normalized = debugValue.toLowerCase()
    const enableValues = new Set(['1', 'true', 'on', 'yes'])
    const disableValues = new Set(['0', 'false', 'off', 'no'])

    if (enableValues.has(normalized)) {
      window.localStorage.setItem('debug', '1')
    }

    if (disableValues.has(normalized)) {
      window.localStorage.removeItem('debug')
    }
  }, [locationSearch])

  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        <QueryClientProvider client={queryClient}>
          {children}
          <TanStackDevtools
            config={{
              position: 'bottom-right',
            }}
            plugins={[
              {
                name: 'Tanstack Router',
                render: <TanStackRouterDevtoolsPanel />,
              },
            ]}
          />
        </QueryClientProvider>
        <Scripts />
      </body>
    </html>
  )
}
