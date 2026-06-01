import { useQuery } from '@tanstack/react-query'
import apiClient from '@/lib/api'

export function useForecastDomains() {
  return useQuery({
    queryKey: ['forecasts', 'domaines'],
    queryFn: async () => {
      const { data } = await apiClient.get('/api/forecasts/domaines')
      return data
    },
    staleTime: 30 * 60 * 1000,
  })
}

export function useForecastSegments(domain: string) {
  return useQuery({
    queryKey: ['forecasts', 'segments', domain],
    queryFn: async () => {
      const { data } = await apiClient.get(`/api/forecasts/segments?domaine=${domain}`)
      return data
    },
    enabled: !!domain,
    staleTime: 30 * 60 * 1000,
  })
}

export function useForecastKpis(domain: string) {
  return useQuery({
    queryKey: ['forecasts', 'kpis', domain],
    queryFn: async () => {
      const { data } = await apiClient.get(`/api/forecasts/kpis?domaine=${domain}`)
      return data
    },
    enabled: !!domain,
    staleTime: 30 * 60 * 1000,
  })
}

export function useForecastDetail(domain: string, kpi?: string, entity?: string, horizon = 30) {
  return useQuery({
    queryKey: ['forecast', domain, kpi, entity, horizon],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (kpi) params.append('kpi', kpi)
      if (entity) params.append('entity', entity)
      params.append('horizon', String(horizon))
      const { data } = await apiClient.get(`/api/forecast/${domain}?${params}`)
      return data
    },
    enabled: !!domain,
    staleTime: 10 * 60 * 1000,
  })
}

export function useRiskScore() {
  return useQuery({
    queryKey: ['risk-score', 'latest'],
    queryFn: async () => {
      const { data } = await apiClient.get('/api/risk-score/latest')
      return data
    },
    staleTime: 5 * 60 * 1000,
    refetchInterval: 10 * 60 * 1000,
  })
}

export function useRiskScoreHistory(days = 30) {
  return useQuery({
    queryKey: ['risk-score', 'history', days],
    queryFn: async () => {
      const { data } = await apiClient.get(`/api/risk-score/history?days=${days}`)
      return data
    },
    staleTime: 10 * 60 * 1000,
  })
}