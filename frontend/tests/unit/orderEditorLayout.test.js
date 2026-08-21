import { describe, expect, it } from 'vitest'
import { withoutLegacyOrderFields } from '@/utils/orderEditorLayout'

describe('order editor field layout', () => {
  it('hides legacy order fields without mutating the source layout', () => {
    const layout = [
      {
        name: 'data',
        sections: [
          {
            name: 'legacy',
            columns: [
              {
                name: 'order',
                fields: [
                  { fieldname: 'products' },
                  { fieldname: 'applications' },
                  { fieldname: 'total' },
                  { fieldname: 'net_total' },
                ],
              },
            ],
          },
          {
            name: 'production',
            columns: [
              {
                name: 'details',
                fields: [
                  { fieldname: 'production_deadline' },
                  { fieldname: 'manager' },
                  { fieldname: 'notes' },
                ],
              },
            ],
          },
        ],
      },
    ]
    const original = structuredClone(layout)

    const result = withoutLegacyOrderFields(layout)

    expect(layout).toEqual(original)
    expect(result).not.toBe(layout)
    expect(result[0].sections.map((section) => section.name)).toEqual([
      'production',
    ])
    expect(
      result[0].sections[0].columns[0].fields.map((field) => field.fieldname),
    ).toEqual(['production_deadline', 'manager', 'notes'])
  })

  it('preserves Payment and Source/Attribution fields', () => {
    const fields = [
      'payment_section',
      'payment_status',
      'payment_method',
      'source',
      'source_details',
      'utm_source',
      'attribution',
    ].map((fieldname) => ({ fieldname }))
    const layout = [
      {
        name: 'data',
        sections: [
          {
            name: 'commercial',
            columns: [{ name: 'details', fields }],
          },
        ],
      },
    ]

    expect(
      withoutLegacyOrderFields(layout)[0].sections[0].columns[0].fields,
    ).toEqual(fields)
  })

  it('supports string fieldnames returned by older layouts', () => {
    const layout = [
      {
        sections: [
          { columns: [{ fields: ['products', 'source', 'Payment'] }] },
        ],
      },
    ]

    expect(
      withoutLegacyOrderFields(layout)[0].sections[0].columns[0].fields,
    ).toEqual(['source', 'Payment'])
  })
})
