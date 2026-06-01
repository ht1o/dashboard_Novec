"use client"

import { Card } from "@/components/ui/card"
import { cn } from "@/lib/utils"

interface MetricCardProps {
  value: string
  label: string
  subtitle: string
  colorClass: string
  bgColorClass: string
}

export function MetricCard({
  value,
  label,
  subtitle,
  colorClass,
  bgColorClass,
}: MetricCardProps) {
  return (
    <Card
      className={cn(
        "relative overflow-hidden border-t-4 p-4 transition-all duration-200 hover:shadow-lg",
        bgColorClass
      )}
    >
      <div className="flex flex-col gap-1">
        <span className={cn("text-3xl font-bold tracking-tight", colorClass)}>
          {value}
        </span>
        <span className="text-sm font-medium text-foreground">{label}</span>
        <span className="text-xs text-muted-foreground">{subtitle}</span>
      </div>
    </Card>
  )
}
