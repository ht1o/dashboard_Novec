"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts"
import { TrendingUp } from "lucide-react"

interface TrendPoint {
  month: string
  dispo: number | null
  bugs: number
  qualite: number | null
}

interface TrendsChartProps {
  data: TrendPoint[]
  selectedApp: string
}

export function TrendsChart({ data, selectedApp }: TrendsChartProps) {
  return (
    <Card className="bg-white border border-[#e1dfdd] h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-[#252423] flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-[#118dff]" />
          Tendances 13 mois{selectedApp ? ` — ${selectedApp}` : " — Toutes applications"}
        </CardTitle>
        <div className="flex items-center gap-4 text-xs text-[#605e5c] mt-1">
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#118dff] inline-block" />Disponibilité %</span>
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#107c10] inline-block" />Qualité données %</span>
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#d13438] inline-block" />Bugs critiques</span>
        </div>
      </CardHeader>
      <CardContent className="h-[260px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e1dfdd" vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#605e5c" }} tickLine={false}
              axisLine={{ stroke: "#e1dfdd" }} angle={-40} textAnchor="end" height={40} />
            <YAxis yAxisId="pct" domain={[85, 100]} tick={{ fontSize: 10, fill: "#605e5c" }}
              tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} />
            <YAxis yAxisId="count" orientation="right" tick={{ fontSize: 10, fill: "#605e5c" }}
              tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{ backgroundColor: "#fff", border: "1px solid #e1dfdd", borderRadius: "4px", fontSize: "12px" }}
              formatter={(v, name) => {
                const val = typeof v === "number" ? v : Number(v)
                if (name === "dispo" || name === "qualite") return [`${val.toFixed(1)}%`, name === "dispo" ? "Disponibilité" : "Qualité données"]
                return [val, "Bugs critiques"]
              }}
            />
            <Line yAxisId="pct"   type="monotone" dataKey="dispo"   stroke="#118dff" strokeWidth={2} dot={false} />
            <Line yAxisId="pct"   type="monotone" dataKey="qualite" stroke="#107c10" strokeWidth={2} dot={false} strokeDasharray="4 3" />
            <Line yAxisId="count" type="monotone" dataKey="bugs"    stroke="#d13438" strokeWidth={2} dot={{ r: 3, fill: "#d13438", strokeWidth: 0 }} />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}