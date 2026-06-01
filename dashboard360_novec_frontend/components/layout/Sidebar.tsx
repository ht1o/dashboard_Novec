'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import { ROLE_PAGES, NAV_ITEMS } from '@/lib/constants'
import { useAuth } from '@/hooks/useAuth'
import {
  LayoutDashboard, Server, Shield, Headphones, AppWindow,
  Monitor, Car, Wrench, BarChart3, Bell, LogOut, Activity,
} from 'lucide-react'

const ICONS: Record<string, React.ElementType> = {
  LayoutDashboard, Server, Shield, Headphones, AppWindow,
  Monitor, Car, Wrench, BarChart3, Bell,
}

export function Sidebar() {
  const pathname = usePathname()
  const { user, logout } = useAuth()
  const role = user?.role ?? ''
  const allowed = ROLE_PAGES[role] ?? []

  const visibleItems = NAV_ITEMS.filter(item => allowed.includes(item.key))

  return (
    <aside className="w-64 min-h-screen bg-[#1e293b] border-r border-slate-700 flex flex-col">
      {/* Logo */}
      <div className="px-5 py-4 border-b border-slate-700 flex items-center gap-3">
        <div className="w-9 h-9 bg-sky-500 rounded-lg flex items-center justify-center">
          <Activity className="w-5 h-5 text-white" />
        </div>
        <div>
          <p className="text-sm font-bold text-slate-100">Dashboard 360°</p>
          <p className="text-xs text-slate-400">Novec — DSI</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {visibleItems.map(item => {
          const Icon = ICONS[item.icon] ?? LayoutDashboard
          const active = pathname.startsWith(item.href)
          return (
            <Link
              key={item.key}
              href={item.href}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                active
                  ? 'bg-sky-500/20 text-sky-400 font-medium'
                  : 'text-slate-400 hover:bg-slate-700/50 hover:text-slate-200'
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {item.label}
            </Link>
          )
        })}
      </nav>

      {/* User */}
      <div className="px-4 py-3 border-t border-slate-700">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-slate-200">{user?.username}</p>
            <p className="text-xs text-slate-500 capitalize">{role}</p>
          </div>
          <button
            onClick={logout}
            className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-400/10 transition-colors"
            title="Déconnexion"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  )
}