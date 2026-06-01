"use client"

import { Card } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { CheckCircle2, AlertTriangle } from "lucide-react"

interface ServiceKPICardProps {
  value: string | number
  label: string
  sublabel?: string
  variant?: "default" | "success" | "warning" | "danger"
  showCheck?: boolean
  showWarning?: boolean
  className?: string
}

export function ServiceKPICard({ value, label, sublabel, variant = "default", showCheck, showWarning, className }: ServiceKPICardProps) {
  const valueColor = {
    default: "text-[#118dff]",
    success: "text-[#107c10]",
    warning: "text-[#e66c37]",
    danger:  "text-[#d13438]",
  }[variant]

  const borderColor = {
    default: "border-l-[#118dff]",
    success: "border-l-[#107c10]",
    warning: "border-l-[#e66c37]",
    danger:  "border-l-[#d13438]",
  }[variant]

  return (
    <Card className={cn(
      "relative p-4 bg-white border border-[#e1dfdd] border-l-4 transition-all duration-200 hover:shadow-md",
      borderColor, className
    )}>
      <p className={cn("text-3xl font-bold", valueColor)}>{value}</p>
      <p className="text-sm font-medium text-[#252423] mt-1">{label}</p>
      {sublabel && (
        <div className="flex items-center gap-1 text-xs text-[#605e5c] mt-0.5">
          {showCheck   && <CheckCircle2  className="h-3 w-3 text-[#107c10] shrink-0" />}
          {showWarning && <AlertTriangle className="h-3 w-3 text-[#e66c37] shrink-0" />}
          <span>{sublabel}</span>
        </div>
      )}
    </Card>
  )
}