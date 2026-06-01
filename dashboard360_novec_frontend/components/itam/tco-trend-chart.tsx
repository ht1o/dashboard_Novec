"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from "recharts"
import { formatMAD } from "@/lib/utils"

interface TcoPt { month: string; tco_par_poste: number | null }

export function TcoTrendChart({ data }: { data: TcoPt[] }) {
  return (
    <Card className="bg-white border border-[#e1dfdd] h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-[#252423]">
          TCO Moyen / Poste — Évolution 13 mois
        </CardTitle>
      </CardHeader>
      <CardContent className="h-[240px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 10, left: 10, bottom: 30 }}>
            <defs>
              <linearGradient id="tcoGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#6b52ae" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#6b52ae" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e1dfdd" vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#605e5c" }}
              tickLine={false} axisLine={{ stroke: "#e1dfdd" }}
              angle={-40} textAnchor="end" height={40} />
            <YAxis tick={{ fontSize: 10, fill: "#605e5c" }} tickLine={false} axisLine={false}
              tickFormatter={v => `${(v / 1000).toFixed(0)}K`} />
            <Tooltip
              contentStyle={{ backgroundColor: "#fff", border: "1px solid #e1dfdd", borderRadius: "4px", fontSize: "12px" }}
              formatter={(v) => [typeof v === "number" ? formatMAD(v) : String(v), "TCO / poste"]}
            />
            <Area type="monotone" dataKey="tco_par_poste" stroke="#6b52ae" strokeWidth={2}
              fill="url(#tcoGrad)" dot={{ fill: "#6b52ae", r: 3, strokeWidth: 0 }} />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}