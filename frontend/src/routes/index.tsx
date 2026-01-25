import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useEffect } from 'react'

export const Route = createFileRoute('/')({
  ssr: true,
  headers: () => ({
    'Cache-Control': 'public, max-age=3600', // Static redirect page
  }),
  component: HomePage,
})

function HomePage() {
  const navigate = useNavigate()

  useEffect(() => {
    navigate({ to: '/login' })
  }, [navigate])

  return null
}
