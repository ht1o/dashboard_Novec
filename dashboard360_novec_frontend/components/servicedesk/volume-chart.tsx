"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts"

interface VolumeChartProps {
  data: Array<{ month: string; P1: number; P2: number; P3: number }>
  selectedPriorities: string[]
}

export function VolumeChart({ data, selectedPriorities }: VolumeChartProps) {
  return (
    <Card className="h-full bg-white border border-[#e1dfdd]">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-[#252423]">
          Volume Tickets par Priorité — 13 mois
        </CardTitle>
        <div className="flex items-center gap-4 text-xs mt-2 text-[#605e5c]">
          {selectedPriorities.includes("P1") && <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-[#d13438] inline-block" />P1 Critique</span>}
          {selectedPriorities.includes("P2") && <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-[#118dff] inline-block" />P2 Urgent</span>}
          {selectedPriorities.includes("P3") && <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-[#00b7c3] inline-block" />P3 Normal</span>}
        </div>
      </CardHeader>
      <CardContent className="h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e1dfdd" vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#605e5c" }} tickLine={false} axisLine={{ stroke: "#e1dfdd" }} />
            <YAxis tick={{ fontSize: 10, fill: "#605e5c" }} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{ backgroundColor: "#fff", border: "1px solid #e1dfdd", borderRadius: "4px", fontSize: "12px" }}
              formatter={(value, name) => [
                typeof value === "number" ? value.toLocaleString("fr-FR") : String(value),
                name === "P1" ? "P1 Critique" : name === "P2" ? "P2 Urgent" : "P3 Normal",
              ]}
            />
            {selectedPriorities.includes("P3") && <Bar dataKey="P3" stackId="a" fill="#00b7c3" />}
            {selectedPriorities.includes("P2") && <Bar dataKey="P2" stackId="a" fill="#118dff" />}
            {selectedPriorities.includes("P1") && <Bar dataKey="P1" stackId="a" fill="#d13438" radius={[3,3,0,0]} />}
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}