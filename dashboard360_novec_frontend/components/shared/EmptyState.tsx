import { Inbox } from 'lucide-react'

export function EmptyState({ message = 'Aucune donnée disponible' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-3 text-slate-400">
      <Inbox className="w-10 h-10" />
      <p className="text-sm">{message}</p>
    </div>
  )
}