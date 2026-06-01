import { useQuery } from '@tanstack/react-query'
import apiClient from '@/lib/api'
import type {
  ExecutiveResponse, InfraResponse, FinanceResponse, CybersecResponse,
  ITSMResponse, AppsResponse, ITAMResponse, ParcAutoResponse,
  MaintenanceResponse, AlertsDashboardResponse,
} from '@/types/api'

type DashboardParams = Record<string, string | null | undefined>

function buildParams(params?: DashboardParams) {
  const p = new URLSearchParams()
  if (!params) return ''
  Object.entries(params).forEach(([k, v]) => { if (v) p.append(k, v) })
  const s = p.toString()
  return s ? `?${s}` : ''
}

// Generic hook — utilisé par les hooks spécialisés ci-dessous
export function useDashboard<T>(domain: string, params?: DashboardParams) {
  return useQuery<T>({
    queryKey: ['dashboard', domain, params],
    queryFn: async () => {
      const { data } = await apiClient.get<T>(`/api/dashboard/${domain}${buildParams(params)}`)
      return data
    },
    staleTime: 5 * 60 * 1000,
    retry: 2,
    refetchOnWindowFocus: false,
  })
}

// Hooks spécialisés par page
export const useExecutiveDashboard = (params?: DashboardParams) =>
  useDashboard<ExecutiveResponse>('executive', params)

export const useInfraDashboard = (params?: DashboardParams) =>
  useDashboard<InfraResponse>('infrastructure', params)

export const useGovernanceDashboard = (params?: DashboardParams) =>
  useDashboard<FinanceResponse>('finance', params)

export const useCybersecDashboard = (params?: DashboardParams) =>
  useDashboard<CybersecResponse>('cybersecurity', params)

export const useITSMDashboard = (params?: DashboardParams) =>
  useDashboard<ITSMResponse>('itsm', params)

export const useAppsDashboard = (params?: DashboardParams) =>
  useDashboard<AppsResponse>('applications', params)

export const useITAMDashboard = (params?: DashboardParams) =>
  useDashboard<ITAMResponse>('itam', params)

export const useParcAutoDashboard = (params?: DashboardParams) =>
  useDashboard<ParcAutoResponse>('parc-auto', params)

export const useMaintenanceDashboard = (params?: DashboardParams) =>
  useDashboard<MaintenanceResponse>('maintenance', params)

export const useAlertsDashboard = (params?: DashboardParams) =>
  useDashboard<AlertsDashboardResponse>('alerts', params)