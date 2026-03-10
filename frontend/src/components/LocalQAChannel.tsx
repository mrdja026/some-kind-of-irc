import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getLocalAIStatus, queryLocalAI, queryLocalAIStream } from '../api'
import type { LocalAIMessage } from '../types'

type LocalChatMessage = LocalAIMessage & {
  id: number
  agent?: string
}

interface LocalQAChannelProps {
  channelId: number
  channelName?: string
  currentUserId?: number | null
}

function safeReadMessages(key: string): LocalChatMessage[] {
  if (typeof window === 'undefined') return []
  const raw = sessionStorage.getItem(key)
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((item) => item && typeof item.content === 'string')
  } catch {
    return []
  }
}

export function LocalQAChannel({
  channelId,
  channelName = 'Q&A local',
  currentUserId = null,
}: LocalQAChannelProps) {
  const storageScope = useMemo(
    () => `localqa:${currentUserId ?? 'anon'}:${channelId}`,
    [channelId, currentUserId],
  )
  const messagesKey = `${storageScope}:messages`
  const greetedKey = `${storageScope}:greeted`

  const [messages, setMessages] = useState<LocalChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [greetingAttempted, setGreetingAttempted] = useState(false)
  const streamAbortRef = useRef<AbortController | null>(null)

  const { data: localStatus } = useQuery({
    queryKey: ['localAiStatus', channelId],
    queryFn: getLocalAIStatus,
    retry: false,
    refetchInterval: 30000,
  })

  useEffect(() => {
    setMessages(safeReadMessages(messagesKey))
    setGreetingAttempted(false)
    setInput('')
    setError(null)
  }, [messagesKey])

  useEffect(() => {
    if (typeof window === 'undefined') return
    sessionStorage.setItem(messagesKey, JSON.stringify(messages))
  }, [messages, messagesKey])

  useEffect(() => {
    return () => {
      streamAbortRef.current?.abort()
      streamAbortRef.current = null
    }
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return
    if (!currentUserId || greetingAttempted) return
    // Allow retry if greeted but messages are empty (e.g., sessionStorage cleared)
    if (sessionStorage.getItem(greetedKey) === '1' && messages.length > 0) return

    setGreetingAttempted(true)
    queryLocalAI('', { mode: 'greeting' })
      .then((response) => {
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now(),
            role: 'assistant',
            content: response.message,
            agent: response.agent,
          },
        ])
        sessionStorage.setItem(greetedKey, '1')
      })
      .catch((err: unknown) => {
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now(),
            role: 'system',
            content:
              err instanceof Error
                ? err.message
                : 'Local Q&A greeting failed. Please try again.',
            agent: 'System',
          },
        ])
      })
  }, [currentUserId, greetedKey, greetingAttempted])

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    const query = input.trim()
    if (!query || isSubmitting) return

    setError(null)
    const userMessage: LocalChatMessage = {
      id: Date.now(),
      role: 'user',
      content: query,
    }

    const nextMessages = [...messages, userMessage]
    setMessages(nextMessages)
    setInput('')
    setIsSubmitting(true)

    const abortController = new AbortController()
    streamAbortRef.current?.abort()
    streamAbortRef.current = abortController
    let streamProducedOutput = false

    try {
      let streamMessageId: number | null = null
      let assistantAgent = 'Photography & Art Consultant'

      await queryLocalAIStream(
        query,
        {
          signal: abortController.signal,
          onError: (message) => setError(message),
          onEvent: (event) => {
            if (event.type === 'meta') {
              assistantAgent = event.agent || assistantAgent
              return
            }

            if (event.type === 'delta') {
              if (!event.text) return
              streamProducedOutput = true
              if (streamMessageId === null) {
                streamMessageId = Date.now() + 1
                setMessages((prev) => [
                  ...prev,
                  {
                    id: streamMessageId as number,
                    role: 'assistant',
                    content: event.text,
                    agent: event.agent || assistantAgent,
                  },
                ])
                return
              }
              setMessages((prev) =>
                prev.map((message) =>
                  message.id === streamMessageId
                    ? { ...message, content: `${message.content}${event.text}` }
                    : message,
                ),
              )
              return
            }

            if (event.type === 'rejected' || event.type === 'fallback') {
              streamProducedOutput = true
              setMessages((prev) => [
                ...prev,
                {
                  id: Date.now() + 2,
                  role: 'system',
                  content: event.message,
                  agent: event.agent || (event.type === 'rejected' ? 'Scope Guard' : 'System'),
                },
              ])
            }
          },
        },
        {
          mode: 'chat',
          history: nextMessages.map((item) => ({
            role: item.role,
            content: item.content,
          })),
        },
      )

      if (!streamProducedOutput) {
        setError('No streamed response was received. Please retry.')
      }
    } catch (err: unknown) {
      if (abortController.signal.aborted) return
      setError(err instanceof Error ? err.message : 'Local Q&A stream failed')
    } finally {
      if (streamAbortRef.current === abortController) {
        streamAbortRef.current = null
      }
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="p-2 md:p-2.5 border-b chat-header text-xs chat-meta">
        {channelName} · {localStatus?.online ? 'Local AI online' : 'Local AI offline'}
      </div>

      <div className="flex-1 overflow-y-auto p-1.5 md:p-2 touch-pan-y">
        {messages.length === 0 ? (
          <div className="text-center py-4 chat-meta text-sm">
            No local Q&A messages yet.
          </div>
        ) : (
          <div className="space-y-1 md:space-y-1.5">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`chat-card p-2 rounded-lg ${
                  message.role === 'user' ? 'ml-6' : 'mr-6'
                }`}
              >
                <div className="text-[10px] chat-meta mb-1">
                  {message.role === 'user'
                    ? 'You'
                    : message.agent || (message.role === 'system' ? 'System' : 'Local AI')}
                </div>
                <div className="chat-message-text text-xs md:text-sm break-words leading-tight">
                  {message.content}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="p-2 border-t chat-header flex gap-2">
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask about art or photography..."
          className="flex-1 px-3 py-2 rounded text-sm chat-input min-h-[44px]"
          disabled={isSubmitting}
        />
        <button
          type="submit"
          className="px-3 py-2 text-sm font-semibold rounded chat-send-button min-h-[44px] disabled:opacity-60"
          disabled={isSubmitting || !input.trim()}
        >
          {isSubmitting ? '...' : 'Send'}
        </button>
      </form>
      {error && <div className="px-3 pb-2 text-xs text-red-600">{error}</div>}
    </div>
  )
}
