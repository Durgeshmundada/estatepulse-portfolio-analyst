// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ResultCard from './ResultCard'

describe('ResultCard', () => {
  it('renders a verified summary card', () => {
    render(<ResultCard card={{ type: 'summary', title: 'Actual portfolio', metrics: [{ label: 'Portfolio value', value: '₹29.70 Cr' }], rent_complete: true }} />)
    expect(screen.getByText('Actual portfolio')).toBeInTheDocument()
    expect(screen.getByText('₹29.70 Cr')).toBeInTheDocument()
  })

  it('labels scenarios as hypothetical', () => {
    render(<ResultCard card={{ type: 'scenario', title: 'What-if', baseline: '₹29.70 Cr', scenario: '₹17.70 Cr', delta: '₹-12.00 Cr', operations: [] }} />)
    expect(screen.getByText('Hypothetical')).toBeInTheDocument()
    expect(screen.getByText(/actual portfolio has not been modified/i)).toBeInTheDocument()
  })
})
