'use client'
import { useState } from 'react'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import { BarChart3, TrendingUp, Users, CheckCircle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { RAGBadge } from '@/components/shared/RAGBadge'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorState } from '@/components/shared/ErrorState'
import { useGovernanceDashboard } from '@/hooks/useDashboard'
import { formatMAD, formatPercent } from '@/lib/utils'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend, Cell,
} from 'recharts'
import { RAG_COLORS } from '@/lib/constants'

export default function GouvernancePage() {
  const [segment, setSegment] = useState<string>('')

  const { data, isLoading, error, refetch } = useGovernanceDashboard({
    segment: segment || null,
  })

  const kpis = data?.kpis

  return (
    <ProtectedRoute requiredPage="finance">
      <PageWrapper>
        <div className="min-h-screen bg-[#0f172a]">
          <header className="bg-[#1e293b] border-b border-slate-700 px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-8 h-8 bg-indigo-500 rounded flex items-center justify-center">
                  <BarChart3 className="w-5 h-5 text-white" />
                </div>
                <h1 className="text-xl font-semibold text-slate-100">Gouvernance & Budget IT</h1>
                {data?.rag_status && <RAGBadge status={data.rag_status} />}
              </div>
              {data?.available_depts && (
                <Select value={segment} onValueChange={setSegment}>
                  <SelectTrigger className="w-52 bg-[#334155] border-slate-600 text-slate-100 text-sm">
                    <SelectValue placeholder="Toutes directions" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#1e293b] border-slate-700">
                    <SelectItem value="">Toutes directions</SelectItem>
                    {data.available_depts.map(d => (
                      <SelectItem key={d} value={d}>{d}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
          </header>

          <main className="p-6 space-y-6">
            {isLoading && <LoadingSpinner label="Chargement budget..." />}
            {error && <ErrorState message="Erreur chargement gouvernance" onRetry={() => refetch()} />}

            {data && (
              <>
                {/* KPIs */}
                <section>
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-1 h-5 bg-indigo-500 rounded" />
                    <h2 className="text-sm font-bold text-indigo-400 uppercase tracking-wider">Santé Budgétaire</h2>
                  </div>
                  <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
                    {[
                      { label: 'Budget Alloué', value: formatMAD(kpis?.budget_alloue_mad), sub: 'Toutes directions', color: 'text-sky-400' },
                      { label: 'Budget Consommé', value: formatMAD(kpis?.budget_consomme_mad), sub: 'Période courante', color: 'text-emerald-400' },
                      { label: 'Écart Budgétaire', value: formatPercent(kpis?.ecart_budget_pct, true), sub: 'Négatif = économies', color: (kpis?.ecart_budget_pct ?? 0) <= 0 ? 'text-emerald-400' : 'text-red-400', rag: kpis?.rag_ecart },
                      { label: 'ROI Moyen IT', value: formatPercent(kpis?.roi_moyen_pct), sub: '↑ vs trimestre préc.', color: 'text-orange-400', rag: kpis?.rag_roi },
                      { label: 'CSAT Utilisateurs', value: `${kpis?.csat_it_moyen?.toFixed(2) ?? '—'} / 5`, sub: 'Satisfaction IT', color: 'text-purple-400' },
                    ].map(card => (
                      <Card key={card.label} className="bg-[#1e293b] border-slate-700">
                        <CardContent className="p-4">
                          <p className={`text-2xl font-bold ${card.color}`}>{card.value}</p>
                          <p className="text-sm text-slate-200 mt-1">{card.label}</p>
                          <p className="text-xs text-slate-500 mt-1">{card.sub}</p>
                          {card.rag && <RAGBadge status={card.rag} size="sm" />}
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </section>

                {/* Charts */}
                <section className="grid grid-cols-1 lg:grid-cols-5 gap-6">
                  <div className="lg:col-span-3">
                    <Card className="bg-[#1e293b] border-slate-700">
                      <CardHeader>
                        <CardTitle className="text-sm text-indigo-400 uppercase tracking-wider flex items-center gap-2">
                          <TrendingUp className="w-4 h-4" />Évolution Budget vs Consommation — 12 mois
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="h-[280px]">
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={data.budget_trends_12m} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
                              <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                              <XAxis dataKey="date" tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} tickFormatter={v => v.slice(0, 7)} />
                              <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `${(v/1000).toFixed(0)}K`} />
                              <Tooltip
                                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px', fontSize: '12px' }}
                                formatter={(v) => [typeof v === 'number' ? formatMAD(v) : String(v)]}
                              />
                              <Legend wrapperStyle={{ fontSize: '12px', color: '#94a3b8' }} />
                              <Bar dataKey="alloue" name="Alloué" fill="#3b82f6" radius={[2,2,0,0]} />
                              <Bar dataKey="consomme" name="Consommé" fill="#8b5cf6" radius={[2,2,0,0]} />
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                  <div className="lg:col-span-2">
                    <Card className="bg-[#1e293b] border-slate-700 h-full">
                      <CardHeader>
                        <CardTitle className="text-sm text-indigo-400 uppercase tracking-wider flex items-center gap-2">
                          <Users className="w-4 h-4" />Par Direction
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-3">
                          {data.par_direction.slice(0, 6).map(d => (
                            <div key={d.departement} className="flex items-center justify-between gap-3">
                              <span className="text-xs text-slate-300 w-28 truncate">{d.departement}</span>
                              <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
                                <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(d.pct_consomme ?? 0, 100)}%`, backgroundColor: RAG_COLORS[d.rag]?.dot ?? '#22c55e' }} />
                              </div>
                              <span className="text-xs text-slate-400 w-12 text-right">{d.pct_consomme?.toFixed(0) ?? '—'}%</span>
                              <RAGBadge status={d.rag} size="sm" showLabel={false} />
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                </section>

                {/* Adoption */}
                <section>
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-1 h-5 bg-emerald-500 rounded" />
                    <h2 className="text-sm font-bold text-emerald-400 uppercase tracking-wider">Adoption Digitale & Efficience</h2>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    {[
                      { label: 'Adoption Digitale', value: formatPercent(data.adoption?.adoption_digital_pct), icon: <CheckCircle className="w-5 h-5 text-sky-400" /> },
                      { label: 'Projets à Temps', value: formatPercent(data.adoption?.projets_a_temps_pct), icon: <TrendingUp className="w-5 h-5 text-emerald-400" /> },
                      { label: 'Coût IT / Employé', value: formatMAD(data.adoption?.cout_it_par_employe_mad), icon: <BarChart3 className="w-5 h-5 text-purple-400" /> },
                    ].map(m => (
                      <Card key={m.label} className="bg-[#1e293b] border-slate-700">
                        <CardContent className="p-4 flex items-center gap-4">
                          {m.icon}
                          <div>
                            <p className="text-xl font-bold text-slate-100">{m.value}</p>
                            <p className="text-sm text-slate-400">{m.label}</p>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </section>
              </>
            )}
          </main>

          <footer className="px-6 py-3 border-t border-slate-700 text-xs text-slate-500 flex justify-between">
            <span>Dashboard 360° Novec — Gouvernance & Budget IT</span>
            <span>Màj : {data?.timestamp ? format(new Date(data.timestamp), 'dd/MM/yyyy HH:mm', { locale: fr }) : '—'}</span>
          </footer>
        </div>
      </PageWrapper>
    </ProtectedRoute>
  )
}