"use client"

import { useMemo } from "react"
import { format } from "date-fns"
import { fr } from "date-fns/locale"
import { ArrowRight, Info } from "lucide-react"
import { MaintKPICard } from "@/components/maintenance/maint-kpi-card"
import { OtChart } from "@/components/maintenance/ot-chart"
import { RatioChart } from "@/components/maintenance/ratio-chart"
import { RupturesChart } from "@/components/maintenance/ruptures-chart"
import { MaintPredictionsCard } from "@/components/maintenance/maint-predictions-card"
import { PageWrapper } from "@/components/layout/PageWrapper"
import { ProtectedRoute } from "@/components/layout/ProtectedRoute"
import { LoadingSpinner } from "@/components/shared/LoadingSpinner"
import { ErrorState } from "@/components/shared/ErrorState"
import { Skeleton } from "@/components/ui/skeleton"
import { useMaintenanceDashboard } from "@/hooks/useDashboard"

export default function MaintenancePage() {
  const { data, isLoading, error, refetch } = useMaintenanceDashboard({
    date_from: "2025-04-01",
    date_to:   "2026-04-30",
  })

  const kpis = data?.kpis

  /* ── Séries graphiques ── */
  const otData = useMemo(() =>
    (data?.trends_13m ?? []).map(d => ({
      month:        d.date.slice(0, 7),
      ot_preventif: d.ot_preventif,
      ot_correctif: d.ot_correctif,
    })), [data])

  const ratioData = useMemo(() =>
    (data?.trends_13m ?? []).map(d => ({
      month:      d.date.slice(0, 7),
      ratio_prev: d.ratio_prev,
      taux_real:  d.taux_real,
    })), [data])

  const rupturesData = useMemo(() =>
    (data?.trends_13m ?? []).map(d => ({
      month:    d.date.slice(0, 7),
      ruptures: d.ruptures,
    })), [data])

  /* ── Prédictions M+3 ── */
  const predictions = useMemo(() => {
    const p = data?.predictions_m3
    if (!p) return []

    const otVal      = p.ot_m3?.yhat_m3      ?? 0
    const ratioVal   = p.ratio_prev_m3?.yhat_m3 ?? 0
    const ruptVal    = p.ruptures_m3?.yhat_m3 ?? 0

    return [
      {
        label:   "OT Total M+3",
        value:   otVal > 0 ? `~${Math.round(otVal)} OT` : "—",
        note:    otVal > (kpis?.total_ot ?? 0) * 1.1
          ? "Hausse anticipée — renforcer les équipes"
          : "Charge stable sur l'horizon M+3",
        rag:     p.ot_m3?.rag ?? "AMBRE",
        date_m3: p.ot_m3?.date_m3 ?? "—",
      },
      {
        label:   "Ratio Préventif M+3",
        value:   ratioVal > 0 ? `~${ratioVal.toFixed(1)}%` : "—",
        note:    ratioVal >= (kpis?.ratio_cible ?? 70)
          ? "Objectif préventif atteint"
          : `Sous la cible ${kpis?.ratio_cible ?? 70}% — plan correctif`,
        rag:     p.ratio_prev_m3?.rag ?? "AMBRE",
        date_m3: p.ratio_prev_m3?.date_m3 ?? "—",
      },
      {
        label:   "Ruptures Stock M+3",
        value:   ruptVal > 0 ? `~${Math.round(ruptVal)} ruptures` : "0 rupture",
        note:    ruptVal === 0
          ? "Aucune rupture prévue — stock suffisant"
          : ruptVal > 3
            ? "Risque rupture élevé — réappro urgente"
            : "Quelques ruptures anticipées — surveiller",
        rag:     p.ruptures_m3?.rag ?? "VERT",
        date_m3: p.ruptures_m3?.date_m3 ?? "—",
      },
    ]
  }, [data, kpis])

  return (
    <ProtectedRoute requiredPage="maintenance">
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
                <h1 className="text-lg font-semibold">Page 9 — Maintenance</h1>
              </div>
              <div className="flex items-center gap-2 text-sm text-[#a19f9d]">
                <span className="text-white font-medium">Avr 2025</span>
                <ArrowRight className="h-4 w-4" />
                <span className="text-white font-medium">Avr 2026</span>
              </div>
            </div>
          </header>

          <main className="max-w-[1600px] mx-auto p-6 space-y-6">
            {isLoading && <LoadingSpinner label="Chargement Maintenance..." />}
            {error     && <ErrorState message="Erreur chargement maintenance" onRetry={() => refetch()} />}

            {/* ── Section 1 : KPIs ── */}
            <section>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-1 h-4 bg-[#118dff]" />
                <h2 className="text-xs font-bold text-[#12239e] uppercase tracking-widest">
                  État de la Maintenance — Situation Actuelle
                  {kpis?.derniere_date && (
                    <span className="normal-case font-normal text-[#605e5c] ml-2">
                      ({format(new Date(kpis.derniere_date), "MMM yyyy", { locale: fr })})
                    </span>
                  )}
                </h2>
              </div>

              {isLoading ? (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-sm" />)}
                </div>
              ) : data && (
                <>
                  {/* Ligne 1 : volumes */}
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
                    <MaintKPICard
                      value={String(kpis?.total_ot ?? 0)}
                      label="Total OT"
                      sublabel={`Dernier mois : ${kpis?.ot_dernier_mois ?? "—"} OT`}
                      rag="VERT"
                    />
                    <MaintKPICard
                      value={String(kpis?.ot_preventif ?? 0)}
                      label="OT Préventifs"
                      sublabel={`${kpis?.pct_preventif_realise != null ? `${kpis.pct_preventif_realise.toFixed(0)}% réalisés` : "—"}`}
                      rag={kpis?.rag_ratio ?? "AMBRE"}
                    />
                    <MaintKPICard
                      value={String(kpis?.ot_correctif ?? 0)}
                      label="OT Correctifs"
                      sublabel="Interventions non planifiées"
                      rag={(kpis?.ot_correctif ?? 0) > (kpis?.ot_preventif ?? 0) ? "ROUGE" : "VERT"}
                    />
                    <MaintKPICard
                      value={kpis?.alertes_rouge ? `${kpis.alertes_rouge}` : "0"}
                      label="Alertes Critiques"
                      sublabel="Alertes rouge actives"
                      rag={kpis?.alertes_rouge && kpis.alertes_rouge > 0 ? "ROUGE" : "VERT"}
                    />
                  </div>

                  {/* Ligne 2 : indicateurs qualité */}
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <MaintKPICard
                      value={kpis?.ratio_preventif_pct != null ? `${kpis.ratio_preventif_pct.toFixed(1)}%` : "—"}
                      label="Ratio Préventif"
                      cible={`Cible : ≥ ${kpis?.ratio_cible ?? 70}%`}
                      sublabel={`Dernier mois : ${kpis?.ratio_dernier_mois != null ? `${kpis.ratio_dernier_mois.toFixed(1)}%` : "—"}`}
                      rag={kpis?.rag_ratio ?? "AMBRE"}
                      delta={kpis?.ratio_delta_vs_mois ?? null}
                    />
                    <MaintKPICard
                      value={kpis?.taux_realisation_pct != null ? `${kpis.taux_realisation_pct.toFixed(1)}%` : "—"}
                      label="Taux de Réalisation"
                      cible={`Cible : ≥ ${kpis?.taux_cible ?? 85}%`}
                      sublabel={`Dernier mois : ${kpis?.taux_real_dernier_mois != null ? `${kpis.taux_real_dernier_mois.toFixed(1)}%` : "—"}`}
                      rag={kpis?.rag_taux ?? "AMBRE"}
                    />
                    <MaintKPICard
                      value={String(kpis?.ruptures_stock ?? 0)}
                      label="Ruptures de Stock"
                      cible="Objectif : 0 rupture"
                      sublabel={`Dernier mois : ${kpis?.ruptures_dernier_mois ?? 0} rupture(s)`}
                      rag={kpis?.rag_ruptures ?? "VERT"}
                    />
                    <MaintKPICard
                      value={kpis?.pct_preventif_realise != null ? `${kpis.pct_preventif_realise.toFixed(1)}%` : "—"}
                      label="% Préventif Réalisé"
                      sublabel="OT préventifs exécutés / planifiés"
                      rag={(kpis?.pct_preventif_realise ?? 0) >= 85 ? "VERT" : (kpis?.pct_preventif_realise ?? 0) >= 70 ? "AMBRE" : "ROUGE"}
                    />
                  </div>
                </>
              )}
            </section>

            {/* ── Section 2 : Tendances 13 mois ── */}
            {data && (
              <section>
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-1 h-4 bg-[#118dff]" />
                  <h2 className="text-xs font-bold text-[#12239e] uppercase tracking-widest">
                    Tendances Maintenance — 13 mois
                  </h2>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  <OtChart data={otData} />
                  <RatioChart
                    data={ratioData}
                    ratioCible={kpis?.ratio_cible ?? 70}
                    tauxCible={kpis?.taux_cible ?? 85}
                  />
                  <RupturesChart data={rupturesData} />
                </div>
              </section>
            )}

            {/* ── Section 3 : Prédictions M+3 ── */}
            {data && predictions.length > 0 && (
              <section>
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-1 h-4 bg-[#6b52ae]" />
                  <h2 className="text-xs font-bold text-[#6b52ae] uppercase tracking-widest">
                    Prédictions IA — Horizon M+3
                  </h2>
                </div>
                <MaintPredictionsCard predictions={predictions} />
              </section>
            )}

            {/* ── Bandeau info ── */}
            {data && (
              <div className="bg-[#e8f4fd] border border-[#0078d4]/30 rounded-sm px-4 py-3 flex items-start gap-2">
                <Info className="h-4 w-4 text-[#0078d4] shrink-0 mt-0.5" />
                <p className="text-xs text-[#605e5c] leading-relaxed">
                  <span className="font-semibold text-[#252423]">STRATÉGIE MAINTENANCE :</span>
                  {" "}Un ratio préventif ≥ {kpis?.ratio_cible ?? 70}% réduit les pannes imprévues et allonge la durée de vie des équipements.
                  Le taux de réalisation mesure l'exécution des OT planifiés. Les ruptures de stock bloquent les interventions
                  préventives et doivent être anticipées par une gestion proactive des pièces détachées.
                  {data.rag_status && (
                    <span className="ml-1 font-medium" style={{
                      color: data.rag_status === "ROUGE" ? "#d13438" : data.rag_status === "AMBRE" ? "#e66c37" : "#107c10"
                    }}>
                      Statut global : {data.rag_status}.
                    </span>
                  )}
                </p>
              </div>
            )}
          </main>

          {/* ── Footer ── */}
          <footer className="border-t border-[#e1dfdd] bg-white py-3 px-6 mt-4">
            <div className="max-w-[1600px] mx-auto flex items-center justify-between text-xs text-[#605e5c]">
              <div className="flex items-center gap-2">
                <span>PFE 2025 — Dashboard DSI</span>
                <span>|</span>
                <span>Page 9 sur 9</span>
                <span>|</span>
                <span>Maintenance</span>
              </div>
              <span>Màj : {data?.timestamp ? format(new Date(data.timestamp), "MMM yyyy", { locale: fr }) : "—"}</span>
            </div>
          </footer>
        </div>
      </PageWrapper>
    </ProtectedRoute>
  )
}