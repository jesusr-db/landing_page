import { render, screen, fireEvent } from '@testing-library/react'
import { AppCard } from './AppCard'
import type { AppItem } from '../types'

const mockApp: AppItem = {
  name: 'digital-twins',
  display_name: 'Digital Twins',
  description: '[Operations] Real-time tracking',
  url: 'https://workspace.example.com/apps/digital-twins',
  status: 'RUNNING',
  category: 'Operations',
  can_manage: false,
}

test('renders app name and description', () => {
  render(<AppCard app={mockApp} />)
  expect(screen.getByText('Digital Twins')).toBeInTheDocument()
  expect(screen.getByText('[Operations] Real-time tracking')).toBeInTheDocument()
})

test('renders initials avatar from display_name', () => {
  render(<AppCard app={mockApp} />)
  expect(screen.getByText('DT')).toBeInTheDocument()
})

test('renders status badge', () => {
  render(<AppCard app={mockApp} />)
  expect(screen.getByText(/Available/)).toBeInTheDocument()
})

test('Open App button opens URL in new tab', () => {
  const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)
  render(<AppCard app={mockApp} />)
  fireEvent.click(screen.getByText('Open App →'))
  expect(openSpy).toHaveBeenCalledWith(mockApp.url, '_blank')
  openSpy.mockRestore()
})

test('non-RUNNING app shows deploying status', () => {
  render(<AppCard app={{ ...mockApp, status: 'DEPLOYING', can_manage: true }} />)
  expect(screen.getByText(/Deploying/)).toBeInTheDocument()
})
