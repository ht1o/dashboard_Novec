"use client"

import { useState, useMemo } from "react"
import { format } from "date-fns"
import { fr } from "date-fns/locale"
import { ArrowRight, AlertTriangle, CheckCircle, BarChart2 } from "lucide-react"
import { AppKPICard } from "@/components/applications-bi/app-kpi-card"
import { DispoByAppTable } from "@/components/applications-bi/dispo-by-app-table"
import { TrendsChart } from "@/components/applications-bi/trends-chart"
import { AppPredictionCard } from "@/components/applications-bi/prediction-card"
import { PageWrapper } from "@/components/layout/PageWrapper"
import { ProtectedRoute } from "@/components/layout/ProtectedRoute"
import { LoadingSpinner } from "@/components/shared/LoadingSpinner"
import { ErrorState } from "@/components/shared/ErrorState"
import { useAppsDashboard } from "@/hooks/useDashboard"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"

export default function ApplicationsBIPage() {
  const [selectedApp, setSelectedApp] = useState<string>("")

  const { data, isLoading, error, refetch } = useAppsDashboard({
    app:       selectedApp || null,
    date_from: "2025-04-01",
    date_to:   "2026-04-30",
  })

  const kpis = data?.kpis

  /* ── Séries tendances — agrégation par mois si plusieurs apps ── */
  const trendsData = useMemo(() => {
    const raw = data?.trends_13m ?? []
    // Grouper par date, moyenner dispo/qualite, sommer bugs
    const byDate = new Map<string, { dispo: number[]; qualite: number[]; bugs: number }>()
    raw.forEach(d => {
      const key = d.date.slice(0, 7)
      if (!byDate.has(key)) byDate.set(key, { dispo: [], qualite: [], bugs: 0 })
      const entry = byDate.get(key)!
      if (d.dispo    != null) entry.dispo.push(d.dispo)
      if (d.qualite  != null) entry.qualite.push(d.qualite)
      entry.bugs += d.bugs ?? 0
    })
    return Array.from(byDate.entries()).map(([month, v]) => ({
      month,
      dispo:   v.dispo.length   ? +(v.dispo.reduce((a, b)   => a + b, 0) / v.dispo.length).toFixed(2)   : null,
      qualite: v.qualite.length ? +(v.qualite.reduce((a, b) => a + b, 0) / v.qualite.length).toFixed(2) : null,
      bugs:    v.bugs,
    }))
  }, [data])

  /* ── KPI couleur helpers ── */
  const dispoColor   = (kpis?.disponibilite_moy_pct  ?? 100) >= 99   ? "#107c10" : (kpis?.disponibilite_moy_pct  ?? 100) >= 95 ? "#e66c37" : "#d13438"
  const trColor      = (kpis?.temps_reponse_moy_ms   ?? 0)   <= 500  ? "#107c10" : (kpis?.temps_reponse_moy_ms   ?? 0)   <= 1000 ? "#e66c37" : "#d13438"
  const bugsColor    = (kpis?.bugs_critiques          ?? 0)   === 0   ? "#107c10" : (kpis?.bugs_critiques          ?? 0)   <= 3    ? "#e66c37" : "#d13438"
  const qualiteColor = (kpis?.qualite_donnees_pct     ?? 100) >= 95   ? "#107c10" : "#e66c37"
  const biColor      = (kpis?.adoption_powerbi_pct    ?? 0)   >= 70   ? "#107c10" : "#e66c37"

  const dispoBorder   = dispoColor   === "#107c10" ? "border-l-[#107c10]" : dispoColor   === "#e66c37" ? "border-l-[#e66c37]" : "border-l-[#d13438]"
  const trBorder      = trColor      === "#107c10" ? "border-l-[#107c10]" : trColor      === "#e66c37" ? "border-l-[#e66c37]" : "border-l-[#d13438]"
  const bugsBorder    = bugsColor    === "#107c10" ? "border-l-[#107c10]" : bugsColor    === "#e66c37" ? "border-l-[#e66c37]" : "border-l-[#d13438]"
  const qualiteBorder = qualiteColor === "#107c10" ? "border-l-[#107c10]" : "border-l-[#e66c37]"
  const biBorder      = biColor      === "#107c10" ? "border-l-[#107c10]" : "border-l-[#e66c37]"

  return (
    <ProtectedRoute requiredPage="apps">
      <PageWrapper>
        <div className="min-h-screen bg-[#f0f0f0]">

          {/* ── Header ── */}
          <header className="bg-[#1b2a4a] text-white px-6 py-3">
            <div className="max-w-[1600px] mx-auto flex items-center justify-between">
              <div className="flex items-center gap-8">
                <div className="flex items-center gap-2">
                  <span className="text-[#ffb900] text-xl font-bold">DSI</span>
                  <span className="text-[#a19f9d]">·</span>
                  <span className="text-[#a19f9d] text-sm">Power BI</span>
                </div>
                <h1 className="text-lg font-semibold">Page 6 — Applications &amp; BI</h1>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 text-sm text-[#a19f9d]">
                  <span className="text-white font-medium">Avr 2025</span>
                  <ArrowRight className="h-4 w-4" />
                  <span className="text-white font-medium">Avr 2026</span>
                </div>
                {/* Filtre application */}
                <Select value={selectedApp} onValueChange={setSelectedApp}>
                  <SelectTrigger className="w-44 bg-[#118dff] hover:bg-[#0078d4] border-0 text-white text-sm font-medium">
                    <SelectValue placeholder="Toutes les apps" />
                  </SelectTrigger>
                  <SelectContent className="bg-white border-[#e1dfdd]">
                    <SelectItem value="">Toutes les apps</SelectItem>
                    {(data?.available_apps ?? []).map(a => (
                      <SelectItem key={a} value={a}>{a}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </header>

          <main className="max-w-[1600px] mx-auto p-6 space-y-6">
            {isLoading && <LoadingSpinner label="Chargement Applications & BI..." />}
            {error     && <ErrorState message="Erreur chargement applications" onRetry={() => refetch()} />}

            {data && (
              <>
                {/* ── Section 1 : KPIs ── */}
                <section>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-1 h-4 bg-[#118dff]" />
                    <h2 className="text-xs font-bold text-[#12239e] uppercase tracking-widest">
                      KPIs Applications — Situation Actuelle
                    </h2>
                  </div>

                  {isLoading ? (
                    <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
                      {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-sm" />)}
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
                      <AppKPICard
                        value={kpis?.disponibilite_moy_pct != null ? `${kpis.disponibilite_moy_pct.toFixed(1)}%` : "—"}
                        label="Disponibilité Moyenne"
                        sublabel={`Cible : ≥ ${kpis?.disponibilite_cible ?? 99}% · ${kpis?.nb_applications ?? 0} apps`}
                        accentColor={dispoColor}
                        borderColor={dispoBorder}
                        badge={
                          (kpis?.disponibilite_moy_pct ?? 100) >= 99
                            ? <CheckCircle  className="h-4 w-4 text-[#107c10]" />
                            : <AlertTriangle className="h-4 w-4 text-[#e66c37]" />
                        }
                      />
                      <AppKPICard
                        value={kpis?.temps_reponse_moy_ms != null ? `${kpis.temps_reponse_moy_ms.toFixed(0)} ms` : "—"}
                        label="Temps de Réponse Moyen"
                        sublabel={kpis?.temps_reponse_max_ms != null ? `Max : ${kpis.temps_reponse_max_ms.toFixed(0)} ms` : ""}
                        note="Seuil alerte : > 1 000 ms"
                        accentColor={trColor}
                        borderColor={trBorder}
                      />
                      <AppKPICard
                        value={String(kpis?.bugs_critiques ?? 0)}
                        label="Bugs Critiques"
                        sublabel={kpis?.alertes_rouge ? `${kpis.alertes_rouge} alertes rouge actives` : "Aucune alerte active"}
                        accentColor={bugsColor}
                        borderColor={bugsBorder}
                        badge={
                          (kpis?.bugs_critiques ?? 0) === 0
                            ? <CheckCircle  className="h-4 w-4 text-[#107c10]" />
                            : <AlertTriangle className="h-4 w-4 text-[#d13438]" />
                        }
                      />
                      <AppKPICard
                        value={kpis?.qualite_donnees_pct != null ? `${kpis.qualite_donnees_pct.toFixed(1)}%` : "—"}
                        label="Qualité des Données"
                        sublabel="Cible : ≥ 95%"
                        note="Taux de complétude et cohérence des données métier"
                        accentColor={qualiteColor}
                        borderColor={qualiteBorder}
                      />
                      <AppKPICard
                        value={kpis?.adoption_powerbi_pct != null ? `${kpis.adoption_powerbi_pct.toFixed(1)}%` : "—"}
                        label="Adoption Power BI"
                        sublabel="Cible : ≥ 70%"
                        note="% utilisateurs actifs sur les rapports BI déployés"
                        accentColor={biColor}
                        borderColor={biBorder}
                      />
                    </div>
                  )}
                </section>

                {/* ── Section 2 : Tableau dispo + Tendances ── */}
                <section>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-1 h-4 bg-[#118dff]" />
                    <h2 className="text-xs font-bold text-[#12239e] uppercase tracking-widest">
                      Performance par Application &amp; Tendances
                    </h2>
                  </div>
                  <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
                    <div className="lg:col-span-2">
                      <DispoByAppTable rows={data.dispo_by_app} />
                    </div>
                    <div className="lg:col-span-3">
                      <TrendsChart data={trendsData} selectedApp={selectedApp} />
                    </div>
                  </div>
                </section>

                {/* ── Section 3 : Prédiction IA ── */}
                <section>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-1 h-4 bg-[#6b52ae]" />
                    <h2 className="text-xs font-bold text-[#6b52ae] uppercase tracking-widest">
                      Prédiction IA — Alertes Applicatives J+7
                    </h2>
                  </div>
                  <AppPredictionCard prediction={data.prediction_ia} />
                </section>

                {/* ── Bandeau récap ── */}
                <div className="bg-[#e8f4fd] border border-[#0078d4]/30 rounded-sm px-4 py-3 flex items-start gap-2">
                  <BarChart2 className="h-4 w-4 text-[#0078d4] shrink-0 mt-0.5" />
                  <p className="text-xs text-[#605e5c] leading-relaxed">
                    <span className="font-semibold text-[#252423]">DONNÉES POWER BI :</span>
                    {" "}Le taux d'adoption Power BI mesure l'utilisation active des rapports déployés par la DSI.
                    Un score &lt; 70% indique un besoin de formation ou de simplification des tableaux de bord.
                    La qualité des données alimentant ces rapports est tracée séparément.
                  </p>
                </div>
              </>
            )}
          </main>

          {/* ── Footer ── */}
          <footer className="border-t border-[#e1dfdd] bg-white py-3 px-6 mt-4">
            <div className="max-w-[1600px] mx-auto flex items-center justify-between text-xs text-[#605e5c]">
              <div className="flex items-center gap-2">
                <span>PFE 2025 — Dashboard DSI</span>
                <span>|</span>
                <span>Page 6 sur 9</span>
                <span>|</span>
                <span>Applications &amp; BI</span>
              </div>
              <span>Màj : {data?.timestamp ? format(new Date(data.timestamp), "MMM yyyy", { locale: fr }) : "—"}</span>
            </div>
          </footer>
        </div>
      </PageWrapper>
    </ProtectedRoute>
  )
}