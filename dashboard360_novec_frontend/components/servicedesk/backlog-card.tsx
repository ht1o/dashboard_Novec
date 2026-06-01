"use client"

import { Card } from "@/components/ui/card"
import { AlertTriangle } from "lucide-react"

interface BacklogCardProps {
  value: number
  growth: string
}

export function BacklogCard({ value, growth }: BacklogCardProps) {
  return (
    <Card className="relative p-4 bg-[#fef3f2] border border-[#e1dfdd] border-l-4 border-l-[#d13438] transition-all duration-200 hover:shadow-md">
      <p className="text-3xl font-bold text-[#d13438]">{value.toLocaleString("fr-FR")} tickets</p>
      <p className="text-sm font-medium text-[#252423] mt-1">Backlog Total</p>
      <div className="flex items-center gap-1 text-xs text-[#d13438] mt-0.5">
        <AlertTriangle className="h-3 w-3 shrink-0" />
        <span>{growth}</span>
      </div>
    </Card>
  )
}