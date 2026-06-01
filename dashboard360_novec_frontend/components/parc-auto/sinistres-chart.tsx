"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LabelList, Cell } from "recharts"
import { AlertTriangle } from "lucide-react"

interface SinistresChartProps {
  data: Array<{ month: string; sinistres: number }>
  picLabel?: string | null
  picValue?: number
}

export function SinistresChart({ data, picLabel, picValue }: SinistresChartProps) {
  const maxVal = Math.max(...data.map(d => d.sinistres), 1)

  return (
    <Card className="bg-white border border-[#e1dfdd] h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-[#e66c37]">
          Sinistres par mois — {picLabel ? `Pic ${picLabel}` : "13 mois"}
        </CardTitle>
      </CardHeader>
      <CardContent className="h-[240px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 20, right: 10, left: -15, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e1dfdd" vertical={false} />
            <XAxis
              dataKey="month" tick={{ fontSize: 10, fill: "#605e5c" }}
              tickLine={false} axisLine={{ stroke: "#e1dfdd" }}
              angle={-40} textAnchor="end" height={40}
            />
            <YAxis tick={{ fontSize: 10, fill: "#605e5c" }} tickLine={false} axisLine={false} allowDecimals={false} />
            <Tooltip
              contentStyle={{ backgroundColor: "#fff", border: "1px solid #e1dfdd", borderRadius: "4px", fontSize: "12px" }}
              formatter={(v) => [typeof v === "number" ? v : String(v), "Sinistres"]}
            />
            <Bar dataKey="sinistres" radius={[3, 3, 0, 0]} maxBarSize={38}>
              <LabelList dataKey="sinistres" position="top" style={{ fontSize: 10, fill: "#605e5c" }} />
              {data.map((entry, i) => (
                <Cell key={i} fill={entry.sinistres === maxVal && entry.sinistres > 0 ? "#d13438" : "#e66c37"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
      {picLabel && picValue != null && (
        <div className="mx-4 mb-3 flex items-center gap-1.5 border border-[#d13438]/40 bg-[#fef3f2] rounded px-3 py-1.5 text-xs text-[#d13438]">
          <AlertTriangle className="h-3 w-3 shrink-0" />
          Pic {picLabel} : {picValue} sinistres — à analyser (météo ? surmenage ?)
        </div>
      )}
    </Card>
  )
}