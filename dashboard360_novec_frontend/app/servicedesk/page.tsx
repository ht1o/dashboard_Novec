"use client"

import { useState, useMemo } from "react"
import { format } from "date-fns"
import { fr } from "date-fns/locale"
import { Calendar, ArrowRight } from "lucide-react"
import { ServiceKPICard } from "@/components/servicedesk/service-kpi-card"
import { BacklogCard } from "@/components/servicedesk/backlog-card"
import { VolumeChart } from "@/components/servicedesk/volume-chart"
import { BacklogChart } from "@/components/servicedesk/backlog-chart"
import { SLAPredictionChart } from "@/components/servicedesk/sla-prediction-chart"
import { VolumePredictionCard } from "@/components/servicedesk/volume-prediction-card"
import { PriorityFilter } from "@/components/servicedesk/priority-filter"
import { PageWrapper } from "@/components/layout/PageWrapper"
import { ProtectedRoute } from "@/components/layout/ProtectedRoute"
import { LoadingSpinner } from "@/components/shared/LoadingSpinner"
import { ErrorState } from "@/components/shared/ErrorState"
import { useITSMDashboard } from "@/hooks/useDashboard"

export default function ServiceDeskPage() {
  const [selectedPriorities, setSelectedPriorities] = useState<string[]>(["P1", "P2", "P3"])
  const [dateRange] = useState({ from: new Date("2025-04-01"), to: new Date("2026-04-30") })

  const { data, isLoading, error, refetch } = useITSMDashboard({
    date_from: format(dateRange.from, "yyyy-MM-dd"),
    date_to:   format(dateRange.to,   "yyyy-MM-dd"),
  })

  const kpis = data?.kpis

  // Volume chart — trends_13m → { month, P1, P2, P3 }
  const volumeData = useMemo(() =>
    (data?.trends_13m ?? []).map(d => ({
      month: d.date ? d.date.slice(0, 7) : "",
      P1: d.p1 ?? 0,
      P2: d.p2 ?? 0,
      P3: d.p3 ?? 0,
    })), [data])

  const filteredVolumeData = useMemo(() =>
    volumeData.map(item => ({
      ...item,
      P1: selectedPriorities.includes("P1") ? item.P1 : 0,
      P2: selectedPriorities.includes("P2") ? item.P2 : 0,
      P3: selectedPriorities.includes("P3") ? item.P3 : 0,
    })), [volumeData, selectedPriorities])

  // Backlog chart — trends_13m → { month, value }
  const backlogData = useMemo(() =>
    (data?.trends_13m ?? []).map(d => ({
      month: d.date ? d.date.slice(0, 7) : "",
      value: d.backlog ?? 0,
    })), [data])

  // SLA prediction : 6 semaines réelles + prédiction J+7
  const slaPredData = useMemo(() => {
    const reals = (data?.sla_weekly ?? []).slice(-6).map(d => ({
      week: `S${d.semaine}`,
      real: d.sla_reel,
      predicted: null as number | null,
    }))
    const preds = (data?.sla_prediction_j7 ?? []).slice(0, 3).map((d, i) => ({
      week: `J+${i + 1}`,
      real: null as number | null,
      predicted: d.yhat,
    }))
    return [...reals, ...preds]
  }, [data])

  // Backlog growth label
  const backlogLabel = useMemo(() => {
    if (!kpis) return "—"
    const delta = kpis.backlog_delta_13m
    if (delta == null) return `Total : ${kpis.backlog_total}`
    return `${delta > 0 ? "+" : ""}${delta.toFixed(0)}x depuis début période`
  }, [kpis])

  return (
    <ProtectedRoute requiredPage="itsm">
      <PageWrapper>
        <div className="min-h-screen bg-[#f0f0f0]">

          {/* Header — fidèle à la maquette */}
          <header className="bg-[#1b1a19] text-white px-6 py-4">
            <div className="max-w-[1600px] mx-auto flex items-center justify-between">
              <div className="flex items-center gap-8">
                <div className="flex items-center gap-2">
                  <span className="text-[#ffb900] text-xl font-bold">DSI</span>
                  <span className="text-[#a19f9d]">·</span>
                  <span className="text-[#a19f9d] text-sm">Power BI</span>
                </div>
                <h1 className="text-lg font-semibold">Page 5 — Service Desk &amp; Support</h1>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2 text-sm text-[#a19f9d]">
                  <Calendar className="h-4 w-4" />
                  <span>Avr 2025</span>
                  <ArrowRight className="h-4 w-4" />
                  <span className="text-white">Avr 2026</span>
                </div>
                <PriorityFilter
                  selectedPriorities={selectedPriorities}
                  onSelectionChange={setSelectedPriorities}
                />
              </div>
            </div>
          </header>

          <main className="max-w-[1600px] mx-auto p-6 space-y-6">
            {isLoading && <LoadingSpinner label="Chargement Service Desk..." />}
            {error   && <ErrorState message="Erreur de chargement ITSM" onRetry={() => refetch()} />}

            {data && (
              <>
                {/* ── Section 1 : KPIs ── */}
                <section>
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-1 h-4 bg-[#118dff]" />
                    <h2 className="text-sm font-bold text-[#12239e] uppercase tracking-wide">
                      KPIs Service Desk — Situation Actuelle
                    </h2>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                    <ServiceKPICard
                      value={kpis?.volume_tickets_jour?.toLocaleString("fr-FR") ?? "—"}
                      label="Volume Tickets / Jour"
                      sublabel="Dernier jour enregistré"
                      variant="default"
                    />
                    <ServiceKPICard
                      value={kpis?.sla_moyen_pct != null ? `${kpis.sla_moyen_pct.toFixed(1)}%` : "—"}
                      label="SLA Moyen"
                      sublabel={`Objectif : ≥ ${kpis?.sla_cible ?? 95}%`}
                      variant={(kpis?.sla_moyen_pct ?? 0) >= (kpis?.sla_cible ?? 95) ? "success" : "warning"}
                      showCheck={(kpis?.sla_moyen_pct ?? 0) >= (kpis?.sla_cible ?? 95)}
                    />
                    <ServiceKPICard
                      value={kpis?.fcr_moyen_pct != null ? `${kpis.fcr_moyen_pct.toFixed(1)}%` : "—"}
                      label="FCR (First Call Res.)"
                      sublabel={`Cible : ${kpis?.fcr_cible ?? 70}% — À améliorer`}
                      variant={(kpis?.fcr_moyen_pct ?? 0) >= (kpis?.fcr_cible ?? 70) ? "success" : "warning"}
                      showWarning={(kpis?.fcr_moyen_pct ?? 0) < (kpis?.fcr_cible ?? 70)}
                    />
                    <ServiceKPICard
                      value={kpis?.mttr_moyen_hours != null ? `${kpis.mttr_moyen_hours.toFixed(1)} h` : "—"}
                      label="MTTR Moyen"
                      sublabel={`P1 priorité max ≤ ${kpis?.mttr_p1_cible ?? 4}h`}
                      variant={(kpis?.mttr_moyen_hours ?? 99) <= (kpis?.mttr_p1_cible ?? 4) ? "success" : "default"}
                    />
                    <ServiceKPICard
                      value={kpis?.csat_moyen != null ? `${kpis.csat_moyen.toFixed(2)} / 5` : "—"}
                      label="CSAT Moyen"
                      sublabel="Satisfaction utilisateurs"
                      variant={(kpis?.csat_moyen ?? 0) >= 4 ? "success" : "warning"}
                    />
                    <BacklogCard
                      value={kpis?.backlog_total ?? 0}
                      growth={backlogLabel}
                    />
                  </div>
                </section>

                {/* ── Section 2 : Volumétrie ── */}
                <section>
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-1 h-4 bg-[#118dff]" />
                    <h2 className="text-sm font-bold text-[#12239e] uppercase tracking-wide">
                      Volumétrie &amp; Tendances
                    </h2>
                  </div>
                  <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
                    <div className="lg:col-span-5">
                      <VolumeChart data={filteredVolumeData} selectedPriorities={selectedPriorities} />
                    </div>
                    <div className="lg:col-span-4">
                      <BacklogChart data={backlogData} />
                    </div>
                    <div className="lg:col-span-3">
                      <SLAPredictionChart data={slaPredData} />
                    </div>
                  </div>
                </section>

                {/* ── Section 3 : Prédiction Volume J+7 (remplace Charge Techniciens) ── */}
                <section>
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-1 h-4 bg-[#00b7c3]" />
                    <h2 className="text-sm font-bold text-[#12239e] uppercase tracking-wide">
                      Prédiction Volume J+7
                    </h2>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
                    {/* Détail des 4 premiers jours prédits */}
                    {(data.prediction_volume_j7?.points ?? []).slice(0, 4).map((pt, i) => (
                      <div key={i} className="bg-white border border-[#e1dfdd] rounded-lg p-3 hover:shadow-md transition-all">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-semibold text-[#252423]">
                            {pt.date ? format(new Date(pt.date), "EEE dd/MM", { locale: fr }) : `J+${i + 1}`}
                          </span>
                          <span className="text-xs text-[#605e5c]">
                            {pt.yhat != null ? `${Math.round(pt.yhat)} tickets` : "—"}
                          </span>
                        </div>
                        <div className="h-2 bg-[#f3f2f1] rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-500"
                            style={{
                              width: `${Math.min(((pt.yhat ?? 0) / (kpis?.volume_tickets_jour ?? 100)) * 100, 100)}%`,
                              backgroundColor:
                                (pt.yhat ?? 0) > (kpis?.volume_tickets_jour ?? 0) * 1.15 ? "#d13438"
                                : (pt.yhat ?? 0) > (kpis?.volume_tickets_jour ?? 0) * 1.05 ? "#e66c37"
                                : "#107c10",
                            }}
                          />
                        </div>
                        <div className="text-xs mt-1 text-[#605e5c]">
                          {pt.lower != null && pt.upper != null
                            ? `[${Math.round(pt.lower)} – ${Math.round(pt.upper)}]`
                            : "Intervalle N/A"}
                        </div>
                      </div>
                    ))}

                    {/* Carte prédiction synthèse */}
                    <VolumePredictionCard
                      tendancePct={data.prediction_volume_j7?.tendance_pct ?? null}
                      points={data.prediction_volume_j7?.points}
                    />
                  </div>
                </section>
              </>
            )}
          </main>

          {/* Footer */}
          <footer className="border-t border-[#e1dfdd] bg-white py-3 px-6 mt-8">
            <div className="max-w-[1600px] mx-auto flex items-center justify-between text-xs text-[#605e5c]">
              <div className="flex items-center gap-2">
                <span>PFE 2025 — Dashboard DSI</span>
                <span>|</span>
                <span>Page 5 sur 9</span>
                <span>|</span>
                <span>Service Desk &amp; Support</span>
              </div>
              <span>Màj : {data?.timestamp ? format(new Date(data.timestamp), "MMM yyyy", { locale: fr }) : "—"}</span>
            </div>
          </footer>
        </div>
      </PageWrapper>
    </ProtectedRoute>
  )
}