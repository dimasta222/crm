import { describe, expect, it, vi } from 'vitest'
import {
  canRemoveOrderItem,
  calculateApplicationAmount,
  calculateOrderPreview,
  getOrderCurrencyPrecision,
  incompatibleOrderCategories,
  SHEET_FORMATS,
  selectStudioProduct,
} from '@/utils/orderEditor'

describe('order editor preview', () => {
  it('prices embroidery from the editable rate plus artwork preparation', () => {
    const application = {
      production_type: 'Embroidery',
      stitch_count: 12500,
      stitch_rate_per_1000: 70,
      embroidery_setup_fee: 500,
      qty: 32,
      rate: 227.5,
      use_manual_amount: 0,
    }

    expect(calculateApplicationAmount(application, 2)).toBe(7780)
    expect(
      calculateOrderPreview({ order_applications: [application] }, 2),
    ).toMatchObject({ applicationsSubtotal: 7780, orderTotal: 7780 })
  })

  it('calculates 40 services at 227.5 as exactly 9100', () => {
    expect(
      calculateApplicationAmount(
        {
          production_type: 'DTF Printing',
          qty: 40,
          rate: 227.5,
        },
        2,
      ),
    ).toBe(9100)
  })

  it('always prices a Customer Item at zero, ignoring its manual rate', () => {
    expect(
      calculateOrderPreview({
        order_items: [
          {
            supply_type: 'Customer Item',
            qty: 2,
            base_rate: 20,
            manual_rate: 15,
            use_manual_rate: 1,
            discount_percentage: 35,
          },
        ],
      }),
    ).toMatchObject({ itemsSubtotal: 0, discountAmount: 0, subtotal: 0 })
  })

  it('uses Studio Product base rate unless its manual-rate flag is set, including zero', () => {
    expect(
      calculateOrderPreview({
        order_items: [
          {
            supply_type: 'Studio Product',
            qty: 2,
            base_rate: 20,
            manual_rate: 0,
            use_manual_rate: 0,
            discount_percentage: 0,
          },
          {
            supply_type: 'Studio Product',
            qty: 2,
            base_rate: 20,
            manual_rate: 0,
            use_manual_rate: 1,
            discount_percentage: 0,
          },
        ],
      }),
    ).toMatchObject({ itemsSubtotal: 40, subtotal: 40 })
  })

  it('rounds each line and final total with server ROUND_HALF_UP semantics', () => {
    expect(
      calculateOrderPreview({
        order_items: [
          {
            supply_type: 'Studio Product',
            qty: '2.5',
            base_rate: '1.005',
            discount_percentage: 10,
          },
        ],
        dtf_roll_lines: [
          { length_m: 1, rate_per_meter: '1.005' },
          { length_m: 1, rate_per_meter: '1.005' },
        ],
      }),
    ).toMatchObject({
      itemsSubtotal: 2.28,
      discountAmount: 0.25,
      dtfRollSubtotal: 2.02,
      subtotal: 4.3,
      orderTotal: 4.3,
    })
  })

  it.each([
    [
      0,
      {
        itemsSubtotal: 3,
        discountAmount: 0,
        dtfRollSubtotal: 2,
        subtotal: 5,
        orderTotal: 5,
      },
    ],
    [
      2,
      {
        itemsSubtotal: 2.28,
        discountAmount: 0.25,
        dtfRollSubtotal: 2.02,
        subtotal: 4.3,
        orderTotal: 4.3,
      },
    ],
    [
      3,
      {
        itemsSubtotal: 2.262,
        discountAmount: 0.251,
        dtfRollSubtotal: 2.01,
        subtotal: 4.272,
        orderTotal: 4.272,
      },
    ],
  ])(
    'uses precision %i with ROUND_HALF_UP line and total rounding',
    (precision, expected) => {
      expect(
        calculateOrderPreview(
          {
            order_items: [
              {
                supply_type: 'Studio Product',
                qty: '2.5',
                base_rate: '1.005',
                discount_percentage: 10,
              },
            ],
            dtf_roll_lines: [
              { length_m: 1, rate_per_meter: '1.005' },
              { length_m: 1, rate_per_meter: '1.005' },
            ],
          },
          precision,
        ),
      ).toMatchObject(expected)
    },
  )

  it('resolves preview precision through field meta, system defaults, then 2', () => {
    expect(
      getOrderCurrencyPrecision({ precision: '0' }, { currency_precision: 3 }),
    ).toBe(0)
    expect(
      getOrderCurrencyPrecision({ precision: '3' }, { currency_precision: 2 }),
    ).toBe(3)
    expect(getOrderCurrencyPrecision({}, { currency_precision: '2' })).toBe(2)
    expect(
      getOrderCurrencyPrecision(
        { precision: '10' },
        { currency_precision: '12' },
      ),
    ).toBe(2)
  })

  it('selects a Studio Product and stores its loaded standard rate', async () => {
    const row = { product: '', base_rate: 1 }
    const getProduct = vi.fn().mockResolvedValue({
      name: 'PRODUCT-001',
      product_name: 'Футболка оверсайз',
      standard_rate: 19.95,
    })

    await expect(
      selectStudioProduct(row, 'PRODUCT-001', getProduct),
    ).resolves.toEqual({ error: null })
    expect(getProduct).toHaveBeenCalledWith('PRODUCT-001')
    expect(row).toMatchObject({
      product: 'PRODUCT-001',
      item_name: 'Футболка оверсайз',
      base_rate: 19.95,
      manual_rate: 19.95,
      use_manual_rate: 1,
    })
  })

  it('ignores a late Studio Product response after another product is selected', async () => {
    const row = { product: '', base_rate: 1 }
    const requests = {}
    const getProduct = vi.fn(
      (product) =>
        new Promise((resolve) => {
          requests[product] = resolve
        }),
    )

    const selectA = selectStudioProduct(row, 'PRODUCT-A', getProduct)
    const selectB = selectStudioProduct(row, 'PRODUCT-B', getProduct)

    requests['PRODUCT-B']({ standard_rate: 20 })
    await selectB
    expect(row).toMatchObject({ product: 'PRODUCT-B', base_rate: 20 })

    requests['PRODUCT-A']({ standard_rate: 10 })
    await selectA
    expect(row).toMatchObject({ product: 'PRODUCT-B', base_rate: 20 })
  })

  it('reports a Studio Product rate load error without replacing the rate with zero', async () => {
    const row = { product: '', base_rate: 12 }

    await expect(
      selectStudioProduct(
        row,
        'PRODUCT-001',
        vi.fn().mockRejectedValue(new Error('offline')),
      ),
    ).resolves.toEqual({ error: 'load-failed' })
    expect(row).toMatchObject({ product: 'PRODUCT-001', base_rate: null })

    await expect(
      selectStudioProduct(row, 'PRODUCT-002', vi.fn().mockResolvedValue({})),
    ).resolves.toEqual({ error: 'missing-standard-rate' })
    expect(row).toMatchObject({ product: 'PRODUCT-002', base_rate: null })
  })

  it('honours zero manual amount overrides and ignores disabled overrides', () => {
    expect(
      calculateOrderPreview({
        order_applications: [
          { qty: 2, rate: 5, use_manual_amount: 1, manual_amount: 0 },
          { qty: 2, rate: 5, use_manual_amount: 0, manual_amount: 0 },
        ],
        use_manual_total: 1,
        manual_order_total: 0,
      }),
    ).toMatchObject({ applicationsSubtotal: 10, subtotal: 10, orderTotal: 0 })
  })

  it('ignores hidden DTF Piece sizing values when pricing Quantity Only rows', () => {
    expect(
      calculateOrderPreview({
        dtf_piece_lines: [
          {
            sizing_mode: 'Quantity Only',
            sheet_format: 'A3++',
            width_cm: 999,
            height_cm: 999,
            qty: 3,
            unit_price: '1.005',
          },
        ],
      }),
    ).toMatchObject({ dtfPieceSubtotal: 3.03, subtotal: 3.03 })
  })

  it('keeps incompatible rows when order type changes and reports them', () => {
    const doc = {
      order_type: 'DTF Roll',
      order_items: [{ item_key: 'ITEM-1' }],
      dtf_piece_lines: [{}],
    }
    expect(incompatibleOrderCategories(doc)).toEqual([
      'Product Printing',
      'DTF Pieces',
    ])
    expect(doc.order_items).toEqual([{ item_key: 'ITEM-1' }])
  })

  it('blocks removing an item while an application references its item key', () => {
    const doc = {
      order_items: [{ item_key: 'ITEM-1' }, { item_key: 'ITEM-2' }],
      order_applications: [{ item_key: 'ITEM-1' }],
    }
    expect(canRemoveOrderItem(doc, 'ITEM-1')).toBe(false)
    expect(canRemoveOrderItem(doc, 'ITEM-2')).toBe(true)
  })

  it('does not mutate document values used by the dirty-state save flow', () => {
    const doc = {
      order_items: [
        {
          supply_type: 'Studio Product',
          qty: 1,
          base_rate: '1.005',
          discount_percentage: 0,
        },
      ],
    }
    const beforePreview = structuredClone(doc)
    calculateOrderPreview(doc)
    expect(doc).toEqual(beforePreview)
  })

  it('uses the backend sheet-format contract', () => {
    expect(SHEET_FORMATS).toEqual(['A6', 'A5', 'A4', 'A3', 'A3+', 'A3++'])
  })
})
