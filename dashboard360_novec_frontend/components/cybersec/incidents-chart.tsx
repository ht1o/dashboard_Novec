'use client'

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

interface IncidentsChartProps {
  data: Array<{
    month: string
    incidents: number
  }>
}

export function IncidentsChart({ data }: IncidentsChartProps) {
  return (
    <div className="w-full h-80 bg-white p-6 rounded-md shadow-sm">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">Incidents Critiques / mois</h3>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e1e8ed" />
          <XAxis 
            dataKey="month" 
            tick={{ fontSize: 12 }}
            angle={-45}
            textAnchor="end"
            height={80}
          />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip 
            contentStyle={{ backgroundColor: '#fff', border: '1px solid #ccc' }}
          />
          <Bar 
            dataKey="incidents" 
            fill="#d13438"
            radius={[4, 4, 0, 0]}
            name="Incidents Critiques"
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
