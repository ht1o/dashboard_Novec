"use client"

import { AlertTriangle, Info } from "lucide-react"
import { cn } from "@/lib/utils"

interface AttentionBannerProps {
  titre: string
  description: string
  action: string
  rag: string
}

const STYLE: Record<string, { bg: string; border: string; text: string; Icon: React.ElementType }> = {
  ROUGE: { bg: "bg-[#fef3f2]", border: "border-[#d13438]", text: "text-[#d13438]", Icon: AlertTriangle },
  AMBRE: { bg: "bg-[#fff8f0]", border: "border-[#e66c37]", text: "text-[#e66c37]", Icon: AlertTriangle },
  VERT:  { bg: "bg-[#f0faf0]", border: "border-[#107c10]", text: "text-[#107c10]", Icon: Info },
}

export function AttentionBanner({ titre, description, action, rag }: AttentionBannerProps) {
  const s = STYLE[rag?.toUpperCase()] ?? STYLE.AMBRE
  const { Icon } = s

  return (
    <div className={cn("border rounded-sm p-4", s.bg, s.border)}>
      <div className={cn("flex items-center gap-2 font-bold text-sm mb-2", s.text)}>
        <Icon className="h-4 w-4 shrink-0" />
        {titre}
      </div>
      <p className={cn("text-sm font-medium leading-relaxed", s.text)}>{description}</p>
      {action && <p className="text-xs text-[#605e5c] mt-1">{action}</p>}
    </div>
  )
}