'use client'

interface PredictionCardProps {
  value: string | number
  label: string
  subtext?: string
}

export function PredictionCard({ value, label, subtext }: PredictionCardProps) {
  return (
    <div className="p-6 bg-gradient-to-r from-purple-600 to-purple-700 text-white rounded-md shadow-sm hover:shadow-md transition-shadow">
      <div className="text-3xl font-bold mb-2">{value}</div>
      <div className="text-sm font-semibold mb-2">{label}</div>
      {subtext && <div className="text-xs opacity-90">{subtext}</div>}
    </div>
  )
}
