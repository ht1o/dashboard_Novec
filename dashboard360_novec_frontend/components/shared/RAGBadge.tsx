import { cn } from '@/lib/utils'
import { RAG_COLORS } from '@/lib/constants'
import type { RAGStatus } from '@/types/api'

interface RAGBadgeProps {
  status: string | null | undefined
  size?: 'sm' | 'md'
  showLabel?: boolean
}

const LABELS: Record<string, string> = { ROUGE: 'Critique', AMBRE: 'Attention', VERT: 'Nominal' }

export function RAGBadge({ status, size = 'md', showLabel = true }: RAGBadgeProps) {
  const s = (status?.toUpperCase() ?? 'AMBRE') as RAGStatus
  const colors = RAG_COLORS[s] ?? RAG_COLORS.AMBRE
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full font-medium',
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'
      )}
      style={{ backgroundColor: colors.bg, color: colors.text, border: `1px solid ${colors.border}` }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: colors.dot }} />
      {showLabel && LABELS[s]}
    </span>
  )
}
