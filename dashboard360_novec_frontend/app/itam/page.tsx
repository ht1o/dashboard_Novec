"use client"

import { useMemo } from "react"
import { format } from "date-fns"
import { fr } from "date-fns/locale"
import { ArrowRight, Monitor, Info } from "lucide-react"
import { ITAMKPICard } from "@/components/itam/itam-kpi-card"
import { ITAMTrendsChart } from "@/components/itam/itam-trends-chart"
import { TcoTrendChart } from "@/components/itam/tco-trend-chart"
import { LicencesChart } from "@/components/itam/licences-chart"
import { ITAMPredictionsCard } from "@/components/itam/itam-predictions-card"
import { PageWrapper } from "@/components/layout/PageWrapper"
import { ProtectedRoute } from "@/components/layout/ProtectedRoute"
import { LoadingSpinner } from "@/components/shared/LoadingSpinner"
import { ErrorState } from "@/components/shared/ErrorState"
import { Skeleton } from "@/components/ui/skeleton"
import { useITAMDashboard } from "@/hooks/useDashboard"
import { formatMAD } from "@/lib/utils"

export default function ITAMPage() {
  const { data, isLoading, error, refetch } = useITAMDashboard({
    date_from: "2025-04-01",
    date_to:   "2026-04-30",
  })

  const kpis = data?.kpis

  /* ── Séries graphiques ── */
  const indicatorsData = useMemo(() =>
    (data?.trends_13m ?? []).map(d => ({
      month:                d.date.slice(0, 7),
      vetuste_pct:          d.vetuste_pct,
      conformite_licences:  d.conformite_licences,
      cmdb_couverture:      d.cmdb_couverture,
      licences_inutilisees: d.licences_inutilisees,
    })), [data])

  const tcoData = useMemo(() =>
    (data?.trends_13m ?? []).map(d => ({
      month:        d.date.slice(0, 7),
      tco_par_poste: d.tco_par_poste,
    })), [data])

  const licData = useMemo(() =>
    (data?.trends_13m ?? []).map(d => ({
      month:                d.date.slice(0, 7),
      licences_inutilisees: d.licences_inutilisees,
    })), [data])

  /* ── Prédictions M+6 ── */
  const predictions = useMemo(() => {
    const p = data?.predictions_m6
    if (!p) return []
    const vetusteVal  = p.vetuste_m6?.yhat_m6  ?? 0
    const licencesVal = p.licences_m6?.yhat_m6 ?? 0
    return [
      {
        label:   "Vétusté M+6",
          unit:    "%",
        yhat_m6: p.vetuste_m6?.yhat_m6 ?? null,
        rag:     p.vetuste_m6?.rag ?? "AMBRE",
        date_m6: p.vetuste_m6?.date_m6 ?? "—",
        format:  (v: number) => `${v.toFixed(1)}%`,
        note:    vetusteVal > 30
          ? "⚠ Seuil critique dépassé — plan renouvellement requis"
          : "Vétusté sous contrôle sur l'horizon M+6",
      },
      {
        label:   "TCO moyen M+6",
          unit:    "MAD",
        yhat_m6: p.tco_m6?.yhat_m6 ?? null,
        rag:     p.tco_m6?.rag ?? "AMBRE",
        date_m6: p.tco_m6?.date_m6 ?? "—",
        format:  (v: number) => formatMAD(v),
        note:    "Projection coût total de possession par poste",
      },
      {
        label:   "Conformité licences M+6",
          unit:    "%",
        yhat_m6: p.licences_m6?.yhat_m6 ?? null,
        rag:     p.licences_m6?.rag ?? "AMBRE",
        date_m6: p.licences_m6?.date_m6 ?? "—",
        format:  (v: number) => `${v.toFixed(1)}%`,
        note:    licencesVal < 95
          ? "Risque non-conformité — audit recommandé"
          : "Conformité attendue ≥ 95% — situation stable",
      },
    ]
  }, [data])

  return (
    <ProtectedRoute requiredPage="itam">
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
                <h1 className="text-lg font-semibold">Page 7 — Parc Informatique (ITAM)</h1>
              </div>
              <div className="flex items-center gap-2 text-sm text-[#a19f9d]">
                <span className="text-white font-medium">Avr 2025</span>
                <ArrowRight className="h-4 w-4" />
                <span className="text-white font-medium">Avr 2026</span>
              </div>
            </div>
          </header>

          <main className="max-w-[1600px] mx-auto p-6 space-y-6">
            {isLoading && <LoadingSpinner label="Chargement Parc Informatique..." />}
            {error     && <ErrorState message="Erreur chargement ITAM" onRetry={() => refetch()} />}

            {/* ── Section 1 : KPIs ── */}
            <section>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-1 h-4 bg-[#118dff]" />
                <h2 className="text-xs font-bold text-[#12239e] uppercase tracking-widest">
                  État du Parc Informatique — Situation Actuelle
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
                  {/* Ligne 1 : parc & vétusté */}
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
                    <ITAMKPICard
                      value={kpis?.total_postes != null ? `${kpis.total_postes.toLocaleString("fr-FR")} postes` : "—"}
                      label="Parc Total"
                      sublabel="Postes de travail gérés"
                      rag="VERT"
                    />
                    <ITAMKPICard
                      value={kpis?.vetuste_pct != null ? `${kpis.vetuste_pct.toFixed(1)}%` : "—"}
                      label="Taux de Vétusté"
                      cible={`Seuil alerte : > ${kpis?.vetuste_seuil_alerte ?? 30}%`}
                      sublabel={kpis?.vetuste_pct != null && kpis.vetuste_pct > 30
                        ? "⚠ Plan de renouvellement requis"
                        : "Sous le seuil d'alerte"}
                      rag={kpis?.rag_vetuste ?? "AMBRE"}
                    />
                    <ITAMKPICard
                      value={kpis?.tco_moyen_par_poste_mad != null ? formatMAD(kpis.tco_moyen_par_poste_mad) : "—"}
                      label="TCO Moyen / Poste"
                      sublabel={kpis?.tco_delta_vs_mois_prec != null
                        ? `${kpis.tco_delta_vs_mois_prec > 0 ? "+" : ""}${kpis.tco_delta_vs_mois_prec.toFixed(1)}% vs mois préc.`
                        : ""}
                      cible={kpis?.tco_total_mad != null ? `Total parc : ${formatMAD(kpis.tco_total_mad)}` : undefined}
                      rag="AMBRE"
                    />
                    <ITAMKPICard
                      value={String(kpis?.alertes_rouge ?? 0)}
                      label="Alertes Critiques"
                      sublabel="Alertes rouge actives"
                      rag={kpis?.alertes_rouge && kpis.alertes_rouge > 0 ? "ROUGE" : "VERT"}
                    />
                  </div>

                  {/* Ligne 2 : licences, délai, CMDB */}
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <ITAMKPICard
                      value={kpis?.conformite_licences_pct != null ? `${kpis.conformite_licences_pct.toFixed(1)}%` : "—"}
                      label="Conformité Licences"
                      cible={`Cible : ≥ ${kpis?.conformite_cible ?? 95}%`}
                      sublabel={`${kpis?.licences_inutilisees ?? 0} licences inutilisées`}
                      rag={kpis?.rag_licences ?? "AMBRE"}
                    />
                    <ITAMKPICard
                      value={kpis?.licences_inutilisees != null ? String(kpis.licences_inutilisees) : "—"}
                      label="Licences Inutilisées"
                      sublabel="Licences payées non utilisées"
                      cible="Objectif : 0"
                      rag={kpis?.licences_inutilisees && kpis.licences_inutilisees > 10 ? "ROUGE" : kpis?.licences_inutilisees && kpis.licences_inutilisees > 0 ? "AMBRE" : "VERT"}
                    />
                    <ITAMKPICard
                      value={kpis?.delai_mise_dispo_jours != null ? `${kpis.delai_mise_dispo_jours.toFixed(1)} j` : "—"}
                      label="Délai Mise à Disposition"
                      cible={`Cible : ≤ ${kpis?.delai_cible ?? 3} jours`}
                      sublabel="Nouveau poste → utilisateur"
                      rag={kpis?.rag_delai ?? "AMBRE"}
                    />
                    <ITAMKPICard
                      value={kpis?.cmdb_couverture_pct != null ? `${kpis.cmdb_couverture_pct.toFixed(1)}%` : "—"}
                      label="Couverture CMDB"
                      cible={`Cible : ≥ ${kpis?.cmdb_cible ?? 95}%`}
                      sublabel="Assets référencés dans la CMDB"
                      rag={kpis?.rag_cmdb ?? "AMBRE"}
                    />
                  </div>
                </>
              )}
            </section>

            {/* ── Section 2 : Tendances ── */}
            {data && (
              <section>
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-1 h-4 bg-[#118dff]" />
                  <h2 className="text-xs font-bold text-[#12239e] uppercase tracking-widest">
                    Tendances Parc — 13 mois
                  </h2>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  <div className="lg:col-span-1">
                    <ITAMTrendsChart data={indicatorsData} />
                  </div>
                  <div className="lg:col-span-1">
                    <TcoTrendChart data={tcoData} />
                  </div>
                  <div className="lg:col-span-1">
                    <LicencesChart data={licData} />
                  </div>
                </div>
              </section>
            )}

            {/* ── Section 3 : Prédictions M+6 ── */}
            {data && predictions.length > 0 && (
              <section>
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-1 h-4 bg-[#6b52ae]" />
                  <h2 className="text-xs font-bold text-[#6b52ae] uppercase tracking-widest">
                    Prédictions IA — Horizon M+6
                  </h2>
                </div>
                <ITAMPredictionsCard predictions={predictions} />
              </section>
            )}

            {/* ── Bandeau info ── */}
            {data && (
              <div className="bg-[#e8f4fd] border border-[#0078d4]/30 rounded-sm px-4 py-3 flex items-start gap-2">
                <Info className="h-4 w-4 text-[#0078d4] shrink-0 mt-0.5" />
                <p className="text-xs text-[#605e5c] leading-relaxed">
                  <span className="font-semibold text-[#252423]">GESTION DU PARC :</span>
                  {" "}La vétusté est calculée sur les postes de plus de 5 ans. Le délai de mise à disposition mesure
                  le temps entre la commande et la remise du matériel à l'utilisateur. La couverture CMDB reflète
                  l'exhaustivité de l'inventaire des assets IT.
                  {data.risk_score != null && (
                    <span className="ml-1">
                      Score de risque global ITAM : <strong>{Math.round(data.risk_score * 100)}%</strong>.
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
                <span>Page 7 sur 9</span>
                <span>|</span>
                <span>Parc Informatique (ITAM)</span>
              </div>
              <span>Màj : {data?.timestamp ? format(new Date(data.timestamp), "MMM yyyy", { locale: fr }) : "—"}</span>
            </div>
          </footer>
        </div>
      </PageWrapper>
    </ProtectedRoute>
  )
}