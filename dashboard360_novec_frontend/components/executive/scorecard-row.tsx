"use client"

import { useRouter } from "next/navigation"
import { cn } from "@/lib/utils"
import { NAV_ITEMS } from "@/lib/constants"

interface ScorecardItemProps {
  domainKey: string
  label: string
  rag: string
  kpiLabel: string
  kpiValue: number | null
  kpiUnit: string
  action: { titre: string; action: string; rag: string } | null
}

const RAG_DOT: Record<string, string> = {
  VERT:  "bg-[#107c10]",
  AMBRE: "bg-[#e66c37]",
  ROUGE: "bg-[#d13438]",
}
const RAG_BORDER: Record<string, string> = {
  VERT:  "border-l-[#107c10]",
  AMBRE: "border-l-[#e66c37]",
  ROUGE: "border-l-[#d13438]",
}
const ACTION_STYLE: Record<string, string> = {
  VERT:  "border border-[#107c10] text-[#107c10] bg-[#e6f4e6]",
  AMBRE: "border border-[#e66c37] text-[#e66c37] bg-[#fff4ec]",
  ROUGE: "border border-[#d13438] text-[#d13438] bg-[#fef3f2]",
}

export function ScorecardItem({ domainKey, label, rag, kpiLabel, kpiValue, kpiUnit, action }: ScorecardItemProps) {
  const router = useRouter()
  const navItem = NAV_ITEMS.find(n => n.key === domainKey)
  const ragUpper = rag?.toUpperCase() ?? "AMBRE"

  const handleClick = () => {
    if (navItem) router.push(navItem.href)
  }

  return (
    <div
      onClick={handleClick}
      className={cn(
        "flex items-center justify-between bg-white border border-[#e1dfdd] border-l-4 rounded-sm p-3 cursor-pointer hover:shadow-md transition-all duration-150 group",
        RAG_BORDER[ragUpper] ?? "border-l-[#e66c37]"
      )}
    >
      <div className="flex items-center gap-3 min-w-0">
        {/* RAG dot */}
        <span className={cn("w-4 h-4 rounded-full flex-shrink-0", RAG_DOT[ragUpper] ?? "bg-[#e66c37]")} />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[#252423] group-hover:text-[#0078d4] transition-colors truncate">{label}</p>
          <p className="text-xs text-[#605e5c] truncate">
            {kpiLabel}{kpiValue != null ? ` ${kpiValue}${kpiUnit}` : ""}
          </p>
        </div>
      </div>
      {/* Action recommandée */}
      {action && (
        <div className={cn("ml-3 flex-shrink-0 max-w-[160px] text-xs font-medium px-2 py-1 rounded text-center leading-tight", ACTION_STYLE[action.rag?.toUpperCase()] ?? ACTION_STYLE.AMBRE)}>
          {action.titre}
        </div>
      )}
    </div>
  )
}