'use client'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'

export function ProtectedRoute({ children, requiredPage }: { children: React.ReactNode; requiredPage?: string }) {
  const { user, isLoading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!isLoading && !user) router.push('/login')
  }, [user, isLoading, router])

  if (isLoading) return <LoadingSpinner label="Authentification..." />
  if (!user) return null
  return <>{children}</>
}