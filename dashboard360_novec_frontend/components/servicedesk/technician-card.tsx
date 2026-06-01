"use client"

import { Card } from "@/components/ui/card"

interface TechnicianCardProps {
  name: string
  tickets: number
  load: number
}

export function TechnicianCard({ name, tickets, load }: TechnicianCardProps) {
  const getLoadColor = (load: number) => {
    if (load >= 85) return "#d13438"
    if (load >= 70) return "#e66c37"
    return "#107c10"
  }

  const color = getLoadColor(load)

  return (
    <Card className="p-3 transition-all duration-200 hover:shadow-md">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-semibold text-[#252423]">{name}</span>
        <span className="text-xs text-[#605e5c]">{tickets} tickets</span>
      </div>
      <div className="h-2 bg-[#f3f2f1] rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${Math.min(load, 100)}%`,
            backgroundColor: color,
          }}
        />
      </div>
      <div className="text-xs mt-1" style={{ color }}>
        {load}%
      </div>
    </Card>
  )
}
