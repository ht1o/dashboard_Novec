'use client'

import { AlertCircle, Check, TrendingDown } from 'lucide-react'

interface SecurityKPICardProps {
  value: string | number
  label: string
  info?: string
  variant?: 'default' | 'success' | 'warning' | 'danger'
  subtext?: string
  trend?: number
}

export function SecurityKPICard({
  value,
  label,
  info,
  variant = 'default',
  subtext,
  trend,
}: SecurityKPICardProps) {
  const colorMap = {
    default: 'border-l-4 border-l-blue-500 bg-white',
    success: 'border-l-4 border-l-green-500 bg-white',
    warning: 'border-l-4 border-l-amber-500 bg-white',
    danger: 'border-l-4 border-l-red-500 bg-white',
  }

  const textColorMap = {
    default: 'text-blue-600',
    success: 'text-green-600',
    warning: 'text-amber-600',
    danger: 'text-red-600',
  }

  return (
    <div className={`p-6 rounded-md ${colorMap[variant]} shadow-sm hover:shadow-md transition-shadow`}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className={`text-3xl font-bold ${textColorMap[variant]} mb-1`}>
            {value}
          </div>
          <div className="text-sm font-semibold text-gray-700 mb-2">{label}</div>
          {subtext && <div className="text-xs text-gray-600 mb-3">{subtext}</div>}
        </div>
        {variant === 'success' && <Check className="w-5 h-5 text-green-600 flex-shrink-0" />}
        {variant === 'danger' && <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />}
      </div>
      {info && (
        <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded text-xs text-green-700">
          ℹ️ {info}
        </div>
      )}
      {variant === 'danger' && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded text-xs text-red-700">
          ⚠️ Systemes exposes non corrigies
        </div>
      )}
    </div>
  )
}
