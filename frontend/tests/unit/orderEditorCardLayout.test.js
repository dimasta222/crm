import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const source = (name) =>
  readFileSync(
    resolve(process.cwd(), 'src/components/OrderEditor', name),
    'utf8',
  )

describe('order editor card layout', () => {
  it('renders each service as a labelled card instead of a shared table', () => {
    const applications = source('OrderApplicationsTable.vue')

    expect(applications).toContain('data-testid="order-service-card"')
    expect(applications).toContain(":label=\"__('Qty')\"")
    expect(applications).toContain(":label=\"__('Rate')\"")
    expect(applications).toContain(":label=\"__('Width (cm)')\"")
    expect(applications).toContain(":label=\"__('Height (cm)')\"")
    expect(applications).not.toContain("__('Optional')")
    expect(applications).not.toContain('<table')
  })

  it('keeps services and a live total inside their product card', () => {
    const items = source('OrderItemsTable.vue')

    expect(items).toContain('data-testid="order-item-group"')
    expect(items).toContain(
      '<OrderApplicationsTable :doc="doc" :item-key="row.item_key" />',
    )
    expect(items).toContain('groupAmount(row)')
    expect(items).not.toContain('<table')
  })
})
