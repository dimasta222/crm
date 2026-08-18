import { describe, expect, it } from 'vitest'
import {
  getRememberedViewType,
  rememberViewType,
} from '@/utils/viewPreferences'

function createStorage() {
  const values = new Map()
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  }
}

describe('view preferences', () => {
  it('stores lead and deal views independently', () => {
    const storage = createStorage()

    rememberViewType('Leads', 'kanban', storage)
    rememberViewType('Deals', 'list', storage)

    expect(getRememberedViewType('Leads', storage)).toBe('kanban')
    expect(getRememberedViewType('Deals', storage)).toBe('list')
  })

  it('ignores unsupported routes and view types', () => {
    const storage = createStorage()

    rememberViewType('Contacts', 'kanban', storage)
    rememberViewType('Leads', 'group_by', storage)

    expect(getRememberedViewType('Contacts', storage)).toBeNull()
    expect(getRememberedViewType('Leads', storage)).toBeNull()
  })
})
