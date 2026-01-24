import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { createFileRoute } from '@tanstack/react-router'
import { login, register } from '../api'

export const Route = createFileRoute('/login')({ component: LoginPage })

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
    <div className="min-h-screen flex items-center justify-center login-page px-4">
      <div className="login-card rounded-2xl p-8 max-w-md w-full">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold login-title mb-2">
            {isLogin ? 'Welcome Back' : 'Create Account'}
          </h1>
          <p className="login-subtitle">
            {isLogin
              ? 'Sign in to your IRC chat account'
              : 'Join the IRC chat community'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {error && (
            <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-4">
              <p className="text-red-600">{error}</p>
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
              className="w-full px-4 py-3 rounded-lg transition-all login-input"
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
              className="w-full px-4 py-3 rounded-lg transition-all login-input"
              placeholder="Enter your password"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 font-semibold rounded-lg transition-colors login-button disabled:opacity-60"
          >
            {loading ? 'Loading...' : isLogin ? 'Sign In' : 'Sign Up'}
          </button>
        </form>

        <div className="mt-6 text-center">
          <p className="login-subtitle">
            {isLogin ? "Don't have an account?" : 'Already have an account?'}
            <button
              onClick={() => setIsLogin(!isLogin)}
              className="ml-2 font-semibold login-toggle"
            >
              {isLogin ? 'Sign Up' : 'Sign In'}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
