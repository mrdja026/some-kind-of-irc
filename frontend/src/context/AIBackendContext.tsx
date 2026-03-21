import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'

export type AIBackendType = 'crewai' | 'googleAdk'

const STORAGE_KEY = 'ai-backend-preference'

interface AIBackendContextValue {
  backend: AIBackendType | null
  setBackend: (backend: AIBackendType) => void
  isLoading: boolean
  needsSelection: boolean
}

const AIBackendContext = createContext<AIBackendContextValue | undefined>(undefined)

interface AIBackendProviderProps {
  children: ReactNode
}

export function AIBackendProvider({ children }: AIBackendProviderProps) {
  const [backend, setBackendState] = useState<AIBackendType | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Load preference from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'crewai' || stored === 'googleAdk') {
      setBackendState(stored)
    }
    setIsLoading(false)
  }, [])

  // Persist preference to localStorage
  const setBackend = useCallback((newBackend: AIBackendType) => {
    localStorage.setItem(STORAGE_KEY, newBackend)
    setBackendState(newBackend)
  }, [])

  const needsSelection = !isLoading && backend === null

  return (
    <AIBackendContext.Provider
      value={{
        backend,
        setBackend,
        isLoading,
        needsSelection,
      }}
    >
      {children}
    </AIBackendContext.Provider>
  )
}

export function useAIBackend(): AIBackendContextValue {
  const context = useContext(AIBackendContext)
  if (context === undefined) {
    throw new Error('useAIBackend must be used within an AIBackendProvider')
  }
  return context
}

// Helper to get current backend preference synchronously (for API calls)
export function getAIBackendPreference(): AIBackendType | null {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'crewai' || stored === 'googleAdk') {
    return stored
  }
  return null
}
