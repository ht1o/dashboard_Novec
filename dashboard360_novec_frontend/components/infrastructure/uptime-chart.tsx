"use client"

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts"

interface UptimeData {
  date: string
  fullDate: string
  uptime: number
}

interface UptimeChartProps {
  data: UptimeData[]
}

export function UptimeChart({ data }: UptimeChartProps) {
  const minUptime = Math.min(...data.map((d) => d.uptime), 97)
  const yMin = Math.floor(minUptime - 1)

  return (
    <div className="h-[200px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e1dfdd" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 10, fill: "#605e5c" }}
            tickLine={false}
            axisLine={{ stroke: "#e1dfdd" }}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[yMin, 100]}
            tick={{ fontSize: 10, fill: "#605e5c" }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value) => `${value}%`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#ffffff",
              border: "1px solid #e1dfdd",
              borderRadius: "4px",
              boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
              fontSize: "12px",
            }}
            formatter={(value: any) => [`${value.toFixed(2)}%`, "Uptime"]}
            labelFormatter={(label) => `Date: ${label}`}
          />
          <ReferenceLine
            y={99}
            stroke="#d13438"
            strokeDasharray="5 5"
            strokeWidth={1}
          />
          <Line
            type="monotone"
            dataKey="uptime"
            stroke="#118dff"
            strokeWidth={2}
            dot={{ fill: "#118dff", strokeWidth: 0, r: 3 }}
            activeDot={{ r: 5, fill: "#118dff", stroke: "#ffffff", strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
