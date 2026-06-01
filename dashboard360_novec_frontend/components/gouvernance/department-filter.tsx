"use client"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ChevronDown, Filter } from "lucide-react"
import { departments, type Department } from "@/lib/gouvernance-data"

interface DepartmentFilterProps {
  selectedDepartments: Department[]
  onSelectionChange: (departments: Department[]) => void
}

export function DepartmentFilter({
  selectedDepartments,
  onSelectionChange,
}: DepartmentFilterProps) {
  const toggleDepartment = (dept: Department) => {
    if (selectedDepartments.includes(dept)) {
      if (selectedDepartments.length > 1) {
        onSelectionChange(selectedDepartments.filter((d) => d !== dept))
      }
    } else {
      onSelectionChange([...selectedDepartments, dept])
    }
  }

  const selectAll = () => {
    onSelectionChange([...departments])
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button className="gap-2 bg-[#118dff] text-white hover:bg-[#0078d4]">
          <Filter className="h-4 w-4" />
          Département
          <ChevronDown className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuCheckboxItem
          checked={selectedDepartments.length === departments.length}
          onCheckedChange={selectAll}
        >
          Toutes directions
        </DropdownMenuCheckboxItem>
        {departments.map((dept) => (
          <DropdownMenuCheckboxItem
            key={dept}
            checked={selectedDepartments.includes(dept)}
            onCheckedChange={() => toggleDepartment(dept)}
          >
            {dept}
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
