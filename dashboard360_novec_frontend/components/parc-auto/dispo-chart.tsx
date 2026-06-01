"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts"

interface DispoChartProps {
  data: Array<{ month: string; dispo: number | null }>
}

export function DispoChart({ data }: DispoChartProps) {
  return (
    <Card className="bg-white border border-[#e1dfdd] h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-[#252423]">
          Disponibilité Flotte % — 13 mois
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
            <YAxis
              domain={[85, 97]} tick={{ fontSize: 10, fill: "#605e5c" }}
              tickLine={false} axisLine={false}
            />
            <Tooltip
              contentStyle={{ backgroundColor: "#fff", border: "1px solid #e1dfdd", borderRadius: "4px", fontSize: "12px" }}
              formatter={(v) => [typeof v === "number" ? `${v.toFixed(1)}%` : String(v), "Disponibilité"]}
            />
            <Line type="monotone" dataKey="dispo" stroke="#00b7c3" strokeWidth={2}
              dot={{ fill: "#00b7c3", r: 3, strokeWidth: 0 }}
              activeDot={{ r: 5, fill: "#00b7c3", stroke: "#fff", strokeWidth: 2 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}