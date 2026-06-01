"use client"

import { CheckCircle2 } from "lucide-react"

interface InfoBannerProps {
  children: React.ReactNode
}

export function InfoBanner({ children }: InfoBannerProps) {
  return (
    <div className="flex items-start gap-2 rounded bg-[#fff4ce] px-4 py-3 text-sm text-[#8a6d3b]">
      <span className="shrink-0 text-amber-500">💡</span>
      <div className="flex flex-wrap items-center gap-1">
        {children}
      </div>
    </div>
  )
}

export function GreenCheck() {
  return <CheckCircle2 className="inline h-4 w-4 text-[#107c10]" />
}
