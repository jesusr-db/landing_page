import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'

// Mock useApps — use vi.fn() factory so tests can override with mockReturnValueOnce
vi.mock('./hooks/useApps', () => ({
  useApps: vi.fn(() => ({
    apps: [],
    user: { email: 'u@test.com', username: 'u', groups: [], portal_title: 'Test Portal' },
    loading: false,
    error: null,
    isStale: false,
  })),
}))

import App from './App'
import { useApps } from './hooks/useApps'

test('renders portal title from user data', () => {
  render(<App />)
  expect(screen.getByText('Test Portal')).toBeInTheDocument()
})

test('renders user email in header', () => {
  render(<App />)
  expect(screen.getByText('u@test.com')).toBeInTheDocument()
})

test('renders empty state when no apps', () => {
  render(<App />)
  expect(screen.getByText(/No apps are available/)).toBeInTheDocument()
})

test('shows stale banner when isStale is true', () => {
  vi.mocked(useApps).mockReturnValueOnce({
    apps: [{ name: 'a', display_name: 'A', description: '', url: '', status: 'RUNNING', category: 'General', can_manage: false }],
    user: { email: 'u@test.com', username: 'u', groups: [], portal_title: 'Test Portal' },
    loading: false,
    error: null,
    isStale: true,
  })
  render(<App />)
  expect(screen.getByText(/App list may be outdated/)).toBeInTheDocument()
})
