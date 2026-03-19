import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  createCalendarEvent,
  fetchGmailMessages,
  generateCalendarQuestion,
  generateGmailQuestions,
  generateGmailSummary,
  generatePdf,
  getAIHealth,
  getAIStatus,
} from '../api'
import type { CalendarEventPayload } from '../types'
import { Bot, Sparkles, Mail, ArrowUp, BookOpen, Calendar, Inbox } from 'lucide-react'

interface AIChannelProps {
  channelId: number
  channelName?: string
  showHeader?: boolean
  onCommand?: (command: string) => void
}

type ConversationEntry = {
  id: number
  query: string
  response: string
  agent: string
  mode?: 'agent_message'
  emails?: any[]
  pdfUrl?: string
}

const GMAIL_OPTIONS = [
  {
    id: '1',
    label: 'Analyze my emails',
    icon: Inbox,
    description: 'Summarize recent discovery emails and get a PDF report',
  },
  {
    id: '2',
    label: 'Create a meeting',
    icon: Calendar,
    description: 'Schedule a new meeting in your calendar',
  },
]

export function AIChannel({
  channelId,
  channelName = '#ai',
  showHeader = true,
  onCommand,
}: AIChannelProps) {
  const [query, setQuery] = useState('')
  const [responses, setResponses] = useState<ConversationEntry[]>([])
  const [activeQuestion, setActiveQuestion] = useState<string | null>(null)
  const [streamProgress, setStreamProgress] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [streamError, setStreamError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const inputBarRef = useRef<HTMLDivElement | null>(null)
  
  // Gmail Agent State
  const [gmailStage, setGmailStage] = useState<
    | 'choice'
    | 'quiz'
    | 'analyzing'
    | 'summary'
    | 'calendar-intake'
    | 'calendar-clarify'
    | 'calendar-confirm'
    | 'calendar-done'
  >('choice')
  const [gmailQuestions, setGmailQuestions] = useState<string[]>([])
  const [gmailAnswers, setGmailAnswers] = useState<string[]>([])
  const [gmailSummary, setGmailSummary] = useState<{ final_summary: string; top_email_ids: string[]; reasoning: string } | null>(null)
  const [gmailEmails, setGmailEmails] = useState<any[]>([])
  const [generatedPdfUrl, setGeneratedPdfUrl] = useState<string | null>(null)
  const [calendarAnswers, setCalendarAnswers] = useState<string[]>([])
  const [calendarQuestionsAsked, setCalendarQuestionsAsked] = useState(0)
  const [calendarEventDraft, setCalendarEventDraft] =
    useState<CalendarEventPayload | null>(null)

  const {
    data: aiHealth,
    error: aiHealthError,
  } = useQuery({
    queryKey: ['aiHealth', channelId],
    queryFn: getAIHealth,
    retry: false,
    refetchInterval: 30000,
  })

  const {
    data: aiStatus,
    error: aiStatusError,
  } = useQuery({
    queryKey: ['aiStatus', channelId],
    queryFn: getAIStatus,
    enabled: aiHealth?.status === 'ok',
    retry: false,
    refetchInterval: 60000,
  })

  useEffect(() => {
    if (aiHealth?.status === 'ok') {
      console.info(`[AIChannel] health ok for ${channelName}`)
    }
  }, [aiHealth?.status, channelName])

  useEffect(() => {
    if (!containerRef.current || !inputBarRef.current) {
      return
    }
    if (typeof ResizeObserver === 'undefined') {
      return
    }
    const updatePadding = () => {
      const height = inputBarRef.current?.offsetHeight ?? 0
      containerRef.current?.style.setProperty(
        '--floating-input-height',
        `${height}px`,
      )
    }
    updatePadding()
    const observer = new ResizeObserver(updatePadding)
    observer.observe(inputBarRef.current)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (aiHealthError) {
      console.warn('[AIChannel] health check failed', aiHealthError)
    }
  }, [aiHealthError])

  const healthMessage =
    aiHealthError instanceof Error ? aiHealthError.message : null
  const aiAccessMessage =
    aiStatusError instanceof Error ? aiStatusError.message : null

  const isAffirmativeResponse = (value: string) => {
    const normalized = value.trim().toLowerCase()
    return /^(yes|y|yep|sure|ok|okay|confirm)\b/.test(normalized)
  }

  const handleReset = useCallback(() => {
    setGmailStage('choice')
    setGmailQuestions([])
    setGmailAnswers([])
    setGmailSummary(null)
    setGmailEmails([])
    setGeneratedPdfUrl(null)
    setCalendarAnswers([])
    setCalendarQuestionsAsked(0)
    setCalendarEventDraft(null)
    setStreamError(null)
    setActiveQuestion(null)
    setResponses([])
  }, [])

  const handleOptionSelect = async (optionId: string) => {
    setIsSubmitting(true)
    setStreamProgress(null)
    setStreamError(null)

    try {
      if (optionId === '1') {
        setStreamProgress('Fetching emails...')
        const { emails } = await fetchGmailMessages()
        setGmailEmails(emails)
        setGmailStage('quiz')
        setGmailAnswers([])
        setGmailQuestions([])

        setStreamProgress('Generating first question...')
        const { questions } = await generateGmailQuestions(emails, '', [], 1)
        const firstQuestion =
          questions?.[0] ||
          'What are your primary interests? (e.g., Tech news, Finance, Photography...)'
        const q1 = `Step 1: ${firstQuestion}`
        setResponses([
          {
            id: Date.now(),
            query: '',
            response: q1,
            agent: 'Gmail Agent',
            mode: 'agent_message',
          },
        ])
        setActiveQuestion(q1)
        setStreamProgress(null)
        setIsSubmitting(false)
        return
      }

      if (optionId === '2') {
        const greeting =
          "Hi, I'm your calendar assistant. Describe the meeting you'd like to schedule (e.g., title, date, time, duration, attendees)."
        setResponses([
          {
            id: Date.now(),
            query: '',
            response: greeting,
            agent: 'Calendar Agent',
            mode: 'agent_message',
          },
        ])
        setGmailStage('calendar-intake')
        setActiveQuestion(greeting)
        setStreamProgress(null)
        setIsSubmitting(false)
        return
      }
    } catch (err) {
      setStreamError('Failed to start. Please try again.')
      setStreamProgress(null)
      console.error(err)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmedAnswer = query.trim()
    if (!trimmedAnswer) return

    if (trimmedAnswer.startsWith('/')) {
      const command = trimmedAnswer.slice(1).trim().toLowerCase()
      if (command) {
        onCommand?.(command)
      }
      setQuery('')
      return
    }

    setIsSubmitting(true)
    setStreamProgress(null)
    setStreamError(null)

    const responseId = Date.now()
    setResponses((prev) => [
      ...prev,
      {
        id: responseId,
        query: trimmedAnswer,
        response: '',
        agent: 'You',
      },
    ])

    try {
      if (gmailStage === 'calendar-intake' || gmailStage === 'calendar-clarify') {
        setStreamProgress('Reviewing meeting details...')
        const { status, question, event } = await generateCalendarQuestion(
          trimmedAnswer,
          calendarAnswers,
        )
        const updatedAnswers = [...calendarAnswers, trimmedAnswer]
        setCalendarAnswers(updatedAnswers)

        if (status === 'clarify') {
          const nextCount = calendarQuestionsAsked + 1
          setCalendarQuestionsAsked(nextCount)
          setCalendarEventDraft(event)

          if (nextCount > 3) {
            setStreamError('Unable to confirm meeting details in 3 questions.')
            setGmailStage('calendar-done')
            setStreamProgress(null)
            setIsSubmitting(false)
            setQuery('')
            return
          }

          const nextQ = `Step ${nextCount}: ${question}`
          setResponses((prev) => [
            ...prev,
            {
              id: Date.now() + 1,
              query: '',
              response: nextQ,
              agent: 'Calendar Agent',
              mode: 'agent_message',
            },
          ])
          setGmailStage('calendar-clarify')
          setActiveQuestion(nextQ)
          setStreamProgress(null)
          setIsSubmitting(false)
          setQuery('')
          return
        }

        const confirmQ = `Confirm: ${question}`
        setCalendarEventDraft(event)
        setGmailStage('calendar-confirm')
        setResponses((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            query: '',
            response: confirmQ,
            agent: 'Calendar Agent',
            mode: 'agent_message',
          },
        ])
        setActiveQuestion(confirmQ)
        setStreamProgress(null)
        setIsSubmitting(false)
        setQuery('')
        return
      }

      if (gmailStage === 'calendar-confirm') {
        if (!calendarEventDraft) {
          setStreamError('Missing meeting details to confirm.')
          setIsSubmitting(false)
          setQuery('')
          return
        }

        if (isAffirmativeResponse(trimmedAnswer)) {
          setStreamProgress('Creating calendar event...')
          try {
            const result = await createCalendarEvent(calendarEventDraft)
            if (!result.event_id && !result.html_link) {
              throw new Error('Calendar event creation failed')
            }
            const details: string[] = []
            if (calendarEventDraft.title) {
              details.push(calendarEventDraft.title)
            }
            if (calendarEventDraft.start_datetime && calendarEventDraft.end_datetime) {
              details.push(
                `${calendarEventDraft.start_datetime} → ${calendarEventDraft.end_datetime} (${calendarEventDraft.timezone || 'UTC'})`,
              )
            }
            const detailText = details.join(' — ') || result.summary || 'your event'
            const confirmation = result.html_link
              ? `Meeting created in your calendar: ${detailText}. Link: ${result.html_link}`
              : `Meeting created in your calendar: ${detailText}.`

            setResponses((prev) => [
              ...prev,
              {
                id: Date.now() + 1,
                query: '',
                response: confirmation,
                agent: 'Calendar Agent',
                mode: 'agent_message',
              },
            ])
            setGmailStage('calendar-done')
            setActiveQuestion(null)
            setStreamProgress(null)
            setIsSubmitting(false)
            setQuery('')
            return
          } catch (error) {
            setStreamError(
              'Failed to create the calendar event. Please reconnect Gmail/Calendar and try again.',
            )
            setStreamProgress(null)
            setIsSubmitting(false)
            setQuery('')
            return
          }
        }

        const retryPrompt =
          'Okay, please describe the meeting details again (title, date, time, duration).'
        setCalendarAnswers([])
        setCalendarQuestionsAsked(0)
        setCalendarEventDraft(null)
        setGmailStage('calendar-intake')
        setResponses((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            query: '',
            response: retryPrompt,
            agent: 'Calendar Agent',
            mode: 'agent_message',
          },
        ])
        setActiveQuestion(retryPrompt)
        setStreamProgress(null)
        setIsSubmitting(false)
        setQuery('')
        return
      }

      if (gmailAnswers.length === 0) {
        setStreamProgress('Generating questions...')
        const { questions } = await generateGmailQuestions(
          gmailEmails,
          trimmedAnswer,
          [],
          2,
        )
        const followUpQuestions = questions ?? []
        setGmailQuestions(followUpQuestions)
        setGmailAnswers([trimmedAnswer])
        setStreamProgress(null)

        const nextQuestionText =
          followUpQuestions[0] || 'What should we prioritize next?'
        const nextQ = `Step 2: ${nextQuestionText}`
        setResponses((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            query: '',
            response: nextQ,
            agent: 'Gmail Agent',
            mode: 'agent_message',
          },
        ])
        setActiveQuestion(nextQ)
        setIsSubmitting(false)
        setQuery('')
        return
      }

      if (gmailAnswers.length < 3) {
        const newAnswers = [...gmailAnswers, trimmedAnswer]
        setGmailAnswers(newAnswers)

        if (newAnswers.length < 3) {
          const followUpQuestion =
            gmailQuestions[newAnswers.length - 1] || 'Any other priorities?'
          const nextQ = `Step ${newAnswers.length + 1}: ${followUpQuestion}`
          setResponses((prev) => [
            ...prev,
            {
              id: Date.now() + 1,
              query: '',
              response: nextQ,
              agent: 'Gmail Agent',
              mode: 'agent_message',
            },
          ])
          setActiveQuestion(nextQ)
          setStreamProgress(null)
          setIsSubmitting(false)
          setQuery('')
          return
        }

        setGmailStage('analyzing')
        setStreamProgress('Analyzing emails and generating summary...')

        const result = await generateGmailSummary(
          gmailEmails,
          newAnswers[0],
          newAnswers.slice(1),
        )

        setGmailSummary(result)
        setGmailStage('summary')

        setStreamProgress('Generating PDF report...')
        const { url } = await generatePdf(
          `Gmail Summary: ${newAnswers[0]}`,
          [
            { heading: 'Executive Summary', content: result.final_summary },
            { heading: 'AI Reasoning', content: result.reasoning },
          ],
          result.top_email_ids
            .map((id) => gmailEmails.find((e) => e.message_id === id)?.permalink || '')
            .filter(Boolean),
        )
        setGeneratedPdfUrl(url)

        setResponses((prev) => [
          ...prev,
          {
            id: Date.now() + 2,
            query: '',
            response: result.final_summary,
            agent: 'Gmail Agent',
            mode: 'agent_message',
            emails: result.top_email_ids.map((id) =>
              gmailEmails.find((e) => e.message_id === id),
            ),
            pdfUrl: url,
          },
        ])

        setStreamProgress(null)
        setActiveQuestion(null)
        setIsSubmitting(false)
        setQuery('')
        return
      }
    } catch (err) {
      setStreamError('Gmail agent failed. Please try again.')
      setStreamProgress(null)
      console.error(err)
    } finally {
      setIsSubmitting(false)
      setQuery('')
    }
  }

  const isFlowComplete = gmailStage === 'summary' || gmailStage === 'calendar-done'
  const showOptionCards = gmailStage === 'choice' && responses.length === 0 && !isSubmitting

  return (
    <div ref={containerRef} className="flex-1 flex flex-col relative min-h-0">
      {/* Channel header */}
      {showHeader && (
        <div className="p-3 md:p-4 border-b chat-header">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <Sparkles size={18} className="text-amber-600 flex-shrink-0" />
              <div className="font-semibold text-sm md:text-base truncate">{channelName}</div>
              <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 flex-shrink-0">
                Gmail Assistant
              </span>
            </div>
            {aiStatus && (
              <div className="text-xs chat-meta flex-shrink-0">
                {aiStatus.remaining_requests}/{aiStatus.max_requests_per_hour}{' '}
                requests left
              </div>
            )}
          </div>
          {(healthMessage || aiAccessMessage) && (
            <div className="mt-2 text-xs text-red-700">
              {aiAccessMessage || healthMessage}
            </div>
          )}
        </div>
      )}

      {/* Messages area */}
      <div
        className="flex-1 overflow-y-auto p-2 md:p-4 touch-pan-y"
        style={{
          paddingBottom: 'calc(var(--floating-input-height, 0px) + 24px)',
        }}
      >
        {/* Welcome message with option cards */}
        {showOptionCards && (
          <div className="text-center py-6 md:py-8 px-4">
            <div className="inline-flex items-center justify-center w-12 h-12 md:w-16 md:h-16 rounded-full bg-amber-100 mb-3 md:mb-4">
              <Mail size={24} className="md:w-8 md:h-8 text-amber-600" />
            </div>
            <h2 className="text-lg md:text-xl font-semibold mb-2">Gmail Assistant</h2>
            <p className="chat-meta mb-6 md:mb-8 max-w-md mx-auto text-sm md:text-base">
              Choose what you'd like to do:
            </p>

            {/* Option cards */}
            <div className="grid gap-3 md:gap-4 max-w-lg mx-auto">
              {GMAIL_OPTIONS.map((option) => {
                const Icon = option.icon
                return (
                  <button
                    key={option.id}
                    onClick={() => handleOptionSelect(option.id)}
                    disabled={isSubmitting || Boolean(healthMessage) || Boolean(aiAccessMessage)}
                    className="flex items-center gap-3 md:gap-4 p-4 md:p-5 rounded-xl chat-card hover:border-amber-300 hover:bg-amber-50/50 transition-all text-left group min-h-[72px] disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <div className="w-12 h-12 md:w-14 md:h-14 rounded-full flex items-center justify-center bg-amber-100 group-hover:bg-amber-200 transition-colors flex-shrink-0">
                      <Icon size={24} className="md:w-7 md:h-7 text-amber-700" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-brown text-sm md:text-base mb-0.5">
                        {option.label}
                      </div>
                      <div className="text-xs md:text-sm chat-meta">
                        {option.description}
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>

            {/* Loading state for initial selection */}
            {isSubmitting && (
              <div className="mt-6 flex items-center justify-center gap-2">
                <div className="w-2 h-2 rounded-full bg-amber-400 animate-bounce"></div>
                <div className="w-2 h-2 rounded-full bg-amber-400 animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-2 h-2 rounded-full bg-amber-400 animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                <span className="text-sm text-amber-600 ml-2">{streamProgress || 'Starting...'}</span>
              </div>
            )}
          </div>
        )}

        {/* Error messages at top */}
        {(healthMessage || aiAccessMessage) && showOptionCards && (
          <div className="p-3 md:p-4 rounded-xl bg-red-50 border border-red-200 mb-4 max-w-lg mx-auto">
            <div className="text-red-800 font-medium text-sm md:text-base">AI unavailable</div>
            <div className="text-red-700 text-xs md:text-sm">
              {aiAccessMessage || healthMessage}
            </div>
          </div>
        )}

        {aiStatus?.available === false && showOptionCards && (
          <div className="p-3 md:p-4 rounded-xl bg-red-50 border border-red-200 mb-4 max-w-lg mx-auto">
            <div className="text-red-800 font-medium text-sm md:text-base">AI unavailable</div>
            <div className="text-red-700 text-xs md:text-sm">
              AI service is not configured yet. Please contact administrator.
            </div>
          </div>
        )}

        {/* Conversation */}
        {responses.map((response, index) => (
          <div key={index} className="mb-4 md:mb-6">
            {/* User query */}
            {response.query && (
              <div className="flex gap-2 md:gap-3 chat-card p-2 md:p-3 rounded-xl mb-2 md:mb-3">
                <div className="w-6 h-6 md:w-8 md:h-8 rounded-full flex items-center justify-center flex-shrink-0 chat-avatar">
                  <span className="text-xs font-semibold">You</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <div className="text-xs md:text-sm font-semibold">You</div>
                  </div>
                  <div className="mt-1 chat-message-text text-sm md:text-base break-words">{response.query}</div>
                </div>
              </div>
            )}

            {/* AI response */}
            {response.response && (
              <div className="flex gap-2 md:gap-3 p-3 md:p-4 rounded-xl bg-amber-50 border border-amber-200">
                <div className="w-6 h-6 md:w-8 md:h-8 rounded-full flex items-center justify-center flex-shrink-0 bg-amber-200">
                  <Mail size={14} className="md:w-4 md:h-4 text-amber-700" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <div className="text-xs md:text-sm font-semibold text-amber-800">
                      {response.agent}
                    </div>
                    <span className="text-xs px-1.5 py-0.5 rounded-full bg-amber-200 text-amber-800">
                      AI
                    </span>
                  </div>
                  <div className="text-amber-900 whitespace-pre-wrap text-sm md:text-base break-words">
                    {response.response}
                    
                    {/* Email list */}
                    {response.mode === 'agent_message' && response.emails && (
                      <div className="mt-4 border-t border-amber-200 pt-4">
                        <h4 className="text-xs font-semibold text-amber-800 uppercase tracking-wider mb-3">
                          Top Relevant Emails
                        </h4>
                        <div className="space-y-2">
                          {response.emails.map((email: any) => (
                            <a 
                              key={email.message_id} 
                              href={email.permalink} 
                              target="_blank" 
                              rel="noreferrer"
                              className="block p-2 rounded bg-white/50 border border-amber-100 hover:bg-amber-50 hover:border-amber-300 transition-colors text-xs md:text-sm"
                            >
                              <div className="flex justify-between items-center mb-1">
                                <span className="font-medium text-amber-900 truncate pr-2 max-w-[70%]">
                                  {email.from}
                                </span>
                                <span className="text-amber-600 text-[10px]">
                                  {new Date(parseInt(email.received_at)).toLocaleDateString()}
                                </span>
                              </div>
                              <div className="text-gray-600 truncate">
                                {email.subject || '(No Subject)'}
                              </div>
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    {/* PDF download */}
                    {response.mode === 'agent_message' && response.pdfUrl && (
                      <div className="mt-4">
                        <a
                          href={response.pdfUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm"
                        >
                          <BookOpen size={16} />
                          Download PDF Report
                        </a>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}

        {/* Loading skeleton */}
        {isSubmitting && !showOptionCards && (
          <div className="mb-4 md:mb-6">
            <div className="flex gap-2 md:gap-3 chat-card p-2 md:p-3 rounded-xl mb-2 md:mb-3">
              <div className="w-6 h-6 md:w-8 md:h-8 rounded-full flex items-center justify-center flex-shrink-0 chat-avatar">
                <span className="text-xs font-semibold">You</span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <div className="text-xs md:text-sm font-semibold">You</div>
                </div>
                <div className="mt-1 chat-message-text text-sm md:text-base break-words">{query}</div>
              </div>
            </div>

            <div className="flex gap-2 md:gap-3 p-3 md:p-4 rounded-xl bg-amber-50 border border-amber-200 animate-pulse">
              <div className="w-6 h-6 md:w-8 md:h-8 rounded-full flex items-center justify-center flex-shrink-0 bg-amber-200">
                <Bot size={14} className="md:w-4 md:h-4 text-amber-700" />
              </div>
              <div className="flex-1 space-y-2 md:space-y-3">
                <div className="flex items-center gap-2">
                  <div className="h-3 md:h-4 w-16 md:w-20 bg-amber-200 rounded"></div>
                  <div className="h-3 md:h-4 w-6 md:w-8 bg-amber-200 rounded-full"></div>
                </div>
                <div className="space-y-2">
                  <div className="h-3 bg-amber-200/60 rounded w-full"></div>
                  <div className="h-3 bg-amber-200/60 rounded w-5/6"></div>
                  <div className="h-3 bg-amber-200/60 rounded w-4/6"></div>
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
                    {streamProgress || 'Processing...'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Error message */}
        {streamError && !showOptionCards && (
          <div className="p-3 md:p-4 rounded-xl bg-red-50 border border-red-200 mb-4">
            <div className="text-red-800 font-medium text-sm md:text-base">Error</div>
            <div className="text-red-700 text-xs md:text-sm">
              {streamError || 'Something went wrong. Please try again.'}
            </div>
          </div>
        )}
      </div>

      {/* Input area - only show when not on choice screen */}
      {!showOptionCards && (
        <div
          ref={inputBarRef}
          className="absolute bottom-4 left-0 right-0 z-20 px-4 pointer-events-none"
        >
          <div className="max-w-4xl mx-auto w-full pointer-events-auto">
            <div className="mb-2 md:mb-3 flex items-center gap-2 flex-wrap">
              {isFlowComplete && (
                <button
                  onClick={handleReset}
                  className="text-xs md:text-sm px-3 py-1.5 rounded-lg chat-attach-button min-h-[32px] hover:bg-stone-100 transition-colors"
                >
                  Start Over
                </button>
              )}
              <span className="text-xs md:text-sm font-medium px-2 py-1 bg-amber-100/50 rounded-md text-amber-800">
                {gmailStage.includes('calendar') ? 'Calendar Assistant' : 'Gmail Assistant'}
              </span>
            </div>
            <form
              onSubmit={handleSubmit}
              className="flex flex-col sm:flex-row gap-2 relative bg-white/80 p-2 rounded-2xl shadow-xl border border-stone-200/50 backdrop-blur-sm"
            >
              <div className="flex-1 relative min-w-0">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={activeQuestion || 'Type your response...'}
                  className="w-full px-3 py-3 bg-transparent border-0 focus:ring-0 text-sm md:text-base disabled:opacity-50 disabled:cursor-not-allowed placeholder:text-stone-400"
                  style={{ minHeight: '44px' }}
                  autoFocus
                  disabled={isSubmitting || Boolean(healthMessage) || Boolean(aiAccessMessage)}
                />
              </div>
              <button
                type="submit"
                disabled={
                  isSubmitting ||
                  Boolean(healthMessage) ||
                  Boolean(aiAccessMessage) ||
                  !query.trim()
                }
                className="p-2 rounded-xl transition-all chat-send-button disabled:opacity-60 h-[44px] w-[44px] flex items-center justify-center flex-shrink-0 shadow-sm"
              >
                <ArrowUp size={20} />
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Invisible ref for padding calculation when cards are shown */}
      {showOptionCards && <div ref={inputBarRef} />}
    </div>
  )
}
