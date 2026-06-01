"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

interface TcoPoint {
  date: string
  tco: number | null
  rag: string
}

interface TcoBarCardProps {
  points: TcoPoint[]
}

const RAG_COLOR: Record<string, string> = {
  VERT:  "#107c10",
  AMBRE: "#e66c37",
  ROUGE: "#d13438",
}

function monthLabel(dateStr: string): string {
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString("fr-FR", { month: "short", year: "2-digit" }).replace(" ", "'")
  } catch { return dateStr.slice(0, 7) }
}

export function TcoBarCard({ points }: TcoBarCardProps) {
  const maxTco = Math.max(...points.map(p => p.tco ?? 0), 1)

  return (
    <Card className="bg-white border border-[#e1dfdd] h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-[#252423]">
          TCO moyen / véhicule (MAD) — Points clés :
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-end gap-4 pt-2">
          {points.map((p, i) => {
            const pct  = ((p.tco ?? 0) / maxTco) * 100
            const color = RAG_COLOR[p.rag?.toUpperCase()] ?? "#118dff"
            return (
              <div key={i} className="flex flex-col items-center gap-1 flex-1">
                <span className="text-xs font-semibold text-[#252423]">
                  {p.tco != null ? `${(p.tco / 1000).toFixed(0)}K` : "—"}
                </span>
                <div className="w-full h-16 bg-[#f3f2f1] rounded-sm overflow-hidden flex items-end">
                  <div
                    className="w-full rounded-sm transition-all duration-700"
                    style={{ height: `${pct}%`, backgroundColor: color }}
                  />
                </div>
                <span className="text-xs text-[#605e5c] text-center">{monthLabel(p.date)}</span>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}