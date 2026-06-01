"use client"

import { Cpu } from "lucide-react"

interface PredictionItem {
  domaine: string
  kpi: string
  valeur: number | null
  rag: string
  date_alerte: string | null
}

interface PredictionsBandProps {
  predictions: PredictionItem[]
}

const RAG_TEXT: Record<string, string> = {
  VERT:  "text-[#107c10]",
  AMBRE: "text-[#e66c37]",
  ROUGE: "text-[#d13438]",
}

function formatPred(p: PredictionItem): string {
  const kpi = p.kpi.replace(/_/g, " ")
  const days = p.date_alerte
    ? Math.round((new Date(p.date_alerte).getTime() - Date.now()) / 86400000)
    : null

  if (p.rag?.toUpperCase() === "ROUGE" && days != null) {
    return `${p.domaine} — ${kpi} : dans ~${days}j`
  }
  if (p.valeur != null) {
    return `${p.domaine} — ${kpi} : ${p.valeur.toFixed(1)}`
  }
  return `${p.domaine} — ${kpi} : stable`
}

export function PredictionsBand({ predictions }: PredictionsBandProps) {
  if (!predictions?.length) return null

  return (
    <div className="bg-[#f5f0ff] border border-[#9d7fea] rounded-sm p-4">
      <div className="flex items-center gap-2 text-[#6b52ae] font-bold text-sm mb-2">
        <Cpu className="h-4 w-4" />
        PRÉDICTIONS J+7 (IA — en surimpression)
      </div>
      <p className="text-sm text-[#252423] leading-relaxed">
        {predictions.map((p, i) => (
          <span key={i}>
            <span className={RAG_TEXT[p.rag?.toUpperCase()] ?? "text-[#252423]"}>
              {formatPred(p)}
            </span>
            {i < predictions.length - 1 && <span className="text-[#605e5c]"> · </span>}
          </span>
        ))}
      </p>
    </div>
  )
}