'use client'
import { useState } from 'react'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import { Shield, AlertTriangle, Lock, Eye, Target, Brain } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { RAGBadge } from '@/components/shared/RAGBadge'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorState } from '@/components/shared/ErrorState'
import { useCybersecDashboard } from '@/hooks/useDashboard'
import { DateRangePicker } from '@/components/infrastructure/date-range-picker'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend, ReferenceLine,
} from 'recharts'

function KPISecCard({ value, label, sub, color, rag }: { value: string; label: string; sub?: string; color: string; rag?: string }) {
  return (
    <Card className="bg-[#1e293b] border-slate-700">
      <CardContent className="p-4">
        <p className={`text-2xl font-bold ${color}`}>{value}</p>
        <p className="text-sm text-slate-200 mt-1">{label}</p>
        {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
        {rag && <div className="mt-2"><RAGBadge status={rag} size="sm" /></div>}
      </CardContent>
    </Card>
  )
}

export default function CybersecPage() {
  const [dateRange, setDateRange] = useState({ from: new Date('2025-01-01'), to: new Date() })

  const { data, isLoading, error, refetch } = useCybersecDashboard({
    date_from: format(dateRange.from, 'yyyy-MM-dd'),
    date_to: format(dateRange.to, 'yyyy-MM-dd'),
  })

  const kpis = data?.kpis

  return (
    <ProtectedRoute requiredPage="cyber">
      <PageWrapper>
        <div className="min-h-screen bg-[#0f172a]">
          <header className="bg-[#1e293b] border-b border-slate-700 px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-8 h-8 bg-red-600 rounded flex items-center justify-center">
                  <Shield className="w-5 h-5 text-white" />
                </div>
                <h1 className="text-xl font-semibold text-slate-100">Cybersécurité & Conformité</h1>
                {data?.rag_status && <RAGBadge status={data.rag_status} />}
              </div>
              <DateRangePicker dateRange={dateRange} onDateRangeChange={setDateRange} />
            </div>
          </header>

          <main className="p-6 space-y-6">
            {isLoading && <LoadingSpinner label="Chargement cybersécurité..." />}
            {error && <ErrorState message="Erreur chargement cybersécurité" onRetry={() => refetch()} />}

            {data && (
              <>
                {/* KPIs */}
                <section>
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-1 h-5 bg-red-500 rounded" />
                    <h2 className="text-sm font-bold text-red-400 uppercase tracking-wider">Indicateurs de Sécurité</h2>
                  </div>
                  <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
                    <KPISecCard value={String(kpis?.incidents_critiques ?? '—')} label="Incidents Critiques" sub="Période courante" color="text-red-400" rag={kpis?.rag_incidents} />
                    <KPISecCard value={`${kpis?.mttd_moyen_hours?.toFixed(1) ?? '—'}h`} label="MTTD Moyen" sub="Délai détection" color="text-orange-400" rag={kpis?.rag_mttd} />
                    <KPISecCard value={String(kpis?.vuln_non_patchees ?? '—')} label="Vulnérabilités" sub="Non corrigées" color="text-yellow-400" rag={kpis?.rag_vuln} />
                    <KPISecCard value={`${kpis?.systemes_patches_pct?.toFixed(1) ?? '—'}%`} label="Systèmes Patchés" sub="Cible : 100%" color="text-emerald-400" rag={kpis?.rag_patch} />
                    <KPISecCard value={`${kpis?.mfa_adoption_pct?.toFixed(1) ?? '—'}%`} label="MFA Adoption" sub={kpis?.mfa_delta_vs_an_precedent != null ? `${kpis.mfa_delta_vs_an_precedent > 0 ? '+' : ''}${kpis.mfa_delta_vs_an_precedent.toFixed(1)}% vs N-1` : undefined} color="text-sky-400" rag={kpis?.rag_mfa} />
                    <KPISecCard value={`${kpis?.rgpd_conformite_pct?.toFixed(1) ?? '—'}%`} label="Conformité RGPD" sub={`Cible : ${kpis?.rgpd_cible ?? 95}%`} color="text-purple-400" rag={kpis?.rag_rgpd} />
                  </div>
                </section>

                {/* Tendances 13 mois */}
                <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <Card className="bg-[#1e293b] border-slate-700">
                    <CardHeader>
                      <CardTitle className="text-sm text-red-400 uppercase tracking-wider flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4" />Incidents & Vulnérabilités — 13 mois
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="h-[250px]">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={data.trends_13m} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                            <XAxis dataKey="date" tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} tickFormatter={v => v.slice(0, 7)} />
                            <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false} />
                            <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px', fontSize: '12px' }} />
                            <Legend wrapperStyle={{ fontSize: '11px', color: '#94a3b8' }} />
                            <Line type="monotone" dataKey="incidents" name="Incidents" stroke="#ef4444" strokeWidth={2} dot={false} />
                            <Line type="monotone" dataKey="vuln" name="Vulnérabilités" stroke="#f59e0b" strokeWidth={2} dot={false} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    </CardContent>
                  </Card>

                  <Card className="bg-[#1e293b] border-slate-700">
                    <CardHeader>
                      <CardTitle className="text-sm text-sky-400 uppercase tracking-wider flex items-center gap-2">
                        <Lock className="w-4 h-4" />MFA & Conformité RGPD — 13 mois
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="h-[250px]">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={data.trends_13m} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                            <XAxis dataKey="date" tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} tickFormatter={v => v.slice(0, 7)} />
                            <YAxis domain={[0, 100]} tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} />
                            <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px', fontSize: '12px' }} formatter={(v) => [typeof v === 'number' ? `${v.toFixed(1)}%` : v]} />
                            <Legend wrapperStyle={{ fontSize: '11px', color: '#94a3b8' }} />
                            <ReferenceLine y={95} stroke="#22c55e" strokeDasharray="4 4" label={{ value: 'Cible RGPD', fill: '#22c55e', fontSize: 10 }} />
                            <Line type="monotone" dataKey="mfa_pct" name="MFA %" stroke="#38bdf8" strokeWidth={2} dot={false} />
                            <Line type="monotone" dataKey="rgpd_pct" name="RGPD %" stroke="#a78bfa" strokeWidth={2} dot={false} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    </CardContent>
                  </Card>
                </section>

                {/* Prédictions M+3 */}
                {data.predictions_m3 && (
                  <section>
                    <div className="flex items-center gap-2 mb-4">
                      <div className="w-1 h-5 bg-purple-500 rounded" />
                      <h2 className="text-sm font-bold text-purple-400 uppercase tracking-wider">Prédictions IA — M+3</h2>
                    </div>
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                      {[
                        { key: 'mfa_m3', label: 'MFA M+3', icon: <Lock className="w-4 h-4" />, pred: data.predictions_m3.mfa_m3 },
                        { key: 'rgpd_m3', label: 'RGPD M+3', icon: <Target className="w-4 h-4" />, pred: data.predictions_m3.rgpd_m3 },
                        { key: 'incidents_m3', label: 'Incidents M+3', icon: <AlertTriangle className="w-4 h-4" />, pred: data.predictions_m3.incidents_m3 },
                        { key: 'vuln_m3', label: 'Vulns M+3', icon: <Eye className="w-4 h-4" />, pred: data.predictions_m3.vuln_m3 },
                      ].map(p => (
                        <Card key={p.key} className="bg-[#1e293b] border-slate-700">
                          <CardContent className="p-4">
                            <div className="flex items-center gap-2 mb-2 text-purple-400">
                              <Brain className="w-4 h-4" />{p.icon}
                              <span className="text-xs font-medium">{p.label}</span>
                            </div>
                            {p.pred ? (
                              <>
                                <p className="text-xl font-bold text-slate-100">{p.pred.yhat_m3?.toFixed(1) ?? '—'}</p>
                                <p className="text-xs text-slate-400 mt-1">{p.pred.date_m3}</p>
                                <RAGBadge status={p.pred.rag} size="sm" />
                              </>
                            ) : (
                              <p className="text-sm text-slate-500">Données insuffisantes</p>
                            )}
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </section>
                )}
              </>
            )}
          </main>

          <footer className="px-6 py-3 border-t border-slate-700 text-xs text-slate-500 flex justify-between">
            <span>Dashboard 360° Novec — Cybersécurité & Conformité</span>
            <span>Màj : {data?.timestamp ? format(new Date(data.timestamp), 'dd/MM/yyyy HH:mm', { locale: fr }) : '—'}</span>
          </footer>
        </div>
      </PageWrapper>
    </ProtectedRoute>
  )
}