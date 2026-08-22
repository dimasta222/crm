import { calculateOrderPreview } from '@/utils/orderEditor'

export function getDtfRollAmounts(row, precision = 2) {
  const calculatedAmount = calculateOrderPreview(
    {
      dtf_roll_lines: [{ ...row, use_manual_amount: 0 }],
    },
    precision,
  ).dtfRollSubtotal
  const finalAmount = calculateOrderPreview(
    { dtf_roll_lines: [row] },
    precision,
  ).dtfRollSubtotal
  const length = Number(row.length_m)
  const equivalentRate =
    Number.isFinite(length) && length > 0 ? finalAmount / length : null

  return { calculatedAmount, finalAmount, equivalentRate }
}

export function applyDtfRollEquivalentRate(row, precision = 2) {
  const { equivalentRate } = getDtfRollAmounts(row, precision)
  if (equivalentRate == null) return false

  row.rate_per_meter = equivalentRate
  row.use_manual_amount = 0
  row.manual_amount = null
  return true
}
