import { StatusBadge } from './StatusBadge'
import type { AppItem } from '../types'

interface Props {
  app: AppItem
}

function avatarColor(name: string): string {
  const colors = ['#1b3a4b', '#2d1b4b', '#3b2a1b', '#1b3a2d', '#2d1b3a', '#1b2d4b']
  const hash = name.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0)
  return colors[hash % colors.length]
}

function initials(displayName: string): string {
  return displayName
    .split(' ')
    .map((w) => w[0])
    .filter(Boolean)
    .join('')
    .slice(0, 2)
    .toUpperCase() || '?'
}

export function AppCard({ app }: Props) {
  const bg = avatarColor(app.name)

  return (
    <div
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        padding: '14px',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div
          style={{
            width: '36px',
            height: '36px',
            borderRadius: 'var(--radius-md)',
            background: bg,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--accent)',
            fontWeight: 700,
            fontSize: '13px',
            flexShrink: 0,
          }}
        >
          {initials(app.display_name)}
        </div>
        <StatusBadge status={app.status} />
      </div>

      <div style={{ color: 'var(--text-primary)', fontWeight: 600, fontSize: '13px' }}>
        {app.display_name}
      </div>

      <div
        style={{
          color: 'var(--text-muted)',
          fontSize: '11px',
          lineHeight: 1.4,
          flexGrow: 1,
        }}
      >
        {app.description || '\u00A0'}
      </div>

      <button
        onClick={() => window.open(app.url, '_blank')}
        style={{
          background: 'var(--accent-button)',
          border: '1px solid var(--accent-button-border)',
          borderRadius: 'var(--radius-sm)',
          padding: '5px 10px',
          color: 'var(--accent-text)',
          fontSize: '11px',
          cursor: 'pointer',
          textAlign: 'center',
          width: '100%',
        }}
      >
        Open App →
      </button>
    </div>
  )
}
