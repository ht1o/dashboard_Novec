"use client"

import { Card } from "@/components/ui/card"
import { Info } from "lucide-react"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface DepartmentData {
  name: string
  roi: number
  projets: number
  csat: number
  budgetPct: number
}

interface DepartmentBreakdownProps {
  data: DepartmentData[]
  title: string
}

export function DepartmentBreakdown({ data, title }: DepartmentBreakdownProps) {
  return (
    <Card className="p-4">
      <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[#12239e]">
        <span className="text-base">📊</span>
        {title}
      </h3>
      <div className="space-y-4">
        {data.map((dept) => {
          const isOverBudget = dept.budgetPct > 100
          const barColor = isOverBudget ? "#d13438" : "#107c10"
          const displayPct = Math.min(dept.budgetPct, 100)

          return (
            <div key={dept.name} className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="font-medium text-foreground">{dept.name}</span>
                <div className="h-2.5 w-48 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${displayPct}%`,
                      backgroundColor: barColor,
                    }}
                  />
                </div>
                <span
                  className="min-w-[48px] text-right text-sm font-semibold"
                  style={{ color: barColor }}
                >
                  {dept.budgetPct.toFixed(0)}%
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span>ROI: {dept.roi.toFixed(2)}%</span>
                <span className="text-muted-foreground">|</span>
                <span>Projets: {dept.projets.toFixed(2)}%</span>
                <span className="text-muted-foreground">|</span>
                <span>CSAT: {dept.csat.toFixed(2)}/5</span>
              </div>
            </div>
          )
        })}
      </div>
      <div className="mt-4 flex items-start gap-2 rounded bg-[#deecf9] p-2 text-xs text-[#0078d4]">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 cursor-help" />
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-xs">
              <p className="text-xs">
                Le pourcentage représente le ratio budget consommé / budget alloué
              </p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <span>
          Barre = % budget consommé. Vert {"<"} 100% (sous budget) - Rouge {">"} 100% (dépassement)
        </span>
      </div>
    </Card>
  )
}
