'use client'

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

interface MFARGPDChartProps {
  data: Array<{
    month: string
    mfa: number
    rgpd: number
  }>
}

export function MFARGPDChart({ data }: MFARGPDChartProps) {
  return (
    <div className="w-full h-80 bg-white p-6 rounded-md shadow-sm">
      <h3 className="text-sm font-semibold text-blue-700 mb-4">MFA Adoption % vs Conformite RGPD/ISO % — Evolution</h3>
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
          <YAxis tick={{ fontSize: 12 }} domain={[75, 100]} />
          <Tooltip 
            formatter={(value) => value.toFixed(1)}
            contentStyle={{ backgroundColor: '#fff', border: '1px solid #ccc' }}
          />
          <Legend />
          <Line 
            type="monotone" 
            dataKey="mfa" 
            stroke="#00b7c3" 
            strokeWidth={2}
            dot={{ fill: '#00b7c3', r: 4 }}
            activeDot={{ r: 6 }}
            name="MFA Adoption (%)"
          />
          <Line 
            type="monotone" 
            dataKey="rgpd" 
            stroke="#118dff" 
            strokeWidth={2}
            dot={{ fill: '#118dff', r: 4 }}
            activeDot={{ r: 6 }}
            name="Conformite RGPD/ISO (%)"
          />
        </LineChart>
      </ResponsiveContainer>
      <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded text-xs text-yellow-700">
        💡 Les deux courbes progressent. La conformite RGPD (95% cible) sera atteinte si la tendance se maintient d&apos;ici 2 mois.
      </div>
    </div>
  )
}
