import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import { RAG_COLORS, type RAGStatus } from "./constants"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function getRAGColor(status: string | null | undefined) {
  if (!status) return RAG_COLORS.AMBRE
  const s = status.toUpperCase()
  if (s === 'ROUGE' || s === 'RED') return RAG_COLORS.ROUGE
  if (s === 'AMBRE' || s === 'AMBER' || s === 'ORANGE') return RAG_COLORS.AMBRE
  return RAG_COLORS.VERT
}

export function getRAGFromForecast(kpi: string | null, yhat: number, statut_rag?: string): RAGStatus {
  if (statut_rag) return statut_rag.toUpperCase() as RAGStatus
  if (kpi?.includes('Pct') && yhat > 85) return 'ROUGE'
  if (kpi?.includes('Pct') && yhat > 70) return 'AMBRE'
  return 'VERT'
}

export function getForecastInsight(predictionIa: { kpi?: string | null; date_alerte?: string | null; rag?: string | null; risk_score?: number | null } | null) {
  if (!predictionIa) return { text: 'Aucune alerte prévue', rag: 'VERT' as RAGStatus }
  const days = predictionIa.date_alerte
    ? Math.round((new Date(predictionIa.date_alerte).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
    : null
  const rag = predictionIa.rag?.toUpperCase() as RAGStatus
  if (rag === 'ROUGE') {
    return {
      text: `${predictionIa.kpi?.replace(/_/g, ' ')} critique${days ? ` dans ~${days} j` : ''}`,
      rag: 'ROUGE' as RAGStatus,
      confidence: predictionIa.risk_score ? `${Math.round(predictionIa.risk_score * 100)}%` : null,
    }
  }
  return { text: `${predictionIa.kpi ?? 'KPI'} stable sur l'horizon prévu`, rag: 'VERT' as RAGStatus }
}

export function formatMAD(value: number | null | undefined): string {
  if (value == null) return '—'
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M MAD`
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K MAD`
  return `${value} MAD`
}

export function formatPercent(value: number | null | undefined, showSign = false): string {
  if (value == null) return '—'
  const sign = showSign && value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

export function getRechartsColor(rag: string): string {
  const colors = RAG_COLORS[rag as RAGStatus]
  return colors?.dot ?? '#0ea5e9'
}