"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, LabelList } from "recharts"
import { AlertTriangle } from "lucide-react"

interface RuptPt { month: string; ruptures: number }

export function RupturesChart({ data }: { data: RuptPt[] }) {
  const max = Math.max(...data.map(d => d.ruptures), 1)

  return (
    <Card className="bg-white border border-[#e1dfdd] h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-[#252423] flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-[#e66c37]" />
          Ruptures de Stock — 13 mois
        </CardTitle>
        <p className="text-xs text-[#605e5c] mt-0.5">Nombre de ruptures détectées par mois</p>
      </CardHeader>
      <CardContent className="h-[250px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 18, right: 10, left: -15, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e1dfdd" vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#605e5c" }}
              tickLine={false} axisLine={{ stroke: "#e1dfdd" }}
              angle={-40} textAnchor="end" height={40} />
            <YAxis tick={{ fontSize: 10, fill: "#605e5c" }} tickLine={false} axisLine={false} allowDecimals={false} />
            <Tooltip
              contentStyle={{ backgroundColor: "#fff", border: "1px solid #e1dfdd", borderRadius: "4px", fontSize: "12px" }}
              formatter={(v) => [typeof v === "number" ? v : String(v), "Ruptures"]}
            />
            <Bar dataKey="ruptures" radius={[3, 3, 0, 0]} maxBarSize={36}>
              <LabelList dataKey="ruptures" position="top" style={{ fontSize: 10, fill: "#605e5c" }} />
              {data.map((entry, i) => (
                <Cell key={i} fill={
                  entry.ruptures === 0 ? "#107c10"
                  : entry.ruptures === max && max > 0 ? "#d13438"
                  : "#e66c37"
                } />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}