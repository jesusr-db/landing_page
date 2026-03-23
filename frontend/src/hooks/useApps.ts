import useSWR from 'swr'
import type { AppItem, UserInfo, UseAppsResult } from '../types'

async function fetchJson<T>(url: string): Promise<T> {
  const resp = await fetch(url)
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}))
    throw Object.assign(new Error((body as { detail?: string }).detail ?? 'Request failed'), { status: resp.status })
  }
  return resp.json()
}

export function useApps(): UseAppsResult {
  const {
    data: user,
    error: userError,
    isLoading: userLoading,
  } = useSWR<UserInfo>('/api/me', fetchJson, { refreshInterval: 300_000 })

  const {
    data: apps,
    error: appsError,
    isLoading: appsLoading,
  } = useSWR<AppItem[]>('/api/apps', fetchJson, { refreshInterval: 300_000 })

  const loading = userLoading || appsLoading
  const anyError = userError ?? appsError
  const error = anyError
    ? { message: anyError.message ?? 'Failed to load', status: (anyError as { status?: number }).status }
    : null

  const isStale = !loading && !!anyError && (!!user || !!(apps?.length))

  return {
    apps: apps ?? [],
    user: user ?? null,
    loading,
    error,
    isStale,
  }
}
