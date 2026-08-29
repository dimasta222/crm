import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const dirname = path.dirname(fileURLToPath(import.meta.url))
const src = (...parts) =>
  fs.readFileSync(path.resolve(dirname, '../../src', ...parts), 'utf8')

describe('product editor and contact column regressions', () => {
  it('opens an existing studio product inside CRM instead of Frappe Desk', () => {
    const component = src('components', 'OrderEditor', 'OrderItemsTable.vue')

    expect(component).toContain("useDoctypeModal")
    expect(component).toContain("doctype: 'CRM Product'")
    expect(component).toContain('name: row.product')
    expect(component).not.toContain('/app/crm-product/')
  })

  it('adds the selected fieldname to the list rows', () => {
    const component = src('components', 'ColumnSettings.vue')

    expect(component).toContain('rows.value.push(c.fieldname)')
    expect(component).not.toContain('rows.value.push(c.value)')
  })
})
