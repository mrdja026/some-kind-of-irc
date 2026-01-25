import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { Template } from '../types'
import {
  listTemplates,
  createTemplate,
  getTemplate,
  updateTemplate,
  deleteTemplate,
  applyTemplate,
  type CreateTemplateRequest,
  type UpdateTemplateRequest,
  type ApplyTemplateRequest,
  type ApplyTemplateResponse,
} from '../api/dataProcessor'

export interface UseTemplatesOptions {
  channelId?: number
  enabled?: boolean
}

/**
 * Hook for managing templates in a channel
 */
export function useTemplates({ channelId, enabled = true }: UseTemplatesOptions = {}) {
  const queryClient = useQueryClient()

  // Query for fetching templates
  const templatesQuery = useQuery({
    queryKey: ['templates', channelId],
    queryFn: () => listTemplates(channelId),
    enabled: enabled && !!channelId,
    staleTime: 60000, // 1 minute
  })

  // Create template mutation
  const createMutation = useMutation({
    mutationFn: (data: CreateTemplateRequest) => createTemplate(data),
    onSuccess: (newTemplate) => {
      // Add to cache
      queryClient.setQueryData(['templates', channelId], (oldData: Template[] | undefined) => {
        return oldData ? [...oldData, newTemplate] : [newTemplate]
      })
      // Prefetch the new template
      queryClient.setQueryData(['template', newTemplate.id], newTemplate)
    },
  })

  // Update template mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, ...updates }: { id: string } & UpdateTemplateRequest) =>
      updateTemplate(id, updates),
    onSuccess: (updatedTemplate) => {
      // Update in list cache
      queryClient.setQueryData(['templates', channelId], (oldData: Template[] | undefined) => {
        return oldData?.map((t) => (t.id === updatedTemplate.id ? updatedTemplate : t)) || []
      })
      // Update individual template cache
      queryClient.setQueryData(['template', updatedTemplate.id], updatedTemplate)
    },
  })

  // Delete template mutation
  const deleteMutation = useMutation({
    mutationFn: (templateId: string) => deleteTemplate(templateId),
    onSuccess: (_, templateId) => {
      // Remove from list cache
      queryClient.setQueryData(['templates', channelId], (oldData: Template[] | undefined) => {
        return oldData?.filter((t) => t.id !== templateId) || []
      })
      // Remove individual template cache
      queryClient.removeQueries({ queryKey: ['template', templateId] })
    },
  })

  // Computed values
  const templates = templatesQuery.data || []
  const activeTemplates = templates.filter((t) => t.is_active)
  const templatesById = templates.reduce((acc, template) => {
    acc[template.id] = template
    return acc
  }, {} as Record<string, Template>)

  return {
    // Data
    templates,
    activeTemplates,
    templatesById,
    isLoading: templatesQuery.isLoading,
    error: templatesQuery.error,

    // Queries
    templatesQuery,

    // Mutations
    createMutation,
    updateMutation,
    deleteMutation,

    // Actions
    refetch: templatesQuery.refetch,
    invalidate: () => queryClient.invalidateQueries({ queryKey: ['templates', channelId] }),

    // Computed
    hasTemplates: templates.length > 0,
    activeCount: activeTemplates.length,
  }
}

/**
 * Hook for managing a single template
 */
export function useTemplate(templateId: string, enabled = true) {
  const queryClient = useQueryClient()

  // Query for fetching single template
  const templateQuery = useQuery({
    queryKey: ['template', templateId],
    queryFn: () => getTemplate(templateId),
    enabled: enabled && !!templateId,
    staleTime: 60000,
  })

  // Update template mutation
  const updateMutation = useMutation({
    mutationFn: (updates: UpdateTemplateRequest) => updateTemplate(templateId, updates),
    onSuccess: (updatedTemplate) => {
      // Update cache
      queryClient.setQueryData(['template', templateId], updatedTemplate)
      // Also update in templates list if it exists
      queryClient.invalidateQueries({ queryKey: ['templates'], exact: false })
    },
  })

  // Delete template mutation
  const deleteMutation = useMutation({
    mutationFn: () => deleteTemplate(templateId),
    onSuccess: () => {
      // Remove from cache
      queryClient.removeQueries({ queryKey: ['template', templateId] })
      // Invalidate templates list
      queryClient.invalidateQueries({ queryKey: ['templates'], exact: false })
    },
  })

  return {
    // Data
    template: templateQuery.data,
    isLoading: templateQuery.isLoading,
    error: templateQuery.error,

    // Mutations
    updateMutation,
    deleteMutation,

    // Actions
    refetch: templateQuery.refetch,
    invalidate: () => queryClient.invalidateQueries({ queryKey: ['template', templateId] }),

    // Computed
    isActive: templateQuery.data?.is_active ?? false,
    hasLabels: (templateQuery.data?.labels?.length ?? 0) > 0,
    labelCount: templateQuery.data?.labels?.length ?? 0,
  }
}

/**
 * Hook for applying templates to documents
 */
export function useTemplateApplication(documentId: string) {
  const queryClient = useQueryClient()

  // Apply template mutation
  const applyMutation = useMutation({
    mutationFn: (request: ApplyTemplateRequest) => applyTemplate(documentId, request),
    onSuccess: (response) => {
      // Invalidate document to get updated annotations
      queryClient.invalidateQueries({ queryKey: ['document', documentId] })
    },
  })

  return {
    applyTemplate: applyMutation.mutate,
    isApplying: applyMutation.isPending,
    error: applyMutation.error,
    result: applyMutation.data,
  }
}

/**
 * Hook for template operations with optimistic updates
 */
export function useTemplateOperations(channelId?: number) {
  const queryClient = useQueryClient()

  const createTemplateOptimistic = useMutation({
    mutationFn: async (data: CreateTemplateRequest) => {
      // Optimistically add to cache
      const tempId = `temp-${Date.now()}`
      const optimisticTemplate: Template = {
        id: tempId,
        channel_id: data.channel_id.toString(),
        created_by: '', // Will be filled by server
        name: data.name,
        description: data.description || '',
        thumbnail_url: null,
        version: 1,
        is_active: true,
        labels: [],
        created_at: new Date().toISOString(),
      }

      // Add to templates list
      queryClient.setQueryData(['templates', channelId], (oldData: Template[] | undefined) => {
        return oldData ? [...oldData, optimisticTemplate] : [optimisticTemplate]
      })

      try {
        const result = await createTemplate(data)
        // Replace optimistic with real data
        queryClient.setQueryData(['templates', channelId], (oldData: Template[] | undefined) => {
          return oldData?.map((t) => (t.id === tempId ? result : t)) || [result]
        })
        return result
      } catch (error) {
        // Remove optimistic update on error
        queryClient.setQueryData(['templates', channelId], (oldData: Template[] | undefined) => {
          return oldData?.filter((t) => t.id !== tempId) || []
        })
        throw error
      }
    },
  })

  const toggleTemplateActive = useMutation({
    mutationFn: async (templateId: string) => {
      const template = queryClient.getQueryData(['template', templateId]) as Template
      const newActiveState = !template?.is_active
      return updateTemplate(templateId, { is_active: newActiveState })
    },
    onMutate: async (templateId) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['template', templateId] })
      await queryClient.cancelQueries({ queryKey: ['templates', channelId] })

      // Snapshot previous values
      const previousTemplate = queryClient.getQueryData(['template', templateId]) as Template
      const previousTemplates = queryClient.getQueryData(['templates', channelId]) as Template[]

      // Optimistically update
      const newTemplate = { ...previousTemplate, is_active: !previousTemplate.is_active }
      const newTemplates = previousTemplates?.map((t) =>
        t.id === templateId ? newTemplate : t,
      )

      queryClient.setQueryData(['template', templateId], newTemplate)
      queryClient.setQueryData(['templates', channelId], newTemplates)

      return { previousTemplate, previousTemplates }
    },
    onError: (_, templateId, context) => {
      // Revert on error
      if (context) {
        queryClient.setQueryData(['template', templateId], context.previousTemplate)
        queryClient.setQueryData(['templates', channelId], context.previousTemplates)
      }
    },
  })

  return {
    createTemplateOptimistic,
    toggleTemplateActive,
  }
}