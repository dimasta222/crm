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

  it('uses stable semantic colors for every print service', () => {
    const applications = source('OrderApplicationsTable.vue')

    expect(applications).toContain("'DTF Printing': { tone: 'violet'")
    expect(applications).toContain("tone: 'amber'")
    expect(applications).toContain("Embroidery: { tone: 'cyan'")
    expect(applications).toContain("tone: 'green'")
    expect(applications).toContain("Sublimation: { tone: 'pink'")
    expect(applications).toContain("tone: 'orange'")
    expect(applications).toContain("Combined: { tone: 'purple'")
    expect(applications).toContain(':style="serviceCardStyle(row)"')
  })

  it('keeps services and a live total inside their product card', () => {
    const items = source('OrderItemsTable.vue')

    expect(items).toContain('data-testid="order-item-group"')
    expect(items).toContain(
      '<OrderApplicationsTable :doc="doc" :item-key="row.item_key" />',
    )
    expect(items).toContain('groupAmount(row)')
    expect(items).toContain('@click="addService(row)"')
    expect(items).toContain('supplyBadgeClass(row)')
    expect(items).not.toContain('<table')
  })

  it('shows one editable product field for each supply type', () => {
    const items = source('OrderItemsTable.vue')

    expect(items).toContain("v-if=\"row.supply_type !== 'Studio Product'\"")
    expect(items).toContain('<div v-else class="min-w-0 lg:col-span-2">')
    expect(items.match(/:selected-label="row.item_name"/g)).toHaveLength(1)
  })

  it('moves the discount into the styled preliminary calculation card', () => {
    const items = source('OrderItemsTable.vue')
    const totals = source('OrderTotalsPreview.vue')

    expect(items).not.toContain('v-model="row.discount_percentage"')
    expect(totals).toContain('data-testid="order-totals-card"')
    expect(totals).toContain('v-model="doc.order_discount_percentage"')
    expect(totals).toContain("__('Order discount, %')")
    expect(totals).toContain('order-totals-final')
  })
})
