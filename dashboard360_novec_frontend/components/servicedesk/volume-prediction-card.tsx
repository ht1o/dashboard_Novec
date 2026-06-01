"use client"

import { Card } from "@/components/ui/card"
import { Brain, ArrowRight } from "lucide-react"

interface VolumePredictionCardProps {
  tendancePct: number | null
  points?: Array<{ date: string; yhat: number | null }>
}

export function VolumePredictionCard({ tendancePct, points }: VolumePredictionCardProps) {
  const trend = tendancePct ?? 0
  const nextWeekVol = points?.[6]?.yhat

  const increase = nextWeekVol != null
    ? `+${Math.abs(trend).toFixed(0)}% tickets prévus la semaine prochaine`
    : trend > 0
      ? `+${trend.toFixed(0)}% tickets prévus la semaine prochaine`
      : "Volume stable prévu la semaine prochaine"

  const recommendation = trend > 10
    ? "Surcharge probable → redistribution recommandée"
    : trend > 5
      ? "Légère hausse anticipée — surveiller la capacité"
      : "Capacité suffisante selon les prévisions"

  return (
    <Card className="p-4 bg-[#f3f2f1] border border-[#e1dfdd] border-l-4 border-l-[#6b52ae] transition-all duration-200 hover:shadow-md">
      <div className="flex items-center gap-2 text-[#6b52ae] font-semibold text-sm mb-2">
        <Brain className="h-4 w-4" />
        <span>Prédiction Volume J+7</span>
      </div>
      <div className="text-sm text-[#252423] space-y-1">
        <div className="font-medium">{increase}</div>
        <div className="flex items-start gap-1 text-xs text-[#605e5c]">
          <ArrowRight className="h-3 w-3 mt-0.5 shrink-0" />
          <span>{recommendation}</span>
        </div>
      </div>
    </Card>
  )
}