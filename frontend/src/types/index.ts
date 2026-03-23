export type AppStatus =
  | 'RUNNING'
  | 'DEPLOYING'
  | 'CRASHED'
  | 'UNAVAILABLE'
  | 'STOPPED'
  | string  // Fallback for unknown values

export interface AppItem {
  name: string
  display_name: string
  description: string
  url: string
  status: AppStatus
  category: string
  can_manage: boolean
}

export interface UserInfo {
  email: string
  username: string
  groups: string[]
  portal_title: string
}

export interface UseAppsResult {
  apps: AppItem[]
  user: UserInfo | null
  loading: boolean
  error: { message: string; status?: number } | null
  isStale: boolean
}
