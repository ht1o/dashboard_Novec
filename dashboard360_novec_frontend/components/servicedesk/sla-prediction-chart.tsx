"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts"
import { Brain } from "lucide-react"

interface SLAPredictionChartProps {
  data: Array<{
    week: string
    real: number | null
    predicted: number | null
  }>
}

export function SLAPredictionChart({ data }: SLAPredictionChartProps) {
  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-[#252423]">
          SLA % — 8 sem. + Prédiction J+7
        </CardTitle>
        <div className="flex items-center gap-4 text-xs mt-2">
          <div className="flex items-center gap-1">
            <div className="w-4 h-0.5 bg-[#118dff]" />
            <span>SLA Réel (%)</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-4 h-0.5 bg-[#6b52ae] border-dashed" style={{ borderTop: "2px dashed #6b52ae", height: 0 }} />
            <span>Prédiction J+7 (%)</span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="h-[240px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e1dfdd" vertical={false} />
            <XAxis
              dataKey="week"
              tick={{ fontSize: 11, fill: "#605e5c" }}
              tickLine={false}
              axisLine={{ stroke: "#e1dfdd" }}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "#605e5c" }}
              tickLine={false}
              axisLine={false}
              domain={[92, 98]}
              ticks={[92, 94, 96, 98]}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#fff",
                border: "1px solid #e1dfdd",
                borderRadius: "4px",
                fontSize: "12px",
              }}
              formatter={(value: any, name: any) => [
                value?.toFixed(1) + "%",
                name === "real" ? "SLA Réel" : "Prédiction",
              ]}
            />
            <Line
              type="monotone"
              dataKey="real"
              stroke="#118dff"
              strokeWidth={2}
              dot={{ fill: "#118dff", strokeWidth: 0, r: 4 }}
              connectNulls={false}
            />
            <Line
              type="monotone"
              dataKey="predicted"
              stroke="#6b52ae"
              strokeWidth={2}
              strokeDasharray="5 5"
              dot={{ fill: "#6b52ae", strokeWidth: 0, r: 4 }}
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
        <div className="flex items-start gap-1 text-xs text-[#6b52ae] mt-2 px-2">
          <Brain className="h-3 w-3 mt-0.5 shrink-0" />
          <span>Courbe violette = prédiction ML J+7 en surimpression</span>
        </div>
      </CardContent>
    </Card>
  )
}
