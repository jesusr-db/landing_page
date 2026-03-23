import './styles/theme.css'
import { useState } from 'react'
import { useApps } from './hooks/useApps'
import { SearchBar } from './components/SearchBar'
import { CategoryTabs } from './components/CategoryTabs'
import { AppGrid } from './components/AppGrid'

export default function App() {
  const { apps, user, loading, error, isStale } = useApps()
  const [search, setSearch] = useState('')
  const [activeCategory, setActiveCategory] = useState('Available')

  const initials = user?.email?.slice(0, 2).toUpperCase() ?? '??'

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-base)' }}>
      {/* Header */}
      <header
        style={{
          background: 'var(--bg-surface)',
          borderBottom: '1px solid var(--border)',
          padding: '12px 24px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: '28px',
              height: '28px',
              background: 'linear-gradient(135deg, var(--accent), var(--accent-muted))',
              borderRadius: 'var(--radius-sm)',
            }}
          />
          <span style={{ color: 'var(--text-primary)', fontWeight: 700, fontSize: '15px' }}>
            {user?.portal_title ?? 'App Portal'}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              width: '26px',
              height: '26px',
              borderRadius: '50%',
              background: 'var(--accent-muted)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--accent-text)',
              fontSize: '11px',
              fontWeight: 600,
            }}
          >
            {initials}
          </div>
          <span style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>{user?.email}</span>
        </div>
      </header>

      {/* Stale warning banner */}
      {isStale && (
        <div
          style={{
            background: 'var(--status-deploying-bg)',
            borderBottom: `1px solid var(--status-deploying)`,
            padding: '8px 24px',
            color: 'var(--status-deploying)',
            fontSize: '12px',
          }}
        >
          App list may be outdated — refresh to update.
        </div>
      )}

      {/* Main content */}
      <main style={{ padding: '16px 24px', maxWidth: '1200px', margin: '0 auto' }}>
        {loading && (
          <div style={{ color: 'var(--text-muted)', padding: '48px 0', textAlign: 'center' }}>
            Loading apps…
          </div>
        )}

        {error && !isStale && (
          <div
            style={{
              background: 'var(--status-error-bg)',
              border: `1px solid var(--status-error)`,
              borderRadius: 'var(--radius-md)',
              padding: '16px',
              color: 'var(--status-error)',
              margin: '24px 0',
            }}
          >
            Unable to load apps — {error.message}. Please refresh the page.
          </div>
        )}

        {!loading && (
          <>
            <div style={{ marginBottom: '12px' }}>
              <SearchBar onSearch={setSearch} />
            </div>
            <div style={{ marginBottom: '16px' }}>
              <CategoryTabs apps={apps} activeCategory={activeCategory} onCategory={setActiveCategory} />
            </div>
            <AppGrid apps={apps} search={search} activeCategory={activeCategory} />
            {apps.length > 0 && (
              <div style={{ marginTop: '8px', color: 'var(--text-muted)', fontSize: '10px' }}>
                {apps.length} app{apps.length !== 1 ? 's' : ''} available
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}
