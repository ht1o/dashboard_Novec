'use client'

import { ChevronRight } from 'lucide-react'

interface DateRangeDisplayProps {
  startDate: string
  endDate: string
}

export function DateRangeDisplay({ startDate, endDate }: DateRangeDisplayProps) {
  return (
    <div className="flex items-center gap-2 text-gray-700">
      <span className="text-sm">{startDate}</span>
      <ChevronRight className="w-4 h-4" />
      <span className="text-sm">{endDate}</span>
    </div>
  )
}
