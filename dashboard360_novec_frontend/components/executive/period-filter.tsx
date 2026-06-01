"use client"

import { useState } from "react"
import { ChevronDown, Calendar } from "lucide-react"
import {
  DropdownMenu, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"

const PERIODS = [
  { label: "6 derniers mois", from: "2025-11-01", to: "2026-04-30" },
  { label: "Mai 2025 → Avr 2026", from: "2025-05-01", to: "2026-04-30" },
  { label: "Avr 2025 → Avr 2026", from: "2025-04-01", to: "2026-04-30" },
  { label: "Année 2025",           from: "2025-01-01", to: "2025-12-31" },
]

interface PeriodFilterProps {
  onPeriodChange: (from: string, to: string) => void
}

export function PeriodFilter({ onPeriodChange }: PeriodFilterProps) {
  const [selected, setSelected] = useState(PERIODS[1])

  const handleSelect = (p: typeof PERIODS[0]) => {
    setSelected(p)
    onPeriodChange(p.from, p.to)
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button className="bg-[#0078d4] hover:bg-[#106ebe] text-white gap-2 text-sm font-medium px-4">
          <ChevronDown className="h-4 w-4" />
          Période
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-52 bg-white border-[#e1dfdd]">
        {PERIODS.map(p => (
          <DropdownMenuItem
            key={p.label}
            onClick={() => handleSelect(p)}
            className={`text-sm text-[#252423] hover:bg-[#f3f2f1] cursor-pointer ${selected.label === p.label ? "font-semibold" : ""}`}
          >
            <Calendar className="h-3.5 w-3.5 mr-2 text-[#605e5c]" />
            {p.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}