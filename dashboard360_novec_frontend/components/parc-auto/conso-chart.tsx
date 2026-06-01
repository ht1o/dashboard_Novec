"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts"

interface ConsoChartProps {
  data: Array<{ month: string; conso: number | null }>
}

export function ConsoChart({ data }: ConsoChartProps) {
  return (
    <Card className="bg-white border border-[#e1dfdd] h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-[#252423]">
          Conso. L/100km — Évolution 13 mois
        </CardTitle>
      </CardHeader>
      <CardContent className="h-[240px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e1dfdd" vertical={false} />
            <XAxis
              dataKey="month" tick={{ fontSize: 10, fill: "#605e5c" }}
              tickLine={false} axisLine={{ stroke: "#e1dfdd" }}
              angle={-40} textAnchor="end" height={40}
            />
            <YAxis tick={{ fontSize: 10, fill: "#605e5c" }} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{ backgroundColor: "#fff", border: "1px solid #e1dfdd", borderRadius: "4px", fontSize: "12px" }}
              formatter={(v) => [typeof v === "number" ? `${v.toFixed(1)} L/100` : String(v), "Consommation"]}
            />
            <Line type="monotone" dataKey="conso" stroke="#6b52ae" strokeWidth={2}
              dot={{ fill: "#6b52ae", r: 3, strokeWidth: 0 }}
              activeDot={{ r: 5, fill: "#6b52ae", stroke: "#fff", strokeWidth: 2 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}