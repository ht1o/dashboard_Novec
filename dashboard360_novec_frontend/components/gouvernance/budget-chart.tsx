"use client"

import { Card } from "@/components/ui/card"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"

interface BudgetChartData {
  month: string
  budgetAlloue: number
  budgetConsomme: number
}

interface BudgetChartProps {
  data: BudgetChartData[]
}

export function BudgetChart({ data }: BudgetChartProps) {
  const formatValue = (value: number) => {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
    if (value >= 1000) return `${(value / 1000).toFixed(0)}K`
    return value.toString()
  }

  return (
    <Card className="p-4">
      <div className="mb-4 flex items-center justify-center gap-6">
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 rounded-sm bg-[#12239e]" />
          <span className="text-sm text-muted-foreground">Budget Alloué (MAD)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 rounded-sm bg-[#107c10]" />
          <span className="text-sm text-muted-foreground">Budget Consommé (MAD)</span>
        </div>
      </div>
      <div className="h-[280px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            margin={{ top: 10, right: 10, left: 10, bottom: 10 }}
            barGap={2}
            barCategoryGap="20%"
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e1dfdd" vertical={false} />
            <XAxis
              dataKey="month"
              tick={{ fontSize: 12, fill: "#605e5c" }}
              tickLine={false}
              axisLine={{ stroke: "#e1dfdd" }}
            />
            <YAxis
              tick={{ fontSize: 12, fill: "#605e5c" }}
              tickLine={false}
              axisLine={false}
              tickFormatter={formatValue}
            />
            <Tooltip
              formatter={(value: any) => [
                new Intl.NumberFormat("fr-FR").format(value) + " MAD",
              ]}
              contentStyle={{
                backgroundColor: "#fff",
                border: "1px solid #e1dfdd",
                borderRadius: "4px",
                fontSize: "12px",
              }}
            />
            <Bar
              dataKey="budgetAlloue"
              name="Budget Alloué"
              fill="#12239e"
              radius={[2, 2, 0, 0]}
            />
            <Bar
              dataKey="budgetConsomme"
              name="Budget Consommé"
              fill="#107c10"
              radius={[2, 2, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 flex items-start gap-2 rounded bg-[#fff4ce] p-2 text-xs text-[#8a6d3b]">
        <span className="text-amber-500">💡</span>
        <span>
          Conseil de lecture : Les barres vertes (consommé) restent systématiquement en dessous des barres bleues (alloué) → la DSI maîtrise son enveloppe budgétaire sur l&apos;ensemble de l&apos;année.
        </span>
      </div>
    </Card>
  )
}
