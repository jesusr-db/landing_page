import type { AppStatus } from '../types'

interface Props {
  status: AppStatus
}

const STATUS_MAP: Record<string, { label: string; key: string }> = {
  RUNNING: { label: 'Available', key: 'running' },
  DEPLOYING: { label: 'Deploying', key: 'deploying' },
  CRASHED: { label: 'Crashed', key: 'error' },
  UNAVAILABLE: { label: 'Unavailable', key: 'error' },
  STOPPED: { label: 'Stopped', key: 'error' },
}

const ICONS: Record<string, string> = {
  running: '● ',
  deploying: '⟳ ',
  error: '✕ ',
  unknown: '? ',
}

export function StatusBadge({ status }: Props) {
  const { label, key } = STATUS_MAP[status] ?? { label: 'Unknown', key: 'unknown' }
  return (
    <span
      data-status={key}
      style={{
        fontSize: '10px',
        padding: '2px 8px',
        borderRadius: 'var(--radius-pill)',
        background: `var(--status-${key}-bg, var(--status-unknown-bg))`,
        color: `var(--status-${key}, var(--status-unknown))`,
        whiteSpace: 'nowrap',
      }}
    >
      {ICONS[key] ?? '? '}{label}
    </span>
  )
}
