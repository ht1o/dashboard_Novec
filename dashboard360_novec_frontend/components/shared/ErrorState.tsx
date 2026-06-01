import { AlertTriangle } from 'lucide-react'

interface ErrorStateProps {
  message?: string
  onRetry?: () => void
}

export function ErrorState({ message = 'Une erreur est survenue', onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4">
      <AlertTriangle className="w-10 h-10 text-red-400" />
      <p className="text-slate-300 text-sm">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="px-4 py-2 bg-sky-600 hover:bg-sky-500 rounded-lg text-sm text-white transition-colors">
          Réessayer
        </button>
      )}
    </div>
  )
}
