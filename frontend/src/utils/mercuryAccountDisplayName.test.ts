import { describe, expect, it } from 'vitest'

import { mercuryAccountDisplayName } from './mercuryAccountDisplayName'

describe('mercuryAccountDisplayName', () => {
  it('adds the last four digits when the name does not have them', () => {
    expect(mercuryAccountDisplayName({ name: 'Construction 1640 Chateau', account_number_last_four: '1234' })).toBe('Construction 1640 Chateau ••1234')
  })

  it('does not repeat digits the name already ends with, whatever comes before them', () => {
    expect(mercuryAccountDisplayName({ name: 'Mercury Checking ••8027', account_number_last_four: '8027' })).toBe('Mercury Checking ••8027')
    expect(mercuryAccountDisplayName({ name: 'Mercury Checking •8027', account_number_last_four: '8027' })).toBe('Mercury Checking •8027')
    expect(mercuryAccountDisplayName({ name: 'Mercury Checking 8027', account_number_last_four: '8027' })).toBe('Mercury Checking 8027')
    expect(mercuryAccountDisplayName({ name: 'Checking xx8027', account_number_last_four: '8027' })).toBe('Checking xx8027')
  })

  it('still adds them when the name ends with other digits, or a longer number that only ends the same way', () => {
    expect(mercuryAccountDisplayName({ name: 'Mercury Checking ••1111', account_number_last_four: '8027' })).toBe('Mercury Checking ••1111 ••8027')
    expect(mercuryAccountDisplayName({ name: 'Rehab 18027', account_number_last_four: '8027' })).toBe('Rehab 18027 ••8027')
  })

  it('shows only the name when there are no digits, and nothing for no account', () => {
    expect(mercuryAccountDisplayName({ name: 'Checking', account_number_last_four: '' })).toBe('Checking')
    expect(mercuryAccountDisplayName(null)).toBe('')
  })
})
