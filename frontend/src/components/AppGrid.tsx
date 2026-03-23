import { AppCard } from './AppCard'
import type { AppItem } from '../types'

interface Props {
  apps: AppItem[]
  search: string
  activeCategory: string
}

export function AppGrid({ apps, search, activeCategory }: Props) {
  const q = search.toLowerCase().trim()

  const visible = apps.filter((a) => {
    if (activeCategory === 'Available') { if (a.status !== 'RUNNING') return false }
    else if (activeCategory !== 'All' && a.category !== activeCategory) return false
    if (q && !a.display_name.toLowerCase().includes(q) && !a.description.toLowerCase().includes(q)) return false
    return true
  })

  if (visible.length === 0) {
    return (
      <div
        style={{
          padding: '48px 24px',
          textAlign: 'center',
          color: 'var(--text-muted)',
          fontSize: '14px',
        }}
      >
        No apps are available for your account. Contact your workspace admin to request access.
      </div>
    )
  }

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
        gap: '12px',
      }}
    >
      {visible.map((a) => (
        <AppCard key={a.name} app={a} />
      ))}
    </div>
  )
}
