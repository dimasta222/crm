import { describe, expect, it } from 'vitest'
import {
  applyDtfRollEquivalentRate,
  getDtfRollAmounts,
} from '@/utils/orderEditorPresentation'

describe('DTF roll presentation', () => {
  it('shows the calculated amount as final without a manual override', () => {
    expect(
      getDtfRollAmounts({
        length_m: 3,
        rate_per_meter: 500,
        manual_amount: 1400,
        use_manual_amount: 0,
      }),
    ).toEqual({
      calculatedAmount: 1500,
      finalAmount: 1500,
      equivalentRate: 500,
    })
  })

  it('keeps calculated and manual final amounts separate', () => {
    expect(
      getDtfRollAmounts({
        length_m: 3,
        rate_per_meter: 500,
        manual_amount: 1400,
        use_manual_amount: 1,
      }),
    ).toEqual({
      calculatedAmount: 1500,
      finalAmount: 1400,
      equivalentRate: 1400 / 3,
    })
  })

  it('treats a manual zero as a real final amount', () => {
    expect(
      getDtfRollAmounts({
        length_m: 2,
        rate_per_meter: 500,
        manual_amount: 0,
        use_manual_amount: 1,
      }),
    ).toEqual({
      calculatedAmount: 1000,
      finalAmount: 0,
      equivalentRate: 0,
    })
  })

  it('changes the meter rate only when explicitly applied', () => {
    const row = {
      length_m: 3,
      rate_per_meter: 500,
      manual_amount: 1400,
      use_manual_amount: 1,
    }

    getDtfRollAmounts(row)
    expect(row.rate_per_meter).toBe(500)

    expect(applyDtfRollEquivalentRate(row)).toBe(true)
    expect(row).toEqual({
      length_m: 3,
      rate_per_meter: 1400 / 3,
      manual_amount: null,
      use_manual_amount: 0,
    })
  })

  it('does not apply an equivalent rate without a positive length', () => {
    const row = {
      length_m: 0,
      rate_per_meter: 500,
      manual_amount: 0,
      use_manual_amount: 1,
    }

    expect(getDtfRollAmounts(row).equivalentRate).toBeNull()
    expect(applyDtfRollEquivalentRate(row)).toBe(false)
    expect(row).toMatchObject({
      rate_per_meter: 500,
      manual_amount: 0,
      use_manual_amount: 1,
    })
  })
})
