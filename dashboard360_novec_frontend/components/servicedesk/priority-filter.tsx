"use client"

import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuCheckboxItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Filter, ChevronDown } from "lucide-react"

interface PriorityFilterProps {
  selectedPriorities: string[]
  onSelectionChange: (priorities: string[]) => void
}

const priorities = [
  { id: "P1", label: "P1 Critique", color: "#d13438" },
  { id: "P2", label: "P2 Urgent",   color: "#118dff" },
  { id: "P3", label: "P3 Normal",   color: "#00b7c3" },
]

export function PriorityFilter({ selectedPriorities, onSelectionChange }: PriorityFilterProps) {
  const toggle = (id: string) => {
    if (selectedPriorities.includes(id)) {
      if (selectedPriorities.length > 1) onSelectionChange(selectedPriorities.filter(p => p !== id))
    } else {
      onSelectionChange([...selectedPriorities, id])
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button className="bg-[#118dff] hover:bg-[#0078d4] text-white gap-2 text-sm">
          <Filter className="h-4 w-4" />
          Priorité P1/P2/P3
          <ChevronDown className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48 bg-white border-[#e1dfdd]">
        {priorities.map(p => (
          <DropdownMenuCheckboxItem
            key={p.id}
            checked={selectedPriorities.includes(p.id)}
            onCheckedChange={() => toggle(p.id)}
            className="text-[#252423] hover:bg-[#f3f2f1]"
          >
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: p.color }} />
              {p.label}
            </div>
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}