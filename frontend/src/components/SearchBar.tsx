interface Props {
  onSearch: (query: string) => void
}

export function SearchBar({ onSearch }: Props) {
  return (
    <input
      type="search"
      aria-label="Search apps"
      placeholder="🔍  Search apps..."
      onChange={(e) => onSearch(e.target.value)}
      style={{
        width: '100%',
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-sm)',
        padding: '8px 12px',
        color: 'var(--text-primary)',
        fontSize: '13px',
        outline: 'none',
      }}
    />
  )
}
