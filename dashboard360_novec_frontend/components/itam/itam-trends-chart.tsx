"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts"

interface TrendPoint {
  month: string
  vetuste_pct: number | null
  conformite_licences: number | null
  cmdb_couverture: number | null
  licences_inutilisees: number
}

interface ITAMTrendsChartProps {
  data: TrendPoint[]
}

export function ITAMTrendsChart({ data }: ITAMTrendsChartProps) {
  return (
    <Card className="bg-white border border-[#e1dfdd] h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-[#252423]">
          Indicateurs Parc — Évolution 13 mois
        </CardTitle>
        <div className="flex flex-wrap gap-4 text-xs text-[#605e5c] mt-1">
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#d13438] inline-block" />Vétusté %</span>
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#107c10] inline-block" />Conformité licences %</span>
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#118dff] inline-block" />Couverture CMDB %</span>
        </div>
      </CardHeader>
      <CardContent className="h-[260px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e1dfdd" vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#605e5c" }}
              tickLine={false} axisLine={{ stroke: "#e1dfdd" }}
              angle={-40} textAnchor="end" height={40} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "#605e5c" }}
              tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} />
            <Tooltip
              contentStyle={{ backgroundColor: "#fff", border: "1px solid #e1dfdd", borderRadius: "4px", fontSize: "12px" }}
              formatter={(v, name) => {
                const val = typeof v === "number" ? v : Number(v)
                const labels: Record<string, string> = {
                  vetuste_pct: "Vétusté", conformite_licences: "Conformité licences", cmdb_couverture: "Couverture CMDB",
                }
                return [`${val.toFixed(1)}%`, labels[name as string] ?? String(name)]
              }}
            />
            {/* Seuil alerte vétusté 30% */}
            <ReferenceLine y={30} stroke="#d13438" strokeDasharray="4 4"
              label={{ value: "Seuil vétusté 30%", fill: "#d13438", fontSize: 9, position: "right" }} />
            {/* Cible conformité + CMDB 95% */}
            <ReferenceLine y={95} stroke="#107c10" strokeDasharray="4 4"
              label={{ value: "Cible 95%", fill: "#107c10", fontSize: 9, position: "right" }} />
            <Line type="monotone" dataKey="vetuste_pct"         stroke="#d13438" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="conformite_licences" stroke="#107c10" strokeWidth={2} dot={false} strokeDasharray="5 3" />
            <Line type="monotone" dataKey="cmdb_couverture"     stroke="#118dff" strokeWidth={2} dot={false} strokeDasharray="3 3" />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}