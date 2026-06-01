"use client"

import { Calendar, ArrowRight } from "lucide-react"

interface DateRangeDisplayProps {
  startDate: string
  endDate: string
}

export function DateRangeDisplay({ startDate, endDate }: DateRangeDisplayProps) {
  return (
    <div className="flex items-center gap-2 text-sm text-white/90">
      <Calendar className="h-4 w-4" />
      <span>{startDate}</span>
      <ArrowRight className="h-4 w-4" />
      <span>{endDate}</span>
    </div>
  )
}
