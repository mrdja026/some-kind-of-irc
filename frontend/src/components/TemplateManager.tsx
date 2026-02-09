import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { X, Search, Plus, Trash2, Layout } from 'lucide-react'
import {
  listTemplates,
  deleteTemplate,
  applyTemplate,
} from '../api/dataProcessor'
import type { Template, LabelType } from '../types'

// Label type colors
const LABEL_COLORS: Record<LabelType, string> = {
  header: '#3B82F6',
  table: '#10B981',
  signature: '#8B5CF6',
  date: '#F59E0B',
  amount: '#EF4444',
  custom: '#6B7280',
}

interface TemplateManagerProps {
  channelId: number | string
  isOpen: boolean
  onClose: () => void
  onApplyTemplate?: (templateId: string) => void
  selectedDocumentId?: string
  onCreateNew?: () => void
}

export function TemplateManager({
  channelId,
  isOpen,
  onClose,
  onApplyTemplate,
  selectedDocumentId,
  onCreateNew,
}: TemplateManagerProps) {
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data: templates = [], isLoading } = useQuery({
    queryKey: ['templates', channelId],
    queryFn: () => listTemplates(channelId),
    enabled: isOpen && !!channelId,
  })

  const deleteMutation = useMutation({
    mutationFn: deleteTemplate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['templates', channelId] })
      setSelectedId(null)
    },
  })

  const applyMutation = useMutation({
    mutationFn: (templateId: string) =>
      applyTemplate(selectedDocumentId!, { template_id: templateId }),
    onSuccess: () => {
      onApplyTemplate?.(selectedId!)
      onClose()
    },
  })

  if (!isOpen) return null

  const filtered = templates.filter(
    (t) =>
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.description?.toLowerCase().includes(search.toLowerCase()),
  )

  const selectedTemplate = templates.find((t) => t.id === selectedId)

  const handleApply = () => {
    if (selectedId && selectedDocumentId) {
      applyMutation.mutate(selectedId)
    }
  }

  const handleDelete = () => {
    if (selectedId && window.confirm('Delete this template?')) {
      deleteMutation.mutate(selectedId)
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
      <div className="bg-gray-900 rounded-lg w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold text-white">Templates</h2>
          <button
            onClick={onClose}
            className="p-2 rounded hover:bg-gray-800 text-gray-400"
          >
            <X size={20} />
          </button>
        </div>

        {/* Search and Actions */}
        <div className="p-4 border-b border-gray-700 flex gap-3">
          <div className="flex-1 relative">
            <Search
              size={18}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500"
            />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search templates..."
              className="w-full pl-10 pr-4 py-2 rounded bg-gray-800 text-white text-sm border border-gray-700 focus:border-blue-500 focus:outline-none"
            />
          </div>
          {onCreateNew && (
            <button
              onClick={onCreateNew}
              className="flex items-center gap-2 px-4 py-2 rounded bg-blue-600 text-white text-sm hover:bg-blue-700"
            >
              <Plus size={18} />
              New
            </button>
          )}
        </div>

        {/* Template Grid */}
        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <div className="text-center text-gray-500 py-8">Loading...</div>
          ) : filtered.length === 0 ? (
            <div className="text-center text-gray-500 py-8">
              {templates.length === 0
                ? 'No templates yet. Create annotations and save as template.'
                : 'No templates match your search.'}
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              {filtered.map((template) => (
                <TemplateCard
                  key={template.id}
                  template={template}
                  selected={selectedId === template.id}
                  onClick={() => setSelectedId(template.id)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Footer Actions */}
        {selectedTemplate && (
          <div className="p-4 border-t border-gray-700 flex items-center justify-between">
            <div className="text-sm text-gray-400">
              Selected:{' '}
              <span className="text-white">{selectedTemplate.name}</span>
              {' · '}
              {selectedTemplate.labels.length} labels
              {' · '}v{selectedTemplate.version}
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleDelete}
                disabled={deleteMutation.isPending}
                className="px-3 py-2 rounded bg-red-600/20 text-red-400 text-sm hover:bg-red-600/30 disabled:opacity-50"
              >
                <Trash2 size={16} />
              </button>
              <button
                onClick={handleApply}
                disabled={!selectedDocumentId || applyMutation.isPending}
                className="px-4 py-2 rounded bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:opacity-50"
              >
                {applyMutation.isPending ? 'Applying...' : 'Apply to Document'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// Simple template card with preview
function TemplateCard({
  template,
  selected,
  onClick,
}: {
  template: Template
  selected: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-3 rounded border transition-colors ${
        selected
          ? 'border-blue-500 bg-blue-500/10'
          : 'border-gray-700 bg-gray-800 hover:border-gray-600'
      }`}
    >
      {/* Preview area showing label positions */}
      <div className="aspect-[4/3] bg-gray-900 rounded mb-2 relative overflow-hidden">
        {template.labels.length > 0 ? (
          template.labels.map((label) => (
            <div
              key={label.id}
              className="absolute border-2 rounded-sm"
              style={{
                left: `${label.relative_x * 100}%`,
                top: `${label.relative_y * 100}%`,
                width: `${label.relative_width * 100}%`,
                height: `${label.relative_height * 100}%`,
                borderColor: LABEL_COLORS[label.label_type] || '#6B7280',
                backgroundColor:
                  `${LABEL_COLORS[label.label_type]}20` || '#6B728020',
              }}
            />
          ))
        ) : (
          <div className="flex items-center justify-center h-full text-gray-600">
            <Layout size={24} />
          </div>
        )}
      </div>

      {/* Template info */}
      <div className="font-medium text-white text-sm truncate">
        {template.name}
      </div>
      <div className="text-xs text-gray-500 mt-1">
        {template.labels.length} labels · v{template.version}
      </div>
    </button>
  )
}
