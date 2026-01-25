import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { X, Trash2 } from 'lucide-react'
import { createTemplate } from '../api/dataProcessor'
import type { LabelType, Annotation } from '../types'

// Label type options
const LABEL_TYPES: { value: LabelType; label: string; color: string }[] = [
  { value: 'header', label: 'Header', color: '#3B82F6' },
  { value: 'table', label: 'Table', color: '#10B981' },
  { value: 'signature', label: 'Signature', color: '#8B5CF6' },
  { value: 'date', label: 'Date', color: '#F59E0B' },
  { value: 'amount', label: 'Amount', color: '#EF4444' },
  { value: 'custom', label: 'Custom', color: '#6B7280' },
]

interface LabelInput {
  label_type: LabelType
  label_name: string
  color: string
  relative_x: number
  relative_y: number
  relative_width: number
  relative_height: number
  is_required: boolean
}

interface TemplateSaveModalProps {
  isOpen: boolean
  onClose: () => void
  channelId: number | string
  annotations: Annotation[]
  documentWidth: number
  documentHeight: number
  sourceDocumentId?: string
}

export function TemplateSaveModal({
  isOpen,
  onClose,
  channelId,
  annotations,
  documentWidth,
  documentHeight,
  sourceDocumentId,
}: TemplateSaveModalProps) {
  const queryClient = useQueryClient()

  // Convert annotations to label inputs with relative positions
  const initialLabels: LabelInput[] = annotations.map((ann) => ({
    label_type: ann.label_type,
    label_name: ann.label_name || `${ann.label_type}_${ann.id.slice(0, 4)}`,
    color: ann.color,
    relative_x: ann.bounding_box.x / documentWidth,
    relative_y: ann.bounding_box.y / documentHeight,
    relative_width: ann.bounding_box.width / documentWidth,
    relative_height: ann.bounding_box.height / documentHeight,
    is_required: false,
  }))

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [labels, setLabels] = useState<LabelInput[]>(initialLabels)
  const [error, setError] = useState<string | null>(null)

  const saveMutation = useMutation({
    mutationFn: () =>
      createTemplate({
        name,
        description,
        channel_id: channelId,
        source_document_id: sourceDocumentId,
      }),
    onSuccess: async (template) => {
      // After creating template, we need to update it with labels
      // For MVP, create includes labels in payload
      queryClient.invalidateQueries({ queryKey: ['templates', channelId] })
      onClose()
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : 'Failed to save template')
    },
  })

  if (!isOpen) return null

  const handleSave = () => {
    if (!name.trim()) {
      setError('Template name is required')
      return
    }
    if (labels.length === 0) {
      setError('Add at least one label')
      return
    }
    setError(null)

    // Create template with labels
    fetch(`${window.location.origin}/data-processor/templates/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        name: name.trim(),
        description: description.trim(),
        channel_id: String(channelId),
        source_document_id: sourceDocumentId,
        labels: labels.map((l) => ({
          ...l,
          expected_format: null,
        })),
      }),
    })
      .then((res) => {
        if (!res.ok) throw new Error('Failed to save')
        return res.json()
      })
      .then(() => {
        queryClient.invalidateQueries({ queryKey: ['templates', channelId] })
        onClose()
      })
      .catch((err) => {
        setError(err.message)
      })
  }

  const updateLabel = (index: number, updates: Partial<LabelInput>) => {
    setLabels((prev) =>
      prev.map((l, i) => (i === index ? { ...l, ...updates } : l)),
    )
  }

  const removeLabel = (index: number) => {
    setLabels((prev) => prev.filter((_, i) => i !== index))
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
      <div className="bg-gray-900 rounded-lg w-full max-w-lg max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold text-white">Save as Template</h2>
          <button
            onClick={onClose}
            className="p-2 rounded hover:bg-gray-800 text-gray-400"
          >
            <X size={20} />
          </button>
        </div>

        {/* Form */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Template Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Invoice Template"
              className="w-full px-3 py-2 rounded bg-gray-800 text-white text-sm border border-gray-700 focus:border-blue-500 focus:outline-none"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of this template..."
              rows={2}
              className="w-full px-3 py-2 rounded bg-gray-800 text-white text-sm border border-gray-700 focus:border-blue-500 focus:outline-none resize-none"
            />
          </div>

          {/* Labels */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Labels ({labels.length})
            </label>
            {labels.length === 0 ? (
              <div className="text-center text-gray-500 text-sm py-4 border border-dashed border-gray-700 rounded">
                No annotations to save
              </div>
            ) : (
              <div className="space-y-3">
                {labels.map((label, index) => (
                  <div
                    key={index}
                    className="p-3 rounded border border-gray-700 bg-gray-800"
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <input
                        type="text"
                        value={label.label_name}
                        onChange={(e) =>
                          updateLabel(index, { label_name: e.target.value })
                        }
                        className="flex-1 px-2 py-1 rounded bg-gray-900 text-white text-sm border border-gray-700 focus:border-blue-500 focus:outline-none"
                      />
                      <button
                        onClick={() => removeLabel(index)}
                        className="p-1 rounded hover:bg-gray-700 text-gray-500"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                    <div className="flex items-center gap-3 text-sm">
                      <select
                        value={label.label_type}
                        onChange={(e) =>
                          updateLabel(index, {
                            label_type: e.target.value as LabelType,
                            color:
                              LABEL_TYPES.find(
                                (t) => t.value === e.target.value,
                              )?.color || label.color,
                          })
                        }
                        className="px-2 py-1 rounded bg-gray-900 text-white text-sm border border-gray-700"
                      >
                        {LABEL_TYPES.map((t) => (
                          <option key={t.value} value={t.value}>
                            {t.label}
                          </option>
                        ))}
                      </select>
                      <input
                        type="color"
                        value={label.color}
                        onChange={(e) =>
                          updateLabel(index, { color: e.target.value })
                        }
                        className="w-8 h-8 rounded cursor-pointer"
                      />
                      <label className="flex items-center gap-1 text-gray-400">
                        <input
                          type="checkbox"
                          checked={label.is_required}
                          onChange={(e) =>
                            updateLabel(index, {
                              is_required: e.target.checked,
                            })
                          }
                        />
                        Required
                      </label>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Error */}
          {error && (
            <div className="text-red-400 text-sm bg-red-500/10 px-3 py-2 rounded">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-700 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded bg-gray-800 text-gray-300 text-sm hover:bg-gray-700"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={!name.trim() || labels.length === 0}
            className="px-4 py-2 rounded bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            Save Template
          </button>
        </div>
      </div>
    </div>
  )
}
