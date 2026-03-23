import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SearchBar } from './SearchBar'

test('calls onSearch with typed value', async () => {
  const onSearch = vi.fn()
  render(<SearchBar onSearch={onSearch} />)
  await userEvent.type(screen.getByRole('searchbox'), 'twin')
  expect(onSearch).toHaveBeenCalledWith('twin')
})

test('renders search input with placeholder', () => {
  render(<SearchBar onSearch={vi.fn()} />)
  expect(screen.getByPlaceholderText(/Search apps/i)).toBeInTheDocument()
})
