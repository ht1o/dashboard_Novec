"use client"

import { cn } from "@/lib/utils"
import { Info } from "lucide-react"

interface AppKPICardProps {
  value: string
  label: string
  sublabel?: string
  note?: string
  accentColor: string
  borderColor: string
  badge?: React.ReactNode
}

export function AppKPICard({ value, label, sublabel, note, accentColor, borderColor, badge }: AppKPICardProps) {
  return (
    <div className={cn("bg-white border border-[#e1dfdd] border-l-4 rounded-sm p-4 hover:shadow-md transition-all", borderColor)}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-3xl font-bold leading-tight" style={{ color: accentColor }}>{value}</p>
        {badge}
      </div>
      <p className="text-sm font-semibold text-[#252423] mt-2">{label}</p>
      {sublabel && <p className="text-xs text-[#605e5c] mt-0.5">{sublabel}</p>}
      {note && (
        <div className="flex items-start gap-1 mt-2 pt-2 border-t border-[#f3f2f1]">
          <Info className="h-3 w-3 text-[#605e5c] mt-0.5 shrink-0" />
          <p className="text-xs text-[#605e5c] leading-tight">{note}</p>
        </div>
      )}
    </div>
  )
}

