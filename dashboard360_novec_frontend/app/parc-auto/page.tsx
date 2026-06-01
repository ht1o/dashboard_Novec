"use client"

import { useState, useMemo } from "react"
import { format } from "date-fns"
import { fr } from "date-fns/locale"
import { ArrowRight, Car } from "lucide-react"
import { FleetKPICard } from "@/components/parc-auto/fleet-kpi-card"
import { DispoChart } from "@/components/parc-auto/dispo-chart"
import { SinistresChart } from "@/components/parc-auto/sinistres-chart"
import { ConsoChart } from "@/components/parc-auto/conso-chart"
import { TcoBarCard } from "@/components/parc-auto/tco-bar-card"
import { ParcPredictionsCard } from "@/components/parc-auto/predictions-card"
import { PageWrapper } from "@/components/layout/PageWrapper"
import { ProtectedRoute } from "@/components/layout/ProtectedRoute"
import { LoadingSpinner } from "@/components/shared/LoadingSpinner"
import { ErrorState } from "@/components/shared/ErrorState"
import { useParcAutoDashboard } from "@/hooks/useDashboard"
import { formatMAD } from "@/lib/utils"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"

const DEPTS = ["DG", "DRH", "DAF", "DSI", "DOP", "DCM"]

export default function ParcAutoPage() {
  const [dept, setDept] = useState<string>("")

  const { data, isLoading, error, refetch } = useParcAutoDashboard({
    vehicule_dept: dept || null,
    date_from: "2025-04-01",
    date_to:   "2026-04-30",
  })

  const kpis = data?.kpis

  /* ── Séries graphiques ── */
  const dispoData = useMemo(() =>
    (data?.trends_13m ?? []).map(d => ({
      month: d.date ? d.date.slice(0, 7) : "",
      dispo: d.dispo_pct,
    })), [data])

  const sinistresData = useMemo(() =>
    (data?.trends_13m ?? []).map(d => ({
      month: d.date ? d.date.slice(0, 7) : "",
      sinistres: d.sinistres ?? 0,
    })), [data])

  const consoData = useMemo(() =>
    (data?.trends_13m ?? []).map(d => ({
      month: d.date ? d.date.slice(0, 7) : "",
      conso: d.conso_l100km,
    })), [data])

  /* ── TCO points clés ── */
  const tcoPoints = useMemo(() => data?.tco_points_cles ?? [], [data])

  /* ── Prédictions M+3 ── */
  const predItems = useMemo(() => {
    const p = data?.predictions_m3
    if (!p) return []
    return [
      {
        label:    "Conso M+3",
        value:    p.conso_m3?.yhat_m3 != null ? `~${p.conso_m3.yhat_m3.toFixed(1)} L/100` : "—",
        sublabel: p.conso_m3?.date_m3 ?? "",
        note:     p.conso_m3?.rag === "VERT" ? "Stable, légère baisse si conduite éco" : "Hausse anticipée",
        color:    p.conso_m3?.rag === "ROUGE" ? "#d13438" : p.conso_m3?.rag === "AMBRE" ? "#e66c37" : "#107c10",
      },
      {
        label:    "Sinistres M+3",
        value:    p.sinistres_m3?.yhat_m3 != null ? `~${p.sinistres_m3.yhat_m3.toFixed(0)}-${(p.sinistres_m3.yhat_m3 + 1).toFixed(0)} / mois` : "—",
        sublabel: p.sinistres_m3?.date_m3 ?? "",
        note:     "Hiver passé, retour à la normale",
        color:    p.sinistres_m3?.rag === "ROUGE" ? "#d13438" : p.sinistres_m3?.rag === "AMBRE" ? "#e66c37" : "#107c10",
      },
      {
        label:    "TCO M+3",
        value:    p.tco_m3?.yhat_m3 != null ? `~${(p.tco_m3.yhat_m3 / 1000).toFixed(0)} ${Math.round((p.tco_m3.yhat_m3 % 1000) / 100) * 100} MAD` : "—",
        sublabel: p.tco_m3?.date_m3 ?? "",
        note:     "-0.8% si entretien préventif",
        color:    p.tco_m3?.rag === "ROUGE" ? "#d13438" : p.tco_m3?.rag === "AMBRE" ? "#e66c37" : "#107c10",
      },
    ]
  }, [data])

  /* ── Pic sinistres ── */
  const picLabel = data?.pic_sinistres?.date
    ? format(new Date(data.pic_sinistres.date), "MMM yyyy", { locale: fr })
    : null

  return (
    <ProtectedRoute requiredPage="parc_auto">
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
                <h1 className="text-lg font-semibold">Page 8 — Parc Automobile</h1>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 text-sm text-[#a19f9d]">
                  <span className="text-white font-medium">Avr 2025</span>
                  <ArrowRight className="h-4 w-4" />
                  <span className="text-white font-medium">Avr 2026</span>
                </div>
                <Select value={dept} onValueChange={setDept}>
                  <SelectTrigger className="w-40 bg-[#00b7c3] hover:bg-[#00a0ac] border-0 text-white text-sm font-medium">
                    <SelectValue placeholder="Véhicule / Dept" />
                  </SelectTrigger>
                  <SelectContent className="bg-white border-[#e1dfdd]">
                    <SelectItem value="">Tous les Depts</SelectItem>
                    {DEPTS.map(d => <SelectItem key={d} value={d}>{d}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </header>

          <main className="max-w-[1600px] mx-auto p-6 space-y-6">
            {isLoading && <LoadingSpinner label="Chargement Parc Automobile..." />}
            {error    && <ErrorState message="Erreur chargement parc auto" onRetry={() => refetch()} />}

            {data && (
              <>
                {/* ── Section 1 : État de la flotte ── */}
                <section>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-1 h-4 bg-[#118dff]" />
                    <h2 className="text-xs font-bold text-[#12239e] uppercase tracking-widest">
                      État de la Flotte — Situation Actuelle ({kpis?.derniere_date ? format(new Date(kpis.derniere_date), "MMM yyyy", { locale: fr }) : "Avr 2026"})
                    </h2>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {/* Ligne 1 */}
                    <FleetKPICard
                      value={kpis?.flotte_totale != null ? `${kpis.flotte_totale} véhicules` : "—"}
                      label="Flotte Totale"
                      sublabel="Périmètre constant"
                      accentColor="#118dff"
                      borderColor="border-l-[#118dff]"
                    />
                    <FleetKPICard
                      value={kpis?.disponibilite_pct != null ? `${kpis.disponibilite_pct.toFixed(1)}%` : "—"}
                      label="Disponibilité Flotte"
                      sublabel={kpis?.disponibilite_moy_periode != null ? `Dernier jour - Moy : ${kpis.disponibilite_moy_periode.toFixed(1)}%` : ""}
                      accentColor={kpis?.rag_disponibilite === "ROUGE" ? "#d13438" : kpis?.rag_disponibilite === "AMBRE" ? "#e66c37" : "#107c10"}
                      borderColor={kpis?.rag_disponibilite === "ROUGE" ? "border-l-[#d13438]" : kpis?.rag_disponibilite === "AMBRE" ? "border-l-[#e66c37]" : "border-l-[#107c10]"}
                    />
                    <FleetKPICard
                      value={kpis?.sinistres_mois_courant != null ? String(kpis.sinistres_mois_courant) : "—"}
                      label="Sinistres ce mois"
                      sublabel={data.pic_sinistres ? `Pic ${picLabel} : ${data.pic_sinistres.valeur} sinistres` : ""}
                      accentColor={kpis?.rag_sinistralite === "ROUGE" ? "#d13438" : kpis?.rag_sinistralite === "AMBRE" ? "#e66c37" : "#252423"}
                      borderColor={kpis?.rag_sinistralite === "ROUGE" ? "border-l-[#d13438]" : kpis?.rag_sinistralite === "AMBRE" ? "border-l-[#e66c37]" : "border-l-[#e1dfdd]"}
                    />

                    {/* Ligne 2 */}
                    <FleetKPICard
                      value={kpis?.conso_moy_l100km != null ? `${kpis.conso_moy_l100km.toFixed(1)} L` : "—"}
                      label="Conso. Moy. L/100km"
                      sublabel="Stable sur 13 mois"
                      accentColor="#118dff"
                      borderColor="border-l-[#118dff]"
                    />
                    <FleetKPICard
                      value={kpis?.tco_moy_par_vehicule_mad != null ? formatMAD(kpis.tco_moy_par_vehicule_mad) : "—"}
                      label="TCO Moyen / Véhicule"
                      sublabel={kpis?.tco_delta_vs_an_prec != null ? `${kpis.tco_delta_vs_an_prec > 0 ? "+" : ""}${kpis.tco_delta_vs_an_prec.toFixed(1)}% vs Avr 2025` : ""}
                      accentColor={kpis?.rag_tco === "ROUGE" ? "#d13438" : kpis?.rag_tco === "AMBRE" ? "#e66c37" : "#107c10"}
                      borderColor={kpis?.rag_tco === "ROUGE" ? "border-l-[#d13438]" : kpis?.rag_tco === "AMBRE" ? "border-l-[#e66c37]" : "border-l-[#107c10]"}
                    />
                    <FleetKPICard
                      value={kpis?.taux_sinistralite_pct != null ? `${kpis.taux_sinistralite_pct.toFixed(1)}%` : "0%"}
                      label="Taux Sinistralité"
                      sublabel={kpis?.sinistres_mois_courant === 0 ? "Aucun sinistre ce jour" : `${kpis?.sinistres_mois_courant} sinistres ce mois`}
                      accentColor={kpis?.rag_sinistralite === "ROUGE" ? "#d13438" : "#107c10"}
                      borderColor={kpis?.rag_sinistralite === "ROUGE" ? "border-l-[#d13438]" : "border-l-[#107c10]"}
                    />
                  </div>
                </section>

                {/* ── Section 2 : Tendances 13 mois ── */}
                <section>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-1 h-4 bg-[#118dff]" />
                    <h2 className="text-xs font-bold text-[#12239e] uppercase tracking-widest">
                      Tendances Flotte — 13 mois
                    </h2>
                  </div>
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    <DispoChart data={dispoData} />
                    <SinistresChart
                      data={sinistresData}
                      picLabel={picLabel}
                      picValue={data.pic_sinistres?.valeur}
                    />
                    <ConsoChart data={consoData} />
                  </div>
                </section>

                {/* ── Section 3 : TCO & Prédictions ── */}
                <section>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-1 h-4 bg-[#118dff]" />
                    <h2 className="text-xs font-bold text-[#12239e] uppercase tracking-widest">
                      TCO &amp; Prédiction Consommation M+3
                    </h2>
                  </div>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <TcoBarCard points={tcoPoints} />
                    {predItems.length > 0 && <ParcPredictionsCard items={predItems} />}
                  </div>
                </section>
              </>
            )}
          </main>

          {/* ── Footer ── */}
          <footer className="border-t border-[#e1dfdd] bg-white py-3 px-6 mt-4">
            <div className="max-w-[1600px] mx-auto flex items-center justify-between text-xs text-[#605e5c]">
              <div className="flex items-center gap-2">
                <span>PFE 2025 — Dashboard DSI</span>
                <span>|</span>
                <span>Page 8 sur 9</span>
                <span>|</span>
                <span>Parc Automobile</span>
              </div>
              <span>Màj : {data?.timestamp ? format(new Date(data.timestamp), "MMM yyyy", { locale: fr }) : "—"}</span>
            </div>
          </footer>
        </div>
      </PageWrapper>
    </ProtectedRoute>
  )
}