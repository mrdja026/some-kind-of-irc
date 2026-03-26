import { useState, useEffect } from 'react'
import { ChevronDown, ChevronRight, Clock, RefreshCw, X } from 'lucide-react'
import type {
  InferenceLogEvent,
  GmailStepStage,
  StageColorMap,
} from '../types'
import { getInferenceLogs } from '../api'

const STAGE_COLORS: StageColorMap = {
  questions: {
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    text: 'text-blue-800',
    label: 'QUESTIONS',
  },
  summary_action: {
    bg: 'bg-green-50',
    border: 'border-green-200',
    text: 'text-green-800',
    label: 'SUMMARY_ACTION',
  },
  summary_insight: {
    bg: 'bg-emerald-50',
    border: 'border-emerald-200',
    text: 'text-emerald-800',
    label: 'SUMMARY_INSIGHT',
  },
  classification: {
    bg: 'bg-orange-50',
    border: 'border-orange-200',
    text: 'text-orange-800',
    label: 'CLASSIFICATION',
  },
  judge: {
    bg: 'bg-purple-50',
    border: 'border-purple-200',
    text: 'text-purple-800',
    label: 'LLM_JUDGE',
  },
}

const KIND_COLORS: Record<string, { bg: string; border: string; text: string; label: string }> = {
  gmail_questions: {
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    text: 'text-blue-800',
    label: 'QUESTIONS',
  },
  gmail_summary: {
    bg: 'bg-purple-50',
    border: 'border-purple-200',
    text: 'text-purple-800',
    label: 'SUMMARY',
  },
  gmail_step_questions: {
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    text: 'text-blue-800',
    label: 'QUESTIONS',
  },
  gmail_step_summary_action: {
    bg: 'bg-green-50',
    border: 'border-green-200',
    text: 'text-green-800',
    label: 'SUMMARY_ACTION',
  },
  gmail_step_summary_insight: {
    bg: 'bg-emerald-50',
    border: 'border-emerald-200',
    text: 'text-emerald-800',
    label: 'SUMMARY_INSIGHT',
  },
  gmail_step_classification: {
    bg: 'bg-orange-50',
    border: 'border-orange-200',
    text: 'text-orange-800',
    label: 'CLASSIFICATION',
  },
  gmail_step_judge: {
    bg: 'bg-purple-50',
    border: 'border-purple-200',
    text: 'text-purple-800',
    label: 'LLM_JUDGE',
  },
  claims_truth_check: {
    bg: 'bg-red-50',
    border: 'border-red-200',
    text: 'text-red-800',
    label: 'CLAIMS_CHECK',
  },
  claims_candidate: {
    bg: 'bg-rose-50',
    border: 'border-rose-200',
    text: 'text-rose-800',
    label: 'CLAIMS_CANDIDATE',
  },
  claims_followup_candidate: {
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    text: 'text-amber-800',
    label: 'FOLLOWUP_CANDIDATE',
  },
  claims_judge: {
    bg: 'bg-purple-50',
    border: 'border-purple-200',
    text: 'text-purple-800',
    label: 'CLAIMS_JUDGE',
  },
  claims_followup_judge: {
    bg: 'bg-purple-50',
    border: 'border-purple-200',
    text: 'text-purple-800',
    label: 'FOLLOWUP_JUDGE',
  },
  claims_followup: {
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    text: 'text-amber-800',
    label: 'CLAIMS_FOLLOWUP',
  },
}

const FALLBACK_KIND = {
  bg: 'bg-gray-50',
  border: 'border-gray-200',
  text: 'text-gray-700',
  label: 'INFERENCE',
}

function formatTime(isoString: string): string {
  try {
    const date = new Date(isoString)
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  } catch {
    return isoString
  }
}

function formatDate(isoString: string): string {
  try {
    const date = new Date(isoString)
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return isoString
  }
}

interface TimelineEventProps {
  event: InferenceLogEvent
  isExpanded: boolean
  onToggle: () => void
}

function TimelineEvent({ event, isExpanded, onToggle }: TimelineEventProps) {
  const colors = KIND_COLORS[event.kind] || FALLBACK_KIND

  const payload = event.payload as Record<string, unknown>

  const getSummaryText = (): string => {
    switch (event.kind) {
      case 'gmail_questions':
      case 'gmail_step_questions': {
        const response = payload?.response as { questions?: string[] } | undefined
        const questions = response?.questions || (payload?.output as { questions?: string[] })?.questions
        if (questions && questions.length > 0) {
          return `Generated ${questions.length} question(s): "${questions[0]}"`
        }
        return 'Generated questions'
      }
      case 'gmail_summary': {
        const response = payload?.response as { 
          final_summary?: string
          reasoning?: string 
          top_email_ids?: string[]
        } | undefined
        const reasoning = response?.reasoning
        const topIds = response?.top_email_ids?.length || 0
        if (reasoning) {
          return `${String(reasoning).slice(0, 150)}...`
        }
        return `Generated summary with ${topIds} top emails`
      }
      case 'gmail_step_summary_action': {
        const output = payload?.output as { summary_a?: string } | undefined
        return output?.summary_a
          ? `${String(output.summary_a).slice(0, 100)}...`
          : 'Generated action summary'
      }
      case 'gmail_step_summary_insight': {
        const output = payload?.output as { summary_b?: string } | undefined
        return output?.summary_b
          ? `${String(output.summary_b).slice(0, 100)}...`
          : 'Generated insight summary'
      }
      case 'gmail_step_classification': {
        const output = payload?.output as { classification?: { classified_emails?: unknown[] } } | undefined
        const count = output?.classification?.classified_emails?.length || 0
        return `Classified ${count} email(s)`
      }
      case 'gmail_step_judge': {
        const output = payload?.output as { reasoning?: string } | undefined
        return output?.reasoning
          ? `${String(output.reasoning).slice(0, 100)}...`
          : 'Final judgment rendered'
      }
      case 'claims_truth_check': {
        const response = payload?.response as {
          issues?: unknown[]
          status?: string | null
        } | undefined
        const issueCount = response?.issues?.length || 0
        if (response?.status) {
          return `Status: ${response.status} • ${issueCount} issue(s) flagged`
        }
        return issueCount > 0
          ? `${issueCount} issue(s) flagged`
          : 'Truth check complete'
      }
      case 'claims_candidate': {
        const response = payload?.response as { answer?: string } | undefined
        return response?.answer
          ? `${String(response.answer).slice(0, 100)}...`
          : 'Candidate answer generated'
      }
      case 'claims_followup_candidate': {
        const response = payload?.response as { question?: string } | undefined
        return response?.question
          ? `Follow-up candidate: ${String(response.question).slice(0, 100)}...`
          : 'Follow-up candidate generated'
      }
      case 'claims_judge': {
        const response = payload?.response as { reasoning?: string; winner?: number } | undefined
        if (response?.reasoning) {
          return `${String(response.reasoning).slice(0, 100)}...`
        }
        return response?.winner ? `Judge selected response ${response.winner}` : 'Judge completed'
      }
      case 'claims_followup_judge': {
        const response = payload?.response as {
          reasoning?: string
          question?: string
        } | undefined
        if (response?.reasoning) {
          return `${String(response.reasoning).slice(0, 100)}...`
        }
        return response?.question ? `Selected: ${response.question}` : 'Follow-up judged'
      }
      case 'claims_followup': {
        const response = payload?.response as { next_question?: string } | undefined
        return response?.next_question
          ? `Follow-up: ${response.next_question}`
          : 'No follow-up question'
      }
      default:
        return event.kind ? `Event: ${event.kind}` : 'Processing step'
    }
  }

  const getModel = (): string | null => {
    const model = (payload?.model as string) || null
    if (model) return model
    if (event.backend === 'google_adk') return 'Google ADK'
    if (event.backend === 'crewai') return 'CrewAI'
    return null
  }

  return (
    <div className={`rounded-lg border ${colors.border} ${colors.bg} mb-3`}>
      <button
        onClick={onToggle}
        className="w-full flex items-start gap-3 p-3 text-left"
      >
        <div className="flex-shrink-0 mt-0.5">
          {isExpanded ? (
            <ChevronDown size={16} className={colors.text} />
          ) : (
            <ChevronRight size={16} className={colors.text} />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="text-xs font-mono text-gray-500">
              {formatTime(event.recorded_at)}
            </span>
            <span
              className={`text-xs font-semibold px-2 py-0.5 rounded ${colors.bg} ${colors.text} border ${colors.border}`}
            >
              {KIND_COLORS[event.kind]?.label || event.kind?.toUpperCase() || colors.label}
            </span>
            {getModel() && (
              <span className="text-xs text-gray-400">{getModel()}</span>
            )}
            {event.username && (
              <span className="text-xs text-gray-400">@{event.username}</span>
            )}
          </div>
          <p className={`text-sm ${colors.text}`}>{getSummaryText()}</p>
        </div>
      </button>

      {isExpanded && (
        <div className="px-3 pb-3 pt-0 ml-7">
          <div className="border-t border-gray-200 pt-3 space-y-3">
            {payload?.request && (
              <div>
                <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">
                  Request
                </h4>
                <pre className="text-xs bg-white/50 p-2 rounded border border-gray-200 overflow-x-auto whitespace-pre-wrap max-h-48 overflow-y-auto">
                  {JSON.stringify(payload.request, null, 2)}
                </pre>
              </div>
            )}

            {payload?.response && (
              <div>
                <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">
                  Response
                </h4>
                <pre className="text-xs bg-white/50 p-2 rounded border border-gray-200 overflow-x-auto whitespace-pre-wrap max-h-64 overflow-y-auto">
                  {JSON.stringify(payload.response, null, 2)}
                </pre>
              </div>
            )}

            {payload?.output && (
              <div>
                <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">
                  Output
                </h4>
                <pre className="text-xs bg-white/50 p-2 rounded border border-gray-200 overflow-x-auto whitespace-pre-wrap max-h-64 overflow-y-auto">
                  {JSON.stringify(payload.output, null, 2)}
                </pre>
              </div>
            )}

            <div className="flex gap-4 text-xs text-gray-400 flex-wrap">
              <span>Event: {event.event_id}</span>
              {event.request_id && <span>Request ID: {event.request_id.slice(0, 8)}...</span>}
              <span>Source: {event.source}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

interface InferenceTimelineProps {
  onClose?: () => void
}

export function InferenceTimeline({ onClose }: InferenceTimelineProps) {
  const [events, setEvents] = useState<InferenceLogEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedEvents, setExpandedEvents] = useState<Set<string>>(new Set())
  const [lastFetchTime, setLastFetchTime] = useState<Date | null>(null)

  const fetchEvents = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await getInferenceLogs(100)
      setEvents(response.events)
      setLastFetchTime(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load inference logs')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchEvents()
  }, [])

  const toggleEvent = (eventId: string) => {
    setExpandedEvents((prev) => {
      const next = new Set(prev)
      if (next.has(eventId)) {
        next.delete(eventId)
      } else {
        next.add(eventId)
      }
      return next
    })
  }

  const timelineEvents = events

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow-lg border border-gray-200">
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <Clock size={20} className="text-purple-600" />
          <h2 className="font-semibold text-lg">Inference Timeline</h2>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchEvents}
            disabled={loading}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors disabled:opacity-50"
            title="Refresh"
          >
            <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
              title="Close"
            >
              <X size={18} />
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="flex items-center gap-2 text-gray-500">
              <RefreshCw size={20} className="animate-spin" />
              <span>Loading session data...</span>
            </div>
          </div>
        )}

        {error && !loading && (
          <div className="text-center py-12">
            <p className="text-gray-500 mb-4">{error}</p>
            <button
              onClick={fetchEvents}
              className="px-4 py-2 bg-purple-100 text-purple-700 rounded-lg hover:bg-purple-200 transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {!loading && !error && timelineEvents && timelineEvents.length === 0 && (
          <div className="text-center py-12">
            <Clock size={48} className="mx-auto text-gray-300 mb-4" />
            <p className="text-gray-500">No inference events found</p>
            <p className="text-sm text-gray-400 mt-2">
              Run a Gmail summary or Claims Q&A to see the timeline
            </p>
          </div>
        )}

        {!loading && !error && timelineEvents && timelineEvents.length > 0 && (
          <div>
            <div className="mb-4 text-sm text-gray-500">
              {lastFetchTime && (
                <>
                  Loaded: {formatDate(lastFetchTime.toISOString())}{' '}
                  {formatTime(lastFetchTime.toISOString())}
                </>
              )}
              <span className="ml-2 text-gray-400">
                ({timelineEvents.length} event{timelineEvents.length !== 1 ? 's' : ''})
              </span>
            </div>

            <div className="relative">
              <div className="absolute left-[7px] top-4 bottom-4 w-0.5 bg-gray-200" />

              {timelineEvents.map((event) => (
                <div key={event.event_id} className="relative pl-6">
                  <div className="absolute left-0 top-4 w-4 h-4 rounded-full bg-white border-2 border-purple-400" />
                  <TimelineEvent
                    event={event}
                    isExpanded={expandedEvents.has(event.event_id)}
                    onToggle={() => toggleEvent(event.event_id)}
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="px-4 py-2 border-t border-gray-100 text-xs text-gray-400">
        Data from Redis stream • Real-time events
      </div>
    </div>
  )
}
