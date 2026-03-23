import { render, screen, fireEvent } from '@testing-library/react'
import { CategoryTabs } from './CategoryTabs'
import type { AppItem } from '../types'

const makeApp = (category: string): AppItem => ({
  name: 'app', display_name: 'App', description: '', url: '', status: 'RUNNING',
  category, can_manage: false,
})

test('renders All tab with count', () => {
  const apps = [makeApp('Analytics'), makeApp('Operations')]
  render(<CategoryTabs apps={apps} activeCategory="All" onCategory={vi.fn()} />)
  expect(screen.getByText('All (2)')).toBeInTheDocument()
})

test('renders unique category tabs', () => {
  const apps = [makeApp('Analytics'), makeApp('Analytics'), makeApp('Operations')]
  render(<CategoryTabs apps={apps} activeCategory="All" onCategory={vi.fn()} />)
  expect(screen.getAllByText('Analytics')).toHaveLength(1)
  expect(screen.getByText('Operations')).toBeInTheDocument()
})

test('calls onCategory when tab clicked', () => {
  const onCategory = vi.fn()
  const apps = [makeApp('Analytics')]
  render(<CategoryTabs apps={apps} activeCategory="All" onCategory={onCategory} />)
  fireEvent.click(screen.getByText('Analytics'))
  expect(onCategory).toHaveBeenCalledWith('Analytics')
})
