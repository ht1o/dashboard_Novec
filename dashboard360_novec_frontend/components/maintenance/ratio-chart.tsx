"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts"

interface RatioPoint { month: string; ratio_prev: number | null; taux_real: number | null }

interface RatioChartProps { data: RatioPoint[]; ratioCible: number; tauxCible: number }

export function RatioChart({ data, ratioCible, tauxCible }: RatioChartProps) {
  return (
    <Card className="bg-white border border-[#e1dfdd] h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-[#252423]">
          Ratio Préventif &amp; Taux Réalisation — 13 mois
        </CardTitle>
        <div className="flex gap-4 text-xs text-[#605e5c] mt-1">
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#118dff] inline-block" />Ratio préventif %</span>
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#6b52ae] inline-block" />Taux réalisation %</span>
        </div>
      </CardHeader>
      <CardContent className="h-[250px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 30, left: -10, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e1dfdd" vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#605e5c" }}
              tickLine={false} axisLine={{ stroke: "#e1dfdd" }}
              angle={-40} textAnchor="end" height={40} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "#605e5c" }}
              tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} />
            <Tooltip
              contentStyle={{ backgroundColor: "#fff", border: "1px solid #e1dfdd", borderRadius: "4px", fontSize: "12px" }}
              formatter={(v, name) => [
                typeof v === "number" ? `${v.toFixed(1)}%` : String(v),
                name === "ratio_prev" ? "Ratio préventif" : "Taux réalisation",
              ]}
            />
            <ReferenceLine y={ratioCible} stroke="#118dff" strokeDasharray="4 4"
              label={{ value: `Cible ratio ${ratioCible}%`, fill: "#118dff", fontSize: 9, position: "right" }} />
            <ReferenceLine y={tauxCible} stroke="#6b52ae" strokeDasharray="4 4"
              label={{ value: `Cible taux ${tauxCible}%`, fill: "#6b52ae", fontSize: 9, position: "right" }} />
            <Line type="monotone" dataKey="ratio_prev" stroke="#118dff" strokeWidth={2}
              dot={{ fill: "#118dff", r: 3, strokeWidth: 0 }} connectNulls />
            <Line type="monotone" dataKey="taux_real"  stroke="#6b52ae" strokeWidth={2}
              dot={{ fill: "#6b52ae", r: 3, strokeWidth: 0 }} strokeDasharray="5 3" connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}