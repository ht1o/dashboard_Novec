"use client"

import { Card } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { CheckCircle2, Info } from "lucide-react"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface BudgetKPICardProps {
  value: string
  label: string
  subtitle?: string
  colorClass: string
  tooltip?: string
  showCheck?: boolean
}

export function BudgetKPICard({
  value,
  label,
  subtitle,
  colorClass,
  tooltip,
  showCheck,
}: BudgetKPICardProps) {
  return (
    <Card className="relative overflow-hidden border-l-4 bg-card p-4 transition-all duration-200 hover:shadow-lg" style={{ borderLeftColor: colorClass === "text-[#118dff]" ? "#118dff" : colorClass === "text-[#107c10]" ? "#107c10" : colorClass === "text-[#e66c37]" ? "#e66c37" : "#118dff" }}>
      <div className="flex flex-col gap-1">
        <span className={cn("text-3xl font-bold tracking-tight", colorClass)}>
          {value}
        </span>
        <span className="text-sm font-medium text-foreground">{label}</span>
        {subtitle && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            {showCheck && <CheckCircle2 className="h-3.5 w-3.5 text-[#107c10]" />}
            <span>{subtitle}</span>
          </div>
        )}
      </div>
      {tooltip && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <button className="absolute right-2 top-2 text-muted-foreground hover:text-foreground">
                <Info className="h-4 w-4" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="max-w-xs">
              <p className="text-xs">{tooltip}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
    </Card>
  )
}
