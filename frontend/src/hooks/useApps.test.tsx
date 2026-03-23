import { renderHook, waitFor } from '@testing-library/react'
import { SWRConfig } from 'swr'
import type { ReactNode } from 'react'
import { useApps } from './useApps'
import type { AppItem, UserInfo } from '../types'

const mockUser: UserInfo = {
  email: 'user@test.com', username: 'user', groups: [], portal_title: 'Test Portal',
}
const mockApp: AppItem = {
  name: 'app1', display_name: 'App One', description: '', url: 'https://example.com',
  status: 'RUNNING', category: 'General', can_manage: false,
}

// Wrap each renderHook in a fresh SWR cache to prevent test interference
function wrapper({ children }: { children: ReactNode }) {
  return <SWRConfig value={{ provider: () => new Map() }}>{children}</SWRConfig>
}

beforeEach(() => {
  vi.spyOn(global, 'fetch')
})
afterEach(() => {
  vi.restoreAllMocks()
})

test('returns loading true initially', () => {
  vi.mocked(fetch).mockResolvedValue({
    ok: true, json: async () => mockUser,
  } as Response)
  const { result } = renderHook(() => useApps(), { wrapper })
  expect(result.current.loading).toBe(true)
})

test('returns apps and user after successful fetch', async () => {
  // Use URL-aware mock so order doesn't matter
  vi.mocked(fetch).mockImplementation(async (input) => {
    const url = String(input)
    if (url.includes('/api/me')) {
      return { ok: true, json: async () => mockUser } as Response
    }
    return { ok: true, json: async () => [mockApp] } as Response
  })

  const { result } = renderHook(() => useApps(), { wrapper })
  await waitFor(() => expect(result.current.loading).toBe(false))

  expect(result.current.user?.email).toBe('user@test.com')
  expect(result.current.apps).toHaveLength(1)
  expect(result.current.error).toBeNull()
  expect(result.current.isStale).toBe(false)
})

test('returns error on fetch failure', async () => {
  vi.mocked(fetch).mockResolvedValue({
    ok: false, status: 500, json: async () => ({ detail: 'Server error' }),
  } as Response)

  const { result } = renderHook(() => useApps(), { wrapper })
  await waitFor(() => expect(result.current.loading).toBe(false))

  expect(result.current.error).not.toBeNull()
  expect(result.current.apps).toEqual([])
})
