import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  createCalendarEvent,
  fetchRandomClaim,
  fetchGmailMessages,
  generateCalendarQuestion,
  generateClaimAnswer,
  generateGmailQuestions,
  generateGmailSummary,
  generatePdf,
  getAIHealth,
  getAIStatus,
} from '../api'
import type { CalendarEventPayload, ClaimQaHistoryEntry } from '../types'
import { Bot, Sparkles, Mail, ArrowUp, BookOpen, Calendar, Inbox, Clock, Flag } from 'lucide-react'
import { InferenceTimeline } from './InferenceTimeline'

interface AIChannelProps {
  channelId: number
  channelName?: string
  showHeader?: boolean
  onCommand?: (command: string) => void
  requestedIntent?: 'gmail' | null
  onIntentHandled?: () => void
  showTimeline?: boolean
  onToggleTimeline?: () => void
}

type ConversationEntry = {
  id: number
  query: string
  response: string
  agent: string
  mode?: 'agent_message' | 'claim_message' | 'claim_answer'
  emails?: any[]
  pdfUrl?: string
  claim?: unknown
  claimFilename?: string
  claimPretty?: string
  reasoning?: string
  followupReasoning?: string
}

type ClaimReportNode = {
  label?: string
  value?: string
  children?: ClaimReportNode[]
}

type ClaimReportSection = {
  title: string
  nodes: ClaimReportNode[]
}

const AI_OPTIONS = [
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
  {
    id: 'claims',
    label: 'Claims Q&A',
    icon: Flag,
    description: "Review a random claim from the People's Archive",
  },
]

export function AIChannel({
  channelId,
  channelName = '#ai',
  showHeader = true,
  onCommand,
  requestedIntent,
  onIntentHandled,
  showTimeline = false,
  onToggleTimeline,
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
    | 'claims'
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
  const [claimPayload, setClaimPayload] = useState<{ claim: unknown; filename?: string } | null>(null)
  const [claimHistory, setClaimHistory] = useState<ClaimQaHistoryEntry[]>([])
  const [claimQuestionCount, setClaimQuestionCount] = useState(0)
  const [claimAskedQuestions, setClaimAskedQuestions] = useState<string[]>([])
  const [claimPendingFollowup, setClaimPendingFollowup] = useState<string | null>(null)

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

  const formatClaim = (payload: unknown) => {
    try {
      return JSON.stringify(payload, null, 2) || ''
    } catch {
      return String(payload)
    }
  }

  const isRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === 'object' && value !== null && !Array.isArray(value)

  const formatLabel = (value: string) =>
    value
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (char) => char.toUpperCase())

  const formatDateValue = (value: string) => {
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) {
      return value
    }
    const hasTime = value.includes('T') || value.includes(':')
    return hasTime ? parsed.toLocaleString() : parsed.toLocaleDateString()
  }

  const formatClaimValue = (value: unknown, keyPath?: string) => {
    if (value === null || value === undefined) {
      return 'Not reported'
    }
    if (typeof value === 'boolean') {
      return value ? 'Yes' : 'No'
    }
    if (typeof value === 'number') {
      if (keyPath?.toLowerCase().endsWith('_eur')) {
        return `€${value.toLocaleString('en-US')}`
      }
      return value.toLocaleString('en-US')
    }
    if (typeof value === 'string') {
      const trimmed = value.trim()
      if (!trimmed) {
        return 'Not reported'
      }
      const normalizedKey = keyPath?.toLowerCase() ?? ''
      if (normalizedKey.includes('date') || normalizedKey.includes('timestamp') || normalizedKey.endsWith('_at')) {
        return formatDateValue(trimmed)
      }
      return trimmed
    }
    return JSON.stringify(value)
  }

  const MAX_REPORT_DEPTH = 5
  const MAX_ARRAY_ITEMS = 50

  const buildClaimNode = (
    label: string | undefined,
    value: unknown,
    depth: number,
    keyPath: string,
  ): ClaimReportNode => {
    if (value === null || value === undefined) {
      return { label, value: 'Not reported' }
    }

    if (depth >= MAX_REPORT_DEPTH) {
      return { label, value: formatClaimValue(value, keyPath) }
    }

    if (Array.isArray(value)) {
      if (value.length === 0) {
        return { label, value: 'No entries recorded.' }
      }
      const children = value.slice(0, MAX_ARRAY_ITEMS).map((item, index) => {
        const needsLabel = isRecord(item) || Array.isArray(item)
        const itemLabel = needsLabel ? `Item ${index + 1}` : undefined
        return buildClaimNode(itemLabel, item, depth + 1, `${keyPath}[${index}]`)
      })
      if (value.length > MAX_ARRAY_ITEMS) {
        children.push({ value: `...${value.length - MAX_ARRAY_ITEMS} more items` })
      }
      return { label, children }
    }

    if (isRecord(value)) {
      const entries = Object.entries(value)
      if (!entries.length) {
        return { label, value: 'No entries recorded.' }
      }
      const children = entries.map(([key, nestedValue]) =>
        buildClaimNode(formatLabel(key), nestedValue, depth + 1, `${keyPath}.${key}`),
      )
      return { label, children }
    }

    return { label, value: formatClaimValue(value, keyPath) }
  }

  const buildSectionNodes = (
    value: unknown,
    keyPath: string,
    itemLabel?: string,
  ): ClaimReportNode[] => {
    if (value === null || value === undefined) {
      return [{ value: 'Not reported' }]
    }

    if (Array.isArray(value)) {
      if (!value.length) {
        return [{ value: 'No entries recorded.' }]
      }
      return value.slice(0, MAX_ARRAY_ITEMS).map((item, index) => {
        const needsLabel = isRecord(item) || Array.isArray(item)
        const labelPrefix = itemLabel ?? 'Item'
        const label = needsLabel ? `${labelPrefix} ${index + 1}` : undefined
        return buildClaimNode(label, item, 1, `${keyPath}[${index}]`)
      })
    }

    if (isRecord(value)) {
      return Object.entries(value).map(([key, nestedValue]) =>
        buildClaimNode(formatLabel(key), nestedValue, 1, `${keyPath}.${key}`),
      )
    }

    return [{ value: formatClaimValue(value, keyPath) }]
  }

  const buildClaimReport = (payload: unknown): ClaimReportSection[] => {
    if (!isRecord(payload)) {
      return [
        {
          title: 'Collective Summary',
          nodes: [{ value: 'Claim dossier is unavailable or malformed.' }],
        },
      ]
    }

    const record = payload
    const usedKeys = new Set<string>()
    const sections: ClaimReportSection[] = []

    const dossierKeys = [
      'claim_id',
      'policy_id',
      'status',
      'claim_type',
      'loss_date',
      'reported_date',
    ]

    dossierKeys.forEach((key) => usedKeys.add(key))

    sections.push({
      title: "People's Dossier",
      nodes: dossierKeys.map((key) => buildClaimNode(formatLabel(key), record[key], 1, key)),
    })

    const orderedSections: Array<{ title: string; key: string; itemLabel?: string }> = [
      { title: 'Incident & Intake', key: 'claim_intake' },
      { title: 'Insured & Property', key: 'insured' },
      { title: 'Policy & Limits', key: 'policy' },
      { title: 'Coverage Review', key: 'coverage_review' },
      { title: 'Resolution & Payment', key: 'resolution' },
      { title: 'Document Register', key: 'documents', itemLabel: 'Document' },
      { title: 'Adjuster Notes', key: 'adjuster_notes', itemLabel: 'Note' },
      { title: 'Collective Questions', key: 'conversation_seed_questions' },
    ]

    orderedSections.forEach((section) => {
      usedKeys.add(section.key)
      sections.push({
        title: section.title,
        nodes: buildSectionNodes(record[section.key], section.key, section.itemLabel),
      })
    })

    const additionalNodes = Object.entries(record)
      .filter(([key]) => !usedKeys.has(key))
      .map(([key, value]) => buildClaimNode(formatLabel(key), value, 1, key))

    if (additionalNodes.length) {
      sections.push({ title: 'Additional Signals', nodes: additionalNodes })
    }

    return sections
  }

  const renderClaimNodes = (nodes: ClaimReportNode[], depth = 0) => (
    <ul className={`claim-report-list ${depth > 0 ? 'claim-report-list--nested' : ''}`}>
      {nodes.map((node, nodeIndex) => (
        <li key={`${node.label || 'value'}-${nodeIndex}`}>
          {node.label && (
            <span className="claim-report-label">
              {node.label}
              {node.value ? ': ' : ''}
            </span>
          )}
          {node.value && <span className="claim-report-value">{node.value}</span>}
          {node.children && renderClaimNodes(node.children, depth + 1)}
        </li>
      ))}
    </ul>
  )

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
    setClaimPayload(null)
    setClaimHistory([])
    setClaimQuestionCount(0)
    setClaimAskedQuestions([])
    setClaimPendingFollowup(null)
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

      if (optionId === 'claims') {
        setStreamProgress("Requesting a claim from the People's Archive...")
        const { filename, claim } = await fetchRandomClaim()
        const claimPretty = formatClaim(claim)
        const rallyingCall =
          `Comrade, claim ${filename} has been delivered for collective review. ` +
          'Ask your questions below to serve the shared record.'
        setClaimPayload({ claim, filename })
        setClaimHistory([])
        setClaimQuestionCount(0)
        setClaimAskedQuestions([])
        setClaimPendingFollowup(null)
        setResponses([
          {
            id: Date.now(),
            query: '',
            response: rallyingCall,
            agent: 'Claims Q&A',
            mode: 'claim_message',
            claim,
            claimFilename: filename,
            claimPretty,
          },
        ])
        setGmailStage('claims')
        setActiveQuestion(`Ask about ${filename}...`)
        setStreamProgress(null)
        setIsSubmitting(false)
        return
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to start. Please try again.'
      setStreamError(message)
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
      if (gmailStage === 'claims') {
        if (!claimPayload) {
          setStreamError('No claim loaded. Start over to fetch a claim.')
          setIsSubmitting(false)
          setQuery('')
          return
        }

        if (claimQuestionCount >= 5) {
          setStreamError('Maximum of 5 questions reached for this claim.')
          setIsSubmitting(false)
          setQuery('')
          return
        }

        setStreamProgress('Analyzing claim details...')
        const nextCount = claimQuestionCount + 1
        const questionText = claimPendingFollowup
          ? `${claimPendingFollowup}\nUser response: ${trimmedAnswer}`
          : trimmedAnswer
        const askedQuestions = Array.from(
          new Set(
            [
              ...claimAskedQuestions,
              claimPendingFollowup || '',
            ].map((item) => item.trim()).filter(Boolean),
          ),
        )
        const result = await generateClaimAnswer(
          claimPayload.claim,
          questionText,
          claimHistory,
          nextCount,
          askedQuestions,
        )

        setClaimQuestionCount(nextCount)
        setClaimHistory((prev) => [...prev, { question: questionText, answer: result.answer }])
        setClaimPendingFollowup(null)

        setResponses((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            query: '',
            response: result.answer,
            agent: 'Claims Q&A',
            mode: 'claim_answer',
            reasoning: result.reasoning,
          },
        ])

        if (result.next_question && !result.done) {
          const followupId = Date.now() + 2
          const followupQuestion = result.next_question.trim()
          setResponses((prev) => [
            ...prev,
            {
              id: followupId,
              query: '',
              response: followupQuestion,
              agent: 'Claims Q&A',
              mode: 'claim_answer',
              followupReasoning: result.followup_reasoning || undefined,
            },
          ])
          setClaimAskedQuestions((prev) =>
            prev.includes(followupQuestion) ? prev : [...prev, followupQuestion],
          )
          setClaimPendingFollowup(followupQuestion)
          setActiveQuestion(followupQuestion)
        } else {
          let fallbackPrompt = 'Ask another claim question...'
          if (nextCount >= 5) {
            fallbackPrompt = 'Question limit reached for this claim. Start over to load a new one.'
          } else if (claimPayload.filename) {
            fallbackPrompt = `Ask about ${claimPayload.filename}...`
          }
          if (result.done) {
            fallbackPrompt = 'Conversation complete. Ask another claim question if needed.'
          }
          setActiveQuestion(fallbackPrompt)
          setClaimPendingFollowup(null)
        }

        setStreamProgress(null)
        setIsSubmitting(false)
        setQuery('')
        return
      }

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
      const message =
        gmailStage === 'claims'
          ? 'Claims Q&A failed. Please try again.'
          : 'Gmail agent failed. Please try again.'
      setStreamError(message)
      setStreamProgress(null)
      console.error(err)
    } finally {
      setIsSubmitting(false)
      setQuery('')
    }
  }

  const isFlowComplete =
    gmailStage === 'summary' || gmailStage === 'calendar-done' || gmailStage === 'claims'
  const showOptionCards = gmailStage === 'choice' && responses.length === 0 && !isSubmitting
  const isClaimsMode = gmailStage === 'claims'
  const isCalendarMode = gmailStage.includes('calendar')
  const aiUnavailable = Boolean(healthMessage) || Boolean(aiAccessMessage) || aiStatus?.available === false
  const aiUnavailableMessage =
    aiAccessMessage || healthMessage || 'AI service is not configured yet. Please contact administrator.'
  const claimsQuestionLimitReached = isClaimsMode && claimQuestionCount >= 5
  const assistantLabel = isClaimsMode
    ? 'Claims Q&A'
    : isCalendarMode
      ? 'Calendar Assistant'
      : 'Gmail Assistant'
  const assistantBadgeClass = isClaimsMode
    ? 'bg-red-100 text-red-700'
    : 'bg-amber-100 text-amber-700'
  const assistantTagClass = isClaimsMode
    ? 'bg-red-100/70 text-red-800'
    : 'bg-amber-100/50 text-amber-800'
  const assistantIcon = isClaimsMode ? Flag : isCalendarMode ? Calendar : Sparkles
  const assistantIconClass = isClaimsMode ? 'text-red-600' : 'text-amber-600'
  const AssistantIcon = assistantIcon
  const inputDisabled =
    isSubmitting || (!isClaimsMode && aiUnavailable) || claimsQuestionLimitReached

  return (
    <div ref={containerRef} className="flex-1 flex flex-col relative min-h-0">
      {/* Channel header */}
      {showHeader && (
        <div className="p-3 md:p-4 border-b chat-header">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <AssistantIcon size={18} className={`${assistantIconClass} flex-shrink-0`} />
              <div className="font-semibold text-sm md:text-base truncate">{channelName}</div>
              <span
                className={`text-xs px-2 py-0.5 rounded-full flex-shrink-0 ${assistantBadgeClass}`}
              >
                {assistantLabel}
              </span>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {aiStatus && (
                <div className="text-xs chat-meta">
                  {aiStatus.remaining_requests}/{aiStatus.max_requests_per_hour}{' '}
                  requests left
                </div>
              )}
              <button
                onClick={() => onToggleTimeline?.()}
                className={`p-2 rounded-lg transition-colors ${
                  showTimeline
                    ? 'bg-purple-100 text-purple-700'
                    : 'hover:bg-gray-100 text-gray-500'
                }`}
                title="View Inference Timeline"
              >
                <Clock size={18} />
              </button>
            </div>
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
              <Sparkles size={24} className="md:w-8 md:h-8 text-amber-600" />
            </div>
            <h2 className="text-lg md:text-xl font-semibold mb-2">AI Assistants</h2>
            <p className="chat-meta mb-6 md:mb-8 max-w-md mx-auto text-sm md:text-base">
              Choose what you'd like to do:
            </p>

            {/* Option cards */}
            <div className="grid gap-3 md:gap-4 max-w-lg mx-auto">
              {AI_OPTIONS.map((option) => {
                const Icon = option.icon
                const isClaimsOption = option.id === 'claims'
                const isOptionDisabled = isSubmitting || (!isClaimsOption && aiUnavailable)
                return (
                  <button
                    key={option.id}
                    onClick={() => handleOptionSelect(option.id)}
                    disabled={isOptionDisabled}
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

            {streamError && !isSubmitting && (
              <div className="mt-6 p-3 md:p-4 rounded-xl bg-red-50 border border-red-200 max-w-lg mx-auto">
                <div className="text-red-800 font-medium text-sm md:text-base">Request failed</div>
                <div className="text-red-700 text-xs md:text-sm">{streamError}</div>
              </div>
            )}
          </div>
        )}

        {/* Error messages at top */}
        {aiUnavailable && showOptionCards && (
          <div className="p-3 md:p-4 rounded-xl bg-red-50 border border-red-200 mb-4 max-w-lg mx-auto">
            <div className="text-red-800 font-medium text-sm md:text-base">AI unavailable</div>
            <div className="text-red-700 text-xs md:text-sm">
              {aiUnavailableMessage} Claims Q&A is still available.
            </div>
          </div>
        )}

        {/* Conversation */}
        {responses.map((response, index) => {
          const isClaimMessage = response.mode === 'claim_message'
          const isClaimAnswer = response.mode === 'claim_answer'
          const isClaimVariant = isClaimMessage || isClaimAnswer
          const responseCardClass = isClaimVariant
            ? 'bg-red-50 border-red-200'
            : 'bg-amber-50 border-amber-200'
          const responseAvatarClass = isClaimVariant ? 'bg-red-200' : 'bg-amber-200'
          const responseIconClass = isClaimVariant ? 'text-red-700' : 'text-amber-700'
          const responseTitleClass = isClaimVariant ? 'text-red-800' : 'text-amber-800'
          const responseBadgeClass = isClaimVariant
            ? 'bg-red-200 text-red-800'
            : 'bg-amber-200 text-amber-800'
          const responseTextClass = isClaimVariant ? 'text-red-900' : 'text-amber-900'
          const ResponseIcon = isClaimVariant ? Flag : Mail
          const claimReport = isClaimMessage && response.claim ? buildClaimReport(response.claim) : []

          return (
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
              <div className={`flex gap-2 md:gap-3 p-3 md:p-4 rounded-xl border ${responseCardClass}`}>
                <div
                  className={`w-6 h-6 md:w-8 md:h-8 rounded-full flex items-center justify-center flex-shrink-0 ${responseAvatarClass}`}
                >
                  <ResponseIcon size={14} className={`md:w-4 md:h-4 ${responseIconClass}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <div className={`text-xs md:text-sm font-semibold ${responseTitleClass}`}>
                      {response.agent}
                    </div>
                    <span className={`text-xs px-1.5 py-0.5 rounded-full ${responseBadgeClass}`}>
                      AI
                    </span>
                  </div>
                  <div className={`${responseTextClass} whitespace-pre-wrap text-sm md:text-base break-words`}>
                    {isClaimMessage && (
                      <div className="mb-3">
                        <div className="text-xs uppercase tracking-wider text-red-700">
                          People's Claim Archive
                        </div>
                        {response.claimFilename && (
                          <div className="text-xs text-red-700">File: {response.claimFilename}</div>
                        )}
                      </div>
                    )}
                    {response.response}

                    {response.reasoning && (
                      <div className="mt-3 rounded-lg border border-red-200/70 bg-red-50/80 px-3 py-2 text-xs md:text-sm text-red-900">
                        <div className="text-[10px] uppercase tracking-wider text-red-700 mb-1">Reasoning</div>
                        <div className="whitespace-pre-wrap break-words">{response.reasoning}</div>
                      </div>
                    )}

                    {response.followupReasoning && (
                      <div className="mt-3 rounded-lg border border-red-200/70 bg-red-50/80 px-3 py-2 text-xs md:text-sm text-red-900">
                        <div className="text-[10px] uppercase tracking-wider text-red-700 mb-1">Follow-up reasoning</div>
                        <div className="whitespace-pre-wrap break-words">
                          {response.followupReasoning}
                        </div>
                      </div>
                    )}

                    {isClaimMessage && response.claim && (
                      <div className="mt-4 rounded-lg border border-red-200/80 bg-red-50/60 p-4 claim-report">
                        <div className="text-[10px] uppercase tracking-[0.3em] text-red-700 mb-3">
                          Collective Report
                        </div>
                        <div className="space-y-4">
                          {claimReport.map((section, sectionIndex) => (
                            <div key={`${section.title}-${sectionIndex}`}>
                              <div className="claim-report-title text-red-800 text-xs">
                                {section.title}
                              </div>
                              <div className="mt-2 text-sm md:text-base">
                                {renderClaimNodes(section.nodes)}
                              </div>
                            </div>
                          ))}
                        </div>
                        {response.claimPretty && (
                          <details className="claim-report-details mt-4">
                            <summary className="text-xs uppercase tracking-widest text-red-700">
                              Full dossier (raw JSON)
                            </summary>
                            <pre className="mt-2 text-xs font-mono text-red-900 whitespace-pre-wrap break-words">
                              {response.claimPretty}
                            </pre>
                          </details>
                        )}
                      </div>
                    )}
                    
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
          )
        })}

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
              <span className={`text-xs md:text-sm font-medium px-2 py-1 rounded-md ${assistantTagClass}`}>
                {assistantLabel}
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
                  disabled={inputDisabled}
                />
              </div>
              <button
                type="submit"
                disabled={
                  inputDisabled || !query.trim()
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

      {/* Inference Timeline Panel */}
      {showTimeline && (
        <div className="absolute inset-0 z-30 bg-white/95 backdrop-blur-sm">
          <InferenceTimeline onClose={() => onToggleTimeline?.()} />
        </div>
      )}
    </div>
  )
}
