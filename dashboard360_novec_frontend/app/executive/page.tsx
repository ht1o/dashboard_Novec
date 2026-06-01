"use client"

import { useState } from "react"
import { format } from "date-fns"
import { fr } from "date-fns/locale"
import { ArrowRight, Info } from "lucide-react"
import { ScorecardItem } from "@/components/executive/scorecard-row"
import { KPITransversalCard } from "@/components/executive/kpi-transversal-card"
import { AttentionBanner } from "@/components/executive/attention-banner"
import { PredictionsBand } from "@/components/executive/predictions-band"
import { PeriodFilter } from "@/components/executive/period-filter"
import { Skeleton } from "@/components/ui/skeleton"
import { PageWrapper } from "@/components/layout/PageWrapper"
import { ProtectedRoute } from "@/components/layout/ProtectedRoute"
import { ErrorState } from "@/components/shared/ErrorState"
import { useExecutiveDashboard } from "@/hooks/useDashboard"

// Mapping clé domaine backend → label maquette + route
const DOMAIN_META: Record<string, { label: string; key: string }> = {
  infrastructure: { label: "Infrastructure",   key: "infrastructure" },
  cybersecurity:  { label: "Cybersécurité",    key: "cyber"          },
  itsm:           { label: "Service Desk",     key: "itsm"           },
  finance:        { label: "Gouvernance",      key: "finance"        },
  applications:   { label: "Applications",    key: "apps"           },
  itam:           { label: "Parc Informatique",key: "itam"           },
  parc_auto:      { label: "Parc Automobile",  key: "parc_auto"      },
  maintenance:    { label: "Maintenance",      key: "maintenance"    },
  data_bi:        { label: "Data & BI",        key: "apps"           },
}

// Ordre d'affichage de la grille (3 colonnes × 3 lignes)
const GRID_ORDER = [
  "infrastructure", "cybersecurity",  "itsm",
  "finance",        "applications",   "itam",
  "parc_auto",      "maintenance",    "data_bi",
]

export default function ExecutivePage() {
  const [period, setPeriod] = useState({ from: "2025-05-01", to: "2026-04-30" })

  const { data, isLoading, error, refetch } = useExecutiveDashboard({
    date_from: period.from,
    date_to:   period.to,
  })

  const kpis   = data?.kpis_transversaux
  const sc     = data?.scorecard ?? {}

  // Parse période affichée dans le header
  const fromLabel = period.from ? format(new Date(period.from), "MMM yyyy", { locale: fr }) : "—"
  const toLabel   = period.to   ? format(new Date(period.to),   "MMM yyyy", { locale: fr }) : "—"

  return (
    <ProtectedRoute requiredPage="executive">
      <PageWrapper>
        <div className="min-h-screen bg-[#f0f0f0]">

          {/* ── Header ── */}
          <header className="bg-[#1b1a19] text-white px-6 py-3">
            <div className="max-w-[1600px] mx-auto flex items-center justify-between">
              <div className="flex items-center gap-8">
                <div className="flex items-center gap-2">
                  <span className="text-[#ffb900] text-xl font-bold">DSI</span>
                  <span className="text-[#a19f9d]">·</span>
                  <span className="text-[#a19f9d] text-sm">Power BI</span>
                </div>
                <h1 className="text-lg font-semibold">Page 1 — Vue Executive 360°</h1>
              </div>
              <div className="flex items-center gap-3">
                <PeriodFilter onPeriodChange={(from, to) => setPeriod({ from, to })} />
                <div className="flex items-center gap-2 text-sm text-[#a19f9d]">
                  <span className="text-white font-medium capitalize">{fromLabel}</span>
                  <ArrowRight className="h-4 w-4" />
                  <span className="text-white font-medium capitalize">{toLabel}</span>
                </div>
              </div>
            </div>
          </header>

          <main className="max-w-[1600px] mx-auto p-6 space-y-5">

            {/* ── Bandeau intro ── */}
            <div className="bg-[#fffbe6] border border-[#e8c84a] rounded-sm px-4 py-3 flex items-start gap-2">
              <span className="text-base mt-0.5">🧭</span>
              <p className="text-xs text-[#605e5c] leading-relaxed">
                <span className="font-semibold text-[#252423]">VUE D'ENSEMBLE POUR LA DIRECTION :</span>
                {" "}Cette page synthétise les 9 domaines IT en un seul coup d'œil. Les indicateurs RAG (
                <span className="text-[#107c10]">● Vert</span> / <span className="text-[#e66c37]">● Jaune</span> / <span className="text-[#d13438]">● Rouge</span>
                ) signalent les priorités d'action. Pas besoin d'analyser chaque chiffre — concentrez-vous sur les éléments <span className="text-[#e66c37]">🟠</span> et <span className="text-[#d13438]">🔴</span>.
              </p>
            </div>

            {/* ── Scorecard RAG ── */}
            <section>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-1 h-4 bg-[#118dff]" />
                <h2 className="text-sm font-bold text-[#12239e] uppercase tracking-wide">
                  Scorecard RAG — État des Domaines IT
                </h2>
              </div>

              {isLoading ? (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {Array.from({ length: 9 }).map((_, i) => (
                    <Skeleton key={i} className="h-16 rounded-sm" />
                  ))}
                </div>
              ) : error ? (
                <ErrorState message="Erreur chargement scorecard" onRetry={() => refetch()} />
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {GRID_ORDER.map(domainKey => {
                    const meta   = DOMAIN_META[domainKey]
                    const entry  = sc[domainKey]
                    if (!meta) return null
                    return (
                      <ScorecardItem
                        key={domainKey}
                        domainKey={meta.key}
                        label={meta.label}
                        rag={entry?.rag ?? "AMBRE"}
                        kpiLabel={entry?.kpi_label ?? ""}
                        kpiValue={entry?.kpi_value ?? null}
                        kpiUnit={entry?.kpi_unit ?? ""}
                        action={entry?.action ?? null}
                      />
                    )
                  })}
                </div>
              )}

              {/* Note actions */}
              <div className="flex items-center gap-2 mt-3 bg-[#e8f4fd] border border-[#0078d4]/30 rounded-sm px-3 py-2">
                <Info className="h-3.5 w-3.5 text-[#0078d4] shrink-0" />
                <p className="text-xs text-[#605e5c]">
                  Les cases avec une action recommandée (colonne droite) sont les points d'attention prioritaires pour la prochaine réunion de direction.
                </p>
              </div>
            </section>

            {/* ── KPIs Transversaux ── */}
            <section>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-1 h-4 bg-[#118dff]" />
                <h2 className="text-sm font-bold text-[#12239e] uppercase tracking-wide">
                  KPIs Transversaux IT + Business
                </h2>
              </div>

              {isLoading ? (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-36 rounded-sm" />)}
                </div>
              ) : (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  {/* IT Cost / Revenue */}
                  <KPITransversalCard
                    value={kpis?.digital_adoption_pct != null ? `${kpis.digital_adoption_pct.toFixed(1)}%` : "—"}
                    label="Digital Adoption"
                    sublabel="Cible : 80%"
                    note="% d'employés utilisant activement les outils numériques déployés par la DSI."
                    accentColor="#0078d4"
                    headerBg="#0078d4"
                  />
                  {/* IT Risk Score */}
                  <KPITransversalCard
                    value={kpis?.it_risk_score != null ? `${Math.round(kpis.it_risk_score)} / 100` : "—"}
                    label="IT Risk Score"
                    sublabel=""
                    statusLabel={
                      (kpis?.it_risk_score ?? 0) > 70 ? "Risque élevé"
                      : (kpis?.it_risk_score ?? 0) > 40 ? "Risque modéré"
                      : "Risque faible"
                    }
                    statusColor={
                      (kpis?.it_risk_score ?? 0) > 70 ? "#d13438"
                      : (kpis?.it_risk_score ?? 0) > 40 ? "#e66c37"
                      : "#107c10"
                    }
                    note="Score composite Sécu + Conformité + Infra. Objectif : descendre sous 50."
                    accentColor="#e66c37"
                    headerBg="#e66c37"
                  />
                  {/* Alertes actives */}
                  <KPITransversalCard
                    value={String((kpis?.nb_alertes_rouge ?? 0) + (kpis?.nb_alertes_ambre ?? 0))}
                    label="Alertes Actives"
                    sublabel={`🔴 ${kpis?.nb_alertes_rouge ?? 0} critiques · 🟠 ${kpis?.nb_alertes_ambre ?? 0} attention`}
                    note={kpis?.top_contributeurs ?? "Domaines les plus actifs."}
                    accentColor="#0078d4"
                    headerBg="#0078d4"
                  />
                  {/* Prédiction J+7 */}
                  <KPITransversalCard
                    value={data?.predictions_j7?.[0]?.valeur != null
                      ? `${data.predictions_j7[0].valeur > 0 ? "+" : ""}${data.predictions_j7[0].valeur.toFixed(1)}%`
                      : "—"}
                    label="Prédiction J+7"
                    sublabel={`Tendance ${data?.predictions_j7?.[0]?.domaine ?? ""}`}
                    note="Prévision ML à 7 jours sur l'évolution des coûts IT. En surimpression sur le budget."
                    accentColor="#6b52ae"
                    headerBg="#6b52ae"
                    icon={<span>⚡</span>}
                  />
                </div>
              )}
            </section>

            {/* ── Point d'attention + Prédictions ── */}
            {data && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {data.point_attention ? (
                  <AttentionBanner
                    titre={`POINT D'ATTENTION DIRECTION — ${data.point_attention.domaine.toUpperCase()}`}
                    description={data.point_attention.description}
                    action={data.point_attention.action}
                    rag={data.point_attention.rag}
                  />
                ) : (
                  <div className="bg-[#f0faf0] border border-[#107c10] rounded-sm px-4 py-3 flex items-center gap-2">
                    <span className="text-[#107c10] font-bold text-sm">✓ Aucun point d'attention critique</span>
                  </div>
                )}

                <PredictionsBand predictions={data.predictions_j7 ?? []} />
              </div>
            )}

            {/* ── Bandeau navigation ── */}
            <div className="bg-[#fffbe6] border border-[#e8c84a] rounded-sm px-4 py-3 flex items-start gap-2">
              <span className="text-base mt-0.5">💡</span>
              <p className="text-xs text-[#605e5c] leading-relaxed">
                <span className="font-semibold text-[#252423]">NAVIGATION :</span>
                {" "}Cliquez sur un domaine <span className="text-[#e66c37]">🟠</span> ou <span className="text-[#d13438]">🔴</span> dans le scorecard pour accéder directement à la page de détail correspondante. Utilisez le filtre Période (en haut à droite) pour comparer les mois.
              </p>
            </div>

          </main>

          {/* ── Footer ── */}
          <footer className="border-t border-[#e1dfdd] bg-white py-3 px-6 mt-4">
            <div className="max-w-[1600px] mx-auto flex items-center justify-between text-xs text-[#605e5c]">
              <div className="flex items-center gap-2">
                <span>PFE 2025 — Dashboard DSI</span>
                <span>|</span>
                <span>Page 1 sur 9</span>
                <span>|</span>
                <span>Vue Executive 360°</span>
              </div>
              <span>Màj : {data?.timestamp ? format(new Date(data.timestamp), "MMM yyyy", { locale: fr }) : "—"}</span>
            </div>
          </footer>
        </div>
      </PageWrapper>
    </ProtectedRoute>
  )
}