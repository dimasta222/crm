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

  it('loads global views before the current user view', () => {
    const api = fs.readFileSync(
      path.resolve(dirname, '../../../crm/api/views.py'),
      'utf8',
    )

    expect(api).toContain('bool(view.get("user"))')
    const controls = src('components', 'ViewControls.vue')
    expect(controls).toContain(
      'load_default_columns: Boolean(_view?.load_default_columns)',
    )
    expect(controls).not.toContain('load_default_columns: _view?.row || true')

    const dataApi = fs.readFileSync(
      path.resolve(dirname, '../../../crm/api/doc.py'),
      'utf8',
    )
    expect(dataApi).toContain('order_by="modified desc"')

    const viewSettings = fs.readFileSync(
      path.resolve(
        dirname,
        '../../../crm/fcrm/doctype/crm_view_settings/crm_view_settings.py',
      ),
      'utf8',
    )
    expect(viewSettings).toContain('order_by="modified desc"')
  })

  it('uses the CRM Product title instead of its internal codes', () => {
    const items = src('components', 'OrderEditor', 'OrderItemsTable.vue')
    const applications = src(
      'components',
      'OrderEditor',
      'OrderApplicationsTable.vue',
    )

    expect(items).toContain(':selected-label="row.item_name"')
    expect(items).toContain('selectedProduct?.product_name')
    expect(applications).toContain(
      'label: item.item_name || item.product || item.item_key',
    )
  })
})
