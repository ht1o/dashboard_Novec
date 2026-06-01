'use client'

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

interface PhishingChartProps {
  data: Array<{
    month: string
    phishing: number
  }>
}

export function PhishingChart({ data }: PhishingChartProps) {
  return (
    <div className="w-full h-80 bg-white p-6 rounded-md shadow-sm">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">Taux Phishing (%)</h3>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
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
            formatter={(value) => value.toFixed(2)}
            contentStyle={{ backgroundColor: '#fff', border: '1px solid #ccc' }}
          />
          <Line 
            type="monotone" 
            dataKey="phishing" 
            stroke="#e66c37" 
            strokeWidth={2}
            dot={{ fill: '#e66c37', r: 4 }}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>
      <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded text-xs text-green-700">
        ✓ Phishing : -58% sur 1 an [16% → 6.9%]
      </div>
    </div>
  )
}
