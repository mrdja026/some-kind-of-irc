import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { queryAIStream, getAIStatus } from '../api'
import type { AIIntent, AIQueryResponse, AIStreamEvent } from '../types'
import { DollarSign, BookOpen, Bot, Sparkles } from 'lucide-react'

const INTENTS: {
  id: AIIntent
  label: string
  icon: typeof DollarSign
  description: string
}[] = [
  {
    id: 'afford',
    label: 'Can I afford this?',
    icon: DollarSign,
    description: 'Get financial analysis and budget advice',
  },
  {
    id: 'learn',
    label: 'Find me learning material',
    icon: BookOpen,
    description: 'Discover courses, tutorials, and resources',
  },
]

interface AIChannelProps {
  channelId: number
  channelName?: string
  showHeader?: boolean
  onCommand?: (command: string) => void
}

export function AIChannel({
  channelId,
  channelName = '#ai',
  showHeader = true,
  onCommand,
}: AIChannelProps) {
  const [selectedIntent, setSelectedIntent] = useState<AIIntent | null>(null)
  const [query, setQuery] = useState('')
  const [responses, setResponses] = useState<
    Array<AIQueryResponse & { id: number }>
  >([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamError, setStreamError] = useState<string | null>(null)

  // Get AI status (remaining requests)
  const { data: aiStatus } = useQuery({
    queryKey: ['aiStatus'],
    queryFn: getAIStatus,
    refetchInterval: 60000, // Refresh every minute
  })

  const handleIntentSelect = (intent: AIIntent) => {
    setSelectedIntent(intent)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = query.trim()
    if (!trimmed || isStreaming) return
    if (trimmed.startsWith('/')) {
      const command = trimmed.slice(1).trim().toLowerCase()
      if (command) {
        onCommand?.(command)
      }
      setQuery('')
      setSelectedIntent(null)
      return
    }
    if (!selectedIntent || trimmed.length < 10) return

    const responseId = Date.now()
    const initialResponse: AIQueryResponse & { id: number } = {
      id: responseId,
      intent: selectedIntent,
      query: trimmed,
      response: '',
      agent: 'JudgeBot',
      disclaimer:
        'AI responses are for informational purposes only. Always verify important decisions with qualified professionals.',
    }

    setResponses((prev) => [...prev, initialResponse])
    setIsStreaming(true)
    setStreamError(null)

    const handleEvent = (event: AIStreamEvent) => {
      if (event.type === 'meta') {
        setResponses((prev) =>
          prev.map((item) =>
            item.id === responseId
              ? {
                  ...item,
                  intent: event.intent,
                  query: event.query,
                  agent: event.agent,
                  disclaimer: event.disclaimer,
                }
              : item,
          ),
        )
      }
      if (event.type === 'delta') {
        setResponses((prev) =>
          prev.map((item) =>
            item.id === responseId
              ? { ...item, response: item.response + event.text }
              : item,
          ),
        )
      }
      if (event.type === 'error') {
        setStreamError(event.message)
      }
    }

    try {
      await queryAIStream(selectedIntent, trimmed, {
        onEvent: handleEvent,
        onError: (message) => setStreamError(message),
      })
    } catch (error) {
      setStreamError(
        error instanceof Error ? error.message : 'AI stream failed',
      )
    } finally {
      setIsStreaming(false)
      setQuery('')
      setSelectedIntent(null)
    }
  }

  const handleBack = () => {
    setSelectedIntent(null)
    setQuery('')
  }

  return (
    <div className="flex-1 flex flex-col">
      {/* Channel header */}
      {showHeader && (
        <div className="p-4 border-b chat-header">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles size={18} className="text-amber-600" />
              <div className="font-semibold">{channelName}</div>
              <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
                AI Agents
              </span>
            </div>
            {aiStatus && (
              <div className="text-xs chat-meta">
                {aiStatus.remaining_requests}/{aiStatus.max_requests_per_hour}{' '}
                requests left
              </div>
            )}
          </div>
        </div>
      )}

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* Welcome message */}
        {responses.length === 0 && !selectedIntent && (
          <div className="text-center py-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-amber-100 mb-4">
              <Bot size={32} className="text-amber-600" />
            </div>
            <h2 className="text-xl font-semibold mb-2">Welcome to AI Agents</h2>
            <p className="chat-meta mb-6 max-w-md mx-auto">
              Get help from our AI experts. Choose what you need assistance
              with:
            </p>
          </div>
        )}

        {/* Previous responses */}
        {responses.map((response, index) => (
          <div key={index} className="mb-6">
            {/* User query */}
            <div className="flex gap-3 chat-card p-3 rounded-xl mb-3">
              <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 chat-avatar">
                <span className="text-xs font-semibold">You</span>
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <div className="text-sm font-semibold">You</div>
                  <span className="text-xs px-1.5 py-0.5 rounded bg-sage/30 text-brown/70">
                    {response.intent}
                  </span>
                </div>
                <div className="mt-1 chat-message-text">{response.query}</div>
              </div>
            </div>

            {/* AI response */}
            <div className="flex gap-3 p-4 rounded-xl bg-amber-50 border border-amber-200">
              <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 bg-amber-200">
                <Bot size={16} className="text-amber-700" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <div className="text-sm font-semibold text-amber-800">
                    {response.agent}
                  </div>
                  <span className="text-xs px-1.5 py-0.5 rounded-full bg-amber-200 text-amber-800">
                    AI
                  </span>
                </div>
                <div className="text-amber-900 whitespace-pre-wrap">
                  {response.response}
                </div>
                <div className="mt-3 text-xs text-amber-700/70 italic">
                  {response.disclaimer}
                </div>
              </div>
            </div>
          </div>
        ))}

        {/* Loading skeleton */}
        {isStreaming && (
          <div className="mb-6">
            {/* User query shown immediately */}
            <div className="flex gap-3 chat-card p-3 rounded-xl mb-3">
              <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 chat-avatar">
                <span className="text-xs font-semibold">You</span>
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <div className="text-sm font-semibold">You</div>
                </div>
                <div className="mt-1 chat-message-text">{query}</div>
              </div>
            </div>

            {/* Skeleton loader for AI response */}
            <div className="flex gap-3 p-4 rounded-xl bg-amber-50 border border-amber-200 animate-pulse">
              <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 bg-amber-200">
                <Bot size={16} className="text-amber-700" />
              </div>
              <div className="flex-1 space-y-3">
                <div className="flex items-center gap-2">
                  <div className="h-4 w-20 bg-amber-200 rounded"></div>
                  <div className="h-4 w-8 bg-amber-200 rounded-full"></div>
                </div>
                <div className="space-y-2">
                  <div className="h-3 bg-amber-200/60 rounded w-full"></div>
                  <div className="h-3 bg-amber-200/60 rounded w-5/6"></div>
                  <div className="h-3 bg-amber-200/60 rounded w-4/6"></div>
                  <div className="h-3 bg-amber-200/60 rounded w-full"></div>
                  <div className="h-3 bg-amber-200/60 rounded w-3/4"></div>
                </div>
                <div className="flex items-center gap-2 pt-2">
                  <div className="w-2 h-2 rounded-full bg-amber-300 animate-bounce"></div>
                  <div
                    className="w-2 h-2 rounded-full bg-amber-300 animate-bounce"
                    style={{ animationDelay: '0.1s' }}
                  ></div>
                  <div
                    className="w-2 h-2 rounded-full bg-amber-300 animate-bounce"
                    style={{ animationDelay: '0.2s' }}
                  ></div>
                  <span className="text-xs text-amber-600 ml-1">
                    AI is thinking...
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Error message */}
        {streamError && (
          <div className="p-4 rounded-xl bg-red-50 border border-red-200 mb-4">
            <div className="text-red-800 font-medium">Error</div>
            <div className="text-red-700 text-sm">
              {streamError || 'Something went wrong. Please try again.'}
            </div>
          </div>
        )}

        {/* Intent selection - show when no intent selected and not loading */}
        {!selectedIntent && !isStreaming && (
          <div className="grid gap-3 max-w-lg mx-auto">
            {INTENTS.map((intent) => {
              const Icon = intent.icon
              return (
                <button
                  key={intent.id}
                  onClick={() => handleIntentSelect(intent.id)}
                  className="flex items-center gap-4 p-4 rounded-xl chat-card hover:border-amber-300 transition-all text-left group"
                >
                  <div className="w-12 h-12 rounded-full flex items-center justify-center bg-amber-100 group-hover:bg-amber-200 transition-colors">
                    <Icon size={24} className="text-amber-700" />
                  </div>
                  <div className="flex-1">
                    <div className="font-semibold text-brown">
                      {intent.label}
                    </div>
                    <div className="text-sm chat-meta">
                      {intent.description}
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </div>

      {/* Input area - show when intent is selected */}
      {selectedIntent && !isStreaming && (
        <div className="p-4 border-t chat-input-bar">
          <div className="mb-3 flex items-center gap-2">
            <button
              onClick={handleBack}
              className="text-sm px-2 py-1 rounded chat-attach-button"
            >
              ← Back
            </button>
            <span className="text-sm font-medium">
              {INTENTS.find((i) => i.id === selectedIntent)?.label}
            </span>
          </div>
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={getPlaceholder(selectedIntent)}
              className="flex-1 px-4 py-2 rounded-lg transition-all chat-input"
              autoFocus
              minLength={query.trim().startsWith('/') ? 1 : 10}
            />
            <button
              type="submit"
              disabled={
                !query.trim() ||
                (!query.trim().startsWith('/') && query.length < 10)
              }
              className="px-4 py-2 font-semibold rounded-lg transition-colors chat-send-button disabled:opacity-60"
            >
              Ask AI
            </button>
          </form>
          {query.length > 0 &&
            query.length < 10 &&
            !query.trim().startsWith('/') && (
              <div className="mt-2 text-xs text-amber-600">
                Please provide more details (at least 10 characters)
              </div>
            )}
        </div>
      )}

      {/* Show prompt to select intent when viewing responses */}
      {!selectedIntent && responses.length > 0 && !isStreaming && (
        <div className="p-4 border-t chat-input-bar text-center">
          <p className="chat-meta text-sm">
            Select an option above to ask another question
          </p>
        </div>
      )}
    </div>
  )
}

function getPlaceholder(intent: AIIntent): string {
  switch (intent) {
    case 'afford':
      return 'e.g., Can I afford a Tesla Model 3 on a $60k salary?'
    case 'learn':
      return 'e.g., I want to learn machine learning from scratch'
    default:
      return 'Type your question...'
  }
}
