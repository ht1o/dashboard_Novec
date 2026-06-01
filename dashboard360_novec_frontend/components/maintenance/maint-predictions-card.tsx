"use client"

import { Brain } from "lucide-react"
import { RAG_COLORS } from "@/lib/constants"
import type { RAGStatus } from "@/types/api"

interface MaintPred {
  label: string
  value: string
  note: string
  rag: string
  date_m3: string
}

export function MaintPredictionsCard({ predictions }: { predictions: MaintPred[] }) {
  return (
    <div className="bg-white border-2 border-[#6b52ae] rounded-sm p-4">
      <div className="flex items-center gap-2 text-[#6b52ae] font-bold text-sm mb-4">
        <Brain className="h-4 w-4" />
        Prédictions Prophet — M+3
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {predictions.map((p, i) => {
          const rag    = p.rag?.toUpperCase() as RAGStatus
          const colors = RAG_COLORS[rag] ?? RAG_COLORS.AMBRE
          return (
            <div key={i} className="rounded-sm p-3"
              style={{ backgroundColor: colors.bg, border: `1px solid ${colors.border}` }}>
              <p className="text-xs font-semibold mb-1" style={{ color: colors.text }}>{p.label}</p>
              <p className="text-2xl font-bold" style={{ color: colors.text }}>{p.value}</p>
              <p className="text-xs mt-1" style={{ color: colors.text }}>Horizon : {p.date_m3}</p>
              <p className="text-xs text-[#605e5c] mt-1 leading-tight">{p.note}</p>
            </div>
          )
        })}
      </div>
    </div>
  )
}