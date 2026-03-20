import { useState } from 'react'
import { Cpu, ChevronDown, Check } from 'lucide-react'
import { useAIBackend, type AIBackendType } from '../context/AIBackendContext'

interface BackendOption {
  value: AIBackendType
  label: string
  description: string
}

const BACKEND_OPTIONS: BackendOption[] = [
  {
    value: 'crewai',
    label: 'CrewAI',
    description: 'Original AI backend',
  },
  {
    value: 'googleAdk',
    label: 'Google ADK',
    description: 'Google ADK backend',
  },
]

export function AIBackendToggle() {
  const { backend, setBackend, isLoading } = useAIBackend()
  const [isOpen, setIsOpen] = useState(false)

  if (isLoading) {
    return null
  }

  const currentOption = BACKEND_OPTIONS.find((opt) => opt.value === backend)
  const displayLabel = currentOption?.label || 'Select Backend'

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg bg-gray-700/50 hover:bg-gray-700 transition-colors text-sm"
        aria-label="Select AI Backend"
      >
        <Cpu size={14} className="text-purple-400" />
        <span className="text-gray-200 hidden sm:inline">{displayLabel}</span>
        <ChevronDown
          size={14}
          className={`text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />

          {/* Dropdown */}
          <div className="absolute right-0 top-full mt-1 z-50 w-48 rounded-lg bg-gray-800 border border-gray-700 shadow-xl overflow-hidden">
            <div className="p-1">
              {BACKEND_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  onClick={() => {
                    setBackend(option.value)
                    setIsOpen(false)
                  }}
                  className={`w-full flex items-center gap-2 px-3 py-2 rounded-md text-left transition-colors ${
                    backend === option.value
                      ? 'bg-purple-600/20 text-purple-300'
                      : 'hover:bg-gray-700 text-gray-300'
                  }`}
                >
                  <div className="flex-1">
                    <div className="text-sm font-medium">{option.label}</div>
                    <div className="text-xs text-gray-500">{option.description}</div>
                  </div>
                  {backend === option.value && (
                    <Check size={14} className="text-purple-400 flex-shrink-0" />
                  )}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
