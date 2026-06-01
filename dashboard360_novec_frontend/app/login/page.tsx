'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { Activity, Eye, EyeOff, Loader2 } from 'lucide-react'
import { ROLE_PAGES } from '@/lib/constants'

const DEMO_USERS = [
  { label: 'DSI (admin)', username: 'admin', password: 'admin' },
  { label: 'Executive', username: 'executive', password: 'executive' },
  { label: 'Manager Infra', username: 'manager', password: 'manager' },
  { label: 'Démo / Auditeur', username: 'demo', password: 'demo' },
]

export default function LoginPage() {
  const router = useRouter()
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const data = await login(username, password)
      const pages = ROLE_PAGES[data.role] ?? []
      const firstPage = pages[0] ? `/${pages[0] === 'cyber' ? 'cybersec' : pages[0] === 'itsm' ? 'servicedesk' : pages[0] === 'finance' ? 'gouvernance' : pages[0] === 'apps' ? 'applications-BI' : pages[0]}` : '/executive'
      router.push(firstPage)
    } catch {
      setError('Identifiants incorrects. Vérifiez votre nom d\'utilisateur et mot de passe.')
    } finally {
      setLoading(false)
    }
  }

  const fillDemo = (u: typeof DEMO_USERS[0]) => {
    setUsername(u.username)
    setPassword(u.password)
  }

  return (
    <div className="min-h-screen bg-[#0f172a] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-sky-500 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Activity className="w-9 h-9 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-slate-100">Dashboard 360°</h1>
          <p className="text-slate-400 text-sm mt-1">Monitoring IT — Novec</p>
        </div>

        {/* Form */}
        <div className="bg-[#1e293b] rounded-2xl border border-slate-700 p-8">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">Nom d'utilisateur</label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="admin"
                autoComplete="username"
                className="w-full bg-[#0f172a] border border-slate-600 rounded-lg px-4 py-2.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 transition-colors text-sm"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">Mot de passe</label>
              <div className="relative">
                <input
                  type={showPwd ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  className="w-full bg-[#0f172a] border border-slate-600 rounded-lg px-4 py-2.5 pr-10 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 transition-colors text-sm"
                  required
                />
                <button type="button" onClick={() => setShowPwd(v => !v)} className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-200">
                  {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-400 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-sky-600 hover:bg-sky-500 disabled:opacity-60 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-lg flex items-center justify-center gap-2 transition-colors text-sm"
            >
              {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> Connexion...</> : 'Se connecter'}
            </button>
          </form>

          {/* Demo users */}
          <div className="mt-6 pt-5 border-t border-slate-700">
            <p className="text-xs text-slate-500 mb-3 text-center">Comptes de démonstration</p>
            <div className="grid grid-cols-2 gap-2">
              {DEMO_USERS.map(u => (
                <button
                  key={u.username}
                  onClick={() => fillDemo(u)}
                  className="px-3 py-2 bg-slate-700/50 hover:bg-slate-700 rounded-lg text-xs text-slate-300 hover:text-slate-100 transition-colors text-left"
                >
                  <span className="font-medium block">{u.label}</span>
                  <span className="text-slate-500">{u.username} / {u.password}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}