"use client"

import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { LucideIcon } from "lucide-react"

interface KPICardProps {
  title: string
  value: number
  format?: "percent" | "number" | "ms"
  icon: LucideIcon
  subtitle?: string
  accentColor?: string
  bgGradient?: string
  warning?: boolean
}

export function KPICard({
  title,
  value,
  format = "percent",
  icon: Icon,
  subtitle,
  accentColor = "text-primary",
  bgGradient = "from-primary/10 to-primary/5",
  warning = false,
}: KPICardProps) {
  const formatValue = () => {
    switch (format) {
      case "percent":
        return `${value.toFixed(1)}%`
      case "ms":
        return `${value.toFixed(1)} ms`
      default:
        return value.toFixed(0)
    }
  }

  return (
    <Card
      className={cn(
        "relative overflow-hidden transition-all duration-300 hover:shadow-lg hover:scale-[1.02] cursor-pointer border-l-4",
        warning ? "border-l-[#e66c37]" : "border-l-transparent hover:border-l-primary"
      )}
    >
      <div className={cn("absolute inset-0 bg-gradient-to-br opacity-50", bgGradient)} />
      <CardContent className="relative p-4">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <p className={cn("text-3xl font-bold", accentColor)}>{formatValue()}</p>
            <p className="text-sm font-medium text-foreground mt-1">{title}</p>
            {subtitle && (
              <p className="text-xs text-muted-foreground mt-2">{subtitle}</p>
            )}
          </div>
          <div className={cn("p-2 rounded-lg bg-background/80", accentColor)}>
            <Icon className="h-5 w-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
