"use client"

import { cn } from "@/lib/utils"
import { CheckCircle, AlertTriangle, XCircle } from "lucide-react"

type RagVariant = "VERT" | "AMBRE" | "ROUGE"

const RAG_CONFIG: Record<RagVariant, { border: string; color: string; Icon: React.ElementType }> = {
  VERT:  { border: "border-l-[#107c10]", color: "#107c10", Icon: CheckCircle  },
  AMBRE: { border: "border-l-[#e66c37]", color: "#e66c37", Icon: AlertTriangle },
  ROUGE: { border: "border-l-[#d13438]", color: "#d13438", Icon: XCircle      },
}

interface ITAMKPICardProps {
  value: string
  label: string
  sublabel?: string
  cible?: string
  rag: string
}

export function ITAMKPICard({ value, label, sublabel, cible, rag }: ITAMKPICardProps) {
  const r   = (rag?.toUpperCase() ?? "AMBRE") as RagVariant
  const cfg = RAG_CONFIG[r] ?? RAG_CONFIG.AMBRE

  return (
    <div className={cn("bg-white border border-[#e1dfdd] border-l-4 rounded-sm p-4 hover:shadow-md transition-all", cfg.border)}>
      <div className="flex items-start justify-between">
        <p className="text-3xl font-bold leading-tight" style={{ color: cfg.color }}>{value}</p>
        <cfg.Icon className="h-4 w-4 mt-1 shrink-0" style={{ color: cfg.color }} />
      </div>
      <p className="text-sm font-semibold text-[#252423] mt-2">{label}</p>
      {cible    && <p className="text-xs text-[#605e5c] mt-0.5">{cible}</p>}
      {sublabel && <p className="text-xs text-[#605e5c] mt-0.5">{sublabel}</p>}
    </div>
  )
}

