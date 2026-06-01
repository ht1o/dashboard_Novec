"use client"

import { cn } from "@/lib/utils"
import { Info } from "lucide-react"

interface KPITransversalCardProps {
  value: string
  label: string
  sublabel?: string
  note?: string
  statusLabel?: string
  statusColor?: string
  accentColor: string        // ex: "#107c10"
  headerBg: string           // ex: "#107c10"
  icon?: React.ReactNode
}

export function KPITransversalCard({
  value, label, sublabel, note, statusLabel, statusColor,
  accentColor, headerBg, icon,
}: KPITransversalCardProps) {
  return (
    <div className="bg-white border border-[#e1dfdd] rounded-sm overflow-hidden flex flex-col">
      {/* Barre couleur top */}
      <div className="h-1.5 w-full" style={{ backgroundColor: headerBg }} />
      <div className="p-4 flex-1 flex flex-col">
        <div className="flex items-start gap-2">
          {icon && <span className="text-xl mt-0.5">{icon}</span>}
          <p className="text-4xl font-bold leading-none" style={{ color: accentColor }}>{value}</p>
        </div>
        <p className="text-sm font-semibold text-[#252423] mt-2">{label}</p>
        {sublabel && <p className="text-xs text-[#605e5c] mt-0.5">{sublabel}</p>}
        {statusLabel && (
          <div className="flex items-center gap-1.5 mt-2">
            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: statusColor ?? accentColor }} />
            <span className="text-xs text-[#605e5c]">{statusLabel}</span>
          </div>
        )}
        {note && (
          <div className="flex items-start gap-1 mt-3 pt-2 border-t border-[#f3f2f1]">
            <Info className="h-3 w-3 text-[#605e5c] mt-0.5 shrink-0" />
            <p className="text-xs text-[#605e5c] leading-tight">{note}</p>
          </div>
        )}
      </div>
    </div>
  )
}