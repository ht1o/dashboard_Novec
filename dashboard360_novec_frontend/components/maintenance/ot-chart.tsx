"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from "recharts"
import { Wrench } from "lucide-react"

interface OtPoint { month: string; ot_preventif: number; ot_correctif: number }

export function OtChart({ data }: { data: OtPoint[] }) {
  return (
    <Card className="bg-white border border-[#e1dfdd] h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-[#252423] flex items-center gap-2">
          <Wrench className="h-4 w-4 text-[#118dff]" />
          Ordres de Travail — Préventif vs Correctif (13 mois)
        </CardTitle>
        <div className="flex gap-4 text-xs text-[#605e5c] mt-1">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-[#107c10] inline-block" />Préventif</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-[#d13438] inline-block" />Correctif</span>
        </div>
      </CardHeader>
      <CardContent className="h-[250px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 10, right: 10, left: -15, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e1dfdd" vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#605e5c" }}
              tickLine={false} axisLine={{ stroke: "#e1dfdd" }}
              angle={-40} textAnchor="end" height={40} />
            <YAxis tick={{ fontSize: 10, fill: "#605e5c" }} tickLine={false} axisLine={false} allowDecimals={false} />
            <Tooltip
              contentStyle={{ backgroundColor: "#fff", border: "1px solid #e1dfdd", borderRadius: "4px", fontSize: "12px" }}
              formatter={(v, name) => [
                typeof v === "number" ? v : String(v),
                name === "ot_preventif" ? "Préventif" : "Correctif",
              ]}
            />
            <Bar dataKey="ot_preventif" stackId="a" fill="#107c10" name="ot_preventif" />
            <Bar dataKey="ot_correctif" stackId="a" fill="#d13438" name="ot_correctif" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}