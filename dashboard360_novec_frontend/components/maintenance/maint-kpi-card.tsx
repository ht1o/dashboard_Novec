"use client"

import { cn } from "@/lib/utils"
import { CheckCircle, AlertTriangle, XCircle, TrendingUp, TrendingDown, Minus } from "lucide-react"

const RAG_CFG = {
  VERT:  { border: "border-l-[#107c10]", color: "#107c10", StatusIcon: CheckCircle  },
  AMBRE: { border: "border-l-[#e66c37]", color: "#e66c37", StatusIcon: AlertTriangle },
  ROUGE: { border: "border-l-[#d13438]", color: "#d13438", StatusIcon: XCircle      },
} as const

interface MaintKPICardProps {
  value: string
  label: string
  cible?: string
  sublabel?: string
  rag: string
  delta?: number | null   // variation vs mois précédent
}

export function MaintKPICard({ value, label, cible, sublabel, rag, delta }: MaintKPICardProps) {
  const r   = (rag?.toUpperCase() ?? "AMBRE") as keyof typeof RAG_CFG
  const cfg = RAG_CFG[r] ?? RAG_CFG.AMBRE
  const DeltaIcon = delta == null ? null : delta > 0 ? TrendingUp : delta < 0 ? TrendingDown : Minus
  const deltaColor = delta == null ? "" : delta > 0 ? "text-[#d13438]" : delta < 0 ? "text-[#107c10]" : "text-[#605e5c]"

  return (
    <div className={cn("bg-white border border-[#e1dfdd] border-l-4 rounded-sm p-4 hover:shadow-md transition-all", cfg.border)}>
      <div className="flex items-start justify-between">
        <p className="text-3xl font-bold leading-tight" style={{ color: cfg.color }}>{value}</p>
        <cfg.StatusIcon className="h-4 w-4 mt-1 shrink-0" style={{ color: cfg.color }} />
      </div>
      <p className="text-sm font-semibold text-[#252423] mt-2">{label}</p>
      {cible    && <p className="text-xs text-[#605e5c] mt-0.5">{cible}</p>}
      {sublabel && <p className="text-xs text-[#605e5c] mt-0.5">{sublabel}</p>}
      {delta != null && DeltaIcon && (
        <div className={cn("flex items-center gap-1 text-xs mt-1.5 font-medium", deltaColor)}>
          <DeltaIcon className="h-3 w-3" />
          {delta > 0 ? "+" : ""}{delta.toFixed(1)} pts vs mois préc.
        </div>
      )}
    </div>
  )
}

