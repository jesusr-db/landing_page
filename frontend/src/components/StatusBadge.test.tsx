import { render, screen } from '@testing-library/react'
import { StatusBadge } from './StatusBadge'

test('RUNNING shows green Available', () => {
  render(<StatusBadge status="RUNNING" />)
  const badge = screen.getByText(/Available/)
  expect(badge).toBeInTheDocument()
  expect(badge.closest('[data-status]')).toHaveAttribute('data-status', 'running')
})

test('DEPLOYING shows amber Deploying', () => {
  render(<StatusBadge status="DEPLOYING" />)
  expect(screen.getByText(/Deploying/)).toBeInTheDocument()
})

test('CRASHED shows red Crashed', () => {
  render(<StatusBadge status="CRASHED" />)
  expect(screen.getByText(/Crashed/)).toBeInTheDocument()
})

test('UNAVAILABLE shows red Unavailable', () => {
  render(<StatusBadge status="UNAVAILABLE" />)
  expect(screen.getByText(/Unavailable/)).toBeInTheDocument()
})

test('STOPPED shows red Stopped', () => {
  render(<StatusBadge status="STOPPED" />)
  expect(screen.getByText(/Stopped/)).toBeInTheDocument()
})

test('unknown status shows gray Unknown', () => {
  render(<StatusBadge status="MYSTERY_STATUS" />)
  const badge = screen.getByText(/Unknown/)
  expect(badge).toBeInTheDocument()
  expect(badge.closest('[data-status]')).toHaveAttribute('data-status', 'unknown')
})
