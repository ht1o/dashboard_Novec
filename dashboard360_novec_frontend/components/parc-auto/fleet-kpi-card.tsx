"use client"

import { cn } from "@/lib/utils"

interface FleetKPICardProps {
  value: string
  label: string
  sublabel?: string
  accentColor: string   // ex: "#118dff"
  borderColor: string   // ex: "border-l-[#118dff]"
}

export function FleetKPICard({ value, label, sublabel, accentColor, borderColor }: FleetKPICardProps) {
  return (
    <div className={cn("bg-white border border-[#e1dfdd] border-l-4 rounded-sm p-4 hover:shadow-md transition-all", borderColor)}>
      <p className="text-4xl font-bold leading-tight" style={{ color: accentColor }}>{value}</p>
      <p className="text-sm font-semibold text-[#252423] mt-2">{label}</p>
      {sublabel && <p className="text-xs text-[#605e5c] mt-0.5">{sublabel}</p>}
    </div>
  )
}

