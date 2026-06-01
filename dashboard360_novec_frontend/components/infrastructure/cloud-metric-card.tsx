"use client"

import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

interface CloudMetricCardProps {
  value: number
  label: string
  format?: "percent" | "ms" | "number"
  color?: string
  showProgress?: boolean
}

export function CloudMetricCard({
  value,
  label,
  format = "number",
  color = "bg-secondary",
  showProgress = false,
}: CloudMetricCardProps) {
  const formatValue = () => {
    switch (format) {
      case "percent":
        return `${value.toFixed(1)}%`
      case "ms":
        return `${value.toFixed(0)} ms`
      default:
        return value.toString()
    }
  }

  return (
    <Card className={cn("text-white overflow-hidden border-0 shadow-lg hover:shadow-xl transition-shadow", color)}>
      <CardContent className="p-4 relative">
        {showProgress && (
          <div className="absolute top-0 left-0 h-1 bg-white/20 w-full">
            <div
              className="h-full bg-white transition-all duration-700 ease-out"
              style={{ width: `${Math.min(value, 100)}%` }}
            />
          </div>
        )}
        <p className="text-3xl font-bold">{formatValue()}</p>
        <p className="text-sm font-medium opacity-90 mt-1">{label}</p>
      </CardContent>
    </Card>
  )
}
