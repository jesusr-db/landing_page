import type { CSSProperties } from 'react'
import type { AppItem } from '../types'

interface Props {
  apps: AppItem[]
  activeCategory: string
  onCategory: (category: string) => void
}

export function CategoryTabs({ apps, activeCategory, onCategory }: Props) {
  const categories = [...new Set(apps.map((a) => a.category))]
  const availableCount = apps.filter((a) => a.status === 'RUNNING').length

  const tabStyle = (active: boolean): CSSProperties => ({
    fontSize: '11px',
    padding: '4px 12px',
    borderRadius: 'var(--radius-pill)',
    border: `1px solid ${active ? 'var(--accent-button-border)' : 'var(--border-subtle)'}`,
    background: active ? 'var(--accent-muted)' : 'transparent',
    color: active ? 'var(--accent-text)' : 'var(--text-muted)',
    cursor: 'pointer',
    whiteSpace: 'nowrap' as const,
  })

  return (
    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
      <button style={tabStyle(activeCategory === 'Available')} onClick={() => onCategory('Available')}>
        Available ({availableCount})
      </button>
      <button style={tabStyle(activeCategory === 'All')} onClick={() => onCategory('All')}>
        All ({apps.length})
      </button>
      {categories.map((cat) => (
        <button key={cat} style={tabStyle(activeCategory === cat)} onClick={() => onCategory(cat)}>
          {cat}
        </button>
      ))}
    </div>
  )
}
