"use client"

interface PredItem {
  label: string
  value: string
  sublabel: string
  note: string
  color: string
}

interface ParcPredictionsCardProps {
  items: PredItem[]
}

export function ParcPredictionsCard({ items }: ParcPredictionsCardProps) {
  return (
    <div className="bg-white border-2 border-[#6b52ae] rounded-sm p-4 h-full">
      <p className="text-sm font-bold text-[#6b52ae] mb-4">Prédictions M+3 (modèle IA)</p>
      <div className="grid grid-cols-3 gap-4">
        {items.map((item, i) => (
          <div key={i}>
            <p className="text-2xl font-bold" style={{ color: item.color }}>{item.value}</p>
            <p className="text-xs font-semibold text-[#252423] mt-1">{item.label}</p>
            <p className="text-xs text-[#605e5c] mt-0.5">{item.sublabel}</p>
            <p className="text-xs mt-1" style={{ color: item.color }}>{item.note}</p>
          </div>
        ))}
      </div>
    </div>
  )
}