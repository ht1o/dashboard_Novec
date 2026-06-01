"use client"

import { Brain, AlertTriangle, CheckCircle } from "lucide-react"
import { format } from "date-fns"
import { fr } from "date-fns/locale"

interface AppPrediction {
  app: string | null
  kpi: string | null
  date_alerte: string | null
  yhat: number | null
  rag: string | null
  risk_score: number | null
}

interface AppPredictionCardProps {
  prediction: AppPrediction | null
}

const RAG_STYLE: Record<string, { border: string; bg: string; text: string; icon: React.ElementType }> = {
  ROUGE: { border: "border-[#d13438]", bg: "bg-[#fef3f2]", text: "text-[#d13438]", icon: AlertTriangle },
  AMBRE: { border: "border-[#e66c37]", bg: "bg-[#fff8f0]", text: "text-[#e66c37]", icon: AlertTriangle },
  VERT:  { border: "border-[#107c10]", bg: "bg-[#f0faf0]", text: "text-[#107c10]", icon: CheckCircle  },
}

export function AppPredictionCard({ prediction }: AppPredictionCardProps) {
  if (!prediction) {
    return (
      <div className="bg-[#f0faf0] border border-[#107c10] rounded-sm p-4 flex items-center gap-3">
        <CheckCircle className="h-5 w-5 text-[#107c10] shrink-0" />
        <p className="text-sm text-[#107c10] font-medium">Aucune alerte applicative prévue sur J+7</p>
      </div>
    )
  }

  const rag = prediction.rag?.toUpperCase() ?? "AMBRE"
  const s   = RAG_STYLE[rag] ?? RAG_STYLE.AMBRE
  const { icon: Icon } = s

  const days = prediction.date_alerte
    ? Math.round((new Date(prediction.date_alerte).getTime() - Date.now()) / 86400000)
    : null

  return (
    <div className={`border-2 rounded-sm p-4 ${s.border} ${s.bg}`}>
      <div className={`flex items-center gap-2 font-bold text-sm mb-3 ${s.text}`}>
        <Brain className="h-4 w-4" />
        Prédiction IA — Alerte Applicative
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div>
          <p className={`text-xl font-bold ${s.text}`}>
            {prediction.app ?? "—"}
          </p>
          <p className="text-xs text-[#605e5c] mt-0.5">Application concernée</p>
        </div>
        <div>
          <p className={`text-xl font-bold ${s.text}`}>
            {prediction.kpi?.replace(/_/g, " ") ?? "—"}
          </p>
          <p className="text-xs text-[#605e5c] mt-0.5">KPI en risque</p>
        </div>
        <div>
          <p className={`text-xl font-bold ${s.text}`}>
            {days != null ? `~J+${days}` : prediction.date_alerte
              ? format(new Date(prediction.date_alerte), "dd MMM", { locale: fr })
              : "—"}
          </p>
          <p className="text-xs text-[#605e5c] mt-0.5">
            Échéance · Score risque : {prediction.risk_score != null ? `${Math.round(prediction.risk_score * 100)}%` : "—"}
          </p>
        </div>
      </div>
    </div>
  )
}