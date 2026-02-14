import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  createDirectMessageChannel,
  getAIHealth,
  getAIStatus,
  queryAIStream,
  sendMessage,
  uploadMedia,
} from '../api'
import type {
  AIAgentCandidates,
  AIAgentReasoning,
  AIClarificationState,
  AIIntent,
  AIStreamEvent,
} from '../types'
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
  currentUserId?: number | null
  onCommand?: (command: string) => void
}

type ConversationEntry = {
  id: number
  intent: string
  query: string
  response: string
  agent: string
  disclaimer: string
  candidateQuestions?: string[]
  otherSuggestedQuestions?: string[]
  judgeReasoning?: string
  chosenFromAgent?: string
  agentCandidates?: AIAgentCandidates
  agentReasoning?: AIAgentReasoning
  clarificationSummary?: Array<{ question: string; answer: string; isFallback: boolean }>
}

const DEFAULT_DISCLAIMER =
  'AI responses are for informational purposes only. Always verify important decisions with qualified professionals.'

async function buildQuizReportPdf(params: {
  intent: AIIntent
  originalQuery: string
  channelName: string
  finalResponse: string
  clarifications: Array<{ question: string; answer: string; isFallback: boolean }>
}): Promise<File> {
  const { jsPDF } = await import('jspdf')
  const doc = new jsPDF({ unit: 'pt', format: 'a4' })
  const margin = 40
  const maxWidth = 515
  const lineHeight = 16
  let y = 44

  const addLine = (text: string, spacing = lineHeight) => {
    const lines = doc.splitTextToSize(text, maxWidth)
    lines.forEach((line: string) => {
      if (y > 790) {
        doc.addPage()
        y = 44
      }
      doc.text(line, margin, y)
      y += spacing
    })
  }

  doc.setFont('helvetica', 'bold')
  doc.setFontSize(16)
  addLine('AI Quiz Report', 20)

  doc.setFont('helvetica', 'normal')
  doc.setFontSize(11)
  addLine(`Channel: ${params.channelName}`)
  addLine(`Intent: ${params.intent}`)
  addLine(`Generated: ${new Date().toLocaleString()}`)
  y += 8

  doc.setFont('helvetica', 'bold')
  addLine('Original question:')
  doc.setFont('helvetica', 'normal')
  addLine(params.originalQuery)
  y += 8

  if (params.clarifications.length > 0) {
    doc.setFont('helvetica', 'bold')
    addLine('Clarification Q&A:')
    doc.setFont('helvetica', 'normal')
    params.clarifications.forEach((entry, idx) => {
      addLine(`Q${idx + 1}${entry.isFallback ? ' (fallback)' : ''}: ${entry.question}`)
      addLine(`A${idx + 1}: ${entry.answer}`)
      y += 6
    })
  }

  doc.setFont('helvetica', 'bold')
  addLine('Final recommendation:')
  doc.setFont('helvetica', 'normal')
  addLine(params.finalResponse)

  const fileName = `ai-quiz-report-${Date.now()}.pdf`
  const blob = doc.output('blob')
  return new File([blob], fileName, { type: 'application/pdf' })
}

async function sendQuizReportToSelfDm(params: {
  currentUserId: number
  intent: AIIntent
  originalQuery: string
  channelName: string
  finalResponse: string
  clarifications: Array<{ question: string; answer: string; isFallback: boolean }>
}): Promise<void> {
  const pdfFile = await buildQuizReportPdf({
    intent: params.intent,
    originalQuery: params.originalQuery,
    channelName: params.channelName,
    finalResponse: params.finalResponse,
    clarifications: params.clarifications,
  })
  const upload = await uploadMedia(pdfFile)
  const selfDm = await createDirectMessageChannel(params.currentUserId)
  const content = `Your AI quiz report is ready. Download PDF: ${upload.url}`
  await sendMessage(selfDm.id, content, upload.url)
}

function buildClarificationSummary(
  state: AIClarificationState,
  latestAnswer?: string,
): Array<{ question: string; answer: string; isFallback: boolean }> {
  const allAnswers = [...state.answers]
  if (latestAnswer) {
    allAnswers.push(latestAnswer)
  }
  const fallbackFlags = state.fallback_flags ?? []

  return state.questions
    .map((question, idx) => ({
      question,
      answer: allAnswers[idx] ?? '',
      isFallback: Boolean(fallbackFlags[idx]),
    }))
    .filter((item) => item.answer.trim().length > 0)
}

export function AIChannel({
  channelId,
  channelName = '#ai',
  showHeader = true,
  currentUserId,
  onCommand,
}: AIChannelProps) {
  const [selectedIntent, setSelectedIntent] = useState<AIIntent | null>(null)
  const [query, setQuery] = useState('')
  const [responses, setResponses] = useState<ConversationEntry[]>([])
  const [clarificationState, setClarificationState] =
    useState<AIClarificationState | null>(null)
  const [activeQuestion, setActiveQuestion] = useState<string | null>(null)
  const [streamProgress, setStreamProgress] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [streamError, setStreamError] = useState<string | null>(null)

  const {
    data: aiHealth,
    error: aiHealthError,
  } = useQuery({
    queryKey: ['aiHealth', channelId],
    queryFn: getAIHealth,
    retry: false,
    refetchInterval: 30000,
  })

  // Get AI status (remaining requests)
  const {
    data: aiStatus,
    error: aiStatusError,
  } = useQuery({
    queryKey: ['aiStatus', channelId],
    queryFn: getAIStatus,
    enabled: aiHealth?.status === 'ok',
    retry: false,
    refetchInterval: 60000, // Refresh every minute
  })

  useEffect(() => {
    if (aiHealth?.status === 'ok') {
      console.info(`[AIChannel] health ok for ${channelName}`)
    }
  }, [aiHealth?.status, channelName])

  useEffect(() => {
    if (aiHealthError) {
      console.warn('[AIChannel] health check failed', aiHealthError)
    }
  }, [aiHealthError])

  const healthMessage =
    aiHealthError instanceof Error ? aiHealthError.message : null
  const aiAccessMessage =
    aiStatusError instanceof Error ? aiStatusError.message : null

  const handleIntentSelect = (intent: AIIntent) => {
    setSelectedIntent(intent)
    setClarificationState(null)
    setActiveQuestion(null)
    setQuery('')
    setStreamProgress(null)
    setStreamError(null)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = query.trim()
    if (!trimmed || isSubmitting) return
    if (healthMessage) {
      setStreamError(healthMessage)
      return
    }
    if (aiAccessMessage) {
      setStreamError(aiAccessMessage)
      return
    }
    if (aiStatus && !aiStatus.available) {
      setStreamError('AI service is not configured yet. Please contact administrator.')
      return
    }
    if (trimmed.startsWith('/')) {
      const command = trimmed.slice(1).trim().toLowerCase()
      if (command) {
        onCommand?.(command)
      }
      setQuery('')
      setSelectedIntent(null)
      setClarificationState(null)
      setActiveQuestion(null)
      setStreamProgress(null)
      return
    }
    if (!selectedIntent) return
    if (!clarificationState && trimmed.length < 10) return

    const responseId = Date.now()
    const initialResponse: ConversationEntry = {
      id: responseId,
      intent: selectedIntent,
      query: trimmed,
      response: '',
      agent: 'JudgeBot',
      disclaimer: DEFAULT_DISCLAIMER,
    }

    setResponses((prev) => [...prev, initialResponse])
    setIsSubmitting(true)
    setStreamProgress(null)
    setStreamError(null)

    let streamMode: 'clarify' | 'final' | null = null
    let receivedClarifyEvent = false
    const initialTurn = !clarificationState
    let finalResponseText = ''

    try {
      if (clarificationState) {
        const inFlightSummary = buildClarificationSummary(clarificationState, trimmed)
        setResponses((prev) =>
          prev.map((item) =>
            item.id === responseId
              ? {
                  ...item,
                  clarificationSummary: inFlightSummary,
                }
              : item,
          ),
        )
      }

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
          return
        }

        if (event.type === 'progress') {
          setStreamProgress(event.message)
          return
        }

        if (event.type === 'clarify_question') {
          streamMode = 'clarify'
          receivedClarifyEvent = true
          const roundPrefix =
            event.current_round && event.total_rounds
              ? `Question ${event.current_round}/${event.total_rounds}`
              : 'Selected question'
          const fallbackSuffix = event.is_fallback_question ? ' (fallback)' : ''
          setStreamProgress(`${roundPrefix}${fallbackSuffix} ready`)
          const previousState = clarificationState
          const resolvedState: AIClarificationState =
            event.clarification_state ?? {
              original_query: previousState?.original_query ?? query,
              questions:
                event.questions.length > 0
                  ? event.questions
                  : [...(previousState?.questions ?? []), event.question],
              answers: previousState?.answers ?? [],
              fallback_flags: (() => {
                const prevFlags = previousState?.fallback_flags ?? []
                const needed = (event.questions.length > 0
                  ? event.questions.length
                  : (previousState?.questions.length ?? 0) + 1) - prevFlags.length
                if (needed <= 0) return prevFlags
                return [...prevFlags, ...new Array(needed).fill(Boolean(event.is_fallback_question))]
              })(),
              max_rounds: event.total_rounds ?? previousState?.max_rounds ?? 3,
            }

          setClarificationState(resolvedState)
          setActiveQuestion(`${event.question}${fallbackSuffix}`)
          const clarificationSummary = buildClarificationSummary(
            resolvedState,
          )
          const candidateQuestions = (event.candidate_questions ?? []).filter(
            (candidate) => candidate !== event.question,
          )
          const otherSuggestedQuestions = (
            event.other_suggested_questions ?? event.candidate_questions ?? []
          ).filter((candidate) => candidate !== event.question)
          const renderedQuestion =
            event.current_round && event.total_rounds
              ? `Question ${event.current_round}/${event.total_rounds}${fallbackSuffix}: ${event.question}`
              : `${event.question}${fallbackSuffix}`
          setResponses((prev) =>
            prev.map((item) =>
              item.id === responseId
                ? {
                    ...item,
                    intent: event.intent,
                    query: event.query,
                    response: renderedQuestion,
                    agent: event.agent,
                    disclaimer: event.disclaimer,
                    candidateQuestions,
                    otherSuggestedQuestions,
                    judgeReasoning: event.judge_reasoning,
                    chosenFromAgent: event.chosen_from_agent,
                    agentCandidates: event.agent_candidates,
                    agentReasoning: event.agent_reasoning,
                    clarificationSummary,
                }
              : item,
            ),
          )
          return
        }

        if (event.type === 'delta') {
          streamMode = 'final'
          finalResponseText += event.text
          setResponses((prev) =>
            prev.map((item) =>
              item.id === responseId
                ? {
                    ...item,
                    response: item.response + event.text,
                  }
                : item,
            ),
          )
          return
        }

        if (event.type === 'done') {
          if (event.mode) {
            streamMode = event.mode
          }
          return
        }

        if (event.type === 'error') {
          setStreamError(event.message)
        }
      }

      await queryAIStream(
        selectedIntent,
        trimmed,
        {
          onEvent: handleEvent,
          onError: (message) => setStreamError(message),
        },
        {
        conversationStage: clarificationState ? 'clarification' : 'initial',
        clarificationState,
        },
      )

      if (streamMode === 'final') {
        if (initialTurn && !receivedClarifyEvent) {
          setStreamError(
            'AI returned a direct final answer without clarification. Check that AI requests are targeting ai-service (localhost:8001).',
          )
        }

        if (currentUserId && selectedIntent) {
          const clarifications = clarificationState
            ? buildClarificationSummary(clarificationState, trimmed)
            : []
          const originalQuery = clarificationState?.original_query ?? trimmed
          try {
            await sendQuizReportToSelfDm({
              currentUserId,
              intent: selectedIntent,
              originalQuery,
              channelName,
              finalResponse: finalResponseText,
              clarifications,
            })
            console.info('[AIChannel] quiz report sent to self DM')
          } catch (reportError) {
            console.warn('[AIChannel] failed to send quiz report to self DM', reportError)
          }
        }

        setStreamProgress(null)
        setClarificationState(null)
        setActiveQuestion(null)
        setSelectedIntent(null)
      }
    } catch (error) {
      setStreamError(
        error instanceof Error ? error.message : 'AI request failed',
      )
    } finally {
      if (streamMode !== 'final') {
        setStreamProgress(null)
      }
      setIsSubmitting(false)
      setQuery('')
    }
  }

  const handleBack = () => {
    setSelectedIntent(null)
    setClarificationState(null)
    setActiveQuestion(null)
    setQuery('')
    setStreamProgress(null)
  }

  return (
    <div className="flex-1 flex flex-col">
      {/* Channel header */}
      {showHeader && (
        <div className="p-3 md:p-4 border-b chat-header">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <Sparkles size={18} className="text-amber-600 flex-shrink-0" />
              <div className="font-semibold text-sm md:text-base truncate">{channelName}</div>
              <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 flex-shrink-0">
                AI Agents
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
      <div className="flex-1 overflow-y-auto p-2 md:p-4 touch-pan-y">
        {/* Welcome message */}
        {responses.length === 0 && !selectedIntent && (
          <div className="text-center py-6 md:py-8 px-4">
            <div className="inline-flex items-center justify-center w-12 h-12 md:w-16 md:h-16 rounded-full bg-amber-100 mb-3 md:mb-4">
              <Bot size={24} className="md:w-8 md:h-8 text-amber-600" />
            </div>
            <h2 className="text-lg md:text-xl font-semibold mb-2">Welcome to AI Agents</h2>
            <p className="chat-meta mb-4 md:mb-6 max-w-md mx-auto text-sm md:text-base">
              Get help from our AI experts. Choose what you need assistance
              with:
            </p>
          </div>
        )}

        {/* Previous responses */}
        {responses.map((response, index) => (
          <div key={index} className="mb-4 md:mb-6">
            {/* User query */}
            <div className="flex gap-2 md:gap-3 chat-card p-2 md:p-3 rounded-xl mb-2 md:mb-3">
              <div className="w-6 h-6 md:w-8 md:h-8 rounded-full flex items-center justify-center flex-shrink-0 chat-avatar">
                <span className="text-xs font-semibold">You</span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <div className="text-xs md:text-sm font-semibold">You</div>
                  <span className="text-xs px-1.5 py-0.5 rounded bg-sage/30 text-brown/70">
                    {response.intent}
                  </span>
                </div>
                <div className="mt-1 chat-message-text text-sm md:text-base break-words">{response.query}</div>
              </div>
            </div>

            {/* AI response */}
            <div className="flex gap-2 md:gap-3 p-3 md:p-4 rounded-xl bg-amber-50 border border-amber-200">
              <div className="w-6 h-6 md:w-8 md:h-8 rounded-full flex items-center justify-center flex-shrink-0 bg-amber-200">
                <Bot size={14} className="md:w-4 md:h-4 text-amber-700" />
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
                  {response.chosenFromAgent && (
                    <div className="mb-2 text-xs md:text-sm text-amber-900">
                      <span className="font-semibold">Judge chose:</span> {response.chosenFromAgent}
                    </div>
                  )}
                  {response.judgeReasoning && (
                    <div className="mb-3 p-2 rounded bg-amber-100 border border-amber-200 text-xs md:text-sm text-amber-900">
                      <div className="font-semibold mb-1">Judge reasoning</div>
                      <div>{response.judgeReasoning}</div>
                    </div>
                  )}
                  {response.agentCandidates && Object.keys(response.agentCandidates).length > 0 && (
                    <div className="mb-3 p-2 rounded bg-amber-100 border border-amber-200 text-xs md:text-sm text-amber-900">
                      <div className="font-semibold mb-1">Agent suggestions</div>
                      {Object.entries(response.agentCandidates).map(([agentName, suggestions]) => (
                        <div key={`${response.id}-agent-${agentName}`} className="mb-1">
                          <span className="font-medium">{agentName}:</span>{' '}
                          {(suggestions || []).join(' | ')}
                          {response.agentReasoning?.[agentName] && (
                            <div className="text-[11px] text-amber-800/80">
                              Why: {response.agentReasoning[agentName]}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                  {response.otherSuggestedQuestions && response.otherSuggestedQuestions.length > 0 && (
                    <div className="mb-3 p-2 rounded bg-amber-100 border border-amber-200 text-xs md:text-sm text-amber-900">
                      <div className="font-semibold mb-1">Other candidate follow-ups</div>
                      {response.otherSuggestedQuestions.map((candidate, idx) => (
                        <div key={`${response.id}-candidate-${idx}`}>
                          - {candidate}
                        </div>
                      ))}
                    </div>
                  )}
                  {response.clarificationSummary &&
                    response.clarificationSummary.length > 0 && (
                      <div className="mb-3 p-2 rounded bg-amber-100 border border-amber-200 text-xs md:text-sm text-amber-900">
                        <div className="font-semibold mb-1">Clarification recap</div>
                        {response.clarificationSummary.map((entry, idx) => (
                          <div key={`${response.id}-recap-${idx}`} className="mb-1">
                            <span className="font-medium">Q{idx + 1}:</span>{' '}
                            {entry.question}
                            {entry.isFallback && (
                              <span className="ml-1 text-[10px] px-1 py-0.5 rounded bg-amber-200 text-amber-900">
                                fallback
                              </span>
                            )}
                            <br />
                            <span className="font-medium">A{idx + 1}:</span>{' '}
                            {entry.answer}
                          </div>
                        ))}
                      </div>
                    )}
                  {response.response}
                </div>
                <div className="mt-2 md:mt-3 text-xs text-amber-700/70 italic">
                  {response.disclaimer}
                </div>
              </div>
            </div>
          </div>
        ))}

        {/* Loading skeleton */}
        {isSubmitting && (
          <div className="mb-4 md:mb-6">
            {/* User query shown immediately */}
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

            {/* Skeleton loader for AI response */}
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
                    {streamProgress || 'AI is thinking...'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Error message */}
        {streamError && (
          <div className="p-3 md:p-4 rounded-xl bg-red-50 border border-red-200 mb-4">
            <div className="text-red-800 font-medium text-sm md:text-base">Error</div>
            <div className="text-red-700 text-xs md:text-sm">
              {streamError || 'Something went wrong. Please try again.'}
            </div>
          </div>
        )}

        {(healthMessage || aiAccessMessage) && (
          <div className="p-3 md:p-4 rounded-xl bg-red-50 border border-red-200 mb-4">
            <div className="text-red-800 font-medium text-sm md:text-base">AI unavailable</div>
            <div className="text-red-700 text-xs md:text-sm">
              {aiAccessMessage || healthMessage}
            </div>
          </div>
        )}

        {/* Intent selection - show when no intent selected and not loading */}
        {!selectedIntent && !isSubmitting && !healthMessage && !aiAccessMessage && aiStatus?.available !== false && (
          <div className="grid gap-2 md:gap-3 max-w-lg mx-auto px-2">
            {INTENTS.map((intent) => {
              const Icon = intent.icon
              return (
                <button
                  key={intent.id}
                  onClick={() => handleIntentSelect(intent.id)}
                  className="flex items-center gap-3 md:gap-4 p-3 md:p-4 rounded-xl chat-card hover:border-amber-300 transition-all text-left group min-h-[44px]"
                >
                  <div className="w-10 h-10 md:w-12 md:h-12 rounded-full flex items-center justify-center bg-amber-100 group-hover:bg-amber-200 transition-colors flex-shrink-0">
                    <Icon size={20} className="md:w-6 md:h-6 text-amber-700" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-brown text-sm md:text-base">
                      {intent.label}
                    </div>
                    <div className="text-xs md:text-sm chat-meta">
                      {intent.description}
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        )}

        {aiStatus?.available === false && (
          <div className="p-3 md:p-4 rounded-xl bg-red-50 border border-red-200 mb-4">
            <div className="text-red-800 font-medium text-sm md:text-base">AI unavailable</div>
            <div className="text-red-700 text-xs md:text-sm">
              AI service is not configured yet. Please contact administrator.
            </div>
          </div>
        )}
      </div>

      {/* Input area - show when intent is selected */}
      {selectedIntent && !isSubmitting && (
        <div className="p-2 md:p-4 border-t chat-input-bar">
          <div className="mb-2 md:mb-3 flex items-center gap-2 flex-wrap">
            <button
              onClick={handleBack}
              className="text-sm px-2 py-2 rounded chat-attach-button min-h-[44px]"
            >
              ← Back
            </button>
            <span className="text-xs md:text-sm font-medium">
              {INTENTS.find((i) => i.id === selectedIntent)?.label}
            </span>
            {clarificationState && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-800">
                Question {clarificationState.answers.length + 1}/
                {clarificationState.max_rounds ?? clarificationState.questions.length}
              </span>
            )}
          </div>
          <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={getPlaceholder(selectedIntent, clarificationState, activeQuestion)}
              className="flex-1 px-3 md:px-4 py-2 rounded-lg transition-all chat-input min-h-[44px] text-sm md:text-base"
              autoFocus
              minLength={query.trim().startsWith('/') ? 1 : clarificationState ? 1 : 10}
            />
            <button
              type="submit"
              disabled={
                !query.trim() ||
                (!query.trim().startsWith('/') && !clarificationState && query.length < 10)
              }
              className="px-4 py-2 font-semibold rounded-lg transition-colors chat-send-button disabled:opacity-60 min-h-[44px] text-sm md:text-base w-full sm:w-auto"
            >
              {clarificationState ? 'Submit answer' : 'Ask AI'}
            </button>
          </form>
          {clarificationState && clarificationState.answers.length > 0 && (
            <div className="mt-2 p-2 rounded bg-amber-50 border border-amber-200 text-xs md:text-sm text-amber-900">
              <div className="font-semibold mb-1">Your previous answers</div>
              {buildClarificationSummary(clarificationState).map((entry, idx) => (
                <div key={`active-recap-${idx}`} className="mb-1">
                  <span className="font-medium">Q{idx + 1}:</span> {entry.question}
                  {entry.isFallback && (
                    <span className="ml-1 text-[10px] px-1 py-0.5 rounded bg-amber-200 text-amber-900">
                      fallback
                    </span>
                  )}
                  <br />
                  <span className="font-medium">A{idx + 1}:</span> {entry.answer}
                </div>
              ))}
            </div>
          )}
          {query.length > 0 &&
            query.length < 10 &&
            !clarificationState &&
            !query.trim().startsWith('/') && (
              <div className="mt-2 text-xs text-amber-600">
                Please provide more details (at least 10 characters)
              </div>
            )}
        </div>
      )}

      {/* Show prompt to select intent when viewing responses */}
      {!selectedIntent && responses.length > 0 && !isSubmitting && (
        <div className="p-2 md:p-4 border-t chat-input-bar text-center">
          <p className="chat-meta text-xs md:text-sm">
            Select an option above to ask another question
          </p>
        </div>
      )}
    </div>
  )
}

function getPlaceholder(
  intent: AIIntent,
  clarificationState: AIClarificationState | null,
  activeQuestion: string | null,
): string {
  if (clarificationState) {
    return activeQuestion || 'Please answer this clarification question...'
  }

  switch (intent) {
    case 'afford':
      return 'e.g., Can I afford a Tesla Model 3 on a $60k salary?'
    case 'learn':
      return 'e.g., I want to learn machine learning from scratch'
    default:
      return 'Type your question...'
  }
}
