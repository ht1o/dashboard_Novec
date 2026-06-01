'use client'
import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import apiClient from '@/lib/api'
import type { TokenResponse, MeResponse } from '@/types/api'

interface AuthUser {
  username: string
  role: string
}

export function useAuth() {
  const router = useRouter()
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const stored = localStorage.getItem('user')
    if (stored) {
      try { setUser(JSON.parse(stored)) } catch { /* ignore */ }
    }
    setIsLoading(false)
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const { data } = await apiClient.post<TokenResponse>('/api/auth/login', { username, password })
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    const authUser = { username: data.username, role: data.role }
    localStorage.setItem('user', JSON.stringify(authUser))
    setUser(authUser)
    return data
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
    setUser(null)
    router.push('/login')
  }, [router])

  const getMe = useCallback(async (): Promise<MeResponse> => {
    const { data } = await apiClient.get<MeResponse>('/api/auth/me')
    return data
  }, [])

  return { user, isLoading, login, logout, getMe }
}