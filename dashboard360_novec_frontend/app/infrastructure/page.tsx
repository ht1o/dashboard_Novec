'use client'
import { useState } from 'react'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import { AlertTriangle, Activity, HardDrive, Cpu, MemoryStick, Gauge, TrendingUp, Brain, Server } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { KPICard } from '@/components/infrastructure/kpi-card'
import { UptimeChart } from '@/components/infrastructure/uptime-chart'
import { ResourceBars } from '@/components/infrastructure/resource-bars'
import { AnomaliesChart } from '@/components/infrastructure/anomalies-chart'
import { CloudMetricCard } from '@/components/infrastructure/cloud-metric-card'
import { DateRangePicker } from '@/components/infrastructure/date-range-picker'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { RAGBadge } from '@/components/shared/RAGBadge'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorState } from '@/components/shared/ErrorState'
import { useInfraDashboard } from '@/hooks/useDashboard'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'

export default function InfraDashboard() {
  const [server, setServer] = useState<string>('')
  const [dateRange, setDateRange] = useState({ from: new Date('2025-01-01'), to: new Date() })

  const { data, isLoading, error, refetch } = useInfraDashboard({
    server: server || null,
    date_from: format(dateRange.from, 'yyyy-MM-dd'),
    date_to: format(dateRange.to, 'yyyy-MM-dd'),
  })

  // Prépare les données pour les graphiques
  const dailyUptime = (data?.trends_30j ?? []).map(d => ({
    date: d.date ? d.date.slice(5) : '',
    fullDate: d.date ?? '',
    uptime: d.uptime ?? 0,
  }))

  const weeklyAnomalies = (data?.anomalies_weekly ?? []).map(d => ({
    week: `S${d.semaine}`,
    count: d.nb_anomalies,
  }))

  const kpis = data?.kpis

  return (
    <ProtectedRoute requiredPage="infrastructure">
      <PageWrapper>
        <div className="min-h-screen bg-[#0f172a]">
          {/* Header */}
          <header className="bg-[#1e293b] border-b border-slate-700 px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 bg-sky-500 rounded flex items-center justify-center">
                    <Server className="w-5 h-5 text-white" />
                  </div>
                  <h1 className="text-xl font-semibold text-slate-100">Infrastructure IT</h1>
                </div>
                {data?.rag_status && <RAGBadge status={data.rag_status} />}
              </div>
              <div className="flex items-center gap-3">
                {data?.available_servers && (
                  <Select value={server} onValueChange={setServer}>
                    <SelectTrigger className="w-44 bg-[#334155] border-slate-600 text-slate-100 text-sm">
                      <SelectValue placeholder="Tous les serveurs" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#1e293b] border-slate-700">
                      <SelectItem value="">Tous les serveurs</SelectItem>
                      {data.available_servers.map(s => (
                        <SelectItem key={s} value={s}>{s}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
                <DateRangePicker dateRange={dateRange} onDateRangeChange={setDateRange} />
              </div>
            </div>
          </header>

          <main className="p-6 space-y-6">
            {isLoading && <LoadingSpinner label="Chargement des données infrastructure..." />}
            {error && <ErrorState message="Erreur de chargement des données" onRetry={() => refetch()} />}

            {data && (
              <>
                {/* KPIs Vue d'ensemble */}
                <section>
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-1 h-5 bg-sky-500 rounded" />
                    <h2 className="text-sm font-bold text-sky-400 uppercase tracking-wider">Vue d'ensemble — Infrastructure</h2>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
                    <KPICard title="Uptime Moyen" value={kpis?.uptime_moyen_pct ?? 0} format="percent" icon={Activity} subtitle={`${kpis?.nb_serveurs ?? 0} serveurs`} accentColor="text-sky-400" bgGradient="from-sky-500/10 to-sky-500/5" />
                    <KPICard title="CPU Moyen" value={kpis?.cpu_moyen_pct ?? 0} format="percent" icon={Cpu} subtitle="Seuil critique : 90%" accentColor="text-orange-400" bgGradient="from-orange-500/10 to-orange-500/5" warning={(kpis?.cpu_moyen_pct ?? 0) > 70} />
                    <KPICard title="RAM Utilisée" value={kpis?.ram_moyen_pct ?? 0} format="percent" icon={MemoryStick} subtitle="Seuil critique : 90%" accentColor="text-purple-400" bgGradient="from-purple-500/10 to-purple-500/5" />
                    <KPICard title="Stockage Disque" value={kpis?.disk_moyen_pct ?? 0} format="percent" icon={HardDrive} subtitle={`MTBF : ${kpis?.mtbf_moyen_hours?.toFixed(0) ?? '—'}h`} accentColor="text-emerald-400" bgGradient="from-emerald-500/10 to-emerald-500/5" />
                    <Card className="bg-red-950/50 border-red-900 shadow-lg">
                      <CardContent className="p-4 flex flex-col items-center justify-center h-full">
                        <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center mb-2">
                          <AlertTriangle className="w-5 h-5 text-red-400" />
                        </div>
                        <span className="text-3xl font-bold text-red-400">{kpis?.total_anomalies ?? 0}</span>
                        <span className="text-sm text-red-300">Anomalies</span>
                        <span className="text-xs text-red-500 mt-1">{kpis?.alertes_rouge ?? 0} alertes rouges</span>
                      </CardContent>
                    </Card>
                  </div>
                </section>

                {/* Performance */}
                <section>
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-1 h-5 bg-emerald-500 rounded" />
                    <h2 className="text-sm font-bold text-emerald-400 uppercase tracking-wider">Performance Temps Réel</h2>
                  </div>
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    <Card className="bg-[#1e293b] border-slate-700">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-slate-400 flex items-center gap-2">
                          <TrendingUp className="w-4 h-4" />Uptime Serveurs — 30 jours (%)
                        </CardTitle>
                      </CardHeader>
                      <CardContent><UptimeChart data={dailyUptime} /></CardContent>
                    </Card>
                    <Card className="bg-[#1e293b] border-slate-700">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-slate-400 flex items-center gap-2">
                          <Gauge className="w-4 h-4" />Utilisation Ressources — Moyennes
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <ResourceBars
                          cpu={data.resources_avg?.cpu ?? kpis?.cpu_moyen_pct ?? 0}
                          ram={data.resources_avg?.ram ?? kpis?.ram_moyen_pct ?? 0}
                          disk={data.resources_avg?.disk ?? kpis?.disk_moyen_pct ?? 0}
                        />
                      </CardContent>
                    </Card>
                    <Card className="bg-[#1e293b] border-slate-700">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-slate-400 flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4" />Anomalies IT détectées
                        </CardTitle>
                      </CardHeader>
                      <CardContent><AnomaliesChart data={weeklyAnomalies} /></CardContent>
                    </Card>
                  </div>
                </section>

                {/* Cloud & Prédiction */}
                <section>
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-1 h-5 bg-violet-500 rounded" />
                    <h2 className="text-sm font-bold text-violet-400 uppercase tracking-wider">Cloud & Prédiction IA</h2>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
                    <CloudMetricCard value={data.cloud?.instances_actives ?? 0} label="Instances actives" color="bg-sky-700" />
                    <CloudMetricCard value={data.cloud?.backup_coverage_pct ?? 0} label="Backup Coverage" format="percent" color="bg-emerald-700" showProgress />
                    <CloudMetricCard value={data.cloud?.latence_avg_ms ?? 0} label="Latence avg" format="ms" color="bg-violet-700" />
                    <CloudMetricCard value={data.cloud?.disponibilite_pct ?? 0} label="Disponibilité" format="percent" color="bg-teal-700" showProgress />
                    {data.prediction_ia ? (
                      <Card className="bg-[#12239e]/80 border-blue-700 shadow-lg overflow-hidden">
                        <CardContent className="p-4">
                          <div className="flex items-center gap-1.5 mb-2">
                            <Brain className="w-3.5 h-3.5 text-blue-300" />
                            <span className="text-xs text-blue-300 font-medium">Prédiction IA</span>
                          </div>
                          <p className="text-sm font-semibold text-white leading-tight">
                            {data.prediction_ia.kpi?.replace(/_/g, ' ')}
                          </p>
                          <p className="text-xs text-blue-300 mt-1">
                            {data.prediction_ia.date_alerte ? `~${format(new Date(data.prediction_ia.date_alerte), 'dd MMM', { locale: fr })}` : '—'}
                          </p>
                          <RAGBadge status={data.prediction_ia.rag} size="sm" />
                        </CardContent>
                      </Card>
                    ) : (
                      <Card className="bg-[#1e293b] border-slate-700">
                        <CardContent className="p-4 flex items-center justify-center h-full">
                          <p className="text-xs text-slate-500">Aucune alerte prévue</p>
                        </CardContent>
                      </Card>
                    )}
                  </div>
                </section>
              </>
            )}
          </main>

          <footer className="px-6 py-3 border-t border-slate-700 text-xs text-slate-500 flex items-center justify-between">
            <span>Dashboard 360° Novec — Infrastructure IT</span>
            <span>Màj : {data?.timestamp ? format(new Date(data.timestamp), 'dd/MM/yyyy HH:mm', { locale: fr }) : '—'}</span>
          </footer>
        </div>
      </PageWrapper>
    </ProtectedRoute>
  )
}