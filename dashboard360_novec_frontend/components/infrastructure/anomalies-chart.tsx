"use client"

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts"

interface AnomalyData {
  week: string
  count: number
}

interface AnomaliesChartProps {
  data: AnomalyData[]
}

export function AnomaliesChart({ data }: AnomaliesChartProps) {
  const maxValue = Math.max(...data.map((d) => d.count), 1)

  return (
    <div className="h-[200px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e1dfdd" vertical={false} />
          <XAxis
            dataKey="week"
            tick={{ fontSize: 9, fill: "#605e5c" }}
            tickLine={false}
            axisLine={{ stroke: "#e1dfdd" }}
            angle={-20}
            textAnchor="end"
            height={40}
          />
          <YAxis
            tick={{ fontSize: 10, fill: "#605e5c" }}
            tickLine={false}
            axisLine={false}
            allowDecimals={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#ffffff",
              border: "1px solid #e1dfdd",
              borderRadius: "4px",
              boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
              fontSize: "12px",
            }}
            formatter={(value: any) => [value, "Anomalies"]}
            cursor={{ fill: "rgba(0,0,0,0.05)" }}
          />
          <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={35}>
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.count === maxValue && entry.count > 0 ? "#d13438" : "#e66c37"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
