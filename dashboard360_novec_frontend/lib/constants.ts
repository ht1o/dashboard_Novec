export const RAG_COLORS = {
  VERT:  { bg: '#dcfce7', text: '#166534', border: '#86efac', dot: '#22c55e' },
  AMBRE: { bg: '#fef9c3', text: '#854d0e', border: '#fde047', dot: '#eab308' },
  ROUGE: { bg: '#fee2e2', text: '#991b1b', border: '#fca5a5', dot: '#ef4444' },
} as const

export type RAGStatus = 'ROUGE' | 'AMBRE' | 'VERT'

export const ROLE_PAGES: Record<string, string[]> = {
  executive:        ['executive'],
  dsi:              ['executive', 'infrastructure', 'itsm', 'cyber', 'apps', 'itam', 'parc_auto', 'maintenance', 'finance', 'alerts'],
  cdg_it:           ['finance'],
  manager_infra:    ['infrastructure', 'itam'],
  manager_rssi:     ['cyber', 'infrastructure'],
  manager_sd:       ['itsm'],
  manager_apps:     ['apps'],
  manager_facility: ['parc_auto', 'maintenance'],
  operationnel:     ['alerts'],
  auditeur:         ['executive', 'infrastructure', 'itsm', 'cyber', 'apps', 'itam', 'parc_auto', 'maintenance', 'finance', 'alerts'],
}

export const NAV_ITEMS = [
  { key: 'executive',     label: 'Executive 360°',     href: '/executive',       icon: 'LayoutDashboard' },
  { key: 'infrastructure', label: 'Infrastructure IT',  href: '/infrastructure',  icon: 'Server' },
  { key: 'cyber',         label: 'Cybersécurité',       href: '/cybersec',        icon: 'Shield' },
  { key: 'itsm',          label: 'Service Desk',        href: '/servicedesk',     icon: 'Headphones' },
  { key: 'apps',          label: 'Applications & BI',   href: '/applications-BI', icon: 'AppWindow' },
  { key: 'itam',          label: 'Parc Informatique',   href: '/itam',            icon: 'Monitor' },
  { key: 'parc_auto',     label: 'Parc Automobile',     href: '/parc-auto',       icon: 'Car' },
  { key: 'maintenance',   label: 'Maintenance',         href: '/maintenance',     icon: 'Wrench' },
  { key: 'finance',       label: 'Gouvernance & Budget', href: '/gouvernance',    icon: 'BarChart3' },
  { key: 'alerts',        label: 'Alertes',             href: '/alerts',          icon: 'Bell' },
]