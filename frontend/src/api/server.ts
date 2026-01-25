import { createServerFn } from '@tanstack/react-start'
import { getRequest } from '@tanstack/react-start/server'
import type { User, Channel, Message } from '../types'

// Use internal service address when running on the server inside Docker, and
// fallback to public URL when rendering on the client.
const API_BASE_URL =
  typeof window === 'undefined'
    ? import.meta.env.VITE_API_URL || 'http://backend:8002'
    : (() => {
        const origin = window.location.origin
        const explicit = import.meta.env.VITE_PUBLIC_API_URL?.trim()
        if (explicit) {
          if (explicit.includes('localhost') && window.location.hostname !== 'localhost') {
            return origin
          }
          return explicit
        }
        return origin
      })()

// Helper to make authenticated fetch calls from server
async function serverFetch(
  url: string,
  options: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(options.headers)
  
  // Get request context and forward cookies
  try {
    const request = getRequest()
    const cookieHeader = request.headers.get('cookie')
    if (cookieHeader) {
      headers.set('cookie', cookieHeader)
    }
  } catch (error) {
    // If getRequest() fails (e.g., called from client), that's okay
    // The fetch will still work but without cookies
  }

  return fetch(url, {
    ...options,
    headers,
    credentials: 'include',
  })
}

// Auth server functions
export const getCurrentUserServer = createServerFn({
  method: 'GET',
}).handler(async () => {
  const response = await serverFetch(`${API_BASE_URL}/auth/me`, {})
  if (!response.ok) {
    throw new Error('Failed to get current user')
  }
  return response.json() as Promise<User>
})

export const getUserByIdServer = createServerFn({
  method: 'GET',
}).handler(async ({ data }: { data: { userId: number } }) => {
  const response = await serverFetch(
    `${API_BASE_URL}/auth/users/${data.userId}`,
    {},
  )
  if (!response.ok) {
    throw new Error('Failed to get user')
  }
  return response.json() as Promise<User>
})

// Channel server functions
export const getChannelsServer = createServerFn({
  method: 'GET',
}).handler(async () => {
  const response = await serverFetch(`${API_BASE_URL}/channels`, {})
  if (!response.ok) {
    throw new Error('Failed to get channels')
  }
  return response.json() as Promise<Channel[]>
})

export const getDirectMessagesServer = createServerFn({
  method: 'GET',
}).handler(async () => {
  const response = await serverFetch(`${API_BASE_URL}/channels/dms`, {})
  if (!response.ok) {
    throw new Error('Failed to get direct messages')
  }
  return response.json() as Promise<Channel[]>
})

// Message server functions
export const getMessagesServer = createServerFn({
  method: 'GET',
}).handler(async ({ data }: { data: { channelId: number } }) => {
  const response = await serverFetch(
    `${API_BASE_URL}/channels/${data.channelId}/messages`,
    {},
  )
  if (!response.ok) {
    throw new Error('Failed to get messages')
  }
  return response.json() as Promise<Message[]>
})
