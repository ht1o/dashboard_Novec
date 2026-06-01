"use client"

import { cn } from "@/lib/utils"

interface ResourceBarsProps {
  cpu: number
  ram: number
  disk: number
  criticalThreshold?: number
}

export function ResourceBars({
  cpu,
  ram,
  disk,
  criticalThreshold = 90,
}: ResourceBarsProps) {
  const resources = [
    { name: "CPU", value: cpu, color: "#118dff" },
    { name: "RAM", value: ram, color: "#12239e" },
    { name: "Stockage", value: disk, color: "#00b7c3" },
  ]

  return (
    <div className="space-y-4">
      {resources.map((resource) => (
        <div key={resource.name} className="space-y-1.5">
          <div className="flex justify-between items-center text-sm">
            <span className="text-muted-foreground font-medium">{resource.name}</span>
            <span
              className={cn(
                "font-semibold tabular-nums",
                resource.value >= criticalThreshold ? "text-[#d13438]" : "text-foreground"
              )}
            >
              {resource.value.toFixed(0)}%
            </span>
          </div>
          <div className="h-4 bg-muted rounded overflow-hidden relative">
            <div
              className="h-full rounded transition-all duration-700 ease-out relative overflow-hidden"
              style={{
                width: `${Math.min(resource.value, 100)}%`,
                backgroundColor: resource.value >= criticalThreshold ? "#d13438" : resource.color,
              }}
            >
              <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/20 to-white/0 animate-pulse" />
            </div>
            {/* Critical threshold marker */}
            <div
              className="absolute top-0 bottom-0 w-0.5 bg-[#d13438]/50"
              style={{ left: `${criticalThreshold}%` }}
            />
          </div>
        </div>
      ))}
      <p className="text-xs text-[#d13438] flex items-center gap-1 mt-3">
        <span className="w-2 h-0.5 bg-[#d13438]" />
        Seuil critique: {criticalThreshold}%
      </p>
    </div>
  )
}
