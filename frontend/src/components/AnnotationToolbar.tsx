import {
  MousePointer2,
  Square,
  Trash2,
  FileText,
  Table,
  PenTool,
  Calendar,
  DollarSign,
  Layout,
} from 'lucide-react'
import type { LabelType, Template } from '../types'

interface AnnotationToolbarProps {
  activeLabelType: LabelType
  onLabelTypeChange: (type: LabelType) => void
  tool: 'select' | 'draw'
  onToolChange: (tool: 'select' | 'draw') => void
  labelName: string
  onLabelNameChange: (name: string) => void
  onDelete: () => void
  hasSelection: boolean
  templates: Template[]
  onApplyTemplate: (templateId: string) => void
  isLabelNameRequired?: boolean
  labelNameError?: string | null
  disableLabelTypes?: boolean
  labelInputRef?: React.RefObject<HTMLInputElement>
}

// Label type configuration
const LABEL_TYPES: {
  type: LabelType
  label: string
  color: string
  icon: React.ReactNode
}[] = [
  {
    type: 'header',
    label: 'Header',
    color: '#3B82F6',
    icon: <FileText size={16} />,
  },
  {
    type: 'table',
    label: 'Table',
    color: '#10B981',
    icon: <Table size={16} />,
  },
  {
    type: 'signature',
    label: 'Signature',
    color: '#8B5CF6',
    icon: <PenTool size={16} />,
  },
  {
    type: 'date',
    label: 'Date',
    color: '#F59E0B',
    icon: <Calendar size={16} />,
  },
  {
    type: 'amount',
    label: 'Amount',
    color: '#EF4444',
    icon: <DollarSign size={16} />,
  },
]

export function AnnotationToolbar({
  activeLabelType,
  onLabelTypeChange,
  tool,
  onToolChange,
  labelName,
  onLabelNameChange,
  onDelete,
  hasSelection,
  templates,
  onApplyTemplate,
  isLabelNameRequired,
  labelNameError,
  disableLabelTypes,
  labelInputRef,
}: AnnotationToolbarProps) {
  return (
    <div className="w-64 bg-gray-900 border-r border-gray-700 flex flex-col">
      {/* Tools Section */}
      <div className="p-3 border-b border-gray-700">
        <h3 className="text-xs uppercase tracking-wider font-semibold text-gray-400 mb-3">
          Tools
        </h3>
        <div className="flex gap-2">
          <button
            onClick={() => onToolChange('select')}
            className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded text-sm min-h-[44px] ${
              tool === 'select'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
            }`}
          >
            <MousePointer2 size={18} />
            Select
          </button>
          <button
            onClick={() => onToolChange('draw')}
            className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded text-sm min-h-[44px] ${
              tool === 'draw'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
            }`}
          >
            <Square size={18} />
            Draw
          </button>
        </div>
      </div>

      {/* Label Types Section */}
      <div className="p-3 border-b border-gray-700">
        <h3 className="text-xs uppercase tracking-wider font-semibold text-gray-400 mb-3">
          Label Type
        </h3>
        <div className="grid grid-cols-2 gap-2">
          {LABEL_TYPES.map(({ type, label, color, icon }) => (
            <button
              key={type}
              onClick={() => onLabelTypeChange(type)}
              disabled={disableLabelTypes}
              className={`flex items-center gap-2 px-3 py-2 rounded text-sm min-h-[44px] ${
                activeLabelType === type && !disableLabelTypes
                  ? 'ring-2 ring-blue-500'
                  : 'hover:bg-gray-800'
              }`}
              style={{
                backgroundColor:
                  activeLabelType === type && !disableLabelTypes
                    ? `${color}33`
                    : 'rgb(31 41 55)',
                color:
                  activeLabelType === type && !disableLabelTypes
                    ? color
                    : '#9CA3AF',
                opacity: disableLabelTypes ? 0.4 : 1,
                cursor: disableLabelTypes ? 'not-allowed' : 'pointer',
              }}
            >
              {icon}
              <span className="truncate">{label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Label Name Input */}
      <div className="p-3 border-b border-gray-700">
        <h3 className="text-xs uppercase tracking-wider font-semibold text-gray-400 mb-3">
          Label Name
        </h3>
        <input
          type="text"
          ref={labelInputRef}
          value={labelName}
          onChange={(e) => onLabelNameChange(e.target.value)}
          placeholder={`${activeLabelType} label`}
          className="w-full px-3 py-2 rounded bg-gray-800 text-white text-sm border border-gray-700 focus:border-blue-500 focus:outline-none min-h-[44px]"
          aria-invalid={isLabelNameRequired ? 'true' : 'false'}
          required={isLabelNameRequired}
        />
        <p className="text-xs text-gray-500 mt-2">
          {isLabelNameRequired
            ? 'Required for custom labels.'
            : 'Optional; will auto-name if left blank.'}
        </p>
        {labelNameError && (
          <p className="text-xs text-red-400 mt-1">{labelNameError}</p>
        )}
      </div>

      {/* Actions Section */}
      <div className="p-3 border-b border-gray-700">
        <h3 className="text-xs uppercase tracking-wider font-semibold text-gray-400 mb-3">
          Actions
        </h3>
        <button
          onClick={onDelete}
          disabled={!hasSelection}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded text-sm bg-red-600/20 text-red-400 hover:bg-red-600/30 disabled:opacity-50 disabled:cursor-not-allowed min-h-[44px]"
        >
          <Trash2 size={16} />
          Delete Selected
        </button>
      </div>

      {/* Templates Section */}
      <div className="flex-1 overflow-y-auto p-3">
        <h3 className="text-xs uppercase tracking-wider font-semibold text-gray-400 mb-3">
          Templates
        </h3>
        {templates.length === 0 ? (
          <div className="text-center text-gray-500 text-sm py-4">
            No templates available.
            <br />
            Create annotations and save as template.
          </div>
        ) : (
          <div className="space-y-2">
            {templates.map((template) => (
              <button
                key={template.id}
                onClick={() => onApplyTemplate(template.id)}
                className="w-full flex items-center gap-3 px-3 py-3 rounded bg-gray-800 hover:bg-gray-700 text-left text-sm min-h-[44px]"
              >
                <Layout size={16} className="text-gray-400 flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-white truncate">
                    {template.name}
                  </div>
                  {template.description && (
                    <div className="text-xs text-gray-500 truncate">
                      {template.description}
                    </div>
                  )}
                  <div className="text-xs text-gray-500">
                    {template.labels.length} labels
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Keyboard Shortcuts */}
      <div className="p-3 border-t border-gray-700 bg-gray-950">
        <h3 className="text-xs uppercase tracking-wider font-semibold text-gray-400 mb-2">
          Shortcuts
        </h3>
        <div className="grid grid-cols-2 gap-1 text-xs text-gray-500">
          <div>
            <kbd className="px-1 py-0.5 bg-gray-800 rounded">Esc</kbd> Close
          </div>
          <div>
            <kbd className="px-1 py-0.5 bg-gray-800 rounded">Del</kbd> Delete
          </div>
          <div>
            <kbd className="px-1 py-0.5 bg-gray-800 rounded">+</kbd> Zoom in
          </div>
          <div>
            <kbd className="px-1 py-0.5 bg-gray-800 rounded">-</kbd> Zoom out
          </div>
        </div>
      </div>
    </div>
  )
}
