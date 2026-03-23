import { render, screen } from '@testing-library/react'
import { AppGrid } from './AppGrid'
import type { AppItem } from '../types'

const makeApp = (name: string, category = 'General'): AppItem => ({
  name,
  display_name: name,
  description: '',
  url: `https://example.com/apps/${name}`,
  status: 'RUNNING',
  category,
  can_manage: false,
})

test('shows empty state when no apps', () => {
  render(<AppGrid apps={[]} search="" activeCategory="All" />)
  expect(screen.getByText(/No apps are available/)).toBeInTheDocument()
})

test('renders an AppCard for each visible app', () => {
  const apps = [makeApp('App One'), makeApp('App Two')]
  render(<AppGrid apps={apps} search="" activeCategory="All" />)
  expect(screen.getByText('App One')).toBeInTheDocument()
  expect(screen.getByText('App Two')).toBeInTheDocument()
})

test('filters apps by search query (name)', () => {
  const apps = [makeApp('Digital Twins'), makeApp('Sales Analytics')]
  render(<AppGrid apps={apps} search="twin" activeCategory="All" />)
  expect(screen.getByText('Digital Twins')).toBeInTheDocument()
  expect(screen.queryByText('Sales Analytics')).not.toBeInTheDocument()
})

test('filters apps by search query (description)', () => {
  const apps: AppItem[] = [
    { ...makeApp('App A'), description: 'real-time tracking' },
    { ...makeApp('App B'), description: 'revenue dashboard' },
  ]
  render(<AppGrid apps={apps} search="tracking" activeCategory="All" />)
  expect(screen.getByText('App A')).toBeInTheDocument()
  expect(screen.queryByText('App B')).not.toBeInTheDocument()
})

test('filters apps by active category', () => {
  const apps = [makeApp('Ops App', 'Operations'), makeApp('Analytics App', 'Analytics')]
  render(<AppGrid apps={apps} search="" activeCategory="Operations" />)
  expect(screen.getByText('Ops App')).toBeInTheDocument()
  expect(screen.queryByText('Analytics App')).not.toBeInTheDocument()
})

test('shows empty state when search has no matches', () => {
  render(<AppGrid apps={[makeApp('My App')]} search="zzznomatch" activeCategory="All" />)
  expect(screen.getByText(/No apps are available/)).toBeInTheDocument()
})
