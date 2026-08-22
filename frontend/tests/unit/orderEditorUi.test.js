import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const componentNames = [
  'OrderEditor.vue',
  'OrderItemsTable.vue',
  'OrderApplicationsTable.vue',
  'DtfRollTable.vue',
  'DtfPiecesTable.vue',
  'OrderTotalsPreview.vue',
]
const sources = componentNames.map((name) =>
  readFileSync(
    resolve(process.cwd(), 'src/components/OrderEditor', name),
    'utf8',
  ),
)

describe('order editor CRM UI', () => {
  it('uses theme-compatible CRM controls instead of native form controls', () => {
    for (const source of sources) {
      expect(source).not.toMatch(/<(?:input|select)\b/)
      expect(source).not.toMatch(/(?:bg-white|text-black|theme="red")/)
    }

    const allSources = sources.join('\n')
    expect(allSources).toContain('<Section')
    expect(allSources).toContain('<Select')
    expect(allSources).toContain('<FormControl')
    expect(allSources).toContain('bg-surface-')
    expect(allSources).toContain('text-ink-')
    expect(allSources).toContain('border-outline-')
  })

  it('uses compact ghost trash buttons for every row removal', () => {
    const rowTables = sources.slice(1, 5).join('\n')
    expect(rowTables.match(/icon="trash-2"/g)).toHaveLength(4)
    expect(
      rowTables.match(/icon="trash-2"[\s\S]{0,100}variant="ghost"/g),
    ).toHaveLength(4)
  })

  it('keeps placement Back as the raw value with a contextual label', () => {
    const applications = sources[2]
    expect(applications).toContain("label: __('Back placement')")
    expect(applications).toContain("value: 'Back'")
    expect(applications).not.toContain("__('Back')")
  })

  it('does not expose server implementation notes', () => {
    expect(sources.join('\n')).not.toMatch(
      /server (?:validates|validation|recalculates)/i,
    )
  })
})
