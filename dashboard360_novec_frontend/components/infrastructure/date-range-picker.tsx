"use client"

import { Calendar } from "lucide-react"
import { format } from "date-fns"

interface DateRangePickerProps {
  dateRange: { from: Date; to: Date }
  onDateRangeChange: (range: { from: Date; to: Date }) => void
}

export function DateRangePicker({
  dateRange,
  onDateRangeChange,
}: DateRangePickerProps) {
  return (
    <div className="flex items-center gap-2 bg-card text-card-foreground rounded-lg px-3 py-1.5 border shadow-sm">
      <Calendar className="h-4 w-4 text-muted-foreground" />
      <input
        type="date"
        value={format(dateRange.from, "yyyy-MM-dd")}
        onChange={(e) =>
          onDateRangeChange({ ...dateRange, from: new Date(e.target.value) })
        }
        className="bg-transparent text-sm border-none outline-none w-28 cursor-pointer"
      />
      <span className="text-muted-foreground">→</span>
      <input
        type="date"
        value={format(dateRange.to, "yyyy-MM-dd")}
        onChange={(e) =>
          onDateRangeChange({ ...dateRange, to: new Date(e.target.value) })
        }
        className="bg-transparent text-sm border-none outline-none w-28 cursor-pointer"
      />
    </div>
  )
}
