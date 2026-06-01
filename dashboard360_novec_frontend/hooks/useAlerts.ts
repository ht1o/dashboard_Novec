import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/api'

export function useActiveAlerts() {
  return useQuery({
    queryKey: ['alerts', 'active'],
    queryFn: async () => {
      const { data } = await apiClient.get('/api/alerts/active')
      return data
    },
    staleTime: 2 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  })
}

export function useRecommendations(role?: string, status?: string) {
  return useQuery({
    queryKey: ['recommendations', role, status],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (role) params.append('role', role)
      if (status) params.append('status', status)
      const { data } = await apiClient.get(`/api/recommendations?${params}`)
      return data
    },
    staleTime: 5 * 60 * 1000,
  })
}

export function useAcknowledgeRecommendation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, newStatus }: { id: number; newStatus: string }) => {
      const { data } = await apiClient.patch(`/api/recommendations/${id}?new_status=${newStatus}`)
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recommendations'] })
      qc.invalidateQueries({ queryKey: ['dashboard', 'alerts'] })
    },
  })
}

export function useAnomalies(domain?: string, date?: string, ragStatus?: string) {
  return useQuery({
    queryKey: ['anomalies', domain, date, ragStatus],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (domain) params.append('domain', domain)
      if (date) params.append('date', date)
      if (ragStatus) params.append('rag_status', ragStatus)
      const { data } = await apiClient.get(`/api/anomalies?${params}`)
      return data
    },
    staleTime: 5 * 60 * 1000,
  })
}