'use client'

import { AlertTriangle } from 'lucide-react'
import { useState } from 'react'

export function AlertLevelButton() {
  const [open, setOpen] = useState(false)

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-md font-semibold transition-colors"
      >
        <AlertTriangle className="w-4 h-4" />
        Niveau Alerte
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-48 bg-white border border-gray-200 rounded-md shadow-lg p-4 z-50">
          <div className="text-sm font-semibold text-gray-900 mb-2">Niveau d&apos;alerte actuel</div>
          <div className="text-2xl font-bold text-red-600 mb-3">ÉLEVÉ</div>
          <div className="text-xs text-gray-600 mb-3">
            2 incidents critiques détectés ce mois-ci. Activez les équipes de réponse.
          </div>
          <button
            onClick={() => setOpen(false)}
            className="w-full px-3 py-2 text-xs bg-gray-100 hover:bg-gray-200 rounded text-gray-700 transition-colors"
          >
            Fermer
          </button>
        </div>
      )}
    </div>
  )
}
