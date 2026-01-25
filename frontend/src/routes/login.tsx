import { useState } from 'react'
import { useNavigate, redirect } from '@tanstack/react-router'
import { createFileRoute } from '@tanstack/react-router'
import { login, register } from '../api'
import { getCurrentUserServer } from '../api/server'

export const Route = createFileRoute('/login')({
  ssr: true, // Full SSR for static login page
  loader: async () => {
    try {
      // Check if user is already authenticated
      await getCurrentUserServer()
      // User is authenticated, redirect to chat
      throw redirect({ to: '/chat' })
    } catch (error) {
      // If it's a redirect, re-throw it
      if (error instanceof Response || (error && typeof error === 'object' && 'to' in error)) {
        throw error
      }
      // User is not authenticated, continue to login page
      return {}
    }
  },
  headers: () => ({
    'Cache-Control': 'public, max-age=3600', // Static content, long cache
  }),
  component: LoginPage,
})

function LoginPage() {
  const navigate = useNavigate()
  const [isLogin, setIsLogin] = useState(true)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      if (isLogin) {
        await login(username, password)
      } else {
        await register(username, password)
      }

      navigate({ to: '/chat' })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center login-page px-4 py-8">
      <div className="login-card rounded-2xl p-4 sm:p-6 md:p-8 max-w-sm sm:max-w-md w-full">
        <div className="text-center mb-6 md:mb-8">
          <h1 className="text-2xl sm:text-3xl font-bold login-title mb-2">
            {isLogin ? 'Welcome Back' : 'Create Account'}
          </h1>
          <p className="login-subtitle text-sm sm:text-base">
            {isLogin
              ? 'Sign in to your IRC chat account'
              : 'Join the IRC chat community'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 md:space-y-6">
          {error && (
            <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-3 md:p-4">
              <p className="text-red-600 text-sm md:text-base">{error}</p>
            </div>
          )}

          <div>
            <label htmlFor="username" className="block text-sm font-semibold mb-2">
              Username
            </label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-3 rounded-lg transition-all login-input min-h-[44px] text-base"
              placeholder="Enter your username"
              required
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-semibold mb-2">
              Password
            </label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 rounded-lg transition-all login-input min-h-[44px] text-base"
              placeholder="Enter your password"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 font-semibold rounded-lg transition-colors login-button disabled:opacity-60 min-h-[44px] text-base"
          >
            {loading ? 'Loading...' : isLogin ? 'Sign In' : 'Sign Up'}
          </button>
        </form>

        <div className="mt-4 md:mt-6 text-center">
          <p className="login-subtitle text-sm md:text-base">
            {isLogin ? "Don't have an account?" : 'Already have an account?'}
            <button
              onClick={() => setIsLogin(!isLogin)}
              className="ml-2 font-semibold login-toggle min-h-[44px] inline-flex items-center"
            >
              {isLogin ? 'Sign Up' : 'Sign In'}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
