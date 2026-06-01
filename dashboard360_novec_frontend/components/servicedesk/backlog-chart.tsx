"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts"
import { AlertTriangle } from "lucide-react"

interface BacklogChartProps {
  data: Array<{ month: string; value: number }>
}

export function BacklogChart({ data }: BacklogChartProps) {
  return (
    <Card className="h-full bg-white border-2 border-[#d13438]">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold text-[#d13438]">
          <div className="w-3 h-3 rounded-full bg-[#d13438]" />
          Backlog Total — Évolution 13 mois
        </CardTitle>
      </CardHeader>
      <CardContent className="h-[240px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
            <defs>
              <linearGradient id="backlogGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#e66c37" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#e66c37" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e1dfdd" vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 9, fill: "#605e5c" }} tickLine={false} axisLine={{ stroke: "#e1dfdd" }} angle={-40} textAnchor="end" height={38} />
            <YAxis tick={{ fontSize: 10, fill: "#605e5c" }} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{ backgroundColor: "#fff", border: "1px solid #e1dfdd", borderRadius: "4px", fontSize: "12px" }}
              formatter={(value) => [typeof value === "number" ? value + " tickets" : String(value), "Backlog"]}
            />
            <Area type="monotone" dataKey="value" stroke="#e66c37" strokeWidth={2} fill="url(#backlogGradient)" dot={{ fill: "#e66c37", strokeWidth: 0, r: 3 }} />
          </AreaChart>
        </ResponsiveContainer>
        <div className="flex items-start gap-1 text-xs text-[#d13438] mt-2 px-1">
          <AlertTriangle className="h-3 w-3 mt-0.5 shrink-0" />
          <span>Le backlog x8 en 1 an signale un sous-effectif ou une hausse structurelle du volume.</span>
        </div>
      </CardContent>
    </Card>
  )
}