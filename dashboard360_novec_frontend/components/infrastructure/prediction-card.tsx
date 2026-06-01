"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Brain, TrendingUp } from "lucide-react"

interface PredictionCardProps {
  daysUntilFull: number
  confidence: number
}

export function PredictionCard({ daysUntilFull, confidence }: PredictionCardProps) {
  return (
    <Card className="bg-[#12239e] text-white border-0 shadow-lg hover:shadow-xl transition-shadow overflow-hidden relative">
      <div className="absolute top-0 right-0 w-24 h-24 bg-white/5 rounded-full -translate-y-8 translate-x-8" />
      <CardHeader className="pb-1 pt-3 px-4">
        <CardTitle className="text-xs font-medium flex items-center gap-1.5 text-white/80">
          <Brain className="h-3.5 w-3.5" />
          Prédiction IA
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-3">
        <p className="font-semibold text-sm leading-tight">
          Saturation disque<br />
          dans ~{daysUntilFull} jours
        </p>
        <div className="flex items-center gap-1 mt-2">
          <TrendingUp className="h-3 w-3 text-[#00b7c3]" />
          <p className="text-xs text-[#00b7c3]">Confiance : {confidence}%</p>
        </div>
      </CardContent>
    </Card>
  )
}
