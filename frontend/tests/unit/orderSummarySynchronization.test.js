import { describe, expect, it } from 'vitest'
import { synchronizeOrderSummary } from '../../src/utils/orderEditor'

describe('order summary synchronization', () => {
  it('updates the deal and payment summary when a service price changes', () => {
    const doc = {
      order_type: 'Product Printing',
      order_items: [],
      order_applications: [
        { qty: 2, rate: 100, use_manual_amount: 0, manual_amount: 0 },
      ],
      payments: [{ amount: 50 }],
      payment_status: 'Unpaid',
      payment_terms: 'Prepayment',
    }

    synchronizeOrderSummary(doc, 2)
    expect(doc.order_total).toBe(200)
    expect(doc.deal_value).toBe(200)
    expect(doc.paid_amount).toBe(50)
    expect(doc.balance_amount).toBe(150)
    expect(doc.payment_status).toBe('Partially Paid')

    doc.order_applications[0].rate = 150
    synchronizeOrderSummary(doc, 2)
    expect(doc.order_total).toBe(300)
    expect(doc.balance_amount).toBe(250)
  })

  it('sums partial payments and marks a fully paid order', () => {
    const doc = {
      order_type: 'DTF Pieces',
      dtf_piece_lines: [{ qty: 2, unit_price: 75 }],
      payments: [{ amount: 50 }, { amount: 100 }],
      payment_status: 'Partially Paid',
      payment_terms: 'Prepayment',
    }

    synchronizeOrderSummary(doc, 2)
    expect(doc.order_total).toBe(150)
    expect(doc.paid_amount).toBe(150)
    expect(doc.balance_amount).toBe(0)
    expect(doc.payment_status).toBe('Paid')
  })
})
