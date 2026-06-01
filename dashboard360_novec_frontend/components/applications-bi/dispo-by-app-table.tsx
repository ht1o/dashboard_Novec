"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { AppWindow } from "lucide-react"
import type { RAGStatus } from "@/types/api"

interface DispoRow {
  app: string
  dispo: number | null
  tr_ms: number | null
  bugs: number
  rag: RAGStatus
}

interface DispoByAppTableProps {
  rows: DispoRow[]
}

const RAG_COLORS: Record<string, { dot: string; bg: string; text: string }> = {
  VERT:  { dot: "#107c10", bg: "#e6f4e6", text: "#107c10" },
  AMBRE: { dot: "#e66c37", bg: "#fff4ec", text: "#e66c37" },
  ROUGE: { dot: "#d13438", bg: "#fef3f2", text: "#d13438" },
}

export function DispoByAppTable({ rows }: DispoByAppTableProps) {
  return (
    <Card className="bg-white border border-[#e1dfdd] h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-[#252423] flex items-center gap-2">
          <AppWindow className="h-4 w-4 text-[#118dff]" />
          Disponibilité par Application
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {/* Header */}
          <div className="grid grid-cols-12 gap-2 text-xs font-semibold text-[#605e5c] pb-1 border-b border-[#f3f2f1]">
            <span className="col-span-4">Application</span>
            <span className="col-span-3 text-right">Dispo %</span>
            <span className="col-span-2 text-right">Tps Rep.</span>
            <span className="col-span-2 text-right">Bugs</span>
            <span className="col-span-1" />
          </div>
          {rows.map((r) => {
            const rag = r.rag?.toUpperCase() ?? "AMBRE"
            const colors = RAG_COLORS[rag] ?? RAG_COLORS.AMBRE
            return (
              <div key={r.app} className="grid grid-cols-12 gap-2 items-center text-sm py-1.5 hover:bg-[#f9f9f9] rounded transition-colors">
                <span className="col-span-4 font-medium text-[#252423] truncate text-xs">{r.app}</span>
                <div className="col-span-3 flex items-center justify-end gap-1.5">
                  <div className="flex-1 h-1.5 bg-[#f3f2f1] rounded-full overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${Math.min(r.dispo ?? 0, 100)}%`, backgroundColor: colors.dot }} />
                  </div>
                  <span className="text-xs font-semibold" style={{ color: colors.dot }}>{r.dispo?.toFixed(1) ?? "—"}%</span>
                </div>
                <span className="col-span-2 text-right text-xs text-[#605e5c]">
                  {r.tr_ms != null ? `${r.tr_ms.toFixed(0)} ms` : "—"}
                </span>
                <span className="col-span-2 text-right text-xs font-semibold" style={{ color: r.bugs > 0 ? "#d13438" : "#107c10" }}>
                  {r.bugs}
                </span>
                <div className="col-span-1 flex justify-end">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: colors.dot }} />
                </div>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}